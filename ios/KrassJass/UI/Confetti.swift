import SwiftUI

/// A burst of paper for a game won: gold, red and white, falling and turning.
struct ConfettiView: View {
    private struct Piece {
        let x: Double          // 0…1 across the screen
        let delay: Double
        let speed: Double
        let sway: Double
        let size: Double
        let spin: Double
        let colour: Color
    }

    private let pieces: [Piece] = (0..<90).map { _ in
        Piece(
            x: Double.random(in: 0...1),
            delay: Double.random(in: 0...1.6),
            speed: Double.random(in: 0.22...0.5),
            sway: Double.random(in: 10...36),
            size: Double.random(in: 6...12),
            spin: Double.random(in: 2...7),
            colour: [Theme.gold, Theme.cardRed, Theme.paper, Theme.goldSoft, Theme.rose].randomElement() ?? Theme.gold
        )
    }
    @State private var start = Date()

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                let elapsed = timeline.date.timeIntervalSince(start)
                for piece in pieces {
                    let time = elapsed - piece.delay
                    guard time > 0 else { continue }
                    let y = -20 + time * piece.speed * size.height
                    guard y < size.height + 20 else { continue }
                    let x = piece.x * size.width + sin(time * 2.4 + piece.x * 9) * piece.sway
                    var local = context
                    local.translateBy(x: x, y: y)
                    local.rotate(by: .radians(time * piece.spin))
                    // Seen edge-on as it turns: the width breathes.
                    let width = piece.size * abs(cos(time * piece.spin * 0.7)) + 1
                    let rect = CGRect(x: -width / 2, y: -piece.size / 2, width: width, height: piece.size * 0.62)
                    local.opacity = min(1, max(0, 6 - time))
                    local.fill(Path(roundedRect: rect, cornerRadius: 1.2), with: .color(piece.colour))
                }
            }
        }
        .ignoresSafeArea()
        .onAppear { start = Date() }
    }
}
