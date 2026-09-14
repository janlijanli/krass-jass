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
    "seat.trumpMaker": "chose trump",
    "weis.tag.best": "highest — team scores",
    "weis.tag.counts": "counts too",
    "weis.tag.lost": "beaten",
    "ai.toggle": "AI mode",
    "ai.banner": "AI mode on — opponents enhanced",
    "talk.why.table": "Good cards are for playing, not admiring.",
    "talk.why.chnacht": "A hand so easy you could send the boy.",
    "talk.why.talk": "More talking than playing — a table classic.",
    "talk.why.bock": "You'd call your grandmother a sure winner.",
    "talk.why.wandli": "One suit and one suit only, always.",
    "talk.why.chalb": "Playing the fool to lead us on.",
    "talk.why.helfer": "Cards that work everywhere and win nowhere.",
    "talk.why.zehner": "A ten on the table and everyone loses their head.",
    "talk.why.mischle": "Whoever shuffled that owes us an apology.",
    "talk.why.bretli": "Cards so low you could build a rabbit hutch.",
    "talk.why.trumps": "Draw their trumps before they ruff yours.",
    "talk.why.stich": "You cannot win a trick you never contest.",
    "talk.why.hand": "You play the hand you got.",
    "talk.why.think": "Think first, then lay. In that order.",
    "talk.why.ace": "An ace keeps. It comes in somewhere.",
    "talk.why.lose": "Win one, learn one.",
    "talk.why.shuffle": "A good shuffle is half the game.",
    "talk.why.puur": "The Jack stands alone and beats the lot.",
    "talk.why.stoeck": "The old order of claiming. In that order.",
    "talk.why.under": "Bottom-up counts as a game too.",
    "talk.why.oben": "Top-down is where aces earn their keep.",
    "talk.why.schmier": "Put some points on it, partner.",
    "talk.why.schiebe": "A shove says more than a bid does.",
    "talk.why.nell": "The nine decides more rounds than the ace.",
    "talk.why.zuende": "Do not light a fire that is already burning.",
    "talk.why.nobad": "No bad cards, only bad players. Allegedly.",
    "talk.why.notyet": "Shoving it across is not winning it.",
    "talk.why.twenty": "Twenty is still twenty.",
    "talk.why.count": "Whoever counts, wins.",
    "talk.why.notrump": "Without trumps nothing much happens.",
    "talk.why.last": "The last trick is worth five.",
    "talk.why.match": "All nine tricks. Nothing else counts as one.",
    "talk.why.motz": "No complaining at this table.",
    "talk.why.memory": "The table forgets nothing.",
    "talk.why.laugh": "Whoever is laughing has already won.",
    "talk.why.patience": "Give it time and the trump comes.",
    "talk.why.pair": "A Jack rarely travels alone.",
    "talk.why.wait": "Hesitate and the trick is gone.",
    "talk.why.notyours": "Not every trick is yours to take.",
    "talk.why.withace": "You never do badly with the ace.",
    "talk.why.six": "Even the six does its job.",
    "talk.why.head": "Jass is played in the head.",
    "talk.why.greasy": "Grease the trick and it runs.",
    "talk.why.luck": "Luck always sits across the table.",
    "talk.why.stroke": "In the end only the chalk counts.",
    "talk.why.payup": "Take the trick, then count it.",
    "talk.why.one": "One card, one decision.",
    "talk.why.hope": "Hope dies last. It still dies.",
    "talk.why.again": "After the Jass is before the Jass.",
    "talk.why.quiet": "The quiet one takes the trick.",
    "menu.talk": "Jass sayings",
    "menu.talkNote": "The table says something now and then, the way a real one does. Traditional sayings, kept in dialect — they tell you nothing about the cards.",
    "menu.advice": "Recommendations",
    "menu.adviceNote": "Marks the three cards a fourth bot would play from your seat, best first. It sees exactly what you see — it is not the right answer, just another opinion. Applies at once.",
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

    "contract.DIAMONDS": "Ecken",
    "contract.HEARTS": "Herz",
    "contract.SPADES": "Schaufel",
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
    "seat.trumpMaker": "hat Trumpf gemacht",
    "weis.tag.best": "höchstes — Team zählt",
    "weis.tag.counts": "zählt mit",
    "weis.tag.lost": "überboten",
    "ai.toggle": "KI-Modus",
    "ai.banner": "KI-Modus aktiv — Gegner verstärkt",
    // No Jass-Spruch glosses in German: explaining Swiss German in High
    // German to a reader who just understood it is talking down to them.
    // `showTalk` in table.js suppresses the line entirely for `de`.
    "menu.talk": "Jass-Sprüche",
    "menu.talkNote": "Am Tisch wird geredet, wie an einem echten. Alte Sprüche, im Dialekt belassen — sie verraten nichts über die Karten.",
    "menu.advice": "Empfehlungen",
    "menu.adviceNote": "Markiert die drei Karten, die ein vierter Bot von deinem Platz aus spielen würde, beste zuerst. Er sieht genau, was du siehst — das ist nicht die richtige Antwort, nur eine zweite Meinung. Wirkt sofort.",
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
    "seat.trumpMaker": "a choisi l'atout",
    "weis.tag.best": "le plus haut — l'équipe marque",
    "weis.tag.counts": "compte aussi",
    "weis.tag.lost": "battu",
    "ai.toggle": "Mode IA",
    "ai.banner": "Mode IA activé — adversaires augmentés",
    "talk.why.table": "Les bonnes cartes se jouent, ne s'admirent pas.",
    "talk.why.chnacht": "Une main si simple qu'on enverrait le gamin.",
    "talk.why.talk": "Plus de paroles que de jeu.",
    "talk.why.bock": "Tu traiterais ta grand-mère de carte maîtresse.",
    "talk.why.wandli": "Toujours la même couleur, encore et encore.",
    "talk.why.chalb": "Tu fais l'idiot pour nous égarer.",
    "talk.why.helfer": "Des cartes utiles partout, gagnantes nulle part.",
    "talk.why.zehner": "Un dix sur la table et tout le monde s'affole.",
    "talk.why.mischle": "Celui qui a mélangé nous doit des excuses.",
    "talk.why.bretli": "Des cartes si basses qu'on bâtirait un clapier.",
    "talk.why.trumps": "Tire leurs atouts avant qu'ils ne coupent.",
    "talk.why.stich": "On ne gagne pas un pli qu'on ne dispute pas.",
    "talk.why.hand": "On joue la main qu'on a.",
    "talk.why.think": "D'abord réfléchir, ensuite poser.",
    "talk.why.ace": "Un as se garde. Il passera.",
    "talk.why.lose": "Une fois gagner, une fois apprendre.",
    "talk.why.shuffle": "Bien mélanger, c'est à moitié gagné.",
    "talk.why.puur": "Le valet seul les bat tous.",
    "talk.why.stoeck": "L'ordre des annonces. Dans cet ordre.",
    "talk.why.under": "Undenufe est un jeu aussi.",
    "talk.why.oben": "Obenabe, là où les as se paient.",
    "talk.why.schmier": "Mets-y des points, partenaire.",
    "talk.why.schiebe": "Qui passe en dit plus qu'une annonce.",
    "talk.why.nell": "Le neuf décide plus de manches que l'as.",
    "talk.why.zuende": "N'attise pas un feu déjà pris.",
    "talk.why.nobad": "Pas de mauvaises cartes, que de mauvais joueurs.",
    "talk.why.notyet": "Passer la main n'est pas gagner.",
    "talk.why.twenty": "Vingt, c'est toujours vingt.",
    "talk.why.count": "Qui compte, gagne.",
    "talk.why.notrump": "Sans atout, rien ne se passe.",
    "talk.why.last": "Le dernier pli vaut cinq.",
    "talk.why.match": "Neuf plis. Rien d'autre ne compte.",
    "talk.why.motz": "On ne râle pas à cette table.",
    "talk.why.memory": "La table n'oublie rien.",
    "talk.why.laugh": "Qui rit a déjà gagné.",
    "talk.why.patience": "Avec le temps vient l'atout.",
    "talk.why.pair": "Un valet voyage rarement seul.",
    "talk.why.wait": "Qui hésite perd le pli.",
    "talk.why.notyours": "Tous les plis ne sont pas à toi.",
    "talk.why.withace": "Avec l'as on ne fait jamais mal.",
    "talk.why.six": "Même le six fait son travail.",
    "talk.why.head": "Le Jass se joue dans la tête.",
    "talk.why.greasy": "Qui graisse le pli le fait rouler.",
    "talk.why.luck": "La chance est toujours en face.",
    "talk.why.stroke": "À la fin, seule la craie compte.",
    "talk.why.payup": "Prends le pli, puis compte-le.",
    "talk.why.one": "Une carte, une décision.",
    "talk.why.hope": "L'espoir meurt en dernier. Il meurt quand même.",
    "talk.why.again": "Après le Jass, c'est avant le Jass.",
    "talk.why.quiet": "Le silencieux emporte le pli.",
    "menu.talk": "Dictons du Jass",
    "menu.talkNote": "La table lance une remarque de temps en temps, comme une vraie. Des dictons traditionnels, laissés en dialecte — ils ne disent rien des cartes.",
    "menu.advice": "Recommandations",
    "menu.adviceNote": "Marque les trois cartes qu'un quatrième bot jouerait à votre place, la meilleure d'abord. Il voit exactement ce que vous voyez — ce n'est pas la bonne réponse, juste un autre avis. Effet immédiat.",
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
    "seat.trumpMaker": "ha scelto la briscola",
    "weis.tag.best": "il più alto — segna la squadra",
    "weis.tag.counts": "conta anche",
    "weis.tag.lost": "battuto",
    "ai.toggle": "Modalità IA",
    "ai.banner": "Modalità IA attiva — avversari potenziati",
    "talk.why.table": "Le buone carte si giocano, non si ammirano.",
    "talk.why.chnacht": "Una mano così facile che ci mandi il ragazzo.",
    "talk.why.talk": "Più chiacchiere che gioco.",
    "talk.why.bock": "Chiameresti tua nonna una carta sicura.",
    "talk.why.wandli": "Sempre lo stesso seme, sempre.",
    "talk.why.chalb": "Fai lo scemo per portarci fuori strada.",
    "talk.why.helfer": "Carte utili ovunque, vincenti da nessuna parte.",
    "talk.why.zehner": "Un dieci sul tavolo e tutti perdono la testa.",
    "talk.why.mischle": "Chi ha mescolato ci deve delle scuse.",
    "talk.why.bretli": "Carte così basse da farci una conigliera.",
    "talk.why.trumps": "Togli le briscole prima che taglino.",
    "talk.why.stich": "Non vinci una presa che non contendi.",
    "talk.why.hand": "Si gioca la mano che si ha.",
    "talk.why.think": "Prima pensare, poi calare.",
    "talk.why.ace": "Un asso si tiene. Prima o poi entra.",
    "talk.why.lose": "Una volta vinci, una volta impari.",
    "talk.why.shuffle": "Mescolare bene è metà partita.",
    "talk.why.puur": "Il fante da solo li batte tutti.",
    "talk.why.stoeck": "L'ordine delle dichiarazioni. In quest'ordine.",
    "talk.why.under": "Anche l'Undenufe è un gioco.",
    "talk.why.oben": "Obenabe: lì gli assi rendono.",
    "talk.why.schmier": "Mettici dei punti, compagno.",
    "talk.why.schiebe": "Chi passa dice più di una dichiarazione.",
    "talk.why.nell": "Il nove decide più mani dell'asso.",
    "talk.why.zuende": "Non attizzare un fuoco già acceso.",
    "talk.why.nobad": "Non ci sono carte brutte, solo giocatori.",
    "talk.why.notyet": "Passare la mano non è vincere.",
    "talk.why.twenty": "Venti sono pur sempre venti.",
    "talk.why.count": "Chi conta, vince.",
    "talk.why.notrump": "Senza briscola non succede niente.",
    "talk.why.last": "L'ultima presa vale cinque.",
    "talk.why.match": "Nove prese. Nient'altro conta.",
    "talk.why.motz": "A questo tavolo non ci si lamenta.",
    "talk.why.memory": "Il tavolo non dimentica nulla.",
    "talk.why.laugh": "Chi ride ha già vinto.",
    "talk.why.patience": "Col tempo arriva la briscola.",
    "talk.why.pair": "Un fante viaggia di rado da solo.",
    "talk.why.wait": "Chi esita perde la presa.",
    "talk.why.notyours": "Non ogni presa è tua.",
    "talk.why.withace": "Con l'asso non si sbaglia mai.",
    "talk.why.six": "Anche il sei fa il suo.",
    "talk.why.head": "A Jass si gioca con la testa.",
    "talk.why.greasy": "Chi unge la presa la fa scorrere.",
    "talk.why.luck": "La fortuna siede sempre di fronte.",
    "talk.why.stroke": "Alla fine conta solo il gesso.",
    "talk.why.payup": "Prendi la presa, poi contala.",
    "talk.why.one": "Una carta, una decisione.",
    "talk.why.hope": "La speranza muore per ultima. Ma muore.",
    "talk.why.again": "Dopo lo Jass viene prima dello Jass.",
    "talk.why.quiet": "Il silenzioso prende la presa.",
    "menu.talk": "Detti dello Jass",
    "menu.talkNote": "Ogni tanto al tavolo si commenta, come a uno vero. Detti tradizionali, lasciati in dialetto — non dicono nulla sulle carte.",
    "menu.advice": "Consigli",
    "menu.adviceNote": "Segna le tre carte che un quarto bot giocherebbe dal tuo posto, la migliore per prima. Vede esattamente quello che vedi tu — non è la risposta giusta, solo un altro parere. Ha effetto subito.",
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
