import SwiftUI

/// Settings: the rules of the next game, and how the app behaves around it.
struct MenuSheet: View {
    @EnvironmentObject private var controller: GameController
    @ObservedObject private var l10n = L10n.shared
    @Environment(\.dismiss) private var dismiss
    @State private var confirmNewGame = false
    /// The game that was being played when the picker was changed, so that saying no puts the
    /// picker back rather than leaving the menu describing a game nobody is playing.
    @State private var modeBefore: TableState.Mode?

    private static let targets = [1000, 1500, 2000, 2500]
    private static let contractKeys = ["DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE"]

    var body: some View {
        NavigationStack {
            Form {
                gameSection
                switch controller.settings.mode {
                case .schieber: schieberSection
                case .sidi: sidiSection
                case .coiffeur: coiffeurSection
                }
                discardSection
                Section {
                    Button(t("menu.start")) {
                        if controller.state != nil, controller.state?.isOver == false {
                            confirmNewGame = true
                        } else {
                            startNewGame()
                        }
                    }
                    .font(.system(.body, design: .rounded).weight(.semibold))
                    .foregroundColor(Theme.gold)
                } footer: {
                    Text(t("app.rulesNext"))
                }
                appSection
            }
            .scrollContentBackground(.hidden)
            .background(Theme.feltDeep.ignoresSafeArea())
            .navigationTitle(t("menu.settings"))
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
            // An alert rather than a confirmation dialog: iOS draws the dialog as a compact
            // sheet that shows the destructive button alone and leaves cancelling to a tap
            // outside it. Throwing a game away deserves a visible way to say no.
            .alert(t("menu.newGameConfirm"), isPresented: $confirmNewGame) {
                Button(t("menu.start"), role: .destructive) { startNewGame() }
                Button(t("menu.cancel"), role: .cancel) { keepPlaying() }
            }
        }
        .tint(Theme.gold)
        .preferredColorScheme(.dark)
    }

    private func startNewGame() {
        Haptics.confirm()
        modeBefore = nil
        dismiss()
        Task { await controller.newGame() }
    }

    /// A game in progress that a new one would throw away.
    private var gameRunning: Bool { controller.state.map { !$0.isOver } ?? false }

    /// Saying no to the question the picker asked: back to the game actually on the table.
    private func keepPlaying() {
        guard let mode = modeBefore else { return }
        controller.settings.mode = mode
        controller.settings.target = GameSettings.usualTarget(mode)
        modeBefore = nil
    }

    // MARK: Rules

    private var gameSection: some View {
        Section {
            Picker(t("menu.mode"), selection: modeBinding) {
                ForEach(TableState.Mode.allCases) { mode in
                    Text(l10n.mode(mode)).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            if controller.settings.mode != .coiffeur {
                Picker(t("menu.playTo"), selection: $controller.settings.target) {
                    ForEach(MenuSheet.targets, id: \.self) { value in
                        Text("\(value)").tag(value)
                    }
                }
            }
        } header: {
            Text(t("menu.gameSettings"))
        } footer: {
            switch controller.settings.mode {
            case .schieber: Text(t("splash.note.schieber"))
            case .sidi: Text(t("menu.sidiNote"))
            case .coiffeur: Text(t("menu.coiffeurNote"))
            }
        }
    }

    /// Changing the game also moves the target to what that game is usually played to.
    ///
    /// Every other setting here is for the next game — a multiplier or Weis can wait, and the
    /// footer says so. The game itself cannot: a Schieber on the table does not become a
    /// Coiffeur, so leaving the picker on one game while another is being played says something
    /// false about the table. So this one asks, and a no puts the picker back.
    private var modeBinding: Binding<TableState.Mode> {
        Binding(
            get: { controller.settings.mode },
            set: { mode in
                guard mode != controller.settings.mode else { return }
                let previous = controller.settings.mode
                controller.settings.mode = mode
                controller.settings.target = GameSettings.usualTarget(mode)
                if gameRunning {
                    modeBefore = previous
                    confirmNewGame = true
                }
            }
        )
    }

    private var schieberSection: some View {
        Group {
            Section {
                Toggle(t("menu.weis"), isOn: $controller.settings.weis)
            } footer: {
                Text(t("menu.stoeckNote"))
            }
            Section(t("menu.multipliers")) {
                ForEach(Array(MenuSheet.contractKeys.enumerated()), id: \.offset) { index, key in
                    Stepper(value: multiplierBinding(index), in: 1...7) {
                        HStack(spacing: 10) {
                            ContractSymbol(contract: key, size: 18)
                            Text(l10n.contract(key))
                            Spacer()
                            Text("×\(controller.settings.multipliers[index])")
                                .monospacedDigit()
                                .foregroundColor(Theme.gold)
                        }
                    }
                }
            }
        }
    }

    private func multiplierBinding(_ index: Int) -> Binding<Int> {
        Binding(
            get: { controller.settings.multipliers[index] },
            set: { controller.settings.multipliers[index] = $0 }
        )
    }

    private var sidiSection: some View {
        Section {
            Picker(t("menu.bidPartner"), selection: $controller.settings.bidPartner) {
                Text(t("menu.bidCount")).tag(GameSettings.BidStyle.count)
                Text(t("menu.bidFeel")).tag(GameSettings.BidStyle.feel)
            }
            Picker(t("menu.bidOpponents"), selection: $controller.settings.bidOpponents) {
                Text(t("menu.bidCount")).tag(GameSettings.BidStyle.count)
                Text(t("menu.bidFeel")).tag(GameSettings.BidStyle.feel)
            }
        } header: {
            Text(t("menu.bidStyle"))
        } footer: {
            Text(t("menu.bidStyleNote"))
        }
    }

    private var coiffeurSection: some View {
        Section {
            ForEach(GameSettings.extraRows, id: \.self) { row in
                Toggle(l10n.row(row), isOn: rowBinding(row))
            }
        } header: {
            Text(t("menu.coiffeurRows"))
        } footer: {
            Text(t("menu.coiffeurRowsNote"))
        }
    }

    private func rowBinding(_ row: String) -> Binding<Bool> {
        Binding(
            get: { controller.settings.rows.contains(row) },
            set: { on in
                var rows = controller.settings.rows.filter { $0 != row }
                if on { rows.append(row) }
                // Kept in the sheet's own order, whatever order they were ticked in.
                controller.settings.rows = GameSettings.extraRows.filter { rows.contains($0) }
            }
        )
    }

    private var discardSection: some View {
        Section {
            Picker(t("menu.discard"), selection: $controller.settings.discard) {
                Text(t("menu.discardWeakest")).tag(GameSettings.Discard.weakest)
                Text(t("menu.discardSister")).tag(GameSettings.Discard.sister)
            }
        } footer: {
            Text(t("menu.discardNote"))
        }
    }

    // MARK: App

    private var appSection: some View {
        Group {
            Section {
                Toggle(t("menu.advice"), isOn: $controller.preferences.advice)
            } header: {
                Text(t("app.app"))
            } footer: {
                Text(t("menu.adviceNote"))
            }
            Section {
                Toggle(t("app.haptics"), isOn: $controller.preferences.haptics)
                Toggle(t("app.autoCollect"), isOn: $controller.preferences.autoCollect)
                Picker(t("app.tempo"), selection: $controller.preferences.tempo) {
                    ForEach(AppPreferences.Tempo.allCases) { tempo in
                        Text(t("app.tempo.\(tempo.rawValue)")).tag(tempo)
                    }
                }
                Picker(t("menu.language"), selection: $controller.preferences.language) {
                    Text(t("app.languageAuto")).tag(String?.none)
                    ForEach(l10n.languages, id: \.self) { code in
                        Text(l10n.languageNames[code] ?? code).tag(String?.some(code))
                    }
                }
            } footer: {
                Text(t("app.autoCollectNote"))
            }
        }
    }
}
