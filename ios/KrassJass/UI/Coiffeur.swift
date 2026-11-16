import SwiftUI

/// The Coiffeur's games as the engine names them on the wire (`krass_jass/schedule.py`):
/// TUTTI, MITTE, SLALOM_OBENABE, GUSCHTI4_UNDENUFE, TRIO_HEARTS, MISERE_UNDENUFE — and a
/// choice into the Chance row carries "/CHANCE".
enum CoiffeurWire {
    static func isGame(_ name: String) -> Bool {
        if name == "TUTTI" || name == "MITTE" { return true }
        return ["SLALOM_", "GUSCHTI_", "GUSCHTI4_", "TRIO_", "MISERE_"].contains { name.hasPrefix($0) }
    }

    /// The sheet row a game belongs to: "GUSCHTI4_OBENABE" → "GUSCHTI".
    static func gameRow(_ name: String) -> String {
        var kind = String(name.split(separator: "_").first ?? "")
        if kind.hasSuffix("4") { kind.removeLast() }
        return kind
    }

    static func isExtraRow(_ row: String) -> Bool { GameSettings.extraRows.contains(row) }

    /// May something be written into `row` now?
    static func choosable(_ row: String, legal: [String]) -> Bool {
        if row == "CHANCE" { return legal.contains { $0.hasSuffix("/CHANCE") } }
        if isExtraRow(row) { return !offered(for: row, legal: legal).isEmpty }
        return legal.contains(row)
    }

    /// What may go into an open row: any game for the Chance, or an extra row's own games.
    static func offered(for row: String, legal: [String]) -> [String] {
        if row == "CHANCE" { return legal.filter { $0.hasSuffix("/CHANCE") } }
        return legal.filter { !$0.contains("/") && isGame($0) && gameRow($0) == row }
    }
}

/// A game shown as the orders it runs through: pips for trump, arrows for Obenabe and
/// Undenufe, "?" for a trick whose order is not known yet.
struct GameLabel: View {
    /// Wire name without the "/CHANCE" part.
    let name: String
    var onDark = false

    private var ink: Color { onDark ? .white : Theme.cardBlack }

    var body: some View {
        let parts = name.split(separator: "_").map(String.init)
        let kind = parts.first ?? name
        let first = parts.count > 1 ? parts[1] : nil
        HStack(spacing: 4) {
            switch kind {
            case "TUTTI":
                symbol(nil)
                word(t("coiffeur.row.TUTTI"))
            case "MITTE":
                symbol("MITTE")
                word(t("coiffeur.row.MITTE"))
            case "SLALOM":
                symbol(first)
                symbol(flip(first))
                symbol(first)
                word("…")
            case "GUSCHTI", "GUSCHTI4":
                word(kind == "GUSCHTI" ? "5" : "4")
                symbol(first)
                word(kind == "GUSCHTI" ? "4" : "5")
                symbol(flip(first))
            case "TRIO":
                word("3")
                symbol(first)
                word("+ ? + ?")
            case "MISERE":
                symbol(first)
                word(t("coiffeur.row.MISERE"))
            default:
                symbol(name)
                word(L10n.shared.contract(name))
            }
        }
    }

    private func flip(_ contract: String?) -> String { contract == "OBENABE" ? "UNDENUFE" : "OBENABE" }

    private func symbol(_ contract: String?) -> some View {
        ContractSymbol(contract: contract, size: 15, onDark: onDark)
    }

    private func word(_ text: String) -> some View {
        Text(text)
            .font(.system(.caption, design: .rounded).weight(.semibold))
            .foregroundColor(ink)
            .lineLimit(1)
    }
}

/// The sheet: row, multiplier, us, them. With `pick`, a row that may be written is a button.
@MainActor
struct CoiffeurSheet: View {
    let state: TableState
    let coiffeur: TableState.Coiffeur
    var open: String?
    var pick: ((String) -> Void)?

    /// Cheapest row first, the Chance (×13) last: the order a player weighs them in.
    private var order: [Int] {
        coiffeur.rows.indices.sorted {
            (coiffeur.multipliers[$0], $0) < (coiffeur.multipliers[$1], $1)
        }
    }

    private var mine: Int { state.seat % 2 }

    private func total(_ team: Int) -> Int {
        var sum = 0
        for i in coiffeur.rows.indices {
            if let value = coiffeur.sheet[team][i] { sum += value * coiffeur.multipliers[i] }
        }
        if let stroke = coiffeur.stroke { sum += coiffeur.strokes[team] * stroke }
        return sum
    }

    var body: some View {
        VStack(spacing: 2) {
            line(label: Text(""), mult: "×", us: t("team.us"), them: t("team.them"), style: .header)
            ForEach(order, id: \.self) { i in
                row(i)
            }
            if let stroke = coiffeur.stroke {
                line(
                    label: Text(t("score.match")),
                    mult: "| = \(stroke)",
                    us: strokes(mine),
                    them: strokes(1 - mine),
                    style: .plain
                )
            }
            line(label: Text(t("score.total")), mult: "", us: "\(total(mine))", them: "\(total(1 - mine))", style: .total)
        }
    }

    private func strokes(_ team: Int) -> String {
        let n = coiffeur.strokes[team]
        return n > 0 ? String(repeating: "|", count: n) : "·"
    }

    private enum LineStyle { case header, plain, total, choosable, current, open }

    @ViewBuilder
    private func row(_ i: Int) -> some View {
        let name = coiffeur.rows[i]
        let canPick = pick != nil && CoiffeurWire.choosable(name, legal: coiffeur.legal)
        let style: LineStyle = open == name ? .open : (coiffeur.row == name ? .current : (canPick ? .choosable : .plain))
        let content = line(
            label: rowLabel(name),
            mult: "\(coiffeur.multipliers[i])",
            us: cell(mine, i),
            them: cell(1 - mine, i),
            style: style
        )
        if canPick, let pick {
            Button {
                Haptics.select()
                pick(name)
            } label: {
                content
            }
            .buttonStyle(PressStyle())
        } else {
            content.opacity(pick != nil ? 0.5 : 1)
        }
    }

    private func cell(_ team: Int, _ i: Int) -> String {
        coiffeur.sheet[team][i].map { "\($0)" } ?? "·"
    }

    private func rowLabel(_ name: String) -> Text {
        Text(L10n.shared.row(name))
    }

    private func line(label: Text, mult: String, us: String, them: String, style: LineStyle) -> some View {
        let strong = style == .total || style == .header
        return HStack(spacing: 6) {
            label
                .font(.system(.footnote, design: .rounded).weight(strong ? .bold : .medium))
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(mult)
                .font(.system(.caption, design: .rounded))
                .foregroundColor(Theme.textFaint)
                .frame(width: 44, alignment: .center)
            Text(us)
                .monospacedDigit()
                .frame(width: 52, alignment: .trailing)
            Text(them)
                .monospacedDigit()
                .frame(width: 52, alignment: .trailing)
        }
        .font(.system(.footnote, design: .rounded).weight(strong ? .bold : .regular))
        .foregroundColor(style == .header ? Theme.textFaint : .white)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(background(style))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .strokeBorder(style == .choosable ? Color.white.opacity(0.16) : .clear, lineWidth: 1)
        )
        .contentShape(Rectangle())
    }

    private func background(_ style: LineStyle) -> Color {
        switch style {
        case .header, .plain: return .clear
        case .total: return Color.white.opacity(0.06)
        case .choosable: return Color.white.opacity(0.07)
        case .current: return Theme.gold.opacity(0.14)
        case .open: return Theme.gold.opacity(0.26)
        }
    }
}

/// Pick a row of the sheet — and, for the Chance and the extra rows, the game to play in it.
struct CoiffeurPanel: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState
    @State private var open: String?

    var body: some View {
        if let coiffeur = state.coiffeur, !coiffeur.legal.isEmpty {
            let canShove = coiffeur.legal.contains("SHOVE")
            VStack(spacing: 10) {
                Text(prompt(canShove: canShove))
                    .font(.system(.headline, design: .rounded))
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)

                ScrollView(showsIndicators: false) {
                    CoiffeurSheet(state: state, coiffeur: coiffeur, open: open) { row in
                        pick(row)
                    }
                }

                if let open {
                    let offered = CoiffeurWire.offered(for: open, legal: coiffeur.legal)
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 104), spacing: 8)], spacing: 8) {
                        ForEach(offered, id: \.self) { choice in
                            Button {
                                Haptics.confirm()
                                controller.choose(choice)
                            } label: {
                                GameLabel(name: String(choice.split(separator: "/").first ?? ""))
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 9)
                                    .padding(.horizontal, 6)
                                    .background(
                                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                                            .fill(LinearGradient(colors: [.white, Theme.paperShade], startPoint: .top, endPoint: .bottom))
                                    )
                            }
                            .buttonStyle(PressStyle())
                        }
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                if canShove {
                    Button(t("bid.shove")) {
                        Haptics.confirm()
                        controller.choose("SHOVE")
                    }
                    .buttonStyle(.tablePrimary)
                }
            }
            .padding(14)
            .panel()
            .onChange(of: coiffeur.shoves) { _, _ in open = nil }
        }
    }

    private func pick(_ row: String) {
        if row == "TUTTI" || row == "MITTE" {
            controller.choose(row)                // one game: nothing to pick
        } else if row == "CHANCE" || CoiffeurWire.isExtraRow(row) {
            withAnimation(Motion.panel) { open = open == row ? nil : row }
        } else {
            controller.choose(row)
        }
    }

    private func prompt(canShove: Bool) -> String {
        guard let open else {
            if canShove { return t("coiffeur.prompt") }
            return t(state.muss ? "coiffeur.muessi" : "coiffeur.mustChoose")
        }
        let row = ["row": L10n.shared.row(open)]
        if open == "TRIO" { return t("coiffeur.pickFirstBlock") }
        if open == "CHANCE" { return t("coiffeur.pickAny", row) }
        if CoiffeurWire.isExtraRow(open) { return t("coiffeur.pickGame", row) }
        return t("coiffeur.pickContract", row)
    }
}

/// 3×3: whoever leads trick 4 or 7 names the next block, from the engine's options.
struct BlockPanel: View {
    @EnvironmentObject private var controller: GameController
    let state: TableState
    let blocks: [String]

    var body: some View {
        let at = state.coiffeur?.schedule?.at ?? 0
        VStack(spacing: 12) {
            Text(t("coiffeur.pickBlock", ["n": "\(at + 1)", "m": "\(at + 3)"]))
                .font(.system(.headline, design: .rounded))
                .foregroundColor(.white)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 90), spacing: 10)], spacing: 10) {
                ForEach(blocks, id: \.self) { contract in
                    ContractButton(contract: contract) {
                        controller.block(contract)
                    }
                }
            }
        }
        .padding(16)
        .panel()
    }
}

/// The nine tricks of the game being played, the one on the table marked.
struct ScheduleStrip: View {
    let schedule: TableState.Schedule

    var body: some View {
        HStack(spacing: 3) {
            ForEach(Array(schedule.tricks.enumerated()), id: \.offset) { index, contract in
                ContractSymbol(contract: contract, size: 12)
                    .frame(width: 20, height: 20)
                    .background(
                        Circle().fill(index == schedule.at ? Theme.gold.opacity(0.35) : Color.black.opacity(0.2))
                    )
                    .opacity(index < schedule.at ? 0.4 : 1)
            }
        }
    }
}
