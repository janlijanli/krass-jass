import Foundation
import SwiftUI

/// Drives one table: the player on seat 0, three bots, the engine underneath.
///
/// Everything the web service did for the hosted version — run the turn loop, pace the bots,
/// hold a finished trick until it is cleared — happens here, as `site-src/solo.js` does it for
/// the browser build. The engine decides every rule; this class only decides *when*.
@MainActor
final class GameController: ObservableObject {
    /// Sidi: an opponent has just bid and the player may knock before anyone else speaks.
    struct KnockOffer: Equatable {
        let seat: Int
        let call: String
        let key: String
    }

    /// Something that just happened at the table, for the UI to answer with a haptic or a
    /// flourish. Derived from two consecutive views, never from the engine's hidden state.
    enum TableEvent: Equatable {
        case dealt
        case cardLanded(seat: Int)
        case trickTaken(byUs: Bool)
        case myTurn
        case announced            // a Weis or Stöck was called
        case roundScored(matchForUs: Bool?)
        case gameOver(won: Bool)
        case rejected
        /// Sidi: that seat just doubled. The fist and the two thumps are the view's
        /// (`Knock.swift`), which is why this one carries no haptic of its own.
        case doubled(seat: Int)
    }

    @Published private(set) var state: TableState?
    @Published private(set) var names: [String] = ["", "", "", ""]
    @Published private(set) var advice: [Card] = []
    @Published private(set) var knock: KnockOffer?
    /// Sidi: the last double, and a count so two in a row are two separate events.
    ///
    /// Published in its own right rather than read off `lastEvent`, because a turn can emit
    /// several events at once and SwiftUI only shows a watcher the last of them — a double
    /// ending the auction is followed by "your turn", which was quietly swallowing it.
    @Published private(set) var pound: Pound?

    struct Pound: Equatable {
        let seat: Int
        let count: Int
    }
    /// The rounds scored so far in this game, oldest first — the Jasstafel.
    @Published private(set) var rounds: [TableState.Scorecard] = []
    /// Counts the deals put on screen, so the hand can be dealt in again for each one.
    @Published private(set) var dealID = 0
    /// The rules of the game in play (the menu's settings apply from the next one).
    @Published private(set) var activeSettings = GameSettings()
    /// True until the first view of a restored or new game is on screen.
    @Published private(set) var loading = true
    @Published private(set) var hasSavedGame = false
    /// Counts up with every event, so views can key `onChange` on it.
    @Published private(set) var eventCount = 0
    private(set) var lastEvent: TableEvent?

    @Published var settings: GameSettings {
        didSet { Store.save(settings, key: Keys.settings) }
    }
    @Published var preferences: AppPreferences {
        didSet {
            Store.save(preferences, key: Keys.preferences)
            Haptics.enabled = preferences.haptics
            L10n.shared.setLanguage(preferences.language)
            if preferences.advice != oldValue.advice { refreshAdvice() }
        }
    }

    private let engine = Engine.shared
    private var handle: UInt32?
    private var acked = 0
    private var journal: Journal?
    private var driving = false
    /// Bumped by every new or restored game; a turn loop from the game before stops on it.
    private var generation = 0
    private var knockDeclined: String?
    private var botsKnockedKey: String?
    private var adviceKey: String?

    private enum Keys {
        static let settings = "kj.settings"
        static let preferences = "kj.preferences"
        static let game = "kj.game"
    }

    /// What it takes to rebuild a game: the seed, the rules, and every move in order — the
    /// bots' moves as they were made, not re-decided. Replaying lands on the same position, a
    /// half-played trick included.
    private struct Journal: Codable {
        var seed: UInt64
        var settings: GameSettings
        var moves: [Move]
        var acked = 0
        var knockDeclined: String?
        var botsKnockedKey: String?
        var names: [String]
        /// The Jasstafel's lines, so a resumed game shows its history.
        var rounds: [TableState.Scorecard] = []
    }

    init() {
        settings = Store.load(GameSettings.self, key: Keys.settings) ?? GameSettings()
        let prefs = Store.load(AppPreferences.self, key: Keys.preferences) ?? AppPreferences()
        preferences = prefs
        Haptics.enabled = prefs.haptics
        L10n.shared.setLanguage(prefs.language)
        hasSavedGame = Store.load(Journal.self, key: Keys.game) != nil
    }

    // MARK: Starting

    /// Pick up the saved game. Returns false when there is none that still replays.
    @discardableResult
    func resume() async -> Bool {
        guard let saved = Store.load(Journal.self, key: Keys.game),
              let restored = await engine.restore(seed: saved.seed, settings: saved.settings, moves: saved.moves)
        else {
            Store.remove(key: Keys.game)
            hasSavedGame = false
            return false
        }
        adopt(handle: restored)
        journal = saved
        acked = saved.acked
        knockDeclined = saved.knockDeclined
        botsKnockedKey = saved.botsKnockedKey
        names = saved.names.count == 4 ? saved.names : Names.deal()
        rounds = saved.rounds
        activeSettings = saved.settings
        dealID += 1
        await refresh(animated: false)
        drive()
        return true
    }

    /// Deal a new game with the current settings, in `mode` if given.
    func newGame(mode: TableState.Mode? = nil) async {
        if let mode, mode != settings.mode {
            settings.mode = mode
            settings.target = GameSettings.usualTarget(mode)
        }
        let seed = UInt64.random(in: 0..<(1 << 48))
        let fresh = await engine.newGame(seed: seed, settings: settings)
        adopt(handle: fresh)
        names = Names.deal()
        journal = Journal(seed: seed, settings: settings, moves: [], names: names)
        acked = 0
        knockDeclined = nil
        botsKnockedKey = nil
        rounds = []
        activeSettings = settings
        dealID += 1
        await refresh(animated: false)
        emit(.dealt)
        drive()
    }

    private func adopt(handle fresh: UInt32) {
        if let old = handle { engine.free(old) }
        handle = fresh
        generation += 1
        driving = false
        advice = []
        adviceKey = nil
        pound = nil
        knock = nil
    }

    // MARK: The player's moves

    /// Schieber: choose trump by contract index, or nil to shove.
    func bid(contract: Int?) { human(Move(kind: .bid, seat: Engine.humanSeat, value: contract ?? -1)) }

    func announceWeis(_ announce: Bool) {
        human(Move(kind: .weis, seat: Engine.humanSeat, value: announce ? 1 : 0))
    }

    func play(_ card: Card) {
        guard let state, state.legal.contains(card) else {
            emit(.rejected)
            return
        }
        human(Move(kind: .play, seat: Engine.humanSeat, value: card.index))
    }

    /// Sidi: a call in wire form — "PASS", "DOUBLE", "HEARTS 100".
    func call(_ text: String) {
        guard let code = SidiCall.code(text) else { return }
        human(Move(kind: .call, seat: Engine.humanSeat, value: code))
    }

    /// Sidi: answer "double?" — after the lead, or a knock on an opponent's bid.
    func answerDouble(_ double: Bool) {
        guard let state else { return }
        if state.phase == .doubling {
            human(Move(kind: .double, seat: Engine.humanSeat, value: double ? 1 : 0))
        } else if let offer = knock {
            if double {
                human(Move(kind: .call, seat: Engine.humanSeat, value: -2))
            } else {
                knockDeclined = offer.key
                knock = nil
                save()
                drive()
            }
        }
    }

    /// Coiffeur: one of `coiffeur.legal` by name ("HEARTS", "OBENABE/CHANCE", "TUTTI", "SHOVE").
    func choose(_ name: String) {
        guard let legal = state?.coiffeur?.legal, let index = legal.firstIndex(of: name) else { return }
        human(Move(kind: .choose, seat: Engine.humanSeat, value: name == "SHOVE" ? -1 : index))
    }

    /// Coiffeur 3×3: name the next block by contract name.
    func block(_ contract: String) {
        guard let index = Contract.index(of: contract) else { return }
        human(Move(kind: .block, seat: Engine.humanSeat, value: index))
    }

    /// Clear the finished trick off the table.
    func ackTrick() {
        guard let state, state.trickComplete else { return }
        acked += 1
        Task {
            await refresh()
            drive()
        }
    }

    func nextRound() {
        guard let state, state.phase == .roundOver else { return }
        Task {
            guard await perform(.nextRound()) else { return }
            acked = 0
            dealID += 1
            await refresh(animated: false)
            emit(.dealt)
            drive()
        }
    }

    private func human(_ move: Move) {
        Task {
            if await perform(move) {
                drive()
            } else {
                emit(.rejected)
            }
        }
    }

    // MARK: Engine round trips

    /// Apply a move, journal it if the engine took it, and show the result.
    private func perform(_ move: Move) async -> Bool {
        guard let handle else { return false }
        let mine = generation
        let result = await engine.apply(handle, move, acked: acked)
        guard mine == generation else { return false }
        if result.ok { journal?.moves.append(move) }
        if let next = result.state { show(next, animated: true) }
        return result.ok
    }

    private func refresh(animated: Bool = true) async {
        guard let handle else { return }
        let mine = generation
        let next = await engine.view(handle, acked: acked)
        guard mine == generation, let next else { return }
        show(next, animated: animated)
    }

    /// Put a view on screen: work out what changed, animate to it, save.
    private func show(_ next: TableState, animated: Bool) {
        let previous = state
        let events = Self.events(from: previous, to: next)
        let offer = knockOffer(next)
        if let card = next.scorecard, previous?.scorecard == nil, rounds.last?.round != card.round {
            rounds.append(card)
        }
        if animated {
            withAnimation(Motion.table) {
                state = next
                knock = offer
            }
        } else {
            state = next
            knock = offer
        }
        loading = false
        for event in events { emit(event) }
        save()
        refreshAdvice()
    }

    private func emit(_ event: TableEvent) {
        lastEvent = event
        eventCount += 1
        if case .doubled(let seat) = event { pound = Pound(seat: seat, count: (pound?.count ?? 0) + 1) }
        Haptics.play(event)
    }

    private static func events(from old: TableState?, to new: TableState) -> [TableEvent] {
        guard let old, old.round == new.round else { return [] }
        var out: [TableEvent] = []
        let me = new.seat
        if !new.trickComplete, new.trick.count > old.trick.count || (old.trickComplete && !new.trick.isEmpty),
           let last = new.trick.last, last.seat != me {
            out.append(.cardLanded(seat: last.seat))
        }
        if new.trickComplete && !old.trickComplete {
            if let last = new.trick.last, last.seat != me { out.append(.cardLanded(seat: last.seat)) }
            if let winner = new.trickWinner { out.append(.trickTaken(byUs: new.isUs(winner))) }
        }
        if new.weis.count > old.weis.count || new.stoeck.count > old.stoeck.count {
            out.append(.announced)
        }
        if let card = new.scorecard, old.scorecard == nil {
            if new.phase == .gameOver {
                out.append(.gameOver(won: new.ourScore > new.theirScore))
            } else {
                let mine = me % 2
                let match: Bool? = card.match[mine] > 0 ? true : (card.match[1 - mine] > 0 ? false : nil)
                out.append(.roundScored(matchForUs: match))
            }
        }
        if let seat = Self.doubler(from: old, to: new) { out.append(.doubled(seat: seat)) }
        let wasMine = old.myTurn && !old.trickComplete
        let isMine = new.myTurn && !new.trickComplete && new.scorecard == nil
        if isMine && !wasMine { out.append(.myTurn) }
        return out
    }

    /// Which seat doubled between these two views, or nil. The same reading as `newDouble`
    /// in `web/static/table.js`: a double in the auction is a call with a seat on it, while a
    /// double after the lead only turns `doubled` true — and then it was whoever was being
    /// asked. Taken from two views rather than from the engine, so a replayed game on launch
    /// does not pound the table for every double it rebuilds.
    private static func doubler(from old: TableState, to new: TableState) -> Int? {
        guard new.mode == .sidi, new.doubled, !old.doubled else { return nil }
        if let call = new.auction.first(where: { $0.call == "DOUBLE" }) { return call.seat }
        return old.phase == .doubling ? old.toAct : nil
    }

    // MARK: The turn loop

    /// Let the bots act until it is the player's turn again.
    private func drive() {
        guard !driving, handle != nil else { return }
        driving = true
        let mine = generation
        Task {
            await runBots(generation: mine)
            if mine == generation { driving = false }
        }
    }

    private func runBots(generation mine: Int) async {
        for _ in 0..<500 {
            guard mine == generation, let handle, let state else { return }
            if state.trickComplete {
                // Waiting on a tap — unless the player would rather not tap.
                guard preferences.autoCollect || demoMoves > 0 else { return }
                await pause(demoMoves > 0 ? 0.3 : 1.5)
                guard mine == generation, self.state?.trickComplete == true else { return }
                acked += 1
                await refresh()
                continue
            }
            #if DEBUG
            if demoMoves > 0, let move = Self.demoMove(state, knocking: knock != nil) {
                demoMoves -= 1
                await pause(0.25)
                guard mine == generation, await perform(move) else { return }
                continue
            }
            #endif
            guard let seat = state.toAct, seat != Engine.humanSeat else { return }
            if knock != nil { return }          // the player is being asked whether to knock
            if await botsKnock(state, handle: handle, generation: mine) { continue }
            guard mine == generation else { return }

            let started = Date()
            guard let move = await engine.botDecision(handle, state: state) else { return }
            // The pause is what is left of the target after the search, never added on top:
            // time spent thinking already keeps a bot from answering instantly.
            let target = Self.thinkingTime(for: state) * preferences.tempo.factor
            await pause(target - Date().timeIntervalSince(started))
            guard mine == generation else { return }

            if await perform(move) { continue }
            guard mine == generation else { return }
            // Re-validated like any move; a rejected one falls back rather than stalling.
            guard let fallback = Engine.fallback(for: move), await perform(fallback) else { return }
        }
    }

    private static func thinkingTime(for state: TableState) -> Double {
        switch state.phase {
        case .playing: return Double.random(in: 0.65...1.0)
        case .weis: return Double.random(in: 0.2...0.45)
        case .bidding where state.mode != .schieber: return Double.random(in: 0.5...1.1)
        default: return Double.random(in: 0.4...0.9)
        }
    }

    private func pause(_ seconds: Double) async {
        guard seconds > 0 else { return }
        try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
    }

    // MARK: Demo

    /// Debug builds only: how many of the player's own decisions the app makes by itself
    /// (`-kj.autoplay 12` on the command line), so a screenshot can be taken mid-game without
    /// anyone at the screen. Always 0 in a release build.
    private var demoMoves = 0

    #if DEBUG
    func demo(moves: Int) { demoMoves = max(0, moves) }

    /// The first thing on offer — a way to get somewhere, not a way to play.
    private static func demoMove(_ state: TableState, knocking: Bool) -> Move? {
        let seat = Engine.humanSeat
        guard state.scorecard == nil, !knocking, state.myTurn else { return nil }
        switch state.phase {
        case .playing:
            return state.legal.first.map { Move(kind: .play, seat: seat, value: $0.index) }
        case .weis:
            return Move(kind: .weis, seat: seat, value: 1)
        case .doubling:
            return Move(kind: .double, seat: seat, value: 0)
        case .block:
            return state.coiffeur?.blocks.first.flatMap(Contract.index(of:)).map {
                Move(kind: .block, seat: seat, value: $0)
            }
        case .bidding:
            switch state.mode {
            case .schieber: return Move(kind: .bid, seat: seat, value: 1)
            case .sidi:
                let bid = state.legalCalls.first { SidiCall.bid($0) != nil }
                return (state.auction.count < 2 ? bid : "PASS").flatMap(SidiCall.code).map {
                    Move(kind: .call, seat: seat, value: $0)
                }
            case .coiffeur:
                // Plain rows only: index 0 is always a legal choice when anything is.
                return Move(kind: .choose, seat: seat, value: 0)
            }
        case .roundOver, .gameOver:
            return nil
        }
    }
    #endif

    // MARK: Sidi — the knock

    /// The same rule as `Table.knock_offer` in web/app.py: a double may come at any time, so
    /// the player is asked the moment an opponent bids.
    private func knockOffer(_ v: TableState) -> KnockOffer? {
        guard v.mode == .sidi, v.phase == .bidding, let last = v.auction.last else { return nil }
        let key = "\(v.round)|\(v.auction.count)"
        let opponent = !v.isUs(last.seat)
        if last.call == "PASS" || last.call == "DOUBLE" || !opponent || v.myTurn { return nil }
        if v.auction.contains(where: { $0.call == "DOUBLE" }) || knockDeclined == key { return nil }
        return KnockOffer(seat: last.seat, call: last.call, key: key)
    }

    /// Every bot opposing the standing bid knocks or not, the moment the bid is made — the rule
    /// the player plays by. True if one of them doubled.
    private func botsKnock(_ v: TableState, handle: UInt32, generation mine: Int) async -> Bool {
        guard v.mode == .sidi, v.phase == .bidding else { return false }
        let bids = v.auction.filter { $0.call != "PASS" && $0.call != "DOUBLE" }
        let key = "\(v.round)|\(v.auction.count)"
        guard let bidder = bids.last?.seat,
              !v.auction.contains(where: { $0.call == "DOUBLE" }),
              botsKnockedKey != key else { return false }
        botsKnockedKey = key
        for step in [1, 3] {
            let seat = (bidder + step) % 4
            if seat == Engine.humanSeat { continue }
            guard await engine.botKnocks(handle, seat: seat), mine == generation else { continue }
            await pause(Double.random(in: 0.3...0.6))
            guard mine == generation else { return false }
            return await perform(Move(kind: .call, seat: seat, value: -2))
        }
        return false
    }

    // MARK: Advice

    /// Run the fourth bot when it is the player's card to play and there is a choice to make.
    /// Cached per position: the answer cannot change until a card is played.
    private func refreshAdvice() {
        guard preferences.advice, let state, let handle,
              state.phase == .playing, state.myTurn, state.legal.count >= 2 else {
            if !advice.isEmpty { advice = [] }
            adviceKey = nil
            return
        }
        let key = "\(state.round)|\(state.hand.map(\.code).joined())|\(state.trick.map(\.card.code).joined())"
        guard key != adviceKey else { return }
        adviceKey = key
        advice = []
        let mine = generation
        Task {
            let cards = await engine.advice(handle, round: state.round)
            guard mine == generation, adviceKey == key else { return }
            withAnimation(Motion.quick) { advice = cards }
        }
    }

    // MARK: Saving

    private func save() {
        guard var journal else { return }
        journal.acked = acked
        journal.knockDeclined = knockDeclined
        journal.botsKnockedKey = botsKnockedKey
        journal.names = names
        journal.rounds = rounds
        self.journal = journal
        Store.save(journal, key: Keys.game)
        hasSavedGame = true
    }

    /// The saved game's mode and round, for the "continue" line on the start screen.
    var savedSummary: (mode: TableState.Mode, round: Int)? {
        guard let saved = Store.load(Journal.self, key: Keys.game) else { return nil }
        return (saved.settings.mode, saved.moves.filter { $0.kind == .nextRound }.count + 1)
    }
}
