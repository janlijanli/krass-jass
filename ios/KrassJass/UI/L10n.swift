import Foundation
import SwiftUI

/// The table's wording, in English, German, French and Italian.
///
/// The strings are the web UI's own (`web/static/i18n.js`), exported to `strings.json` by
/// `ios/scripts/make-strings.mjs` — one source for both, so the app and the page say the same
/// thing. Jass vocabulary (Weis, Stöck, Schieben, Obenabe, Undenufe) is not translated there
/// and is not here. The few strings only the app needs are in `appOnly` below.
final class L10n: ObservableObject {
    static let shared = L10n()

    private struct Bundle_: Decodable {
        let languages: [String]
        let names: [String: String]
        let strings: [String: [String: String]]
    }

    @Published private(set) var language = "en"
    private(set) var languages = ["en", "de", "fr", "it"]
    private(set) var languageNames: [String: String] = [:]
    private var strings: [String: [String: String]] = [:]

    private init() {
        if let url = Bundle.main.url(forResource: "strings", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let bundle = try? JSONDecoder().decode(Bundle_.self, from: data) {
            languages = bundle.languages
            languageNames = bundle.names
            strings = bundle.strings
        }
        language = deviceLanguage()
    }

    private func deviceLanguage() -> String {
        for preferred in Locale.preferredLanguages {
            let code = String(preferred.prefix(2)).lowercased()
            // Swiss German has no translation of its own; it reads the German one.
            if code == "gs" { return "de" }
            if languages.contains(code) { return code }
        }
        return "en"
    }

    /// nil follows the device.
    func setLanguage(_ code: String?) {
        let next = code.flatMap { languages.contains($0) ? $0 : nil } ?? deviceLanguage()
        if next != language { language = next }
    }

    /// Look up a string, filling `{placeholders}`. Falls back to English, then to the key.
    func text(_ key: String, _ params: [String: String] = [:]) -> String {
        var text = strings[language]?[key]
            ?? L10n.appOnly[language]?[key]
            ?? strings["en"]?[key]
            ?? L10n.appOnly["en"]?[key]
            ?? key
        for (name, value) in params {
            text = text.replacingOccurrences(of: "{\(name)}", with: value)
        }
        return text
    }

    func contract(_ name: String?) -> String {
        guard let name else { return "" }
        return text("contract.\(name)")
    }

    /// A Coiffeur row: the Chance and the extra rows by their own names, the rest as contracts.
    func row(_ name: String) -> String {
        if name == "CHANCE" || GameSettings.extraRows.contains(name) {
            return text("coiffeur.row.\(name)")
        }
        return contract(name)
    }

    func mode(_ mode: TableState.Mode) -> String { text("splash.mode.\(mode.rawValue)") }

    /// Strings the web UI has no use for.
    private static let appOnly: [String: [String: String]] = [
        "en": [
            "app.haptics": "Haptic feedback",
            "app.autoCollect": "Clear tricks automatically",
            "app.autoCollectNote": "Off: a finished trick stays until you tap the table.",
            "app.tempo": "Pace of the bots",
            "app.tempo.relaxed": "Relaxed",
            "app.tempo.normal": "Normal",
            "app.tempo.brisk": "Brisk",
            "app.languageAuto": "Automatic",
            "app.app": "App",
            "app.tapTable": "Tap the table to continue",
            "app.rulesNext": "Rule changes apply from the next game.",
            "app.won": "You win!",
            "app.lost": "They win.",
            "app.loading": "Shuffling…",
            "app.strokes": "Match strokes",
        ],
        "de": [
            "app.haptics": "Haptisches Feedback",
            "app.autoCollect": "Stiche automatisch abräumen",
            "app.autoCollectNote": "Aus: Ein fertiger Stich bleibt liegen, bis du den Tisch antippst.",
            "app.tempo": "Tempo der Bots",
            "app.tempo.relaxed": "Gemütlich",
            "app.tempo.normal": "Normal",
            "app.tempo.brisk": "Zügig",
            "app.languageAuto": "Automatisch",
            "app.app": "App",
            "app.tapTable": "Tisch antippen zum Weiterspielen",
            "app.rulesNext": "Regeländerungen gelten ab dem nächsten Spiel.",
            "app.won": "Gewonnen!",
            "app.lost": "Sie gewinnen.",
            "app.loading": "Es wird gemischt…",
            "app.strokes": "Matchstriche",
        ],
        "fr": [
            "app.haptics": "Retour haptique",
            "app.autoCollect": "Ramasser les plis automatiquement",
            "app.autoCollectNote": "Désactivé : un pli terminé reste jusqu'à ce que tu touches la table.",
            "app.tempo": "Rythme des bots",
            "app.tempo.relaxed": "Tranquille",
            "app.tempo.normal": "Normal",
            "app.tempo.brisk": "Rapide",
            "app.languageAuto": "Automatique",
            "app.app": "App",
            "app.tapTable": "Touche la table pour continuer",
            "app.rulesNext": "Les changements de règles valent dès la prochaine partie.",
            "app.won": "Gagné !",
            "app.lost": "Ils gagnent.",
            "app.loading": "On mélange…",
            "app.strokes": "Traits de match",
        ],
        "it": [
            "app.haptics": "Feedback aptico",
            "app.autoCollect": "Raccogli le prese automaticamente",
            "app.autoCollectNote": "Spento: una presa finita resta finché tocchi il tavolo.",
            "app.tempo": "Ritmo dei bot",
            "app.tempo.relaxed": "Tranquillo",
            "app.tempo.normal": "Normale",
            "app.tempo.brisk": "Veloce",
            "app.languageAuto": "Automatico",
            "app.app": "App",
            "app.tapTable": "Tocca il tavolo per continuare",
            "app.rulesNext": "Le modifiche alle regole valgono dalla prossima partita.",
            "app.won": "Vinto!",
            "app.lost": "Vincono loro.",
            "app.loading": "Si mescola…",
            "app.strokes": "Tratti di match",
        ],
    ]
}

/// `t("status.yourTurn")` — the short form the views use.
func t(_ key: String, _ params: [String: String] = [:]) -> String {
    L10n.shared.text(key, params)
}
