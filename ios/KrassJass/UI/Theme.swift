import SwiftUI

/// The table's colours — the same felt, paper and gold as the web UI (`web/static/table.css`).
enum Theme {
    static let felt = Color(hex: 0x1F5C49)
    static let feltDark = Color(hex: 0x123A2D)
    static let feltDeep = Color(hex: 0x0B281F)
    static let chrome = Color(hex: 0x164033)
    static let ink = Color(hex: 0x14201C)
    static let paper = Color(hex: 0xFDFBF6)
    static let paperShade = Color(hex: 0xF3EFE5)
    static let cardRed = Color(hex: 0xC0262F)
    static let cardBlack = Color(hex: 0x1B1B1B)
    static let gold = Color(hex: 0xDCB862)
    static let goldSoft = Color(hex: 0xF6E7C2)
    static let rose = Color(hex: 0xF4978C)
    static let panel = Color(hex: 0x0C1E18, opacity: 0.94)
    static let hairline = Color.white.opacity(0.09)
    static let textMuted = Color(hex: 0xDFE5E0)
    static let textFaint = Color(hex: 0xC2CEC7)

    static func suit(_ suit: Suit) -> Color { suit.isRed ? cardRed : cardBlack }

    /// Card height over width: the faces are drawn on a 100 × 140 grid.
    static let cardAspect: CGFloat = 1.4
}

/// The app's springs, named once so the table moves as one thing.
enum Motion {
    /// Cards travelling: hand to table, table to the winner.
    static let table = Animation.spring(response: 0.46, dampingFraction: 0.82)
    /// A card lifting under a finger.
    static let lift = Animation.spring(response: 0.26, dampingFraction: 0.68)
    static let quick = Animation.easeOut(duration: 0.2)
    static let panel = Animation.spring(response: 0.42, dampingFraction: 0.86)
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}

/// The felt: a soft pool of light in the middle of the table, darker towards the edges.
struct FeltBackground: View {
    var body: some View {
        ZStack {
            Theme.chrome
            RadialGradient(
                colors: [Theme.felt, Theme.feltDark, Theme.feltDeep],
                center: UnitPoint(x: 0.5, y: 0.42),
                startRadius: 20,
                endRadius: 620
            )
            // A whisper of weave, so the green reads as cloth rather than as a flat fill.
            Canvas { context, size in
                var path = Path()
                var y: CGFloat = 0
                while y < size.height {
                    path.move(to: CGPoint(x: 0, y: y))
                    path.addLine(to: CGPoint(x: size.width, y: y))
                    y += 3
                }
                context.stroke(path, with: .color(.white.opacity(0.018)), lineWidth: 1)
            }
            .allowsHitTesting(false)
        }
        .ignoresSafeArea()
    }
}

/// The dark glass the panels sit on.
struct PanelBackground: ViewModifier {
    var radius: CGFloat = 20

    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(Theme.panel)
                    .background(
                        .ultraThinMaterial,
                        in: RoundedRectangle(cornerRadius: radius, style: .continuous)
                    )
            )
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(Theme.hairline, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.35), radius: 24, y: 12)
    }
}

extension View {
    func panel(radius: CGFloat = 20) -> some View { modifier(PanelBackground(radius: radius)) }
}

/// A button on the felt: frosted by default, gold when it is the thing to press.
struct TableButtonStyle: ButtonStyle {
    enum Kind { case plain, primary, danger }
    var kind: Kind = .plain

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(.body, design: .rounded).weight(.semibold))
            .foregroundStyle(kind == .primary ? Theme.cardBlack : Color.white)
            .padding(.vertical, 12)
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous).fill(fill)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(border, lineWidth: 1)
            )
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(Motion.lift, value: configuration.isPressed)
    }

    private var fill: Color {
        switch kind {
        case .plain: return Color.white.opacity(0.09)
        case .primary: return Theme.gold
        case .danger: return Color(hex: 0xDC4646, opacity: 0.3)
        }
    }

    private var border: Color {
        switch kind {
        case .plain: return Color.white.opacity(0.16)
        case .primary: return Theme.gold
        case .danger: return Color(hex: 0xDC4646, opacity: 0.55)
        }
    }
}

extension ButtonStyle where Self == TableButtonStyle {
    static var table: TableButtonStyle { TableButtonStyle() }
    static var tablePrimary: TableButtonStyle { TableButtonStyle(kind: .primary) }
    static var tableDanger: TableButtonStyle { TableButtonStyle(kind: .danger) }
}
