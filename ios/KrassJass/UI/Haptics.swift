import UIKit

/// What the table feels like.
///
/// One vocabulary, used the same way everywhere: a light tick for a card lifted, a firm tap
/// for a card played, a soft thud for someone else's card landing, and the system's
/// success / error for a trick, a match and a card that may not be played. Generators are
/// kept and re-armed, so the tap arrives with the card and not a frame after it.
@MainActor
enum Haptics {
    static var enabled = true

    private static let light = UIImpactFeedbackGenerator(style: .light)
    private static let medium = UIImpactFeedbackGenerator(style: .medium)
    private static let rigid = UIImpactFeedbackGenerator(style: .rigid)
    private static let soft = UIImpactFeedbackGenerator(style: .soft)
    private static let heavy = UIImpactFeedbackGenerator(style: .heavy)
    private static let selection = UISelectionFeedbackGenerator()
    private static let notification = UINotificationFeedbackGenerator()

    /// A card lifted out of the fan, or a row or value picked.
    static func select() {
        guard enabled else { return }
        selection.selectionChanged()
        selection.prepare()
    }

    /// The player's own card hitting the table.
    static func playCard() {
        guard enabled else { return }
        rigid.impactOccurred(intensity: 0.9)
        rigid.prepare()
    }

    /// A button that commits something: a bid, a call, the next round.
    static func confirm() {
        guard enabled else { return }
        medium.impactOccurred()
        medium.prepare()
    }

    static func tap() {
        guard enabled else { return }
        light.impactOccurred()
        light.prepare()
    }

    static func error() {
        guard enabled else { return }
        notification.notificationOccurred(.error)
    }

    /// Get the engine ready just before it is likely to be needed (the player's turn).
    static func prepare() {
        guard enabled else { return }
        selection.prepare()
        rigid.prepare()
    }

    static func play(_ event: GameController.TableEvent) {
        guard enabled else { return }
        switch event {
        case .dealt:
            ripple(count: 5, interval: 0.07, generator: soft, intensity: 0.55)
        case .cardLanded:
            soft.impactOccurred(intensity: 0.7)
            soft.prepare()
        case .trickTaken(let byUs):
            if byUs {
                medium.impactOccurred(intensity: 0.8)
            } else {
                light.impactOccurred(intensity: 0.5)
            }
        case .myTurn:
            light.impactOccurred(intensity: 0.6)
            prepare()
        case .announced:
            ripple(count: 2, interval: 0.11, generator: rigid, intensity: 0.8)
        case .roundScored(let matchForUs):
            if matchForUs == true {
                ripple(count: 3, interval: 0.12, generator: heavy, intensity: 1)
            } else {
                notification.notificationOccurred(matchForUs == false ? .warning : .success)
            }
        case .gameOver(let won):
            if won {
                ripple(count: 4, interval: 0.14, generator: heavy, intensity: 1)
            } else {
                notification.notificationOccurred(.warning)
            }
        case .rejected:
            notification.notificationOccurred(.error)
        case .doubled:
            // Nothing here on purpose: the two blows have to land *with* the fist, so
            // `KnockEffect` fires them off the same clock that drives the picture.
            break
        }
    }

    /// One blow of a fist on the table. Heavy, and hit twice by `KnockEffect`.
    ///
    /// `.heavy` alone is a single short knock; the second is given full intensity so the
    /// pair reads as a knock that means it, the way it is pounded at a real table.
    static func pound(intensity: CGFloat) {
        guard enabled else { return }
        heavy.impactOccurred(intensity: intensity)
        heavy.prepare()
    }

    /// A short run of taps — cards being dealt, a match being knocked on the table.
    private static func ripple(count: Int, interval: Double, generator: UIImpactFeedbackGenerator, intensity: CGFloat) {
        generator.prepare()
        Task { @MainActor in
            for i in 0..<count {
                if i > 0 { try? await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000)) }
                guard enabled else { return }
                generator.impactOccurred(intensity: intensity)
            }
        }
    }
}
