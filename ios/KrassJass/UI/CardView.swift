import SwiftUI

/// A playing card: paper, face, edge and shadow. Sized by its width.
struct CardView: View {
    let card: Card
    var width: CGFloat
    /// Not playable right now: drawn under a veil, so the legal cards stand out.
    var dimmed = false
    /// Gold halo — the card that is taking the trick, or the trump Jack's quiet mark.
    var glow = false
    /// 1, 2, 3 = the advice bot's first, second and third choice.
    var adviceRank: Int?

    private var radius: CGFloat { width * 0.085 }

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [.white, Theme.paper, Theme.paperShade],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
            CardFace(card: card)
                .padding(width * 0.02)
            if dimmed {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(Color(hex: 0x0B281F, opacity: 0.42))
            }
        }
        .frame(width: width, height: width * Theme.cardAspect)
        .overlay(
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .strokeBorder(glow ? Theme.gold : Color.black.opacity(0.16), lineWidth: glow ? 2 : 0.6)
        )
        .overlay(alignment: .topTrailing) {
            if let adviceRank {
                Text("\(adviceRank)")
                    .font(.system(size: width * 0.2, weight: .heavy, design: .rounded))
                    .foregroundColor(Theme.cardBlack)
                    .frame(width: width * 0.32, height: width * 0.32)
                    .background(Circle().fill(Theme.gold))
                    .overlay(Circle().strokeBorder(.white.opacity(0.8), lineWidth: 1))
                    .offset(x: width * 0.08, y: -width * 0.1)
                    .opacity(adviceRank == 1 ? 1 : 0.8)
                    .transition(.scale.combined(with: .opacity))
            }
        }
        .shadow(color: glow ? Theme.gold.opacity(0.7) : .clear, radius: width * 0.16)
        .shadow(color: .black.opacity(0.24), radius: width * 0.06, y: width * 0.035)
        .accessibilityLabel(Text(accessibilityName))
    }

    private var accessibilityName: String {
        "\(t("contract.\(card.suit.contractName)")) \(card.rankLabel)"
    }
}

/// The back of a card: deep red, a fine diamond lattice, a paper border.
struct CardBack: View {
    var width: CGFloat

    var body: some View {
        let radius = width * 0.085
        ZStack {
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .fill(Theme.paper)
            RoundedRectangle(cornerRadius: radius * 0.7, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [Color(hex: 0x9E2A2F), Color(hex: 0x6F1A22)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .overlay(
                    Canvas { context, size in
                        var lattice = Path()
                        let step = max(4, size.width / 5)
                        var x = -size.height
                        while x < size.width + size.height {
                            lattice.move(to: CGPoint(x: x, y: 0))
                            lattice.addLine(to: CGPoint(x: x + size.height, y: size.height))
                            lattice.move(to: CGPoint(x: x + size.height, y: 0))
                            lattice.addLine(to: CGPoint(x: x, y: size.height))
                            x += step
                        }
                        context.stroke(lattice, with: .color(.white.opacity(0.22)), lineWidth: 0.6)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: radius * 0.7, style: .continuous))
                )
                .padding(width * 0.07)
        }
        .frame(width: width, height: width * Theme.cardAspect)
        .overlay(
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .strokeBorder(Color.black.opacity(0.18), lineWidth: 0.6)
        )
        .shadow(color: .black.opacity(0.22), radius: width * 0.05, y: width * 0.03)
    }
}

/// A contract as a symbol: the suit for a trump, an arrow for Obenabe (↓) and Undenufe (↑),
/// a dot for Mitte, "?" where it is not known yet.
struct ContractSymbol: View {
    let contract: String?
    var size: CGFloat = 18
    var onDark = true

    var body: some View {
        Group {
            if let contract, let suit = Contract.suit(of: contract) {
                SuitIcon(suit: suit, size: size, onDark: onDark)
            } else {
                Image(systemName: symbolName)
                    .font(.system(size: size * 0.92, weight: .heavy))
                    .foregroundColor(onDark ? Theme.goldSoft : Theme.cardBlack)
                    .frame(width: size, height: size)
            }
        }
    }

    private var symbolName: String {
        switch contract {
        case "OBENABE": return "arrow.down"
        case "UNDENUFE": return "arrow.up"
        case "MITTE": return "arrow.up.and.down"
        default: return "questionmark"
        }
    }
}
