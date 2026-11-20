import SwiftUI

/// Someone doubled: a fist pounding the table at their seat, and the table jumping with it.
///
/// A double is the loudest thing that happens in a Sidi Barrani, and until now it was the
/// quietest: the badge went from "100" to "100 ×2" and nothing else moved. At a real table it
/// arrives as a fist on the wood, so that is what it is here — and the haptics are two heavy
/// blows thrown by the same timeline that moves the fist, not a buzz that happens to be near.
///
/// Follows `poundAt` in `web/static/table.js`, which throws three blows. Two here, by request,
/// which is also what the hand can be felt doing through the glass.
enum Knock {
    /// When each blow lands, in seconds from the start. One source of truth: the fist, the
    /// shock rings, the table's jolt and the haptics all read these, so what is felt and what
    /// is seen cannot drift apart.
    static let blows: [Double] = [0.26, 0.56]
    /// How long the whole thing stays on screen, label and all.
    static let life: Double = 2.1
    /// The second blow is the harder one, as at a table.
    static let force: [CGFloat] = [0.85, 1.0]
    /// How far the table drops under each blow.
    static let drop: [CGFloat] = [3, 5]
}

/// The fist, its shock rings and the name of whoever threw it.
///
/// Animated by walking one state through a handful of poses rather than with a
/// `KeyframeAnimator`: inserted the way this view is — mid-flight, inside the transaction
/// that puts the new table state on screen — the keyframe animator never left its initial
/// value, and a fist at opacity 0 is no fist at all.
struct KnockEffect: View {
    let name: String
    /// Called as each blow lands, with its index. The haptic and the table's jolt hang off
    /// this, so they cannot be a frame out from the picture.
    let onBlow: (Int) -> Void

    /// Where the fist is: raised, down, raised, down harder, settled.
    private struct Pose {
        var lift: CGFloat
        var scale: CGFloat
        var squash: CGFloat
        var tilt: Double

        static let start = Pose(lift: -46, scale: 0.6, squash: 1, tilt: -24)
        static let raised = Pose(lift: -34, scale: 1.12, squash: 1, tilt: -26)
        static let first = Pose(lift: 6, scale: 1.0, squash: 0.84, tilt: 0)
        static let again = Pose(lift: -26, scale: 1.06, squash: 1, tilt: -22)
        static let second = Pose(lift: 10, scale: 1.14, squash: 0.76, tilt: 0)
        static let settled = Pose(lift: 0, scale: 1, squash: 1, tilt: 0)
    }

    @State private var pose = Pose.start
    @State private var shown = false
    @State private var labelUp = false
    /// One entry per blow already thrown. A ring is added when its blow lands rather than
    /// held back by a delay, so there is never a ring sitting on the felt waiting for it.
    @State private var rings: [Int] = []

    var body: some View {
        ZStack {
            ForEach(rings, id: \.self) { _ in
                ShockRing()
            }
            Text(verbatim: "👊")
                .font(.system(size: 46))
                .scaleEffect(x: pose.scale, y: pose.scale * pose.squash, anchor: .bottom)
                .rotationEffect(.degrees(pose.tilt))
                .offset(y: pose.lift)
                .opacity(shown ? 1 : 0)
                .shadow(color: .black.opacity(0.45), radius: 8, y: 6)
            if labelUp {
                Text("\(name): \(t("sidi.doubled"))!")
                    .font(.system(size: 12, weight: .heavy, design: .rounded))
                    .foregroundColor(Theme.cardBlack)
                    .lineLimit(1)
                    .fixedSize()
                    .padding(.horizontal, 10)
                    .padding(.vertical, 3)
                    .background(Capsule().fill(Theme.gold.opacity(0.95)))
                    .shadow(color: .black.opacity(0.3), radius: 5, y: 2)
                    .offset(y: 46)
                    .transition(.scale(scale: 0.6).combined(with: .opacity))
            }
        }
        .frame(width: 120, height: 120)
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .onAppear(perform: throwIt)
    }

    /// A blow landing: its ring, and the thump and jolt the table answers with.
    private func land(_ index: Int) {
        rings.append(index)
        onBlow(index)
    }

    /// The arm, from raised to settled, calling `land` on the two moments it hits.
    private func throwIt() {
        let blows = Knock.blows
        withAnimation(.easeOut(duration: 0.12)) {
            shown = true
            pose = .raised
        }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(0.12))
            // Down, and the first blow lands at `Knock.blows[0]`.
            withAnimation(.easeIn(duration: blows[0] - 0.12)) { pose = .first }
            try? await Task.sleep(for: .seconds(blows[0] - 0.12))
            land(0)
            withAnimation(Motion.quick) { labelUp = true }

            withAnimation(.easeOut(duration: 0.14)) { pose = .again }
            try? await Task.sleep(for: .seconds(0.14))
            withAnimation(.easeIn(duration: blows[1] - blows[0] - 0.14)) { pose = .second }
            try? await Task.sleep(for: .seconds(blows[1] - blows[0] - 0.14))
            land(1)

            withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) { pose = .settled }
            try? await Task.sleep(for: .seconds(Knock.life - blows[1] - 0.35))
            withAnimation(.easeIn(duration: 0.35)) {
                shown = false
                labelUp = false
            }
        }
    }
}

/// A ring thrown out of the table where a blow landed. It spreads from the moment it is put
/// on screen, which is the moment of the blow.
private struct ShockRing: View {
    @State private var out = false

    var body: some View {
        Circle()
            .strokeBorder(Theme.gold.opacity(0.9), lineWidth: 3)
            .frame(width: 70, height: 70)
            .scaleEffect(out ? 1.9 : 0.35)
            .opacity(out ? 0 : 0.95)
            .onAppear { withAnimation(.easeOut(duration: 0.6)) { out = true } }
    }
}
