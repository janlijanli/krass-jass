import Foundation

/// The four suits, in the engine's order (D H S C).
enum Suit: Int, CaseIterable, Hashable {
    case diamonds, hearts, spades, clubs

    static let letters: [Character] = ["D", "H", "S", "C"]

    var letter: Character { Suit.letters[rawValue] }
    var isRed: Bool { self == .diamonds || self == .hearts }
    /// The engine's contract name for this suit as trump.
    var contractName: String { Contract.names[rawValue] }
}

/// A card as the engine names it on the wire: suit letter + rank letter, e.g. "HA", "ST".
///
/// `index` is the engine's own card number (suit × 9 + rank, ace first), which is what the
/// play call takes.
struct Card: Hashable, Identifiable, Decodable, CustomStringConvertible {
    static let ranks: [Character] = ["A", "K", "Q", "J", "T", "9", "8", "7", "6"]
    /// Swiss French cards say König, Dame, Bauer — K, D, B.
    static let rankLabels = ["A", "K", "D", "B", "10", "9", "8", "7", "6"]

    let suit: Suit
    /// 0 = ace … 8 = six, the engine's order.
    let rank: Int

    var index: Int { suit.rawValue * 9 + rank }
    var code: String { "\(suit.letter)\(Card.ranks[rank])" }
    var id: Int { index }
    var description: String { code }
    var rankLetter: Character { Card.ranks[rank] }
    var rankLabel: String { Card.rankLabels[rank] }
    var isCourt: Bool { (1...3).contains(rank) }

    init(suit: Suit, rank: Int) {
        self.suit = suit
        self.rank = rank
    }

    init?(code: String) {
        let chars = Array(code)
        guard chars.count == 2,
              let s = Suit.letters.firstIndex(of: chars[0]),
              let r = Card.ranks.firstIndex(of: chars[1]),
              let suit = Suit(rawValue: s) else { return nil }
        self.suit = suit
        self.rank = r
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let code = try container.decode(String.self)
        guard let card = Card(code: code) else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "not a card: \(code)")
        }
        self = card
    }
}

/// Contract names as the engine writes them, by contract index.
enum Contract {
    static let names = ["DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE"]

    static func index(of name: String) -> Int? { names.firstIndex(of: name) }

    /// The trump suit a contract name stands for; nil for Obenabe, Undenufe and Mitte.
    static func suit(of name: String) -> Suit? {
        guard let i = index(of: name), i < 4 else { return nil }
        return Suit(rawValue: i)
    }
}

/// A Sidi Barrani call in its wire forms: text ("PASS", "DOUBLE", "HEARTS 100") and the one
/// integer the engine takes (-1 pass, -2 double, contract × 1000 + value).
enum SidiCall {
    static func code(_ text: String) -> Int? {
        if text == "PASS" { return -1 }
        if text == "DOUBLE" { return -2 }
        let parts = text.split(separator: " ")
        guard parts.count == 2,
              let contract = Contract.index(of: String(parts[0])),
              let value = Int(parts[1]) else { return nil }
        return contract * 1000 + value
    }

    /// Contract name and value of a bid; nil for a pass or a double.
    static func bid(_ text: String) -> (contract: String, value: Int)? {
        let parts = text.split(separator: " ")
        guard parts.count == 2, let value = Int(parts[1]) else { return nil }
        return (String(parts[0]), value)
    }
}
