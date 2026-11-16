import SwiftUI

/// Where everything in the play area sits, worked out once from its size.
struct TableMetrics {
    let size: CGSize

    var cardW: CGFloat { min(size.width / 4.6, size.height * 0.17, 132) }
    var cardH: CGFloat { cardW * Theme.cardAspect }
    /// Trick cards are the hand's cards, a touch smaller.
    var trickScale: CGFloat { 0.9 }
    var handCentreY: CGFloat { size.height - cardH * 0.5 - 12 }
    var statusY: CGFloat { size.height - cardH - 12 - cardW * 0.34 - 14 }
    /// The felt above the status line: seats, trick, panels.
    var tableHeight: CGFloat { statusY - 18 }
    var trickCentre: CGPoint { CGPoint(x: size.width / 2, y: tableHeight * 0.53) }

    /// A seat as seen from the player: 0 bottom, 1 right, 2 top, 3 left.
    static func side(of seat: Int, from me: Int) -> Int { (seat - me + 4) % 4 }

    func handPlace(_ index: Int, of count: Int) -> (point: CGPoint, angle: Angle) {
        let mid = CGFloat(count - 1) / 2
        let span = size.width - 28 - cardW
        let step = count > 1 ? min(cardW * 0.6, span / CGFloat(count - 1)) : 0
        let rel = mid > 0 ? (CGFloat(index) - mid) / mid : 0
        let spread = min(1, CGFloat(count) / 9)
        let x = size.width / 2 + (CGFloat(index) - mid) * step
        let y = handCentreY + rel * rel * cardW * 0.17 * spread
        return (CGPoint(x: x, y: y), .degrees(Double(rel * 9 * spread)))
    }

    func trickPlace(side: Int, card: Card) -> (point: CGPoint, angle: Angle) {
        let w = cardW * trickScale
        let h = cardH * trickScale
        let c = trickCentre
        // A card thrown on a table never lands square; the same card always lands the same way.
        let jitter = Double((card.index * 37) % 9) - 4
        switch side {
        case 0: return (CGPoint(x: c.x, y: c.y + h * 0.42), .degrees(-2 + jitter))
        case 1: return (CGPoint(x: c.x + w * 0.74, y: c.y), .degrees(7 + jitter))
        case 2: return (CGPoint(x: c.x, y: c.y - h * 0.42), .degrees(2 + jitter))
        default: return (CGPoint(x: c.x - w * 0.74, y: c.y), .degrees(-7 + jitter))
        }
    }

    /// How far off its place a card starts (or ends) when it comes from (goes to) a seat.
    func travel(side: Int) -> CGSize {
        switch side {
        case 0: return CGSize(width: 0, height: size.height * 0.42)
        case 1: return CGSize(width: size.width * 0.62, height: -20)
        case 2: return CGSize(width: 0, height: -size.height * 0.42)
        default: return CGSize(width: -size.width * 0.62, height: -20)
        }
    }

    func seatAnchor(side: Int) -> CGPoint {
        switch side {
        case 1: return CGPoint(x: size.width - 10, y: trickCentre.y - cardH * 0.95)
        case 2: return CGPoint(x: size.width / 2, y: 8)
        case 3: return CGPoint(x: 10, y: trickCentre.y - cardH * 0.95)
        default: return CGPoint(x: size.width / 2, y: statusY)
        }
    }
}

/// A sideways shiver for a card that may not be played.
private struct Shake: GeometryEffect {
    var animatableData: CGFloat

    func effectValue(size: CGSize) -> ProjectionTransform {
        ProjectionTransform(CGAffineTransform(translationX: sin(animatableData * .pi * 4) * 7, y: 0))
    }
}

/// The player's hand and the trick, as one layer.
///
/// Both live in the same coordinate space on purpose: a card keeps its identity from the fan
/// to the table, so playing it is one view changing place — it flies, it does not fade out in
/// one spot and in at another. The bots' cards arrive from their seats, and a cleared trick
/// leaves towards whoever took it.
struct CardLayer: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState
    let metrics: TableMetrics
    @Binding var selected: Card?

    @State private var dealtID = -1
    @State private var dragging: Card?
    @State private var dragOffset: CGSize = .zero
    @State private var shakes: [Int: CGFloat] = [:]

    private struct Placed: Identifiable {
        let card: Card
        var point: CGPoint
        var angle: Angle
        var scale: CGFloat
        var z: Double
        var inHand: Bool
        var handIndex: Int
        var side: Int
        var dimmed = false
        var glow = false
        var advice: Int?
        var id: Int { card.index }
    }

    private var isDealt: Bool { dealtID == controller.dealID }
    private var canPlay: Bool { state.phase == .playing && state.myTurn && !state.trickComplete }

    private var placements: [Placed] {
        var out: [Placed] = []
        let hand = state.hand
        for (i, card) in hand.enumerated() {
            var place = metrics.handPlace(i, of: hand.count)
            var z = 100 + Double(i)
            if !isDealt {
                place = (point: CGPoint(x: metrics.size.width / 2, y: metrics.size.height + metrics.cardH), angle: Angle.degrees(0))
            } else if card == selected || card == dragging {
                place.point.y -= metrics.cardW * 0.3
                if card == dragging { z = 300 }
            }
            let rank = controller.advice.firstIndex(of: card).map { $0 + 1 }
            out.append(Placed(
                card: card, point: place.point, angle: place.angle, scale: 1, z: z,
                inHand: true, handIndex: i, side: 0,
                dimmed: canPlay && !state.legal.contains(card),
                glow: false,
                advice: canPlay ? rank : nil
            ))
        }
        for (order, played) in state.trick.enumerated() {
            let side = TableMetrics.side(of: played.seat, from: state.seat)
            let place = metrics.trickPlace(side: side, card: played.card)
            out.append(Placed(
                card: played.card, point: place.point, angle: place.angle,
                scale: metrics.trickScale, z: Double(order),
                inHand: false, handIndex: 0, side: side,
                glow: state.trickComplete && state.trickWinner == played.seat
            ))
        }
        return out
    }

    var body: some View {
        ZStack {
            ForEach(placements) { item in
                CardView(
                    card: item.card,
                    width: metrics.cardW,
                    dimmed: item.dimmed,
                    glow: item.glow,
                    adviceRank: item.advice
                )
                // Gestures sit on the card itself, before it is moved into place, so the hit
                // area is the card and nothing else.
                .onTapGesture { tap(item.card) }
                .gesture(drag(item.card))
                .allowsHitTesting(item.inHand)
                .scaleEffect(item.scale)
                .rotationEffect(item.angle)
                .modifier(Shake(animatableData: shakes[item.id] ?? 0))
                .offset(dragging == item.card ? dragOffset : .zero)
                .position(item.point)
                .zIndex(item.z)
                .transition(transition(for: item))
                .animation(Motion.table.delay(Double(item.handIndex) * 0.045), value: isDealt)
            }
        }
        .frame(width: metrics.size.width, height: metrics.size.height)
        .task(id: controller.dealID) {
            // One beat with the hand off the table, then it is dealt in card by card.
            try? await Task.sleep(nanoseconds: 120_000_000)
            dealtID = controller.dealID
        }
        .onChange(of: state.hand) { _, _ in
            // The card that was dragged out is on the table now; let go of it in step with
            // its flight, so it travels from where the finger left it.
            withAnimation(Motion.table) {
                dragging = nil
                dragOffset = .zero
                selected = nil
            }
        }
        .onChange(of: controller.eventCount) { _, _ in
            guard controller.lastEvent == .rejected, dragging != nil else { return }
            withAnimation(Motion.lift) {
                dragging = nil
                dragOffset = .zero
            }
        }
    }

    /// A bot's card comes in from its seat; a cleared trick leaves towards its winner.
    private func transition(for item: Placed) -> AnyTransition {
        guard !item.inHand else { return .opacity }
        let from = metrics.travel(side: item.side)
        let winnerSide = TableMetrics.side(of: state.trickWinner ?? state.trickTaker ?? state.seat, from: state.seat)
        let to = metrics.travel(side: winnerSide)
        let arrive = AnyTransition.offset(x: from.width, y: from.height).combined(with: .opacity)
        let leave = AnyTransition.offset(x: to.width - (item.point.x - metrics.trickCentre.x),
                                         y: to.height - (item.point.y - metrics.trickCentre.y))
            .combined(with: .scale(scale: 0.45))
            .combined(with: .opacity)
        return .asymmetric(insertion: arrive, removal: leave)
    }

    private func tap(_ card: Card) {
        guard canPlay else {
            // Not the player's turn: a tap just lifts a card to look at it.
            withAnimation(Motion.lift) { selected = selected == card ? nil : card }
            Haptics.select()
            return
        }
        guard state.legal.contains(card) else {
            refuse(card)
            return
        }
        if selected == card {
            play(card)
        } else {
            withAnimation(Motion.lift) { selected = card }
            Haptics.select()
        }
    }

    private func drag(_ card: Card) -> some Gesture {
        DragGesture(minimumDistance: 12, coordinateSpace: .global)
            .onChanged { value in
                guard canPlay, state.legal.contains(card) else { return }
                if dragging != card {
                    dragging = card
                    Haptics.select()
                }
                dragOffset = value.translation
            }
            .onEnded { value in
                guard dragging == card else {
                    if canPlay, !state.legal.contains(card), value.translation.height < -30 { refuse(card) }
                    return
                }
                let flicked = value.predictedEndTranslation.height < -metrics.cardH * 0.9
                if value.translation.height < -metrics.cardH * 0.45 || flicked {
                    // Stays where the finger left it until the engine answers; then it flies
                    // from there to its place in the trick.
                    play(card)
                } else {
                    withAnimation(Motion.lift) {
                        dragging = nil
                        dragOffset = .zero
                    }
                }
            }
    }

    private func play(_ card: Card) {
        Haptics.playCard()
        controller.play(card)
    }

    private func refuse(_ card: Card) {
        Haptics.error()
        withAnimation(.linear(duration: 0.36)) {
            shakes[card.index, default: 0] += 1
        }
    }
}
