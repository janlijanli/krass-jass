import SwiftUI

/// Card faces, drawn in code — a port of `web/static/cards.js`, which draws them as SVG.
///
/// The suits, the pips, the indices and the ace are drawn here, on the same 100 × 140 grid the
/// web version uses, so the two can be compared number for number. Layout follows a real French
/// deck: corner indices top-left and bottom-right, standard pip arrangements for 6–10, pips
/// below the midline inverted.
///
/// The court figures are the exception: they are CC0 art in the asset catalog, placed by
/// `drawCourt`. See `ios/CARD-ART.md`.

// MARK: - A small SVG path reader

/// Reads the subset of SVG path data the card art uses: absolute M, L, Q, C and Z.
enum SVGPath {
    private static var cache: [String: Path] = [:]

    static func path(_ data: String) -> Path {
        if let hit = cache[data] { return hit }
        let made = parse(data)
        cache[data] = made
        return made
    }

    private static func parse(_ data: String) -> Path {
        var path = Path()
        var command: Character = "M"
        var numbers: [CGFloat] = []
        var token = ""

        func flushToken() {
            if !token.isEmpty, let value = Double(token) { numbers.append(CGFloat(value)) }
            token = ""
        }

        /// Draw as many segments as the collected numbers make; a command letter may be
        /// followed by several coordinate sets.
        func flushCommand() {
            flushToken()
            var i = 0
            func point(_ at: Int) -> CGPoint { CGPoint(x: numbers[at], y: numbers[at + 1]) }
            switch command {
            case "M":
                var first = true
                while i + 1 < numbers.count {
                    if first { path.move(to: point(i)) } else { path.addLine(to: point(i)) }
                    first = false
                    i += 2
                }
            case "L":
                while i + 1 < numbers.count {
                    path.addLine(to: point(i))
                    i += 2
                }
            case "Q":
                while i + 3 < numbers.count {
                    path.addQuadCurve(to: point(i + 2), control: point(i))
                    i += 4
                }
            case "C":
                while i + 5 < numbers.count {
                    path.addCurve(to: point(i + 4), control1: point(i), control2: point(i + 2))
                    i += 6
                }
            case "Z":
                path.closeSubpath()
            default:
                break
            }
            numbers = []
        }

        for ch in data {
            if ch.isLetter {
                flushCommand()
                command = ch
            } else if ch == "-" {
                flushToken()
                token = "-"
            } else if ch.isNumber || ch == "." {
                token.append(ch)
            } else {
                flushToken()
            }
        }
        flushCommand()
        return path
    }
}

// MARK: - Suits

/// The suit symbols, drawn rather than typed, after the Swiss French-suited Jass cards: the
/// spade one solid pointed blade on a short flared foot, the club three clearly separate round
/// lobes on a thin stem — told apart by silhouette, not by colour. Each is drawn in a box from
/// -1 to 1 around the origin.
enum SuitArt {
    private static let heart =
        "M0 0.92 C-0.12 0.8 -1 0.22 -1 -0.34 C-1 -0.74 -0.72 -0.96 -0.46 -0.96 " +
        "C-0.22 -0.96 -0.06 -0.8 0 -0.6 C0.06 -0.8 0.22 -0.96 0.46 -0.96 " +
        "C0.72 -0.96 1 -0.74 1 -0.34 C1 0.22 0.12 0.8 0 0.92 Z"
    private static let diamond = "M0 -1 L0.74 0 L0 1 L-0.74 0 Z"
    private static let spade =
        "M0 -1 C0.18 -0.72 1 -0.3 1 0.18 C1 0.52 0.74 0.7 0.47 0.7 " +
        "C0.28 0.7 0.12 0.6 0.05 0.46 Q0.1 0.78 0.36 1 L-0.36 1 Q-0.1 0.78 -0.05 0.46 " +
        "C-0.12 0.6 -0.28 0.7 -0.47 0.7 C-0.74 0.7 -1 0.52 -1 0.18 C-1 -0.3 -0.18 -0.72 0 -1 Z"
    private static let clubStem = "M-0.05 -0.3 L0.05 -0.3 Q0.07 0.74 0.32 1 L-0.32 1 Q-0.07 0.74 -0.05 -0.3 Z"

    private static let club: Path = {
        var path = SVGPath.path(clubStem)
        // Three lobes that do not touch.
        for centre in [CGPoint(x: 0, y: -0.65), CGPoint(x: -0.6, y: 0.15), CGPoint(x: 0.6, y: 0.15)] {
            path.addEllipse(in: CGRect(x: centre.x - 0.35, y: centre.y - 0.35, width: 0.7, height: 0.7))
        }
        return path
    }()

    /// The symbol in its own -1…1 box.
    static func unit(_ suit: Suit) -> Path {
        switch suit {
        case .hearts: return SVGPath.path(heart)
        case .diamonds: return SVGPath.path(diamond)
        case .spades: return SVGPath.path(spade)
        case .clubs: return club
        }
    }

    /// The symbol centred on `centre`, `half` from centre to edge, upside down if asked.
    static func mark(_ suit: Suit, at centre: CGPoint, half: CGFloat, flipped: Bool = false) -> Path {
        var transform = CGAffineTransform(translationX: centre.x, y: centre.y)
        if flipped { transform = transform.rotated(by: .pi) }
        transform = transform.scaledBy(x: half, y: half)
        return unit(suit).applying(transform)
    }
}

/// A suit symbol as a SwiftUI shape, filling its frame — for badges, buttons and the top bar.
struct SuitShape: Shape {
    let suit: Suit

    func path(in rect: CGRect) -> Path {
        let half = min(rect.width, rect.height) / 2
        return SuitArt.mark(suit, at: CGPoint(x: rect.midX, y: rect.midY), half: half)
    }
}

/// A suit in its card colour, at a given size.
struct SuitIcon: View {
    let suit: Suit
    var size: CGFloat = 18
    /// On dark backgrounds the black suits are drawn in paper white.
    var onDark = false

    var body: some View {
        SuitShape(suit: suit)
            .fill(suit.isRed ? Theme.cardRed : (onDark ? Theme.paper : Theme.cardBlack))
            .frame(width: size, height: size)
    }
}

// MARK: - Court figures

/// One card face, drawn into whatever frame it is given (keep it 100 : 140).
struct CardFace: View {
    let card: Card

    /// Standard pip positions on the 100 × 140 face. Anything below y = 70 is drawn inverted.
    private static let pips: [Int: [(CGFloat, CGFloat)]] = [
        8: [(30, 38), (30, 70), (30, 102), (70, 38), (70, 70), (70, 102)],
        7: [(30, 38), (30, 70), (30, 102), (70, 38), (70, 70), (70, 102), (50, 54)],
        6: [(30, 38), (30, 70), (30, 102), (70, 38), (70, 70), (70, 102), (50, 54), (50, 86)],
        5: [(30, 34), (30, 58), (30, 82), (30, 106), (70, 34), (70, 58), (70, 82), (70, 106), (50, 70)],
        4: [(30, 34), (30, 58), (30, 82), (30, 106), (70, 34), (70, 58), (70, 82), (70, 106), (50, 46), (50, 94)],
    ]

    var body: some View {
        Canvas(opaque: false, rendersAsynchronously: false) { context, size in
            let scale = min(size.width / 100, size.height / 140)
            context.scaleBy(x: scale, y: scale)
            let colour = Theme.suit(card.suit)

            drawIndex(&context, colour: colour)
            var turned = context
            turned.translateBy(x: 100, y: 140)
            turned.rotate(by: .degrees(180))
            drawIndex(&turned, colour: colour)

            if card.rank == 0 {
                context.fill(SuitArt.mark(card.suit, at: CGPoint(x: 50, y: 72), half: 19), with: .color(colour))
            } else if let positions = CardFace.pips[card.rank] {
                for (x, y) in positions {
                    let mark = SuitArt.mark(card.suit, at: CGPoint(x: x, y: y), half: 8.5, flipped: y > 70)
                    context.fill(mark, with: .color(colour))
                }
            } else {
                drawCourt(&context)
            }
        }
        .aspectRatio(100.0 / 140.0, contentMode: .fit)
    }

    /// Rank over suit, in the top-left corner of whichever way up the context is.
    private func drawIndex(_ context: inout GraphicsContext, colour: Color) {
        let label = Text(card.rankLabel)
            .font(.system(size: card.rank == 4 ? 15 : 17, weight: .bold, design: .rounded))
            .foregroundColor(colour)
        context.draw(label, at: CGPoint(x: 13, y: 16), anchor: .center)
        context.fill(SuitArt.mark(card.suit, at: CGPoint(x: 13, y: 32), half: 6.4), with: .color(colour))
    }

    /// The court figure: the CC0 art from `letele/playing-cards`, placed the way the card it
    /// came from places it.
    ///
    /// That card is 240 x 336 and the figure fills a 164.8 x 260.8 box centred on it — the same
    /// proportions as our 100 x 140, so it drops in without distortion. The art is the figure
    /// only: the border, the rank glyph and the corner marks on the source card are left behind
    /// and ours are drawn instead, so the deck keeps its K / D / B.
    /// Pulled in from the source card's 68.7% of the width to 61%, which is what it takes to
    /// clear our corner index: the deck it came from writes its index in a narrower margin
    /// than we do, and the figure would otherwise be drawn over the K, D or B.
    private static let courtInset: CGFloat = 0.89

    private func drawCourt(_ context: inout GraphicsContext) {
        let w = 100 * 164.8 / 240.0 * CardFace.courtInset
        let h = 140 * 260.8 / 336.0 * CardFace.courtInset
        let box = CGRect(x: (100 - w) / 2, y: (140 - h) / 2, width: w, height: h)
        context.draw(context.resolve(Image("Court/\(card.code)")), in: box)
    }
}
