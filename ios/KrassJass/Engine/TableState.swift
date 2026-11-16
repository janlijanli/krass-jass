import Foundation

/// Everything one seat may see — the JSON `game_view` writes (`rust/src/wasm_api.rs`), which
/// mirrors what the web server sends. The app only ever asks for seat 0's view, so no other
/// hand reaches the UI layer.
///
/// Decoded with `.convertFromSnakeCase`: `trick_complete` arrives as `trickComplete`.
struct TableState: Decodable, Equatable {
    enum Phase: String, Decodable {
        case bidding, doubling, weis, playing, block
        case roundOver = "round_over"
        case gameOver = "game_over"
    }

    enum Mode: String, Codable, CaseIterable, Identifiable {
        case schieber, sidi, coiffeur
        var id: String { rawValue }
        /// The integer `game_new` takes.
        var engineCode: UInt32 {
            switch self {
            case .schieber: return 0
            case .sidi: return 1
            case .coiffeur: return 2
            }
        }
    }

    struct TrickCard: Decodable, Equatable, Identifiable {
        let seat: Int
        let card: Card
        var id: Int { card.index }
    }

    struct AuctionCall: Decodable, Equatable {
        let seat: Int
        let call: String
    }

    struct WeisEntry: Decodable, Equatable {
        let seat: Int
        let points: Int
        /// Only the best Weis at the table is turned face up, and only once every call is in.
        let cards: [Card]?
        let winner: Bool
        let best: Bool
    }

    struct StoeckEntry: Decodable, Equatable {
        let seat: Int
        let points: Int
    }

    struct Schedule: Decodable, Equatable {
        let name: String
        /// The contract of each of the nine tricks; nil where it is not known yet.
        let tricks: [String?]
        let misere: Bool
        let at: Int
    }

    struct Coiffeur: Decodable, Equatable {
        let rows: [String]
        let multipliers: [Int]
        /// Points written per team (0 = seats 0 and 2), in `rows` order; nil while open.
        let sheet: [[Int?]]
        let row: String?
        let schedule: Schedule?
        /// What this seat may choose now, in wire form; "SHOVE" last when a shove is allowed.
        let legal: [String]
        let shoves: Int
        let blocks: [String]
        let tens: Bool
        let strokes: [Int]
        let stroke: Int?
    }

    /// One round's result. The three games fill different lines, so most are optional.
    struct Scorecard: Codable, Equatable {
        let round: Int
        let contract: String
        let multiplier: Int?
        let trickPoints: [Int]
        let lastTrick: [Int]
        let match: [Int]
        let weis: [Int]?
        let stoeck: [Int]?
        let bid: Int?
        let doubled: Bool?
        let made: Bool?
        let bonus: [Int]?
        let team: Int?
        let row: String?
        let strokes: [Int]?
        let written: [Int]?
        let roundTotal: [Int]
        let scores: [Int]
    }

    let phase: Phase
    let seat: Int
    let round: Int
    let target: Int
    let toAct: Int?
    let hand: [Card]
    let legal: [Card]
    let trick: [TrickCard]
    let trickComplete: Bool
    let trickWinner: Int?
    /// Who is taking the trick as it lies.
    let trickTaker: Int?
    let contract: String?
    let multiplier: Int?
    let handSizes: [Int]?
    let declarer: Int
    let scores: [Int]
    let canShove: Bool
    let muss: Bool
    let muessi: Bool
    let muessiSeat: Int?
    let mode: Mode
    let coiffeur: Coiffeur?
    let auction: [AuctionCall]
    let legalCalls: [String]
    let bid: Int?
    let doubled: Bool
    let doublePending: Bool
    let tricksWon: [Int]
    let puur: Card?
    let weis: [WeisEntry]
    let stoeck: [StoeckEntry]
    let weisOffer: Int?
    let weisPending: Bool
    let scorecard: Scorecard?

    static func decode(_ data: Data) throws -> TableState {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(TableState.self, from: data)
    }

    // MARK: Derived

    var isOver: Bool { phase == .gameOver }
    var myTurn: Bool { toAct == seat }
    /// The team of a seat, from this seat's side: true for the player and their partner.
    func isUs(_ other: Int) -> Bool { (other - seat + 4) % 2 == 0 }
    var ourScore: Int { scores[seat % 2] }
    var theirScore: Int { scores[1 - seat % 2] }
    /// The trump suit of the trick on the table, if it is a suit contract.
    var trumpSuit: Suit? { contract.flatMap(Contract.suit(of:)) }
}

/// What the advice search thinks: up to three cards, best first (`bot_rank`).
struct Advice: Decodable {
    struct Entry: Decodable {
        let card: Card
        let visits: Int
        let share: Double
    }
    let forced: Card?
    let moves: [Entry]
}
