import SwiftUI

/// The first thing on screen: pick up the saved game, or start one of the three.
struct SplashView: View {
    @EnvironmentObject private var controller: GameController
    let onContinue: () -> Void
    let onNew: (TableState.Mode) -> Void

    @State private var fanned = false

    private static let fan: [(Card, Double)] = [
        (Card(suit: .clubs, rank: 3), -24),
        (Card(suit: .diamonds, rank: 0), -8),
        (Card(suit: .spades, rank: 1), 8),
        (Card(suit: .hearts, rank: 2), 24),
    ]

    var body: some View {
        ZStack {
            FeltBackground()
            VStack(spacing: 22) {
                Spacer(minLength: 10)
                ZStack {
                    ForEach(Array(SplashView.fan.enumerated()), id: \.offset) { index, item in
                        CardView(card: item.0, width: 96)
                            .rotationEffect(.degrees(fanned ? item.1 : 0), anchor: UnitPoint(x: 0.5, y: 1.6))
                            .animation(Motion.table.delay(0.12 + Double(index) * 0.06), value: fanned)
                    }
                }
                .frame(height: 190)

                VStack(spacing: 4) {
                    Text("Krass Jass")
                        .font(.system(size: 38, weight: .heavy, design: .rounded))
                        .foregroundColor(.white)
                    Text("Schieber · Sidi Barrani · Coiffeur")
                        .font(.system(.subheadline, design: .rounded))
                        .foregroundColor(Theme.textFaint)
                }

                VStack(spacing: 10) {
                    if let saved = controller.savedSummary {
                        Button {
                            Haptics.confirm()
                            onContinue()
                        } label: {
                            VStack(spacing: 2) {
                                Text(t("splash.continue"))
                                Text(t("splash.continueNote", ["mode": L10n.shared.mode(saved.mode), "n": "\(saved.round)"]))
                                    .font(.system(.caption, design: .rounded))
                                    .opacity(0.7)
                            }
                        }
                        .buttonStyle(.tablePrimary)

                        Text(t("splash.newGame").uppercased())
                            .font(.system(size: 11, weight: .semibold, design: .rounded))
                            .kerning(1)
                            .foregroundColor(Theme.textFaint)
                            .padding(.top, 8)
                    }
                    ForEach(TableState.Mode.allCases) { mode in
                        Button {
                            Haptics.confirm()
                            onNew(mode)
                        } label: {
                            VStack(spacing: 2) {
                                Text(L10n.shared.mode(mode))
                                Text(t("splash.note.\(mode.rawValue)"))
                                    .font(.system(.caption, design: .rounded))
                                    .fontWeight(.regular)
                                    .multilineTextAlignment(.center)
                                    .opacity(0.7)
                            }
                        }
                        .buttonStyle(.table)
                    }
                }
                .frame(maxWidth: 380)
                .padding(.horizontal, 24)
                Spacer(minLength: 10)
            }
        }
        .onAppear { fanned = true }
    }
}
