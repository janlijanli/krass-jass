import SwiftUI

/// The Jasstafel: the slate on the wall, written in chalk.
///
/// **The notation is `web/static/tafel.js`, point for point** — one denomination per line,
/// hundreds and twenties tallied in fives with the fifth struck across the four, fifties paired
/// into crosses, the far team's half turned upside down so each side reads its own marks the
/// right way up, and the totals either side of a centre strip with the target between them.
/// Changing how a board is written means changing both files. The wobble is the same function
/// over the same seeds, so the two builds draw the same board.
///
/// What is new here is the surface. The web roughs its chalk with an SVG turbulence filter,
/// which `Canvas` has no equivalent of, so the texture is built by hand: a blurred dust halo
/// under every stroke, the stroke itself, and then specks knocked out of it with
/// `destinationOut`, so the chalk breaks over the grain the way it does on stone.
enum Tafel {
    enum Glyph { case tall, slash, tick }

    /// The marks, largest first.
    ///
    /// The glyphs have to be unmistakable at a glance, which is the whole job: height and shape
    /// carry the value, not stroke count.
    ///
    ///   100  a full-height upright, five as four struck through by a backslash
    ///    50  a slash; a second fifty crosses it into an X
    ///    20  a short tick on the baseline, bundled in fives like the hundreds
    ///
    /// Changing the notation is changing this table, not the drawing code.
    static let marks: [(value: Int, glyph: Glyph)] = [(100, .tall), (50, .slash), (20, .tick)]

    /// A tally bundle: four strokes and the fifth struck across them.
    static let bundle = 5
    /// Bundles of five on one line before it continues below.
    static let bundlesPerLine = 2
    /// Crosses (two fifties each) on one line.
    static let crossesPerLine = 6

    /// How many marks of one kind fit on a line.
    static func perLine(_ glyph: Glyph) -> Int {
        glyph == .slash ? crossesPerLine * 2 : bundlesPerLine * bundle
    }

    struct Marks {
        var counts: [Int]
        var remainder: Int

        /// What the marks add up to — the board checked against the real score.
        var total: Int {
            zip(counts, Tafel.marks).reduce(remainder) { $0 + $1.0 * $1.1.value }
        }
    }

    /// The board as it actually gets written: round by round, marks accumulating.
    ///
    /// Chalk is not rubbed out and rewritten each round — marks stay where they were put. Only
    /// the remainder is a number in the corner, and that is the one thing that does get wiped
    /// and written again, because each round's leftover joins it and may become a new mark.
    ///
    /// So a team can end with three 50-marks where a redrawn total would show a hundred and a
    /// fifty. That is not an error, it is what a board that has been written on looks like.
    static func accumulate(_ roundPoints: [Int]) -> Marks {
        var counts = [Int](repeating: 0, count: marks.count)
        var remainder = 0
        for points in roundPoints {
            var pending = remainder + max(0, points)
            for (i, mark) in marks.enumerated() {
                let n = pending / mark.value
                counts[i] += n
                pending -= n * mark.value
            }
            remainder = pending
        }
        return Marks(counts: counts, remainder: remainder)
    }

    /// Lines one denomination takes: always one, more only once a line is full.
    static func lines(_ count: Int, _ glyph: Glyph) -> Int {
        max(1, Int((Double(count) / Double(perLine(glyph))).rounded(.up)))
    }

    /// Lines a whole half takes — one band per denomination, so the board keeps its shape.
    static func rows(_ marks: Marks) -> Int {
        zip(marks.counts, Tafel.marks).reduce(0) { $0 + lines($1.0, $1.1.glyph) }
    }
}

// MARK: - chalk

/// White chalk on a dark slate. The colour lives here, as it lives in one CSS variable on the web.
private enum Chalk {
    static let color = Color(hex: 0xF3F1EA)

    /// Deterministic jitter, so a mark wobbles the same way every time it is drawn and the board
    /// holds still instead of shimmering whenever something else on it changes.
    static func wobble(_ seed: Double, _ amount: Double = 1) -> CGFloat {
        let x = sin(seed * 127.1) * 43758.5453
        return CGFloat((x - x.rounded(.down) - 0.5) * 2 * amount)
    }
}

/// One chalk stroke: a line a hand drew, so it bows a little and its ends are not quite where
/// they were meant to be.
private struct Stroke {
    let a: CGPoint
    let b: CGPoint
    let control: CGPoint
    let width: CGFloat
    let seed: Double

    init(from: CGPoint, to: CGPoint, seed: Double, width: CGFloat = 2.6) {
        self.a = CGPoint(x: from.x + Chalk.wobble(seed, 0.8), y: from.y + Chalk.wobble(seed + 1, 0.8))
        self.b = CGPoint(x: to.x + Chalk.wobble(seed + 4, 0.8), y: to.y + Chalk.wobble(seed + 5, 0.8))
        self.control = CGPoint(
            x: (from.x + to.x) / 2 + Chalk.wobble(seed + 2, 1.3),
            y: (from.y + to.y) / 2 + Chalk.wobble(seed + 3, 1.3)
        )
        self.width = width + Chalk.wobble(seed + 6, 0.25)
        self.seed = seed
    }

    var path: Path {
        var p = Path()
        p.move(to: a)
        p.addQuadCurve(to: b, control: control)
        return p
    }

    func point(_ t: CGFloat) -> CGPoint {
        let u = 1 - t
        return CGPoint(
            x: u * u * a.x + 2 * u * t * control.x + t * t * b.x,
            y: u * u * a.y + 2 * u * t * control.y + t * t * b.y
        )
    }

    var length: CGFloat { hypot(b.x - a.x, b.y - a.y) }
    var angle: CGFloat { atan2(b.y - a.y, b.x - a.x) }
}

/// Chalk, in three passes: the dust that settles either side of the line, the line, and the
/// grain of the stone taking bites out of it.
private func drawChalk(_ ctx: GraphicsContext, _ stroke: Stroke) {
    ctx.drawLayer { layer in
        // Dust, not light: chalk leaves a little either side of the line, it does not glow.
        var dust = layer
        dust.addFilter(.blur(radius: 1.1))
        dust.stroke(
            stroke.path,
            with: .color(Chalk.color.opacity(0.07)),
            style: StrokeStyle(lineWidth: stroke.width * 1.9, lineCap: .round)
        )
        layer.stroke(
            stroke.path,
            with: .color(Chalk.color.opacity(0.93)),
            style: StrokeStyle(lineWidth: stroke.width, lineCap: .round)
        )
        var holes = layer
        holes.blendMode = .destinationOut
        let steps = max(8, Int(stroke.length * 1.3))
        let across = stroke.angle + .pi / 2
        for i in 0..<steps {
            let seed = stroke.seed + Double(i) * 3.7
            let t = CGFloat(i) / CGFloat(steps - 1)
            let on = stroke.point(t)
            let radius = 0.12 + abs(Chalk.wobble(seed + 11)) * 0.3
            let off = Chalk.wobble(seed + 23, Double(stroke.width) * 0.44)
            let c = CGPoint(x: on.x + cos(across) * off, y: on.y + sin(across) * off)
            holes.fill(
                Path(ellipseIn: CGRect(x: c.x - radius, y: c.y - radius, width: radius * 2, height: radius * 2)),
                with: .color(.black)
            )
        }
    }
}

/// A number in chalk: set a touch askew, then broken up the same way a stroke is.
private func drawChalkText(_ ctx: GraphicsContext, _ text: Text, at point: CGPoint, seed: Double) {
    let resolved = ctx.resolve(text)
    let size = resolved.measure(in: CGSize(width: 200, height: 80))
    ctx.drawLayer { layer in
        layer.translateBy(x: point.x, y: point.y)
        layer.rotate(by: .degrees(Double(Chalk.wobble(seed, 1.6))))
        layer.draw(resolved, at: .zero, anchor: .center)
        var holes = layer
        holes.blendMode = .destinationOut
        let count = max(10, Int(size.width * size.height / 7))
        for i in 0..<count {
            let s = seed + Double(i) * 5.3
            let x = Chalk.wobble(s, Double(size.width) / 2)
            let y = Chalk.wobble(s + 101, Double(size.height) / 2)
            let r = 0.14 + abs(Chalk.wobble(s + 202)) * 0.4
            holes.fill(
                Path(ellipseIn: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)),
                with: .color(.black)
            )
        }
    }
}

// MARK: - the board

/// The board's measurements, in the same units as `tafel.js` so the two stay comparable.
private enum Geo {
    static let width: CGFloat = 264
    static let pad: CGFloat = 8
    static let markW: CGFloat = 14
    static let markH: CGFloat = 24
    static let rowH: CGFloat = 36
    static let bundleGap: CGFloat = 16
    static let crossW: CGFloat = 22
    /// Segments shorter than this are stubs left either side of a number — not worth drawing.
    static let minSegment: CGFloat = 8
}

/// The marks themselves, drawn on whatever surface is behind them.
///
/// `history` is `[[us per round], [them per round]]` — the rounds as they were scored, not the
/// totals, because the board is written up one round at a time.
struct TafelMarksView: View {
    let history: [[Int]]
    let target: Int?

    var body: some View {
        let marks = history.map(Tafel.accumulate)
        let rowsThem = Tafel.rows(marks[1])
        let rowsUs = Tafel.rows(marks[0])
        let stripY = Geo.pad + CGFloat(rowsThem) * Geo.rowH + 14
        let height = stripY + 14 + CGFloat(rowsUs) * Geo.rowH + Geo.pad
        Canvas { ctx, size in
            ctx.scaleBy(x: size.width / Geo.width, y: size.width / Geo.width)
            // Their half on top, turned round; yours below, the right way up.
            drawHalf(ctx, x0: Geo.pad, y0: Geo.pad, width: Geo.width - Geo.pad * 2,
                     marks: marks[1], rows: rowsThem, flip: true, seed: 91)
            drawHalf(ctx, x0: Geo.pad, y0: stripY + 14, width: Geo.width - Geo.pad * 2,
                     marks: marks[0], rows: rowsUs, flip: false, seed: 11)
            drawStrip(ctx, stripY: stripY, scores: marks.map(\.total))
        }
        .aspectRatio(Geo.width / height, contentMode: .fit)
        .frame(maxWidth: 320)
    }

    /// The centre strip: the rule runs across with gaps left for the numbers, so nothing is
    /// written over a line.
    ///
    /// Each total sits on the side its own marks are on. Rotating the top half flips its marks
    /// to the right, so the top team's total belongs on the right — putting it on the left, as a
    /// "them on the left, us on the right" reading suggests, sets every total beside the *other*
    /// team's marks and makes the board unreadable.
    private func drawStrip(_ ctx: GraphicsContext, stripY: CGFloat, scores: [Int]) {
        let themX = Geo.width - Geo.pad - 24
        let usX = Geo.pad + 24
        let cuts = [(usX - 22, usX + 22), (Geo.width / 2 - 22, Geo.width / 2 + 22), (themX - 22, themX + 22)]
        var from = Geo.pad
        for (a, b) in cuts {
            if a - from >= Geo.minSegment {
                drawChalk(ctx, Stroke(from: CGPoint(x: from, y: stripY), to: CGPoint(x: a, y: stripY),
                                      seed: 3 + Double(from), width: 2.4))
            }
            from = b
        }
        if Geo.width - Geo.pad - from >= Geo.minSegment {
            drawChalk(ctx, Stroke(from: CGPoint(x: from, y: stripY),
                                  to: CGPoint(x: Geo.width - Geo.pad, y: stripY),
                                  seed: 3 + Double(from), width: 2.4))
        }
        let total = Font.system(size: 15, weight: .bold, design: .rounded)
        drawChalkText(ctx, Text("\(scores[1])").font(total).foregroundColor(Chalk.color.opacity(0.9)),
                      at: CGPoint(x: themX, y: stripY), seed: 7)
        drawChalkText(ctx, Text("\(scores[0])").font(total).foregroundColor(Chalk.color.opacity(0.9)),
                      at: CGPoint(x: usX, y: stripY), seed: 8)
        if let target {
            drawChalkText(
                ctx,
                Text("\(target)").font(.system(size: 12, design: .rounded)).foregroundColor(Chalk.color.opacity(0.5)),
                at: CGPoint(x: Geo.width / 2, y: stripY), seed: 9
            )
        }
    }

    /// One team's half: a line per denomination, counted in bundles.
    ///
    /// Hundreds first, then fifties, then twenties, each on its own line and each keeping its
    /// line even when empty — so the board holds still between rounds instead of re-flowing
    /// every time a mark is added, and so a glance at a line tells you what it is counting
    /// before you have counted it.
    private func drawHalf(
        _ ctx: GraphicsContext, x0: CGFloat, y0: CGFloat, width: CGFloat,
        marks: Tafel.Marks, rows: Int, flip: Bool, seed seedBase: Double
    ) {
        var g = ctx
        if flip {
            let cx = x0 + width / 2
            let cy = y0 + CGFloat(rows) * Geo.rowH / 2
            g.translateBy(x: cx, y: cy)
            g.rotate(by: .degrees(180))
            g.translateBy(x: -cx, y: -cy)
        }
        let left = x0 + 16
        var row = 0
        for (band, mark) in Tafel.marks.enumerated() {
            let count = marks.counts[band]
            let y = y0 + 6 + CGFloat(row) * Geo.rowH
            let seed = seedBase + Double(band) * 131
            if mark.glyph == .slash {
                drawCrosses(g, count: count, left: left, y0: y, seed: seed)
            } else {
                drawTally(g, glyph: mark.glyph, count: count, left: left, y0: y, seed: seed)
            }
            row += Tafel.lines(count, mark.glyph)
        }
        // The remainder, written where the marks are not: on the last line, off to the side.
        drawChalkText(
            g,
            Text("\(marks.remainder)")
                .font(.custom("BradleyHandITCTT-Bold", size: 16))
                .foregroundColor(Chalk.color.opacity(0.85)),
            at: CGPoint(x: x0 + width - 20, y: y0 + 6 + CGFloat(rows - 1) * Geo.rowH + Geo.markH - 6),
            seed: seedBase + 500
        )
    }

    /// Hundreds or twenties: uprights in bundles of five, the fifth a backslash across the four.
    private func drawTally(
        _ ctx: GraphicsContext, glyph: Tafel.Glyph, count: Int,
        left: CGFloat, y0: CGFloat, seed: Double
    ) {
        for i in 0..<count {
            let bundle = i / Tafel.bundle
            let y = y0 + CGFloat(bundle / Tafel.bundlesPerLine) * Geo.rowH
            let x = left + CGFloat(bundle % Tafel.bundlesPerLine)
                * (CGFloat(Tafel.bundle - 1) * Geo.markW + Geo.bundleGap)
            // Hundreds stand full height, twenties are short.
            let top = glyph == .tick ? y + Geo.markH * 0.55 : y
            let bottom = y + Geo.markH
            let k = i % Tafel.bundle
            if k < Tafel.bundle - 1 {
                let at = x + 6 + CGFloat(k) * Geo.markW
                drawChalk(ctx, Stroke(from: CGPoint(x: at, y: top), to: CGPoint(x: at, y: bottom),
                                      seed: seed + Double(i) * 17))
            } else {
                drawChalk(ctx, Stroke(
                    from: CGPoint(x: x - 2, y: top - 3),
                    to: CGPoint(x: x + 14 + CGFloat(Tafel.bundle - 2) * Geo.markW, y: bottom + 3),
                    seed: seed + Double(i) * 17, width: 2.3
                ))
            }
        }
    }

    /// Fifties: a slash, and the next fifty crosses it into an X.
    private func drawCrosses(_ ctx: GraphicsContext, count: Int, left: CGFloat, y0: CGFloat, seed: Double) {
        for i in 0..<count {
            let slot = i / 2
            let y = y0 + CGFloat(slot / Tafel.crossesPerLine) * Geo.rowH
            let x = left + 8 + CGFloat(slot % Tafel.crossesPerLine) * Geo.crossW
            let s = seed + Double(i) * 17
            if i % 2 == 0 {
                drawChalk(ctx, Stroke(from: CGPoint(x: x - 7, y: y + Geo.markH), to: CGPoint(x: x + 7, y: y), seed: s))
            } else {
                drawChalk(ctx, Stroke(from: CGPoint(x: x - 7, y: y), to: CGPoint(x: x + 7, y: y + Geo.markH), seed: s))
            }
        }
    }
}

// MARK: - the slate

/// A hashed value in 0..<1 from one integer — the grain of the stone and of the wood is random
/// but never moves, so the board looks like one object rather than a new one every redraw.
private func hashed(_ n: Int, _ salt: Int) -> CGFloat {
    let x = sin(Double(n) * 12.9898 + Double(salt) * 78.233) * 43758.5453
    return CGFloat(x - x.rounded(.down))
}

/// Quarried slate: dark, never flat, and darker where it has been wiped for years.
private struct StoneFace: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: 0x2B3033), Color(hex: 0x1D2225), Color(hex: 0x121618)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            RadialGradient(colors: [.white.opacity(0.055), .clear],
                           center: UnitPoint(x: 0.28, y: 0.12), startRadius: 4, endRadius: 300)
            RadialGradient(colors: [.white.opacity(0.035), .clear],
                           center: UnitPoint(x: 0.82, y: 0.88), startRadius: 4, endRadius: 240)
            Canvas { ctx, size in
                // Slate splits along planes; a few of them catch the light across the face.
                for i in 0..<7 {
                    let y = hashed(i, 3) * size.height
                    let tilt = (hashed(i, 4) - 0.5) * size.height * 0.26
                    var p = Path()
                    p.move(to: CGPoint(x: -4, y: y))
                    p.addQuadCurve(to: CGPoint(x: size.width + 4, y: y + tilt),
                                   control: CGPoint(x: size.width / 2, y: y + tilt * 0.3))
                    ctx.stroke(p, with: .color(.white.opacity(0.018 + Double(hashed(i, 5)) * 0.022)),
                               style: StrokeStyle(lineWidth: 0.6 + hashed(i, 6) * 1.8))
                }
                // The tooth of the stone: what makes chalk catch.
                let specks = Int(size.width * size.height / 190)
                for i in 0..<specks {
                    let x = hashed(i, 11) * size.width
                    let y = hashed(i, 12) * size.height
                    let r = 0.3 + hashed(i, 13) * 0.75
                    let light = hashed(i, 14) > 0.45
                    ctx.fill(
                        Path(ellipseIn: CGRect(x: x, y: y, width: r, height: r)),
                        with: .color(light ? .white.opacity(0.05) : .black.opacity(0.22))
                    )
                }
            }
        }
    }
}

/// The frame, and the sill a board keeps its chalk on.
private struct WoodFace: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: 0x8A6238), Color(hex: 0x5D3F22), Color(hex: 0x422C17)],
                startPoint: .top, endPoint: .bottom
            )
            Canvas { ctx, size in
                for i in 0..<26 {
                    let y = hashed(i, 21) * size.height
                    var p = Path()
                    p.move(to: CGPoint(x: 0, y: y))
                    p.addQuadCurve(to: CGPoint(x: size.width, y: y + (hashed(i, 22) - 0.5) * 5),
                                   control: CGPoint(x: size.width * 0.5, y: y + (hashed(i, 23) - 0.5) * 7))
                    ctx.stroke(p, with: .color(.black.opacity(0.05 + Double(hashed(i, 24)) * 0.1)),
                               style: StrokeStyle(lineWidth: 0.4 + hashed(i, 25) * 1.1))
                }
            }
        }
    }
}

/// The Jasstafel as an object: slate in a wooden frame, on a sill with the chalk still on it.
struct SlateBoard<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(spacing: 0) {
            content()
                .padding(.horizontal, 12)
                .padding(.vertical, 16)
                .frame(maxWidth: .infinity)
                .background(StoneFace())
                // Worn dark around the edge, where the sponge never quite reaches.
                .overlay(
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .stroke(Color.black.opacity(0.55), lineWidth: 18)
                        .blur(radius: 11)
                )
                .clipShape(RoundedRectangle(cornerRadius: 3, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .strokeBorder(Color.black.opacity(0.5), lineWidth: 1)
                )
                .padding(8)
            sill
        }
        .background(WoodFace())
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .strokeBorder(Color.white.opacity(0.12), lineWidth: 0.8)
        )
        .shadow(color: .black.opacity(0.55), radius: 20, x: 0, y: 12)
    }

    /// The sill: a lip of wood, the dust that gathers on it, and the stub of chalk.
    private var sill: some View {
        ZStack(alignment: .bottomTrailing) {
            LinearGradient(colors: [Color(hex: 0x3A2715), Color(hex: 0x6B4A2A), Color(hex: 0x4A3220)],
                           startPoint: .top, endPoint: .bottom)
            Canvas { ctx, size in
                for i in 0..<90 {
                    let x = hashed(i, 31) * size.width
                    let y = size.height * (0.25 + hashed(i, 32) * 0.7)
                    let r = 0.3 + hashed(i, 33) * 1.1
                    ctx.fill(Path(ellipseIn: CGRect(x: x, y: y, width: r, height: r)),
                             with: .color(Chalk.color.opacity(0.1 + Double(hashed(i, 34)) * 0.22)))
                }
            }
            Capsule(style: .continuous)
                .fill(LinearGradient(colors: [Color(hex: 0xFBF9F2), Color(hex: 0xD9D5C8)],
                                     startPoint: .top, endPoint: .bottom))
                .frame(width: 30, height: 7)
                .overlay(Capsule().strokeBorder(.black.opacity(0.12), lineWidth: 0.5))
                .shadow(color: .black.opacity(0.4), radius: 1.5, x: 0, y: 1)
                .rotationEffect(.degrees(-1.5))
                .padding(.trailing, 16)
                .padding(.bottom, 4)
        }
        .frame(height: 20)
    }
}
