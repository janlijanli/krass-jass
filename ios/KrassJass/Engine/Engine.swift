import Foundation

/// One move that changes a game, in the form it is saved and replayed in.
///
/// `value` is whatever the engine call takes: a contract (-1 = shove), a card index, a call
/// code, a choice index, 0/1 for yes/no.
struct Move: Codable, Equatable {
    enum Kind: String, Codable {
        case bid, weis, play, nextRound, call, double, choose, block
    }
    let kind: Kind
    let seat: Int
    let value: Int

    static func nextRound() -> Move { Move(kind: .nextRound, seat: 0, value: 0) }
}

/// The thread every engine call runs on.
///
/// The Rust side keeps its games in a thread-local registry (it was written for wasm, which
/// has one thread), so a dispatch queue will not do — a queue may hop threads between blocks.
/// A thread of its own also keeps the search off the main thread and gives it a deep stack.
private final class EngineThread: Thread {
    private let condition = NSCondition()
    private var jobs: [() -> Void] = []

    override func main() {
        while true {
            condition.lock()
            while jobs.isEmpty { condition.wait() }
            let job = jobs.removeFirst()
            condition.unlock()
            autoreleasepool { job() }
        }
    }

    func submit(_ job: @escaping () -> Void) {
        condition.lock()
        jobs.append(job)
        condition.signal()
        condition.unlock()
    }
}

/// The Rust engine: rules, phase machine, bots and search — the same crate the server and the
/// browser build run, linked as a static library (`ios/scripts/build-rust.sh`).
///
/// Every method hops to the engine thread and back. Nothing here caches state: the engine is
/// the authority, and the app re-reads the view after every change.
final class Engine {
    static let shared = Engine()

    /// 153,600 iterations, as the browser build and the server play (docs/measurements.md §3b).
    static let determinizations: UInt32 = 40
    static let iterations: UInt32 = 3840
    static let humanSeat = 0

    private let thread: EngineThread

    private init() {
        thread = EngineThread()
        thread.name = "krass-jass.engine"
        thread.stackSize = 16 << 20
        thread.qualityOfService = .userInitiated
        thread.start()
    }

    private func run<T>(_ body: @escaping () -> T) async -> T {
        await withCheckedContinuation { (continuation: CheckedContinuation<T, Never>) in
            thread.submit { continuation.resume(returning: body()) }
        }
    }

    // MARK: Games

    func newGame(seed: UInt64, settings: GameSettings) async -> UInt32 {
        await run { Engine.rawNewGame(seed: seed, settings: settings) }
    }

    /// Deal `seed` again and replay `moves`. nil if one of them no longer applies — an update
    /// changed a rule — in which case nothing is kept: a wrong game is worse than a new one.
    func restore(seed: UInt64, settings: GameSettings, moves: [Move]) async -> UInt32? {
        await run { () -> UInt32? in
            let handle = Engine.rawNewGame(seed: seed, settings: settings)
            for move in moves where !Engine.rawApply(handle, move) {
                game_free(handle)
                return nil
            }
            return handle
        }
    }

    func free(_ handle: UInt32) {
        thread.submit { game_free(handle) }
    }

    func view(_ handle: UInt32, acked: Int) async -> TableState? {
        await run { Engine.rawView(handle, acked: acked) }
    }

    /// Apply a move and read the view back, in one hop. `ok` is false when the engine rejected
    /// it (a stale tap); the view is current either way.
    func apply(_ handle: UInt32, _ move: Move, acked: Int) async -> (ok: Bool, state: TableState?) {
        await run { () -> (ok: Bool, state: TableState?) in
            let ok = Engine.rawApply(handle, move)
            return (ok, Engine.rawView(handle, acked: acked))
        }
    }

    // MARK: Bots

    /// What the bot on `state.toAct` does now — decided, not yet applied, so the caller can
    /// pace it. `round` seeds the decision the way the browser build does.
    func botDecision(_ handle: UInt32, state: TableState) async -> Move? {
        guard let seat = state.toAct else { return nil }
        let s = UInt32(seat)
        let round = UInt32(max(0, state.round))
        return await run { () -> Move? in
            switch state.phase {
            case .bidding where state.mode == .coiffeur:
                return Move(kind: .choose, seat: seat, value: Int(bot_choose(handle, s)))
            case .bidding where state.mode == .sidi:
                return Move(kind: .call, seat: seat, value: Int(bot_call(handle, s)))
            case .bidding:
                return Move(kind: .bid, seat: seat, value: Int(bot_bid(handle, s)))
            case .block:
                return Move(kind: .block, seat: seat, value: Int(bot_block(handle, s)))
            case .doubling:
                return Move(kind: .double, seat: seat, value: Int(bot_double(handle, s)))
            case .weis:
                return Move(kind: .weis, seat: seat, value: 1)   // bots always announce
            case .playing:
                let seed = decision_seed(handle, s, round)
                let card = bot_play(handle, s, Engine.determinizations, Engine.iterations, seed)
                return card < 0 ? nil : Move(kind: .play, seat: seat, value: Int(card))
            case .roundOver, .gameOver:
                return nil
            }
        }
    }

    /// The move to fall back on when the engine rejects a bot's: every bot move is re-validated,
    /// and a rejected one must not stall the table.
    static func fallback(for move: Move) -> Move? {
        switch move.kind {
        case .choose: return Move(kind: .choose, seat: move.seat, value: 0)
        case .call: return Move(kind: .call, seat: move.seat, value: -1)
        default: return nil
        }
    }

    /// Sidi: does the bot on `seat` knock on the standing bid?
    func botKnocks(_ handle: UInt32, seat: Int) async -> Bool {
        await run { bot_knock(handle, UInt32(seat)) == 1 }
    }

    /// The cards a fourth bot would play from the player's own seat, best first. It sees what
    /// the player sees and nothing more.
    func advice(_ handle: UInt32, round: Int) async -> [Card] {
        await run { () -> [Card] in
            let seat = UInt32(Engine.humanSeat)
            let seed = decision_seed(handle, seat, UInt32(max(0, round)))
            let length = bot_rank(handle, seat, Engine.determinizations, Engine.iterations, seed)
            guard let data = Engine.readBuffer(length),
                  let advice = try? JSONDecoder().decode(Advice.self, from: data) else { return [] }
            return advice.moves.map(\.card)
        }
    }

    // MARK: Raw calls — engine thread only

    private static func rawNewGame(seed: UInt64, settings: GameSettings) -> UInt32 {
        var m = settings.multipliers.map { Int32(clamping: $0) }
        while m.count < 6 { m.append(1) }
        return game_new(
            UInt32(truncatingIfNeeded: seed),
            UInt32(truncatingIfNeeded: seed >> 32),
            Int32(clamping: settings.target),
            settings.weis ? 1 : 0,
            1,                                   // the player is asked whether to announce
            m[0], m[1], m[2], m[3], m[4], m[5],
            settings.mode.engineCode,
            settings.extraRowBits,
            settings.discard == .sister ? 1 : 0,
            settings.bidStyleBits
        )
    }

    private static func rawApply(_ handle: UInt32, _ move: Move) -> Bool {
        let seat = UInt32(clamping: move.seat)
        let signed = Int32(clamping: move.value)
        let unsigned = UInt32(clamping: move.value)
        switch move.kind {
        case .bid: return game_bid(handle, seat, signed) == 0
        case .weis: return game_choose_weis(handle, seat, unsigned) == 0
        case .play: return game_play(handle, seat, unsigned) == 0
        case .nextRound: return game_next_round(handle) == 0
        case .call: return game_call(handle, seat, signed) == 0
        case .double: return game_double(handle, seat, unsigned) == 0
        case .choose: return game_choose(handle, seat, signed) == 0
        case .block: return game_block(handle, seat, unsigned) == 0
        }
    }

    private static func rawView(_ handle: UInt32, acked: Int) -> TableState? {
        let length = game_view(handle, UInt32(humanSeat), UInt32(clamping: acked))
        guard let data = readBuffer(length) else { return nil }
        do {
            return try TableState.decode(data)
        } catch {
            // A view the app cannot read is a bug in TableState.swift, not a state to play on.
            assertionFailure("game_view did not decode: \(error)")
            return nil
        }
    }

    /// Copy the engine's shared buffer out before the next call overwrites it.
    private static func readBuffer(_ length: Int) -> Data? {
        guard length > 0, let pointer = view_ptr() else { return nil }
        return Data(bytes: pointer, count: length)
    }
}
