import SwiftUI

/// One line of a scorecard: a label and the two teams' numbers.
private struct ScoreLine: Identifiable {
    enum Style { case plain, faded, note, subtotal, total }
    let id = UUID()
    let label: String
    var us = ""
    var them = ""
    var style: Style = .plain
}

/// The round's arithmetic, laid over the table when the last trick has been cleared.
struct ScorecardOverlay: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState
    @State private var shown = false

    var body: some View {
        ZStack {
            Color.black.opacity(0.5)
                .ignoresSafeArea()
            if let card = state.scorecard {
                VStack(spacing: 14) {
                    header(card)
                    VStack(spacing: 3) {
                        columnHeads
                        ForEach(lines(card)) { line in
                            row(line)
                        }
                    }
                    if state.isOver {
                        Text(state.ourScore > state.theirScore ? t("app.won") : t("app.lost"))
                            .font(.system(.title2, design: .rounded).weight(.heavy))
                            .foregroundColor(Theme.gold)
                            .scaleEffect(shown ? 1 : 0.6)
                    }
                    Button(state.isOver ? t("score.newGame") : t("score.nextRound")) {
                        Haptics.confirm()
                        if state.isOver {
                            Task { await controller.newGame() }
                        } else {
                            controller.nextRound()
                        }
                    }
                    .buttonStyle(.tablePrimary)
                }
                .padding(20)
                .frame(maxWidth: 420)
                .panel(radius: 24)
                .padding(.horizontal, 18)
                .scaleEffect(shown ? 1 : 0.92)
                .opacity(shown ? 1 : 0)
            }
        }
        .onAppear {
            withAnimation(Motion.panel.delay(0.05)) { shown = true }
        }
    }

    private func header(_ card: TableState.Scorecard) -> some View {
        VStack(spacing: 4) {
            Text(state.isOver ? t("score.final") : t("round.n", ["n": "\(card.round + 1)"]))
                .font(.system(.title3, design: .rounded).weight(.bold))
                .foregroundColor(.white)
            HStack(spacing: 6) {
                if let row = card.row {
                    Text(L10n.shared.row(row))
                        .foregroundColor(Theme.goldSoft)
                    Text("·").foregroundColor(Theme.textFaint)
                }
                if !card.contract.isEmpty {
                    ContractSymbol(contract: card.contract, size: 14)
                    Text(L10n.shared.contract(card.contract))
                        .foregroundColor(Theme.goldSoft)
                }
            }
            .font(.system(.subheadline, design: .rounded).weight(.semibold))
        }
    }

    private var columnHeads: some View {
        HStack {
            Spacer()
            Text(t("team.us")).frame(width: 64, alignment: .trailing)
            Text(t("team.them")).frame(width: 64, alignment: .trailing)
        }
        .font(.system(.caption, design: .rounded).weight(.semibold))
        .foregroundColor(Theme.textFaint)
        .padding(.horizontal, 10)
    }

    private func row(_ line: ScoreLine) -> some View {
        let strong = line.style == .total || line.style == .subtotal
        let textStyle: Font.TextStyle = line.style == .total ? .title3 : (line.style == .note ? .caption : .body)
        let colour: Color = line.style == .note ? Theme.textFaint : (line.style == .total ? Theme.gold : Color.white)
        let fill: Color = line.style == .total ? Color.white.opacity(0.07) : Color.clear
        return HStack {
            Text(line.label)
                .frame(maxWidth: .infinity, alignment: .leading)
                .lineLimit(2)
                .minimumScaleFactor(0.8)
            Text(line.us).monospacedDigit().frame(width: 64, alignment: .trailing)
            Text(line.them).monospacedDigit().frame(width: 64, alignment: .trailing)
        }
        .font(.system(textStyle, design: .rounded).weight(strong ? .bold : .regular))
        .foregroundColor(colour)
        .opacity(line.style == .faded ? 0.4 : 1)
        .padding(.horizontal, 10)
        .padding(.vertical, line.style == .total ? 8 : 4)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(fill)
        )
    }

    // MARK: The lines, per game

    private func lines(_ card: TableState.Scorecard) -> [ScoreLine] {
        let mine = state.seat % 2
        func pick(_ pair: [Int]) -> (Int, Int) { (pair[mine], pair[1 - mine]) }
        // Keep empty lines visible but faded rather than hiding them — a row that disappears
        // makes the arithmetic impossible to follow.
        func points(_ label: String, _ pair: [Int]) -> ScoreLine {
            let (us, them) = pick(pair)
            return ScoreLine(
                label: label,
                us: us == 0 ? "—" : "\(us)",
                them: them == 0 ? "—" : "\(them)",
                style: us == 0 && them == 0 ? .faded : .plain
            )
        }
        func sum(_ label: String, _ pair: [Int], _ style: ScoreLine.Style) -> ScoreLine {
            let (us, them) = pick(pair)
            return ScoreLine(label: label, us: "\(us)", them: "\(them)", style: style)
        }

        var out: [ScoreLine] = [
            points(t("score.tricks"), card.trickPoints),
            points(t("score.lastTrick"), card.lastTrick),
        ]
        let cardPoints = card.trickPoints[0] + card.trickPoints[1] + card.lastTrick[0] + card.lastTrick[1]

        if let bid = card.bid {
            // Sidi Barrani: the bid is what the round turns on.
            out.append(points(t("score.match"), card.match))
            out.append(ScoreLine(label: t("score.cardPoints", ["n": "\(cardPoints)"]), style: .note))
            let x = card.doubled == true ? " ×2" : ""
            let verdict = t(card.made == true ? "sidi.made" : "sidi.failed", ["bid": "\(bid)", "x": x])
            out.append(ScoreLine(label: verdict, style: .note))
            if let bonus = card.bonus, bonus.contains(where: { $0 != 0 }) {
                out.append(points(t("sidi.double"), bonus))
            }
        } else if let row = card.row {
            // Coiffeur: card points, written into the row (in tens), times the row's multiplier.
            out.append(points(t("score.match"), card.match))
            out.append(ScoreLine(label: t("score.cardPoints", ["n": "\(cardPoints)"]), style: .note))
            if let written = card.written {
                let key = state.coiffeur?.tens == true ? "coiffeur.writtenTens" : "coiffeur.written"
                out.append(sum(t(key, ["row": L10n.shared.row(row)]), written, .subtotal))
            }
            if let m = card.multiplier {
                out.append(ScoreLine(label: "× \(m)", style: .note))
            }
            if let strokes = card.strokes, strokes.contains(where: { $0 != 0 }) {
                out.append(points(t("app.strokes"), strokes))
            }
            if state.coiffeur?.schedule?.misere == true {
                out.append(ScoreLine(label: t("coiffeur.misereNote"), style: .note))
            }
        } else {
            let weis = card.weis ?? [0, 0]
            let stoeck = card.stoeck ?? [0, 0]
            out.append(points(t("score.weis"), weis))
            out.append(points(t("score.stoeck"), stoeck))
            out.append(points(t("score.match"), card.match))
            // Tricks + last trick is always 157 between the two teams. Say so: it is the
            // number that tells a player whether they had a good round.
            out.append(ScoreLine(label: t("score.cardPoints", ["n": "\(cardPoints)"]), style: .note))
            if let m = card.multiplier, m > 1 {
                // Show the raw subtotal and the multiplication explicitly. Without it the rows
                // sum to one number and "This round" shows another, which reads as an error.
                var raw = [0, 0]
                for pair in [card.trickPoints, card.lastTrick, weis, stoeck, card.match] {
                    raw[0] += pair[0]
                    raw[1] += pair[1]
                }
                out.append(sum(t("score.subtotal"), raw, .subtotal))
                let label = t("score.multiplier", ["n": "\(m)", "contract": L10n.shared.contract(card.contract)])
                out.append(ScoreLine(label: label, style: .note))
            }
        }
        out.append(sum(t("score.thisRound"), card.roundTotal, .subtotal))
        out.append(sum(t("score.total"), card.scores, .total))
        return out
    }
}

/// The Jasstafel: the game so far, round by round — and the Coiffeur's sheet.
struct BoardSheet: View {
    @EnvironmentObject private var controller: GameController
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    if let state = controller.state {
                        if let coiffeur = state.coiffeur {
                            if let schedule = coiffeur.schedule {
                                ScheduleStrip(schedule: schedule)
                            }
                            CoiffeurSheet(state: state, coiffeur: coiffeur)
                        } else {
                            rounds(state)
                        }
                    }
                }
                .padding(18)
            }
            .background(Theme.feltDeep.ignoresSafeArea())
            .navigationTitle(t("tafel.title"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(t("menu.close")) { dismiss() }
                        .tint(Theme.gold)
                }
            }
            .toolbarBackground(Theme.chrome, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    @ViewBuilder
    private func rounds(_ state: TableState) -> some View {
        let mine = state.seat % 2
        Text(t("tafel.playingTo", ["n": "\(state.target)"]))
            .font(.system(.subheadline, design: .rounded))
            .foregroundColor(Theme.textFaint)
        if controller.rounds.isEmpty {
            Text(t("tafel.empty"))
                .font(.system(.body, design: .rounded))
                .foregroundColor(Theme.textMuted)
                .multilineTextAlignment(.center)
                .padding(.top, 30)
        } else {
            VStack(spacing: 4) {
                ForEach(Array(controller.rounds.enumerated()), id: \.offset) { _, card in
                    HStack(spacing: 8) {
                        Text("\(card.round + 1)")
                            .foregroundColor(Theme.textFaint)
                            .frame(width: 26, alignment: .leading)
                        ContractSymbol(contract: card.contract, size: 14)
                        Text(L10n.shared.contract(card.contract))
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text("+\(card.roundTotal[mine])").monospacedDigit().frame(width: 60, alignment: .trailing)
                        Text("+\(card.roundTotal[1 - mine])").monospacedDigit().frame(width: 60, alignment: .trailing)
                    }
                    .font(.system(.callout, design: .rounded))
                    .foregroundColor(.white)
                    .padding(.vertical, 6)
                    .padding(.horizontal, 10)
                    .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color.white.opacity(0.05)))
                }
                HStack {
                    Text(t("score.total")).frame(maxWidth: .infinity, alignment: .leading)
                    Text("\(state.ourScore)").monospacedDigit().frame(width: 60, alignment: .trailing)
                    Text("\(state.theirScore)").monospacedDigit().frame(width: 60, alignment: .trailing)
                }
                .font(.system(.title3, design: .rounded).weight(.bold))
                .foregroundColor(Theme.gold)
                .padding(.vertical, 8)
                .padding(.horizontal, 10)
            }
        }
    }
}
