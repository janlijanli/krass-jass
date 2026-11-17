import Foundation

/// The rules of a table — what `game_new` takes. Changing these applies to the next game;
/// the game in play keeps the ones it was dealt with (they are saved with it).
struct GameSettings: Codable, Equatable {
    enum Discard: String, Codable, CaseIterable, Identifiable {
        case weakest, sister
        var id: String { rawValue }
    }

    enum BidStyle: String, Codable, CaseIterable, Identifiable {
        case count, feel
        var id: String { rawValue }
    }

    /// `schedule::EXTRA_ROWS` in Rust, in its order: the bit a row crosses on.
    static let extraRows = ["TUTTI", "SLALOM", "GUSCHTI", "TRIO", "MISERE", "MITTE"]
    static let defaultMultipliers = [1, 2, 1, 2, 3, 4]

    var mode: TableState.Mode = .schieber
    var target = 1000
    var weis = true
    /// Diamonds, hearts, spades, clubs, Obenabe, Undenufe.
    var multipliers = GameSettings.defaultMultipliers
    var discard: Discard = .weakest
    /// Coiffeur: the extra rows played.
    var rows = GameSettings.extraRows
    /// Sidi: how the partner (and so the player's own bids are read) and the opponents bid.
    var bidPartner: BidStyle = .count
    var bidOpponents: BidStyle = .count

    /// The target a mode is usually played to, offered when the mode changes.
    static func usualTarget(_ mode: TableState.Mode) -> Int { mode == .sidi ? 2000 : 1000 }

    var extraRowBits: UInt32 {
        var bits: UInt32 = 0
        for (i, row) in GameSettings.extraRows.enumerated() where rows.contains(row) {
            bits |= 1 << UInt32(i)
        }
        return bits
    }

    /// Bit i set for a seat that bids «Gspürsch mi, füehlsch mi». The player sits at 0.
    var bidStyleBits: UInt32 {
        var bits: UInt32 = 0
        for seat in 0..<4 {
            let style = seat % 2 == 0 ? bidPartner : bidOpponents
            if style == .feel { bits |= 1 << UInt32(seat) }
        }
        return bits
    }
}

/// How the app behaves around the game — nothing here reaches the engine's rules.
struct AppPreferences: Codable, Equatable {
    enum Tempo: String, Codable, CaseIterable, Identifiable {
        case relaxed, normal, brisk
        var id: String { rawValue }
        var factor: Double {
            switch self {
            case .relaxed: return 1.5
            case .normal: return 1.0
            case .brisk: return 0.55
            }
        }
    }

    var haptics = true
    /// Mark the cards a fourth bot would play from the player's seat.
    var advice = false
    /// Clear a finished trick after a moment instead of waiting for a tap.
    var autoCollect = false
    var tempo: Tempo = .normal
    /// nil = follow the device.
    var language: String?
}

/// Small typed wrapper over UserDefaults for the app's three saved values.
enum Store {
    private static let defaults = UserDefaults.standard

    static func load<T: Decodable>(_ type: T.Type, key: String) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }

    static func save<T: Encodable>(_ value: T, key: String) {
        if let data = try? JSONEncoder().encode(value) {
            defaults.set(data, forKey: key)
        }
    }

    static func remove(key: String) { defaults.removeObject(forKey: key) }
}
