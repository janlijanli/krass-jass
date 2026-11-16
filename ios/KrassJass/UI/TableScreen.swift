import SwiftUI

/// The game: top bar, the felt with its three other seats, the trick, and the player's hand.
struct TableScreen: View {
    @EnvironmentObject private var controller: GameController
    @Binding var showMenu: Bool
    @State private var showBoard = false
    @State private var selected: Card?

    var body: some View {
        ZStack {
            FeltBackground()
            if let state = controller.state {
                VStack(spacing: 0) {
                    TopBar(state: state, onMenu: { showMenu = true }, onBoard: { showBoard = true })
                    GeometryReader { geo in
                        playArea(state, metrics: TableMetrics(size: geo.size))
                    }
                }
                if state.scorecard != nil {
                    ScorecardOverlay(state: state)
                        .transition(.opacity.combined(with: .scale(scale: 0.94)))
                        .zIndex(10)
                }
                if state.isOver, state.scorecard != nil, state.ourScore > state.theirScore {
                    ConfettiView()
                        .allowsHitTesting(false)
                        .zIndex(11)
                }
            } else {
                ProgressView(t("app.loading"))
                    .tint(Theme.gold)
                    .foregroundColor(Theme.textMuted)
            }
        }
        .sheet(isPresented: $showBoard) {
            BoardSheet()
                .environmentObject(controller)
        }
    }

    private func playArea(_ state: TableState, metrics: TableMetrics) -> some View {
        ZStack {
            // The felt itself takes the tap that clears a finished trick.
            Color.clear
                .contentShape(Rectangle())
                .onTapGesture {
                    if state.trickComplete {
                        Haptics.tap()
                        controller.ackTrick()
                    } else if selected != nil {
                        withAnimation(Motion.lift) { selected = nil }
                    }
                }

            ForEach([1, 2, 3], id: \.self) { side in
                let seat = (state.seat + side) % 4
                SeatPlate(state: state, seat: seat, side: side)
                    .position(platePosition(side: side, metrics: metrics))
            }

            WeisShowcase(state: state)
                .position(x: metrics.size.width / 2, y: metrics.trickCentre.y - metrics.cardH * 1.32)

            StatusLine(state: state, selected: selected)
                .position(x: metrics.size.width / 2, y: metrics.statusY)

            CardLayer(state: state, metrics: metrics, selected: $selected)

            // Above the cards, but only ever over the felt: the hand stays in reach. A double
            // after the lead sits at the top, so the card that was led stays in view.
            if !state.trickComplete {
                TablePanels(state: state)
                    .frame(
                        width: min(metrics.size.width - 28, 460),
                        height: max(120, metrics.tableHeight - 70),
                        alignment: state.phase == .doubling ? .top : .center
                    )
                    .position(x: metrics.size.width / 2, y: 66 + max(120, metrics.tableHeight - 70) / 2)
            }
        }
    }

    private func platePosition(side: Int, metrics: TableMetrics) -> CGPoint {
        switch side {
        case 1: return CGPoint(x: metrics.size.width - 62, y: metrics.trickCentre.y - metrics.cardH * 1.0)
        case 2: return CGPoint(x: metrics.size.width / 2, y: 30)
        default: return CGPoint(x: 62, y: metrics.trickCentre.y - metrics.cardH * 1.0)
        }
    }
}

// MARK: - Top bar

/// Scores left and right, what is being played in the middle.
struct TopBar: View {
    let state: TableState
    let onMenu: () -> Void
    let onBoard: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Button(action: onBoard) {
                HStack(spacing: 14) {
                    score(t("team.us"), state.ourScore, leading: true)
                    score(t("team.them"), state.theirScore, leading: true)
                }
            }
            .buttonStyle(.plain)

            Spacer(minLength: 4)
            ContractBadge(state: state)
            Spacer(minLength: 4)

            Button(action: onMenu) {
                Image(systemName: "line.3.horizontal")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(.white)
                    .frame(width: 40, height: 40)
                    .background(Circle().fill(Color.white.opacity(0.1)))
            }
            .accessibilityLabel(Text(t("menu.settings")))
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(
            LinearGradient(colors: [.black.opacity(0.3), .black.opacity(0.12)], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea(edges: .top)
        )
    }

    private func score(_ label: String, _ value: Int, leading: Bool) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .semibold, design: .rounded))
                .kerning(0.8)
                .foregroundColor(Theme.textFaint)
            Text("\(value)")
                .font(.system(size: 22, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundColor(.white)
                .contentTransition(.numericText(value: Double(value)))
                .animation(.snappy(duration: 0.5), value: value)
        }
    }
}

/// What the trick on the table is played in: trump or direction, and what it is worth.
struct ContractBadge: View {
    let state: TableState

    var body: some View {
        Group {
            if let contract = state.contract {
                HStack(spacing: 6) {
                    ContractSymbol(contract: contract, size: 17)
                    Text(L10n.shared.contract(contract))
                        .font(.system(.subheadline, design: .rounded).weight(.semibold))
                        .foregroundColor(Theme.goldSoft)
                        .lineLimit(1)
                    if let detail {
                        Text(detail)
                            .font(.system(.caption, design: .rounded).weight(.bold))
                            .foregroundColor(Theme.cardBlack)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Capsule().fill(Theme.gold))
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Capsule().fill(Theme.gold.opacity(0.16)))
                .overlay(Capsule().strokeBorder(Theme.gold.opacity(0.4), lineWidth: 1))
                .transition(.scale(scale: 0.6).combined(with: .opacity))
                .id(contract)
            } else {
                Text(t("round.n", ["n": "\(state.round + 1)"]))
                    .font(.system(.subheadline, design: .rounded))
                    .foregroundColor(Theme.textFaint)
            }
        }
        .animation(Motion.panel, value: state.contract)
    }

    /// ×3 in the Schieber and the Coiffeur; the bid, and whether it is doubled, in the Sidi.
    private var detail: String? {
        if state.mode == .sidi {
            guard let bid = state.bid else { return nil }
            return state.doubled ? "\(bid) ×2" : "\(bid)"
        }
        guard let m = state.multiplier, m > 1 else { return nil }
        return "×\(m)"
    }
}

// MARK: - Seats

/// One of the other three: name, whose turn, what they said, how many cards they hold.
struct SeatPlate: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState
    let seat: Int
    /// 1 right, 2 partner (top), 3 left.
    let side: Int

    private var active: Bool { state.toAct == seat && !state.trickComplete && state.scorecard == nil }
    private var cards: Int { state.handSizes?[seat] ?? 0 }

    var body: some View {
        VStack(spacing: 5) {
            HStack(spacing: 6) {
                Circle()
                    .fill(active ? Theme.gold : Color.clear)
                    .frame(width: 7, height: 7)
                    .modifier(Pulse(active: active))
                Text(controller.names[seat])
                    .font(.system(.footnote, design: .rounded).weight(.semibold))
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                if state.contract != nil, state.declarer == seat, state.mode != .coiffeur || state.coiffeur?.row != nil {
                    ContractSymbol(contract: state.contract, size: 11)
                        .accessibilityLabel(Text(t("seat.trumpMaker")))
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .frame(maxWidth: side == 2 ? 190 : 112)
            .fixedSize(horizontal: true, vertical: false)
            .background(Capsule().fill(active ? Theme.gold.opacity(0.22) : Color.black.opacity(0.24)))
            .overlay(Capsule().strokeBorder(active ? Theme.gold.opacity(0.5) : Theme.hairline, lineWidth: 1))

            if cards > 0 {
                HStack(spacing: -11) {
                    ForEach(0..<cards, id: \.self) { _ in
                        CardBack(width: 17)
                    }
                }
                .transition(.opacity)
            }

            ForEach(chips, id: \.self) { chip in
                Text(chip)
                    .font(.system(.caption2, design: .rounded).weight(.bold))
                    .foregroundColor(Theme.cardBlack)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Capsule().fill(Theme.gold))
                    .transition(.scale(scale: 0.4).combined(with: .opacity))
            }
        }
        .animation(Motion.panel, value: chips)
        .animation(Motion.quick, value: active)
        .animation(Motion.table, value: cards)
        .opacity(side == 2 || active ? 1 : 0.92)
    }

    /// What this seat has said that is still worth showing.
    private var chips: [String] {
        seatChips(state: state, seat: seat)
    }
}

/// Weis, Stöck, Müessi, and the seat's last call in a Sidi auction.
func seatChips(state: TableState, seat: Int) -> [String] {
    var out: [String] = []
    if state.muessiSeat == seat, state.phase == .bidding || state.hand.count >= 8 {
        out.append(t("muessi.tag"))
    }
    // Weis is called through the first trick; keep it up until the second is under way.
    if state.hand.count >= 8, let entry = state.weis.first(where: { $0.seat == seat }), entry.points > 0 {
        out.append("\(t("weis.generic")) \(entry.points)")
    }
    if state.stoeck.contains(where: { $0.seat == seat }) {
        out.append(t("weis.stoeck"))
    }
    if state.mode == .sidi, state.phase == .bidding,
       let last = state.auction.last(where: { $0.seat == seat }) {
        out.append(callLabel(last.call))
    }
    return out
}

/// A Sidi call in words: "Herz 100", "passt", "Doppelt".
func callLabel(_ call: String) -> String {
    if call == "PASS" { return t("sidi.pass") }
    if call == "DOUBLE" { return t("sidi.double") }
    guard let bid = SidiCall.bid(call) else { return call }
    return "\(L10n.shared.contract(bid.contract)) \(bid.value)"
}

/// A slow breath on the dot of whoever is thinking.
private struct Pulse: ViewModifier {
    let active: Bool
    @State private var on = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(on ? 1.55 : 1)
            .opacity(on ? 0.55 : 1)
            .onAppear { breathe(active) }
            .onChange(of: active) { _, now in breathe(now) }
    }

    private func breathe(_ start: Bool) {
        if start {
            withAnimation(.easeInOut(duration: 0.55).repeatForever(autoreverses: true)) { on = true }
        } else {
            withAnimation(.easeOut(duration: 0.2)) { on = false }
        }
    }
}

// MARK: - Status

/// One line above the hand: whose turn it is and what is being waited for.
struct StatusLine: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState
    let selected: Card?

    var body: some View {
        HStack(spacing: 8) {
            ForEach(seatChips(state: state, seat: state.seat), id: \.self) { chip in
                Text(chip)
                    .font(.system(.caption2, design: .rounded).weight(.bold))
                    .foregroundColor(Theme.cardBlack)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Capsule().fill(Theme.gold))
            }
            Text(text)
                .font(.system(.subheadline, design: .rounded).weight(mine ? .semibold : .regular))
                .foregroundColor(mine ? Theme.goldSoft : Theme.textMuted)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .id(text)
                .transition(.opacity)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 6)
        .background(Capsule().fill(Color.black.opacity(mine ? 0.34 : 0.2)))
        .animation(Motion.quick, value: text)
        .allowsHitTesting(false)
    }

    private var mine: Bool { state.myTurn && !state.trickComplete && state.scorecard == nil }

    private func name(_ seat: Int?) -> String {
        guard let seat, seat != state.seat else { return t("seat.you") }
        return controller.names[seat]
    }

    private var text: String {
        let who = ["who": name(state.toAct)]
        if state.trickComplete {
            guard let winner = state.trickWinner else { return t("status.roundComplete") }
            let side = TableMetrics.side(of: winner, from: state.seat)
            let taker = side == 0 ? t("status.youTake") : (side == 2 ? t("status.partnerTakes") : t("status.theyTake"))
            return controller.preferences.autoCollect ? taker : "\(taker) · \(t("app.tapTable"))"
        }
        switch state.phase {
        case .playing:
            if state.myTurn { return selected != nil ? t("status.tapAgain") : t("status.yourTurn") }
            return t("status.thinking", who)
        case .weis:
            return state.myTurn ? t("status.weisAsk") : t("status.weisWait")
        case .doubling:
            return state.doublePending ? t("sidi.doubleYours") : t("sidi.doubleWait")
        case .block:
            return state.myTurn ? t("coiffeur.yourBlock") : t("coiffeur.naming", who)
        case .roundOver, .gameOver:
            return t("status.roundComplete")
        case .bidding:
            switch state.mode {
            case .sidi:
                return state.myTurn ? t("sidi.yourCall") : t("sidi.calling", who)
            case .coiffeur:
                return state.myTurn ? t("coiffeur.yourChoice") : t("coiffeur.choosing", who)
            case .schieber:
                if state.myTurn {
                    if state.canShove { return t("status.yourBid") }
                    return state.muessi ? t("status.muessi") : t("status.mustChoose")
                }
                if state.muessi, let seat = state.muessiSeat, seat != state.seat {
                    return t("status.muessiOther", ["who": name(seat)])
                }
                return t("status.bidding", who)
            }
        }
    }
}

// MARK: - Weis on the table

/// The winning Weis, turned face up for everyone once the calls are in — shown in the pause
/// after the first trick, which is when a table looks at it.
struct WeisShowcase: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState

    private var shown: [TableState.WeisEntry] {
        guard state.hand.count == 8, state.trickComplete else { return [] }
        return state.weis.filter { $0.cards != nil && $0.points > 0 }
    }

    var body: some View {
        VStack(spacing: 6) {
            ForEach(shown, id: \.seat) { entry in
                HStack(spacing: 8) {
                    Text(entry.seat == state.seat ? t("seat.you") : controller.names[entry.seat])
                        .font(.system(.caption, design: .rounded).weight(.semibold))
                        .foregroundColor(.white)
                    HStack(spacing: -14) {
                        ForEach(entry.cards ?? []) { card in
                            CardView(card: card, width: 34)
                        }
                    }
                    Text("\(entry.points)")
                        .font(.system(.caption, design: .rounded).weight(.heavy))
                        .foregroundColor(Theme.gold)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Capsule().fill(Color.black.opacity(0.45)))
                .transition(.scale(scale: 0.7).combined(with: .opacity))
            }
        }
        .animation(Motion.panel, value: shown.map(\.seat))
        .allowsHitTesting(false)
    }
}
