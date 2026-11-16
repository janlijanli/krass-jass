import SwiftUI

/// Whatever the player is being asked, on the felt: trump, a Weis, a call, a row.
/// Empty when nothing is asked — the table is then just the table.
struct TablePanels: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState

    var body: some View {
        Group {
            if state.scorecard != nil {
                EmptyView()
            } else if controller.knock != nil || (state.phase == .doubling && state.doublePending) {
                DoublePanel(state: state)
            } else if state.phase == .weis && state.myTurn {
                WeisPanel(state: state)
            } else if state.phase == .block && state.myTurn, let blocks = state.coiffeur?.blocks, !blocks.isEmpty {
                BlockPanel(state: state, blocks: blocks)
            } else if state.phase == .bidding && state.myTurn {
                switch state.mode {
                case .schieber: TrumpPanel(state: state)
                case .sidi: SidiPanel(state: state)
                case .coiffeur: CoiffeurPanel(state: state)
                }
            } else if state.phase == .bidding && state.mode == .sidi && !state.auction.isEmpty {
                AuctionStrip(state: state)
            }
        }
        .transition(.scale(scale: 0.92).combined(with: .opacity))
        .animation(Motion.panel, value: panelKey)
    }

    /// Changes whenever a different panel should be up.
    private var panelKey: String {
        "\(state.phase.rawValue)|\(state.myTurn)|\(controller.knock?.key ?? "")|\(state.round)|\(state.auction.count)"
    }
}

/// A prompt over a panel's buttons.
private struct Prompt: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(.headline, design: .rounded))
            .foregroundColor(.white)
            .multilineTextAlignment(.center)
            .fixedSize(horizontal: false, vertical: true)
    }
}

/// A contract as a button: the suit in card colours on paper, or an arrow and a name.
struct ContractButton: View {
    let contract: String
    var detail: String?
    let action: () -> Void

    var body: some View {
        Button {
            Haptics.confirm()
            action()
        } label: {
            VStack(spacing: 4) {
                ContractSymbol(contract: contract, size: 26, onDark: false)
                Text(L10n.shared.contract(contract))
                    .font(.system(.caption, design: .rounded).weight(.semibold))
                    .foregroundColor(Theme.cardBlack)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                if let detail {
                    Text(detail)
                        .font(.system(.caption2, design: .rounded).weight(.bold))
                        .foregroundColor(Theme.cardBlack.opacity(0.55))
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(LinearGradient(colors: [.white, Theme.paperShade], startPoint: .top, endPoint: .bottom))
            )
            .shadow(color: .black.opacity(0.25), radius: 4, y: 2)
        }
        .buttonStyle(PressStyle())
        .accessibilityLabel(Text(L10n.shared.contract(contract)))
    }
}

/// Sinks a little under the finger.
struct PressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .animation(Motion.lift, value: configuration.isPressed)
    }
}

private let threeColumns = Array(repeating: GridItem(.flexible(), spacing: 10), count: 3)

// MARK: - Schieber

/// Choose trump, or shove it to the partner.
struct TrumpPanel: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState

    var body: some View {
        VStack(spacing: 14) {
            Prompt(text: t("bid.prompt"))
            LazyVGrid(columns: threeColumns, spacing: 10) {
                ForEach(Array(Contract.names.enumerated()), id: \.offset) { index, name in
                    ContractButton(contract: name, detail: multiplier(index)) {
                        controller.bid(contract: index)
                    }
                }
            }
            if state.canShove {
                Button(t("bid.shove")) {
                    Haptics.confirm()
                    controller.bid(contract: nil)
                }
                .buttonStyle(.tablePrimary)
            }
        }
        .padding(16)
        .panel()
    }

    private func multiplier(_ contract: Int) -> String? {
        let all = controller.activeSettings.multipliers
        guard contract < all.count, all.contains(where: { $0 != 1 }) else { return nil }
        return "×\(all[contract])"
    }
}

/// Announce a Weis or keep it quiet.
struct WeisPanel: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState

    var body: some View {
        VStack(spacing: 14) {
            if let offer = state.weisOffer {
                Prompt(text: "\(t("weis.prompt.pre")) \(t("weis.prompt.amount", ["n": "\(offer)"]))")
            } else {
                Prompt(text: t("status.weisAsk"))
            }
            HStack(spacing: 10) {
                Button(t("weis.decline")) {
                    Haptics.tap()
                    controller.announceWeis(false)
                }
                .buttonStyle(.table)
                Button(t("weis.announce")) {
                    Haptics.confirm()
                    controller.announceWeis(true)
                }
                .buttonStyle(.tablePrimary)
            }
        }
        .padding(16)
        .panel()
    }
}

// MARK: - Sidi Barrani

/// The auction so far, one chip a call, the standing bid in gold.
struct AuctionStrip: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState

    var body: some View {
        let calls = Array(state.auction.suffix(8).enumerated())
        let high = state.auction.lastIndex(where: { SidiCall.bid($0.call) != nil })
        let offset = max(0, state.auction.count - 8)
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(calls, id: \.offset) { index, call in
                    let standing = high == index + offset
                    Text("\(name(call.seat)): \(callLabel(call.call))")
                        .font(.system(.caption, design: .rounded).weight(standing ? .bold : .regular))
                        .foregroundColor(standing ? Theme.cardBlack : Theme.textMuted)
                        .padding(.horizontal, 9)
                        .padding(.vertical, 4)
                        .background(Capsule().fill(standing ? Theme.gold : Color.white.opacity(0.1)))
                }
            }
            .padding(.horizontal, 2)
        }
        .frame(height: 28)
    }

    private func name(_ seat: Int) -> String {
        seat == state.seat ? t("seat.you") : controller.names[seat]
    }
}

/// The player's call: points, then a contract — or pass, or double.
struct SidiPanel: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState
    @State private var value: Int?

    private var values: [Int] {
        var seen: [Int] = []
        for call in state.legalCalls {
            if let bid = SidiCall.bid(call), !seen.contains(bid.value) { seen.append(bid.value) }
        }
        return seen.sorted()
    }

    private var chosen: Int? {
        if let value, values.contains(value) { return value }
        return values.first
    }

    var body: some View {
        VStack(spacing: 12) {
            if !state.auction.isEmpty { AuctionStrip(state: state) }
            if let chosen {
                Prompt(text: t("sidi.prompt", ["n": "\(chosen)"]))
                ScrollViewReader { proxy in
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(values, id: \.self) { v in
                                Button {
                                    Haptics.select()
                                    withAnimation(Motion.quick) { value = v }
                                } label: {
                                    Text("\(v)")
                                        .font(.system(.subheadline, design: .rounded).weight(.bold))
                                        .monospacedDigit()
                                        .foregroundColor(v == chosen ? Theme.cardBlack : .white)
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 8)
                                        .background(Capsule().fill(v == chosen ? Theme.gold : Color.white.opacity(0.08)))
                                        .overlay(Capsule().strokeBorder(Color.white.opacity(0.18), lineWidth: 1))
                                }
                                .buttonStyle(PressStyle())
                                .id(v)
                            }
                        }
                        .padding(.horizontal, 2)
                    }
                    .onAppear { proxy.scrollTo(chosen, anchor: .leading) }
                }
                LazyVGrid(columns: threeColumns, spacing: 10) {
                    ForEach(Contract.names, id: \.self) { name in
                        ContractButton(contract: name) {
                            controller.call("\(name) \(chosen)")
                        }
                    }
                }
            } else {
                Prompt(text: t("sidi.promptNoBid"))
            }
            HStack(spacing: 10) {
                Button(t("sidi.pass")) {
                    Haptics.tap()
                    controller.call("PASS")
                }
                .buttonStyle(.table)
                if state.legalCalls.contains("DOUBLE") {
                    Button(t("sidi.double")) {
                        Haptics.confirm()
                        controller.call("DOUBLE")
                    }
                    .buttonStyle(.tableDanger)
                }
            }
        }
        .padding(16)
        .panel()
    }
}

/// "Double?" — a knock on an opponent's bid, or the question after the lead.
struct DoublePanel: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState

    private var question: String {
        if let offer = controller.knock {
            return t("sidi.knockAsk", ["who": controller.names[offer.seat], "bid": callLabel(offer.call)])
        }
        let who = state.declarer == state.seat ? t("seat.you") : controller.names[state.declarer]
        return t("sidi.doubleAsk", ["who": who, "bid": "\(state.bid ?? 0)"])
    }

    var body: some View {
        VStack(spacing: 12) {
            Prompt(text: question)
            HStack(spacing: 10) {
                Button(t("sidi.noDouble")) {
                    Haptics.tap()
                    controller.answerDouble(false)
                }
                .buttonStyle(.table)
                Button(t("sidi.double")) {
                    Haptics.confirm()
                    controller.answerDouble(true)
                }
                .buttonStyle(.tableDanger)
            }
        }
        .padding(16)
        .panel()
    }
}
