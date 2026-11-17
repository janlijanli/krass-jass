import SwiftUI

@main
struct KrassJassApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}

/// Start screen over the table; the table over the engine.
struct RootView: View {
    @StateObject private var controller = GameController()
    @ObservedObject private var l10n = L10n.shared
    @State private var showSplash = true
    @State private var showMenu = false

    var body: some View {
        ZStack {
            if showSplash {
                SplashView(
                    onContinue: { start(mode: nil) },
                    onNew: { mode in start(mode: mode) }
                )
                .transition(.opacity)
                .zIndex(1)
            } else {
                TableScreen(showMenu: $showMenu)
                    .transition(.opacity)
            }
        }
        // The strings are read through a global, so a change of language rebuilds the tree
        // rather than threading an observed object through every view that shows a word.
        .id(l10n.language)
        .environmentObject(controller)
        .sheet(isPresented: $showMenu) {
            MenuSheet()
                .environmentObject(controller)
        }
        .preferredColorScheme(.dark)
        .statusBarHidden(false)
        #if DEBUG
        .onAppear(perform: launchArguments)
        #endif
    }

    #if DEBUG
    /// `-kj.autostart sidi` skips the start screen; `-kj.autoplay 12` plays the player's first
    /// twelve decisions. For screenshots in CI; neither exists in a release build.
    private func launchArguments() {
        let defaults = UserDefaults.standard
        controller.demo(moves: defaults.integer(forKey: "kj.autoplay"))
        if let mode = defaults.string(forKey: "kj.autostart").flatMap(TableState.Mode.init(rawValue:)) {
            start(mode: mode)
        }
    }
    #endif

    /// nil continues the saved game; a mode deals a new one.
    private func start(mode: TableState.Mode?) {
        withAnimation(.easeInOut(duration: 0.35)) { showSplash = false }
        Task {
            if let mode {
                await controller.newGame(mode: mode)
            } else if await controller.resume() == false {
                await controller.newGame()
            }
        }
    }
}
