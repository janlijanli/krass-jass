import SwiftUI

/// Card faces, drawn in code — a port of `web/static/cards.js`, which draws them as SVG.
///
/// No image assets: nothing to license, and the faces stay crisp at any size. Everything is
/// laid out on the same 100 × 140 grid the web version uses, so the two can be compared
/// number for number. Layout follows a real French deck: corner indices top-left and
/// bottom-right, standard pip arrangements for 6–10, pips below the midline inverted.

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

/// Court figures, after the Swiss French-suited Jass cards: double-headed half-length figures
/// that fill the frame, split by a line across the middle. The King wears a crown, a beard and
/// an ermine collar and holds a sceptre; the Dame a small crown, her hair up, a pale veil, and
/// a red flower; the Bauer a beret with a red feather, a moustache, a laced doublet and a
/// halberd. Our own drawings of those features, simplified so that the three still read apart
/// by silhouette in a fanned hand.
enum CourtArt {
    static let ink = Color(hex: 0x1B1B1B)
    static let skin = Color(hex: 0xF2D3B3)
    static let gold = Color(hex: 0xE7B53C)
    static let red = Color(hex: 0xC7312C)
    static let blue = Color(hex: 0x2F5D9B)
    static let pale = Color(hex: 0xB9D5EE)
    static let white = Color(hex: 0xFBF8F1)
    static let beard = Color(hex: 0x9B8F84)
    static let hair = Color(hex: 0x8A5A33)
    static let moustache = Color(hex: 0x6B4A2E)
    static let leaf = Color(hex: 0x3D7A3A)

    /// One drawn element: a filled and/or outlined path.
    struct Piece {
        let path: Path
        var fill: Color?
        var stroke: Color? = CourtArt.ink
        var width: CGFloat = 0.8
    }

    private static func p(_ data: String, _ fill: Color?, stroke: Color? = ink, width: CGFloat = 0.8) -> Piece {
        Piece(path: SVGPath.path(data), fill: fill, stroke: stroke, width: width)
    }

    private static func ellipse(_ cx: CGFloat, _ cy: CGFloat, _ rx: CGFloat, _ ry: CGFloat,
                                _ fill: Color?, stroke: Color? = ink) -> Piece {
        Piece(path: Path(ellipseIn: CGRect(x: cx - rx, y: cy - ry, width: rx * 2, height: ry * 2)),
              fill: fill, stroke: stroke)
    }

    private static func rect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat, _ fill: Color?) -> Piece {
        Piece(path: Path(CGRect(x: x, y: y, width: w, height: h)), fill: fill)
    }

    private static func dot(_ cx: CGFloat, _ cy: CGFloat, _ r: CGFloat, _ fill: Color) -> Piece {
        ellipse(cx, cy, r, r, fill, stroke: nil)
    }

    /// The costume colours change from suit to suit, as they do on the printed cards.
    private static func costume(_ suit: Suit) -> (robe: Color, sleeve: Color, panel: Color) {
        switch suit {
        case .spades: return (blue, red, gold)
        case .clubs: return (red, blue, gold)
        case .hearts: return (red, gold, blue)
        case .diamonds: return (blue, gold, red)
        }
    }

    private static func face() -> [Piece] {
        return [
            ellipse(55, 31.5, 6.6, 8, skin),
            dot(52.6, 30.3, 0.75, ink),
            dot(57.4, 30.3, 0.75, ink),
            p("M55 31 L54.3 34 L55.4 34.2", nil),
        ]
    }

    /// Head at (55, 31): face, then what each figure wears. `rank` is 1 King, 2 Dame, 3 Bauer.
    static func head(rank: Int) -> [Piece] {
        switch rank {
        case 1:
            let extra: [Piece] = [
                p("M48.8 33.5 Q48.5 42.5 55 44.5 Q61.5 42.5 61.2 33.5 Q58.5 37.5 55 37.8 Q51.5 37.5 48.8 33.5 Z", beard),
                p("M52.2 36.4 Q55 35.2 57.8 36.4", nil),
                p("M47.5 25 L48.5 15.5 L51.5 20 L55 13.5 L58.5 20 L61.5 15.5 L62.5 25 Z", gold),
                rect(47.5, 23.2, 15, 3.2, red),
                ellipse(55, 13.6, 1.2, 1.2, red),
            ]
            return face() + extra
        case 2:
            let behind: [Piece] = [
                p("M47.4 34 Q45.5 20 55 21 Q64.5 20 62.6 34 Q60 25 55 25.5 Q50 25 47.4 34 Z", hair),
                p("M61.5 26 Q70 34 66 52 L61 52 Q64 38 59 30 Z", pale),
            ]
            let front: [Piece] = [
                p("M52.8 36 Q55 37.2 57.2 36", nil, stroke: red, width: 0.9),
                p("M50.5 22 L51.5 17.5 L53.5 20.2 L55 16.5 L56.5 20.2 L58.5 17.5 L59.5 22 Z", gold),
            ]
            return behind + face() + front
        default:
            let extra: [Piece] = [
                p("M51.5 36.4 Q55 34.6 58.5 36.4 Q55 35.8 51.5 36.4 Z", moustache),
                p("M46.5 24.5 Q47 17.5 56 17.5 Q65 17.5 64.5 23.5 Q56 21.5 46.5 24.5 Z", blue),
                p("M46.3 24.8 Q55 22 64.6 23.8 L64.4 25.4 Q55 23.8 46.5 26.4 Z", red),
                p("M49 19.5 Q42 16 40.5 22.5 Q45 19.5 49.5 21.5 Z", red),
            ]
            return face() + extra
        }
    }

    /// The body from the shoulders to the dividing line at y = 70, and what the hands hold.
    static func body(rank: Int, suit: Suit) -> [Piece] {
        let c = costume(suit)
        let robe: [Piece] = [
            p("M20 70 L20 54 Q23 44.5 40 43 L70 43 Q84 44.5 85 54 L85 70 Z", c.robe),
            p("M20 70 L20 57 Q25 49 36 47.5 L39 70 Z", c.sleeve),
            p("M85 70 L85 57 Q80 49 72 47.5 L69 70 Z", c.sleeve),
        ]
        switch rank {
        case 1:
            let extra: [Piece] = [
                p("M47 43.5 L63 43.5 L64.5 70 L45.5 70 Z", c.panel),
                p("M40 43.2 Q55 50.5 70 43.2 L70 47 Q55 54 40 47 Z", white),
                dot(45, 47, 0.7, ink), dot(52, 49.4, 0.7, ink), dot(58, 49.4, 0.7, ink), dot(65, 47, 0.7, ink),
                rect(72.8, 27, 2.4, 43, gold),
                ellipse(74, 25, 3, 3, gold),
                p("M74 22 L74 20 M72.6 21 L75.4 21", nil),
                ellipse(74, 56, 3.4, 2.8, skin),
            ]
            return robe + extra
        case 2:
            let extra: [Piece] = [
                p("M46 44 L64 44 L66 70 L44 70 Z", c.panel),
                p("M46 44 Q55 49 64 44", nil),
                rect(44.6, 62, 21, 2.6, red),
                p("M35.5 64 Q36 55 38 46", nil, stroke: leaf, width: 1.1),
                p("M36.5 55 Q33 53 32.5 50.5 Q35.5 51.5 36.8 54 Z", leaf, stroke: nil),
                ellipse(38.2, 44.6, 2.8, 2.8, red),
                dot(38.2, 44.6, 1, gold),
                ellipse(36, 58, 3.2, 2.6, skin),
            ]
            return robe + extra
        default:
            let extra: [Piece] = [
                p("M47 43.5 L63 43.5 L63.5 70 L46.5 70 Z", c.panel),
                p("M49 47 L61 55 M61 47 L49 55 M49 55 L61 63 M61 55 L49 63", nil, stroke: red, width: 1),
                p("M46 43.2 Q55 47.5 64 43.2", white),
                rect(73.3, 20, 2, 50, gold),
                p("M74.3 12 L76.5 19 L81 17 Q82 23 76 25 L74.3 26 L72.6 25 Q67 23 68 17 L72.2 19 Z", pale),
                ellipse(74.3, 55, 3.4, 2.8, skin),
            ]
            return robe + extra
        }
    }
}

// MARK: - The face

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

    private func drawCourt(_ context: inout GraphicsContext) {
        let frame = Path(roundedRect: CGRect(x: 21, y: 9, width: 62, height: 122), cornerRadius: 3.5)
        context.fill(frame, with: .color(.white))

        var clipped = context
        clipped.clip(to: frame)
        drawHalf(&clipped)
        var lower = clipped
        // Turned about the frame's own centre, so the second head mirrors the first.
        lower.translateBy(x: 104, y: 140)
        lower.rotate(by: .degrees(180))
        drawHalf(&lower)

        var divider = Path()
        divider.move(to: CGPoint(x: 21, y: 70))
        divider.addLine(to: CGPoint(x: 83, y: 70))
        context.stroke(divider, with: .color(CourtArt.ink), lineWidth: 0.7)
        context.stroke(frame, with: .color(CourtArt.ink.opacity(0.75)), lineWidth: 0.9)
    }

    private func drawHalf(_ context: inout GraphicsContext) {
        draw(CourtArt.body(rank: card.rank, suit: card.suit), in: &context)
        // The head is drawn at a modest size and then enlarged: on the printed cards it is the
        // biggest thing in the frame, and it is what the eye finds first in a fanned hand.
        var head = context
        head.translateBy(x: 55, y: 33.5)
        head.scaleBy(x: 1.3, y: 1.3)
        head.translateBy(x: -55, y: -31.5)
        draw(CourtArt.head(rank: card.rank), in: &head)
        context.fill(SuitArt.mark(card.suit, at: CGPoint(x: 29, y: 21), half: 6), with: .color(Theme.suit(card.suit)))
    }

    private func draw(_ pieces: [CourtArt.Piece], in context: inout GraphicsContext) {
        for piece in pieces {
            if let fill = piece.fill { context.fill(piece.path, with: .color(fill)) }
            if let stroke = piece.stroke {
                context.stroke(
                    piece.path,
                    with: .color(stroke),
                    style: StrokeStyle(lineWidth: piece.width, lineJoin: .round)
                )
            }
        }
    }
}
