/* Language.
 *
 * Picks from the browser and lets the player override it; the choice is remembered per
 * browser. English, German, French, Italian — the three Swiss national languages the game is
 * played in, plus English.
 *
 * Jass vocabulary is deliberately *not* translated. Weis, Stöck, Schieben, Obenabe and
 * Undenufe are the names of the things in every language the game is played in — a French
 * speaker in Fribourg says "Obenabe", not "tout en haut". Translating them would be a worse
 * French page, not a better one. Suit names are translated, because those are ordinary words.
 *
 * `t(key)` returns a string; `t(key, {n: 3})` fills `{n}` placeholders. Missing keys fall
 * back to English rather than rendering a raw key, so a gap shows as untranslated text
 * instead of as `scorecard.total` in the middle of the board.
 */

export const LANGS = ["en", "de", "fr", "it"];
export const LANG_NAMES = { en: "English", de: "Deutsch", fr: "Français", it: "Italiano" };

const STORAGE_KEY = "kj_lang";

const STRINGS = {
  en: {
    "lang.name": "English",

    "seat.you": "You",
    "seat.partner": "Partner",
    "seat.left": "Left",
    "seat.right": "Right",
    "team.us": "Us",
    "team.them": "Them",

    "contract.DIAMONDS": "Diamonds",
    "contract.HEARTS": "Hearts",
    "contract.SPADES": "Spades",
    "contract.CLUBS": "Clubs",
    "contract.OBENABE": "Obenabe",
    "contract.UNDENUFE": "Undenufe",

    "bid.prompt": "Choose trump",
    "bid.shove": "Schieben",

    "weis.prompt.pre": "You hold",
    "weis.prompt.amount": "{n} in Weis",
    "weis.announce": "Announce",
    "weis.decline": "Keep it quiet",
    "weis.stoeck": "Stöck",
    "weis.generic": "Weis",
    "weis.20": "Dreiblatt",
    "weis.50": "Vierblatt",
    "weis.100": "Hundert",
    "weis.150": "150",
    "weis.200": "200",

    "status.yourTurn": "Your turn",
    "status.tapAgain": "Tap again to play",
    "status.yourBid": "Your bid — or push it to your partner",
    "status.mustChoose": "Your partner pushed — you must choose",
    "status.thinking": "{who} is thinking…",
    "status.bidding": "{who} is bidding…",
    "status.weisAsk": "Announce your Weis?",
    "status.weisWait": "Weis…",
    "status.roundComplete": "Round complete",
    "status.youTake": "You take it",
    "status.partnerTakes": "Partner takes it",
    "status.theyTake": "They take it",
    "status.tapTrick": "{who} — tap the trick",
    "status.connected": "Connected",
    "status.connecting": "Connecting…",
    "status.disconnected": "Disconnected — reconnecting…",

    "round.n": "Round {n}",
    "hud.taken": "{us} – {them} of {total}",

    // The table read. Jass vocabulary stays untranslated — see the note at the top — but
    // everything around it is ordinary language.
    "table.points": "{n} pts",
    "table.trumpsOut": "{n} out",

    "score.tricks": "Tricks",
    "score.lastTrick": "Last trick",
    "score.weis": "Weis",
    "score.stoeck": "Stöck",
    "score.match": "Match",
    "score.cardPoints": "of {n} card points",
    "score.subtotal": "Subtotal",
    "score.multiplier": "× {n} ({contract})",
    "score.thisRound": "This round",
    "score.total": "Total",
    "score.final": "Final score",
    "score.nextRound": "Next round",
    "score.newGame": "New game",

    "tafel.title": "Jasstafel",
    "tafel.empty": "Nothing on the board yet — it fills in as rounds finish.",
    "tafel.playingTo": "playing to {n}",
    "tafel.legend": "<b>│</b> 100 · <b>✕</b> 50 · <b>╷</b> 20 · a full row struck · the rest written out",

    "menu.settings": "Settings",
    "menu.about": "How it works",
    "menu.gameSettings": "Game settings",
    "menu.note": "Changing these starts a new game.",
    "menu.noteOffline": "Changing these starts a new game. Everything runs in this tab — no server.",
    "menu.playTo": "Play to",
    "menu.weis": "Weis",
    "menu.on": "On",
    "menu.off": "Off",
    "menu.stoeckNote": "Stöck is always announced — it gives nothing away that the card itself did not.",
    "menu.multipliers": "Multipliers",
    "menu.language": "Language",
    "menu.cancel": "Cancel",
    "menu.start": "Start new game",
    "menu.close": "Close",
    "menu.loading": "Loading…",
    "menu.loadFailed": "Could not load the measurements.",
  },

  de: {
    "lang.name": "Deutsch",

    "seat.you": "Du",
    "seat.partner": "Partner",
    "seat.left": "Links",
    "seat.right": "Rechts",
    "team.us": "Wir",
    "team.them": "Sie",

    "contract.DIAMONDS": "Karo",
    "contract.HEARTS": "Herz",
    "contract.SPADES": "Pik",
    "contract.CLUBS": "Kreuz",
    "contract.OBENABE": "Obenabe",
    "contract.UNDENUFE": "Undenufe",

    "bid.prompt": "Trumpf wählen",
    "bid.shove": "Schieben",

    "weis.prompt.pre": "Du hast",
    "weis.prompt.amount": "{n} im Weis",
    "weis.announce": "Ansagen",
    "weis.decline": "Für dich behalten",
    "weis.stoeck": "Stöck",
    "weis.generic": "Weis",
    "weis.20": "Dreiblatt",
    "weis.50": "Vierblatt",
    "weis.100": "Hundert",
    "weis.150": "150",
    "weis.200": "200",

    "status.yourTurn": "Du bist dran",
    "status.tapAgain": "Nochmals tippen zum Spielen",
    "status.yourBid": "Du bist am Zug — oder schieb zum Partner",
    "status.mustChoose": "Dein Partner hat geschoben — du musst wählen",
    "status.thinking": "{who} überlegt…",
    "status.bidding": "{who} wählt Trumpf…",
    "status.weisAsk": "Weis ansagen?",
    "status.weisWait": "Weis…",
    "status.roundComplete": "Runde beendet",
    "status.youTake": "Du machst den Stich",
    "status.partnerTakes": "Partner macht den Stich",
    "status.theyTake": "Sie machen den Stich",
    "status.tapTrick": "{who} — Stich antippen",
    "status.connected": "Verbunden",
    "status.connecting": "Verbinde…",
    "status.disconnected": "Getrennt — verbinde neu…",

    "round.n": "Runde {n}",
    "hud.taken": "{us} – {them} von {total}",

    "table.points": "{n} Pkt.",
    "table.trumpsOut": "{n} draussen",

    "score.tricks": "Stiche",
    "score.lastTrick": "Letzter Stich",
    "score.weis": "Weis",
    "score.stoeck": "Stöck",
    "score.match": "Match",
    "score.cardPoints": "von {n} Kartenpunkten",
    "score.subtotal": "Zwischentotal",
    "score.multiplier": "× {n} ({contract})",
    "score.thisRound": "Diese Runde",
    "score.total": "Total",
    "score.final": "Schlussresultat",
    "score.nextRound": "Nächste Runde",
    "score.newGame": "Neues Spiel",

    "tafel.title": "Jasstafel",
    "tafel.empty": "Noch nichts auf der Tafel — sie füllt sich mit jeder Runde.",
    "tafel.playingTo": "Spiel bis {n}",
    "tafel.legend": "<b>│</b> 100 · <b>✕</b> 50 · <b>╷</b> 20 · volle Reihe durchgestrichen · der Rest angeschrieben",

    "menu.settings": "Einstellungen",
    "menu.about": "Wie es funktioniert",
    "menu.gameSettings": "Spieleinstellungen",
    "menu.note": "Änderungen starten ein neues Spiel.",
    "menu.noteOffline": "Änderungen starten ein neues Spiel. Alles läuft in diesem Tab — ohne Server.",
    "menu.playTo": "Spiel bis",
    "menu.weis": "Weis",
    "menu.on": "Ein",
    "menu.off": "Aus",
    "menu.stoeckNote": "Stöck wird immer angesagt — es verrät nichts, was die Karte nicht schon verraten hat.",
    "menu.multipliers": "Multiplikatoren",
    "menu.language": "Sprache",
    "menu.cancel": "Abbrechen",
    "menu.start": "Neues Spiel starten",
    "menu.close": "Schliessen",
    "menu.loading": "Lädt…",
    "menu.loadFailed": "Die Messwerte konnten nicht geladen werden.",
  },

  fr: {
    "lang.name": "Français",

    "seat.you": "Toi",
    "seat.partner": "Partenaire",
    "seat.left": "Gauche",
    "seat.right": "Droite",
    "team.us": "Nous",
    "team.them": "Eux",

    "contract.DIAMONDS": "Carreau",
    "contract.HEARTS": "Cœur",
    "contract.SPADES": "Pique",
    "contract.CLUBS": "Trèfle",
    "contract.OBENABE": "Obenabe",
    "contract.UNDENUFE": "Undenufe",

    "bid.prompt": "Choisis l'atout",
    "bid.shove": "Schieben",

    "weis.prompt.pre": "Tu as",
    "weis.prompt.amount": "{n} en Weis",
    "weis.announce": "Annoncer",
    "weis.decline": "Garder pour toi",
    "weis.stoeck": "Stöck",
    "weis.generic": "Weis",
    "weis.20": "Dreiblatt",
    "weis.50": "Vierblatt",
    "weis.100": "Cent",
    "weis.150": "150",
    "weis.200": "200",

    "status.yourTurn": "À toi de jouer",
    "status.tapAgain": "Touche encore pour jouer",
    "status.yourBid": "À toi d'annoncer — ou passe à ton partenaire",
    "status.mustChoose": "Ton partenaire a passé — tu dois choisir",
    "status.thinking": "{who} réfléchit…",
    "status.bidding": "{who} choisit l'atout…",
    "status.weisAsk": "Annoncer ton Weis ?",
    "status.weisWait": "Weis…",
    "status.roundComplete": "Manche terminée",
    "status.youTake": "Tu prends le pli",
    "status.partnerTakes": "Ton partenaire prend le pli",
    "status.theyTake": "Ils prennent le pli",
    "status.tapTrick": "{who} — touche le pli",
    "status.connected": "Connecté",
    "status.connecting": "Connexion…",
    "status.disconnected": "Déconnecté — reconnexion…",

    "round.n": "Manche {n}",
    "hud.taken": "{us} – {them} sur {total}",

    "table.points": "{n} pts",
    "table.trumpsOut": "{n} dehors",

    "score.tricks": "Plis",
    "score.lastTrick": "Dernier pli",
    "score.weis": "Weis",
    "score.stoeck": "Stöck",
    "score.match": "Match",
    "score.cardPoints": "sur {n} points de cartes",
    "score.subtotal": "Sous-total",
    "score.multiplier": "× {n} ({contract})",
    "score.thisRound": "Cette manche",
    "score.total": "Total",
    "score.final": "Score final",
    "score.nextRound": "Manche suivante",
    "score.newGame": "Nouvelle partie",

    "tafel.title": "Jasstafel",
    "tafel.empty": "Rien encore au tableau — il se remplit au fil des manches.",
    "tafel.playingTo": "partie en {n}",
    "tafel.legend": "<b>│</b> 100 · <b>✕</b> 50 · <b>╷</b> 20 · rangée complète barrée · le reste écrit",

    "menu.settings": "Réglages",
    "menu.about": "Comment ça marche",
    "menu.gameSettings": "Réglages de la partie",
    "menu.note": "Les modifier lance une nouvelle partie.",
    "menu.noteOffline": "Les modifier lance une nouvelle partie. Tout tourne dans cet onglet — sans serveur.",
    "menu.playTo": "Partie en",
    "menu.weis": "Weis",
    "menu.on": "Oui",
    "menu.off": "Non",
    "menu.stoeckNote": "Le Stöck est toujours annoncé — il ne révèle rien que la carte n'ait déjà révélé.",
    "menu.multipliers": "Multiplicateurs",
    "menu.language": "Langue",
    "menu.cancel": "Annuler",
    "menu.start": "Lancer une partie",
    "menu.close": "Fermer",
    "menu.loading": "Chargement…",
    "menu.loadFailed": "Impossible de charger les mesures.",
  },

  it: {
    "lang.name": "Italiano",

    "seat.you": "Tu",
    "seat.partner": "Compagno",
    "seat.left": "Sinistra",
    "seat.right": "Destra",
    "team.us": "Noi",
    "team.them": "Loro",

    "contract.DIAMONDS": "Quadri",
    "contract.HEARTS": "Cuori",
    "contract.SPADES": "Picche",
    "contract.CLUBS": "Fiori",
    "contract.OBENABE": "Obenabe",
    "contract.UNDENUFE": "Undenufe",

    "bid.prompt": "Scegli la briscola",
    "bid.shove": "Schieben",

    "weis.prompt.pre": "Hai",
    "weis.prompt.amount": "{n} in Weis",
    "weis.announce": "Annuncia",
    "weis.decline": "Tieni per te",
    "weis.stoeck": "Stöck",
    "weis.generic": "Weis",
    "weis.20": "Dreiblatt",
    "weis.50": "Vierblatt",
    "weis.100": "Cento",
    "weis.150": "150",
    "weis.200": "200",

    "status.yourTurn": "Tocca a te",
    "status.tapAgain": "Tocca di nuovo per giocare",
    "status.yourBid": "Tocca a te annunciare — o passa al compagno",
    "status.mustChoose": "Il compagno ha passato — devi scegliere tu",
    "status.thinking": "{who} sta pensando…",
    "status.bidding": "{who} sceglie la briscola…",
    "status.weisAsk": "Annunciare il tuo Weis?",
    "status.weisWait": "Weis…",
    "status.roundComplete": "Mano finita",
    "status.youTake": "La presa è tua",
    "status.partnerTakes": "La presa è del compagno",
    "status.theyTake": "La presa è loro",
    "status.tapTrick": "{who} — tocca la presa",
    "status.connected": "Connesso",
    "status.connecting": "Connessione…",
    "status.disconnected": "Disconnesso — riconnessione…",

    "round.n": "Mano {n}",
    "hud.taken": "{us} – {them} su {total}",

    "table.points": "{n} pt",
    "table.trumpsOut": "{n} fuori",

    "score.tricks": "Prese",
    "score.lastTrick": "Ultima presa",
    "score.weis": "Weis",
    "score.stoeck": "Stöck",
    "score.match": "Match",
    "score.cardPoints": "su {n} punti carta",
    "score.subtotal": "Parziale",
    "score.multiplier": "× {n} ({contract})",
    "score.thisRound": "Questa mano",
    "score.total": "Totale",
    "score.final": "Punteggio finale",
    "score.nextRound": "Mano successiva",
    "score.newGame": "Nuova partita",

    "tafel.title": "Jasstafel",
    "tafel.empty": "Ancora niente sulla lavagna — si riempie a ogni mano.",
    "tafel.playingTo": "si gioca a {n}",
    "tafel.legend": "<b>│</b> 100 · <b>✕</b> 50 · <b>╷</b> 20 · riga piena sbarrata · il resto scritto",

    "menu.settings": "Impostazioni",
    "menu.about": "Come funziona",
    "menu.gameSettings": "Impostazioni partita",
    "menu.note": "Modificarle avvia una nuova partita.",
    "menu.noteOffline": "Modificarle avvia una nuova partita. Tutto gira in questa scheda — senza server.",
    "menu.playTo": "Si gioca a",
    "menu.weis": "Weis",
    "menu.on": "Sì",
    "menu.off": "No",
    "menu.stoeckNote": "Lo Stöck è sempre annunciato — non rivela nulla che la carta non avesse già rivelato.",
    "menu.multipliers": "Moltiplicatori",
    "menu.language": "Lingua",
    "menu.cancel": "Annulla",
    "menu.start": "Avvia una partita",
    "menu.close": "Chiudi",
    "menu.loading": "Caricamento…",
    "menu.loadFailed": "Impossibile caricare le misurazioni.",
  },
};

/** The browser's preference, narrowed to what we have. */
export function detectLang() {
  const stored = read(STORAGE_KEY);
  if (stored && LANGS.includes(stored)) return stored;
  // `navigator.languages` is in preference order; take the first we speak.
  for (const tag of navigator.languages || [navigator.language || "en"]) {
    const base = String(tag).toLowerCase().split("-")[0];
    if (LANGS.includes(base)) return base;
  }
  return "en";
}

function read(key) {
  // Storage throws in some contexts (private windows, blocked site data) rather than
  // returning null, so every access is guarded.
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* a remembered language is a convenience, not a requirement */
  }
}

let current = "en";

export function setLang(lang) {
  current = LANGS.includes(lang) ? lang : "en";
  write(STORAGE_KEY, current);
  document.documentElement.lang = current;
  return current;
}

export function getLang() {
  return current;
}

/** Look up a string, filling `{placeholders}`. Falls back to English, then to the key. */
export function t(key, params = null) {
  let text = STRINGS[current]?.[key];
  if (text === undefined) text = STRINGS.en[key];
  if (text === undefined) return key;
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (_, name) =>
    params[name] === undefined ? `{${name}}` : String(params[name])
  );
}

/** A contract's name in the current language. */
export function contractName(name) {
  return name ? t(`contract.${name}`) : "";
}

/**
 * Translate the static markup.
 *
 * Elements carry `data-i18n` for their text and `data-i18n-html` where the string contains
 * markup. Keeping the keys in the HTML means the template stays readable and both builds
 * translate the same way.
 */
export function applyStatic(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  root.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
}

setLang(detectLang());
