/* Text for the "How it works" panels, in all four languages.
 *
 * Split from `i18n.js` because it is long prose and the panels are loaded lazily — there is
 * no reason to ship three translations of the documentation to someone who never opens it.
 *
 * Strings may contain `<b>` and `{placeholders}`. Numbers are never written into the prose:
 * they arrive from `docs/measurements.json` as placeholders, so a re-measurement updates
 * every language at once and no translation can quietly carry a stale figure.
 */

export const ABOUT = {
  en: {
    "play.conv.h": "Like a Swiss partner",
    "play.conv.p": "Where the search finds two cards nearly as good, it plays what a Swiss partner expects. As the team that made trump it draws trumps first (with the Bauer once it holds three); otherwise it cashes aces before kings before queens, stays out of suits its partner threw away, leads low in its strong suit, smears points onto its partner's trick and never trumps its partner. “Nearly as good” means at most 0.01 of a round's share worse by its own estimate — measured, that costs nothing, and in {predictable}% of the situations where a convention names a card it now plays that card (before: {before}%; the search alone: {search}%).",
    "tab.rules": "Sidi rules",
    "rules.intro": "<b>Sidi Barrani</b> is a Schieber with an auction: after the deal everybody has a say in which trump is played. Tricks are played exactly as in the Schieber.",
    "rules.bid.h": "Bidding",
    "rules.bid.p": "The player to the dealer's right starts, then round the table. A bid names a <b>contract</b> (a suit, Obenabe or Undenufe) and a <b>number</b>: 40, 50 … 150, then 157 (every card point) and 257 (Match). “Hearts 100” means: with hearts as trump my partner and I take at least 100 points.",
    "rules.bid2.p": "Every bid must beat the standing one — the contract does not count: Hearts 100 beats Spades 90, not Spades 100. A player who passed may come back in later, and you may overbid your own partner.",
    "rules.end_auction.p": "The auction ends when three players pass in a row after a bid, when 257 is bid, or when someone doubles. If all four pass, the hand is thrown in and the next player deals. <b>The highest bidder leads.</b>",
    "rules.double.h": "Doubling",
    "rules.double.p": "Only the highest bidder's opponents may double, until the second card is on the table: during the auction (which ends it at once) or after the lead, when the app asks. A double doubles the stake. There is no redouble.",
    "rules.score.h": "Scoring",
    "rules.score.p": "Both teams write their card points — 157 a hand, 257 with Match. Everything counts once: no multipliers, no Weis, no Stöck. On top, the bid is a <b>stake</b>: if the bidding team reaches its number it writes the bid as well; if not, the opponents write it. Doubled, the stake counts twice.",
    "rules.ex.head": "Example|Declarers|Opponents",
    "rules.ex.1": "Hearts 100, 113 taken|113 + 100 = 213|44",
    "rules.ex.2": "Hearts 120 doubled, 113 taken|113|44 + 240 = 284",
    "rules.ex.3": "Match (257) bid and made|257 + 257 = 514|0",
    "rules.ex.4": "Match doubled, only 119 taken|119|38 + 514 = 552",
    "rules.end.h": "End of the game",
    "rules.end.p": "Play is to 2000. A hand is always played out; if a team then has 2000 or more, the team with more points wins. A wild bid near the target is part of the tactics. After each hand the player to the right of the declarer deals.",
    "rules.lang.h": "The bidding language",
    "rules.lang.p": "Not a rule but an understanding between partners — the bots speak it and read it:",
    "rules.lang.odd": "<b>Odd</b> tens (50, 70, 90, 110): the <b>Bauer</b> (trump jack) and 1, 2, 3, 4 more trumps.",
    "rules.lang.even": "<b>Even</b> tens (40, 60, 80, 100): the <b>Nell</b> (trump nine) without the Bauer, and 1, 2, 3, 4 more trumps.",
    "rules.lang.oben": "<b>Obenabe / Undenufe</b>: 40 = one ace (one six), 50 = two … support with +10 per ace (six) of your own.",
    "rules.lang.support": "<b>Support</b> a Bauer bid with the Nell and at least one more trump, or with three trumps; a Nell bid only with the Bauer. The parity shows your own card.",
    "rules.lang.trust": "The first bid is believed most. After that the parity still says Bauer or Nell, and the count is a judgement call — except after a big jump (60 to 110). Up to 100–110 anything goes.",
    "rules.bots.h": "How the bots play Sidi",
    "rules.bots.p": "They <b>bid</b> this language literally To <b>double</b> they estimate how often the declarers make their number: deal the unseen cards many times over, weight each deal by the bids at the table, and play it out. Under about a third, they double. In <b>play</b> they count what gets written: a point short of the bid costs the whole stake, and the search sees that edge. They read the <b>auction</b> as statements about the other hands — never as facts: a bid makes deals that contradict it less likely, never impossible.",
    "rules.bots.warn": "This is a first version. What reading the auction and playing for the bid are worth is still being measured, and the finer points of bidding (120 instead of 110 to keep the others under, Obenabe 40 to listen first) are not learned yet.",
    "play.advice.h": "Want to see its opinion?",
    "play.advice.p":
      "Settings has a <b>Recommendations</b> switch. Turn it on and your own cards get " +
      "numbered 1\u20133 \u2014 what a fourth bot would play from your seat, best first. It is " +
      "the same search the three you are playing against use, run on your hand, so it sees " +
      "exactly what you see and is guessing just as they are. Treat it as a second opinion, " +
      "not an answer key: on the numbers above it loses a third of its rounds to a player " +
      "who can see everything.",

    "tab.walk": "Nerd-Doc",
    "wt.h": "One decision, start to finish",
    "wt.intro":
      "Seven steps, in the order the engine actually runs them — from \"I cannot see your cards\" to \"I play this one\". Step through it.",
    "wt.prev": "← Back",
    "wt.next": "Next →",
    "wt.replay": "Replay",
    "wt.seat.left": "left",
    "wt.seat.partner": "partner",
    "wt.seat.right": "right",
    "wt.info.h": "1. What it is allowed to know",
    "wt.info.p":
      "Nine cards in its hand, and whatever is face up on the table. The other twenty-seven are a <b>question mark</b> — three quarters of the deck. One function decides what a seat may see, and a test fuzzes every observation looking for a card that should not be there.",
    "wt.deal.h": "2. It invents a deal",
    "wt.deal.p":
      "Since it cannot know, it <b>guesses</b>: the unseen cards are dealt at random into the other three hands. Now it has a complete deal it can reason about perfectly — one that is almost certainly wrong. Press <b>Replay</b> and you get a different one. It will build thousands.",
    "wt.rule.h": "3. Most guesses are already impossible",
    "wt.rule.p":
      "A guess has to fit what the table has shown. Someone who failed to follow suit cannot hold that suit. A Weis turned face up pins those exact cards to that exact hand. And a seat that called <b>nothing</b> in the first trick holds no sequence of three and no four of a kind — which rules out {pct} of the deals the engine would otherwise have imagined.",
    "wt.ruled.legend": "{pct}% contradict what the table said",
    "wt.tree.h": "4. One tree, many worlds",
    "wt.tree.p":
      "Here is the part that makes it a player rather than a calculator. All those imagined deals share <b>one</b> tree. A branch is a card, and its statistics are pooled across every world in which that card was playable — so it has to choose one move that serves every deal it cannot tell apart, which is exactly the constraint you play under.",
    "wt.tree.legend": "visits, shared across worlds",
    "wt.roll.h": "5. It finishes the imagined round",
    "wt.roll.p":
      "From the end of a branch it just plays the imagined deal out to the last trick and counts the points. Crude, and deliberately so: the error in a random finish is as often high as low, so across thousands of them it averages away. A cleverer guess that is <b>consistently</b> wrong would not.",
    "wt.rollout.start": "from here",
    "wt.rollout.end": "…to the last trick",
    "wt.vote.h": "6. The card it visited most",
    "wt.vote.p":
      "Not the card with the best average — the one the search kept coming back to. A move that looks brilliant in one lucky deal gets visited once; a move that holds up across thousands gets visited constantly. That is the answer.",
    "wt.votes.note": "share of visits",
    "wt.endg.h": "7. Near the end it stops guessing",
    "wt.endg.p":
      "With five cards each the round is small enough to solve <b>exactly</b> — every line, both sides playing perfectly. No sampling, no error. It costs about fifteen times more per extra card, which is why it replaces the search rather than running alongside it.",
    "wt.endgame.legend": "positions examined",

    "tab.play": "How it plays",
    "tab.strength": "Is it good?",
    "tab.internals": "Under the hood",

    "play.doing.h": "What it is doing",
    "play.doing.p":
      "It cannot see your cards. So it <b>imagines</b> them — deals the unseen cards into " +
      "the other three hands in every way that fits what the table has shown, favours the " +
      "deals that best explain how the others have played and bid, plays them out thousands of times, " +
      "and repeats with a different guess. The card that does best across all those guesses " +
      "is the one it plays.",
    "play.knows.h": "What it knows, and what it doesn't",
    "play.knows.p":
      "Its own hand, the cards already face up, and which moves are legal. Nothing else — " +
      "no peek at your hand, no deck order. That is enforced in one function and checked by " +
      "a test that fuzzes every observation looking for a card that should not be there.",
    "play.works.h": "What it works out",
    "play.works.p":
      "It reasons from what you play. Step through this — the last step is the one worth " +
      "seeing, because it shows the inference is exact rather than approximate.",
    "play.void.1": "They follow suit, so nothing is known yet.",
    "play.void.2": "They discard a <b>club</b> on a <b>spade</b> lead — so they hold no spades.",
    "play.void.3":
      "Now a <b>heart</b> is led and they discard again. Hearts are trump, so they hold no " +
      "trump — <b>except possibly the Jack</b>, which they are allowed to keep back.",
    "play.void.next": "Next →",
    "play.void.restart": "Start over",
    "play.weak.h": "Where it is weak",
    "play.weak.p": "Its individual card play is much stronger than its <b>team</b> play. It <b>plays</b> the conventions above but does not yet <b>read</b> them: the model of play it reads everyone through was learned from games in which nobody played them, so a partner's ace-then-king says less to it than it should. Retraining that model on games with the conventions is the next step. The model also fits bots better than people, and reading a partner is a known limit of this kind of search — more thinking time does not fix it.",
    "play.human.p":
      "It has also <b>never been measured against a human</b>. The published work on this " +
      "exact variant found a comparable bot scored {parity} — roughly par with strong " +
      "amateurs. That is the research's number, not ours.",

    "strength.h": "Is it actually any good?",
    "strength.intro":
      "Every figure here is measured, dated and carries its sample size.",
    "strength.meta": "Measured {date} · {machine} · {conditions}.",
    "strength.ladder.h": "The baseline ladder",
    "strength.ladder.p":
      "{deals} double rounds per matchup. Dots are the share of points; bars are 95% " +
      "confidence intervals. An interval crossing the centre line means <b>we cannot tell " +
      "the two apart</b>.",
    "strength.ladder.caption":
      "Note the top row: <b>greedy scores the same as random</b>. “Play your highest-value " +
      "legal card” sounds reasonable and is worth nothing — it throws aces into tricks it " +
      "was never going to win.",
    "strength.double.h": "Why every deal is played twice",
    "strength.double.p":
      "The deal dominates. Per-deal share has a standard deviation around 8%, so a short " +
      "match cannot resolve a 2% difference in skill. So each deal is played <b>twice</b>, " +
      "with the two sides swapped, and the pair is compared — which cancels most of the " +
      "luck. Testing that as if the halves were unrelated would throw the benefit away, so " +
      "the test is paired.",
    "strength.budget.h": "What more thinking buys",
    "strength.budget.p":
      "On the search the bots used first, nothing past about 2,400 iterations — the curve " +
      "below. Each budget played {deals} double rounds against a fixed 2,400-iteration opponent.",
    "strength.budget.caption":
      "At the top end, {a} iterations against {b} scored {share} over {n} deals (p = {p}). " +
      "<b>333× the computation, no measurable gain.</b> The shared search tree that replaced " +
      "that search keeps paying: {ships} iterations against 2,400 scored {now} over {nowdeals} " +
      "deals — which is why the bots now search {ships} iterations a move.",
    "strength.trump.h": "What the bidding is worth",
    "strength.trump.p":
      "Identical card play on both sides, only the trump choice differing: <b>{share}</b> " +
      "over {deals} double rounds — a {spread}-point spread. The research predicted {claim}. " +
      "<b>That one reproduced.</b> Re-tuning its weights by simulating every call later won " +
      "<b>{games}</b> of whole games against the original weights.",
    "strength.gap.h": "The number that matters most",
    "strength.gap.p":
      "A bot that <b>sees all four hands</b> beats the real one {share} to {other}. That gap " +
      "— about 7 points — is the price of playing with hidden information, and more thinking " +
      "barely moves it. What narrows it is reading the table better: weighting every imagined " +
      "deal by how likely the other players' cards and bid were, holding it, is worth " +
      "<b>+{beliefs} points</b> of a round's share, measured twice.",
    "strength.caveat":
      "A caveat that applies to all of it: the older figures are measured with Weis, Stöck and " +
      "the match bonus switched off, because they swing scores hard enough to drown the " +
      "difference between two agents; the newer ones under the rules you play. And every " +
      "number here is bots against bots — none has been measured against people.",

    "internals.h": "How it is built",
    "internals.p":
      "The engine is bitboards: a hand is a 36-bit integer and a suit is a 9-bit field, so " +
      "legal moves and trick resolution are table lookups rather than branching logic.",
    "internals.rust.h": "Why the search is in Rust",
    "internals.rust.p":
      "Python managed about 35,000 search iterations a second, which put a training corpus " +
      "at roughly a month of continuous computation. Profiling showed the random playout was " +
      "73% of the time — so porting only that would have capped the gain near 2.4×, and the " +
      "search tree had to move with it.",
    "internals.rust.caption":
      "Per move at 2,400 iterations. The browser build is 1.39× the native one — fast enough " +
      "that the bots on this page now search 153,600 iterations a move, with no server behind it.",
    "internals.rules.h": "The three rules that make Jass different",
    "internals.rules.p":
      "Implementations of other trick-taking games get these wrong. <b>You may always " +
      "trump</b>, even holding the led suit. Once someone has trumped, a <b>lower trump is " +
      "illegal</b> unless your hand is nothing but trumps. And if your only trump is the " +
      "Jack, you need not play it on a trump lead.",
    "internals.endgame.h": "The endgame is solved exactly",
    "internals.endgame.p":
      "Once few enough cards remain, the search is <b>replaced</b> by an exact double-dummy " +
      "solve. Cost roughly 15× per extra card — {costs} — which is why it replaces the " +
      "search rather than running inside it.",
    "internals.honest.h": "How it is kept honest",
    "internals.honest.p":
      "The rules exist twice — Python and Rust — and a third time in a deliberately naive " +
      "reference implementation written from the rules text that imports neither. Property " +
      "tests play whole random rounds and compare all three at every ply. Two implementations " +
      "can agree on the same misreading; three written from different starting points are " +
      "much less likely to.",
    "internals.caveat":
      "One honest limit of <b>this</b> build: it runs entirely in your browser, so all four " +
      "hands are in this tab's memory. The bots genuinely cannot see yours — the filtering " +
      "is the same code the server version runs — but a determined human with developer " +
      "tools can. That is fine for playing against bots and is exactly why multiplayer would " +
      "have to be server-side.",

    "fig.flat": "flat from here",
    "fig.cards": "{n} cards {ms} ms",
  },

  de: {
    "play.conv.h": "Wie ein Schweizer Partner",
    "play.conv.p": "Wo die Suche zwei Karten fast gleich gut findet, spielt er, was ein Schweizer Partner erwartet. Als Trumpfmacher zieht er zuerst Trumpf (mit dem Bauer, sobald er drei hat); sonst holt er Asse vor Königen vor Damen, meidet Farben, die sein Partner abgeworfen hat, zieht in seiner starken Farbe klein an, schmiert auf den Stich des Partners und sticht den Partner nie. «Fast gleich» heisst: nach eigener Schätzung höchstens 0,01 Rundenanteil schlechter — gemessen kostet das nichts, und in {predictable} % der Situationen, in denen eine Konvention eine Karte vorgibt, spielt er sie jetzt (vorher {before} %, die Suche allein {search} %).",
    "tab.rules": "Sidi-Regeln",
    "rules.intro": "<b>Sidi Barrani</b> ist ein Schieber mit Bieten: Nach dem Geben reden alle mit, welcher Trumpf gespielt wird. Gestochen wird genau wie im Schieber.",
    "rules.bid.h": "Bieten",
    "rules.bid.p": "Es beginnt der Spieler rechts vom Geber, dann geht es reihum. Ein Gebot nennt eine <b>Spielart</b> (eine Farbe, Obenabe oder Undenufe) und eine <b>Punktzahl</b>: 40, 50 … 150, dann 157 (alle Kartenpunkte) und 257 (Match). «Herz 100» heisst: Mit Herz als Trumpf machen mein Partner und ich mindestens 100 Punkte.",
    "rules.bid2.p": "Jedes Gebot muss höher sein als das stehende — die Spielart zählt dabei nicht: Herz 100 schlägt Ecken 90, aber nicht Ecken 100. Wer gepasst hat, darf später wieder einsteigen, und auch den eigenen Partner darf man überbieten.",
    "rules.end_auction.p": "Die Auktion endet, wenn nach einem Gebot drei Spieler hintereinander passen, wenn 257 geboten wird oder wenn gedoppelt wird. Passen alle vier, wird neu gegeben, und der nächste Spieler gibt. <b>Wer das höchste Gebot gemacht hat, spielt aus.</b>",
    "rules.double.h": "Doppeln",
    "rules.double.p": "Nur die Gegner des Höchstbietenden dürfen doppeln, und zwar bis die zweite Karte auf dem Tisch liegt: während der Auktion (das beendet sie sofort) oder nach dem ersten Ausspiel, wenn die App fragt. Doppeln verdoppelt den Einsatz. Rückdoppeln gibt es nicht.",
    "rules.score.h": "Abrechnung",
    "rules.score.p": "Beide Teams schreiben ihre Kartenpunkte — 157 pro Runde, 257 mit Match. Alles zählt einfach, es gibt keine Multiplikatoren, keinen Weis und keine Stöck. Dazu ist das Gebot ein <b>Einsatz</b>: Erreicht das bietende Team seine Zahl, schreibt es das Gebot dazu. Sonst schreiben es die Gegner. Gedoppelt zählt der Einsatz doppelt.",
    "rules.ex.head": "Beispiel|Ansager|Gegner",
    "rules.ex.1": "Herz 100, 113 Punkte gemacht|113 + 100 = 213|44",
    "rules.ex.2": "Herz 120 gedoppelt, 113 gemacht|113|44 + 240 = 284",
    "rules.ex.3": "Match (257) geboten und gemacht|257 + 257 = 514|0",
    "rules.ex.4": "Match gedoppelt, nur 119 gemacht|119|38 + 514 = 552",
    "rules.end.h": "Spielende",
    "rules.end.p": "Gespielt wird bis 2000. Eine Runde wird immer fertig gespielt; hat danach ein Team 2000 oder mehr, gewinnt das Team mit mehr Punkten. Ein hohes Gebot kurz vor dem Ziel gehört zur Taktik. Nach jeder Runde gibt der Spieler rechts vom Ansager.",
    "rules.lang.h": "Die Bietsprache",
    "rules.lang.p": "Keine Regel, sondern eine Verständigung zwischen Partnern — die Bots sprechen sie und lesen sie:",
    "rules.lang.odd": "<b>Ungerade</b> Zehner (50, 70, 90, 110): der <b>Bauer</b> und 1, 2, 3, 4 weitere Trümpfe.",
    "rules.lang.even": "<b>Gerade</b> Zehner (40, 60, 80, 100): der <b>Nell</b> ohne Bauer und 1, 2, 3, 4 weitere Trümpfe.",
    "rules.lang.oben": "<b>Obenabe / Undenufe</b>: 40 = ein Ass (eine Sechs), 50 = zwei … Nachsagen mit +10 pro eigenem Ass (Sechs).",
    "rules.lang.support": "<b>Nachsagen</b> auf einen Bauer mit dem Nell und mindestens einem weiteren Trumpf oder mit drei Trümpfen; auf einen Nell nur mit dem Bauer. Die Parität zeigt dabei die eigene Karte.",
    "rules.lang.trust": "Geglaubt wird am meisten die erste Ansage. Danach zeigt die Parität noch Bauer oder Nell, die Anzahl ist Ermessenssache — ausser bei einem grossen Sprung (60 auf 110). Bis 100, 110 gilt Narrenfreiheit.",
    "rules.bots.h": "Wie die Bots Sidi spielen",
    "rules.bots.p": "Sie <b>bieten</b> nach dieser Sprache, wörtlich genommen, Zum <b>Doppeln</b> schätzen sie, wie oft die Ansager ihre Zahl erreichen: Sie verteilen die unbekannten Karten viele Male neu, gewichten jede Verteilung nach den Geboten am Tisch und spielen sie zu Ende. Schaffen die Ansager es in weniger als etwa einem Drittel, wird gedoppelt. Beim <b>Spielen</b> rechnen sie mit dem, was aufgeschrieben wird: Ein Punkt unter dem Gebot kostet den ganzen Einsatz, und diese Kante sieht die Suche. Die <b>Auktion</b> lesen sie als Aussagen über die anderen Hände — nie als Tatsachen: Ein Gebot macht Kartenverteilungen, die ihm widersprechen, unwahrscheinlicher, aber nie unmöglich.",
    "rules.bots.warn": "Das ist die erste Fassung. Wie viel das Lesen der Auktion und das Spielen aufs Gebot bringen, wird noch gemessen; die Feinheiten des Bietens (taktisch 120 statt 110, erst Oben 40 zum Abhören) lernen die Bots noch nicht.",
    "play.advice.h": "Willst du seine Meinung sehen?",
    "play.advice.p":
      "In den Einstellungen gibt es einen Schalter <b>Empfehlungen</b>. Schalte ihn ein, und " +
      "deine eigenen Karten bekommen die Nummern 1\u20133 \u2014 was ein vierter Bot von deinem " +
      "Platz aus spielen w\u00fcrde, beste zuerst. Es ist dieselbe Suche, die auch deine drei " +
      "Gegen\u00fcber benutzen, auf deine Hand angewendet: Sie sieht genau, was du siehst, und " +
      "r\u00e4t genauso wie sie. Nimm es als zweite Meinung, nicht als L\u00f6sung \u2014 gegen " +
      "jemanden, der alle Karten sieht, verliert sie ein Drittel der Runden.",

    "tab.walk": "Nerd-Doc",
    "wt.h": "Eine Entscheidung, von vorn bis hinten",
    "wt.intro":
      "Sieben Schritte, in der Reihenfolge, in der die Engine sie wirklich ausführt — von «ich sehe deine Karten nicht» bis «ich spiele diese». Klick dich durch.",
    "wt.prev": "← Zurück",
    "wt.next": "Weiter →",
    "wt.replay": "Nochmal",
    "wt.seat.left": "links",
    "wt.seat.partner": "Partner",
    "wt.seat.right": "rechts",
    "wt.info.h": "1. Was er wissen darf",
    "wt.info.p":
      "Neun Karten auf der Hand und was offen auf dem Tisch liegt. Die anderen siebenundzwanzig sind ein <b>Fragezeichen</b> — drei Viertel des Decks. Eine einzige Funktion entscheidet, was ein Sitz sehen darf, und ein Test durchsucht jede Beobachtung nach einer Karte, die nicht darin vorkommen dürfte.",
    "wt.deal.h": "2. Er erfindet eine Verteilung",
    "wt.deal.p":
      "Weil er es nicht wissen kann, <b>rät</b> er: die ungesehenen Karten werden zufällig auf die drei anderen Hände verteilt. Jetzt hat er eine vollständige Verteilung, die er perfekt durchrechnen kann — und die mit ziemlicher Sicherheit falsch ist. Drück <b>Nochmal</b>, und es kommt eine andere. Er baut Tausende davon.",
    "wt.rule.h": "3. Die meisten Vermutungen sind längst unmöglich",
    "wt.rule.p":
      "Eine Vermutung muss zu dem passen, was der Tisch gezeigt hat. Wer nicht bedient hat, hat diese Farbe nicht. Ein aufgedecktes Weis nagelt genau diese Karten an genau diese Hand. Und wer im ersten Stich <b>nichts</b> angesagt hat, hat keine Dreierfolge und keinen Vierer — das schliesst {pct} der Verteilungen aus, die die Engine sonst durchgerechnet hätte.",
    "wt.ruled.legend": "{pct}% widersprechen dem, was angesagt wurde",
    "wt.tree.h": "4. Ein Baum, viele Welten",
    "wt.tree.p":
      "Hier wird aus dem Rechner ein Mitspieler. Alle erfundenen Verteilungen teilen sich <b>einen</b> Baum. Ein Ast ist eine Karte, und seine Statistik wird über alle Welten gepoolt, in denen diese Karte spielbar war — er muss also einen Zug wählen, der zu jeder Verteilung passt, die er nicht unterscheiden kann. Genau unter dieser Bedingung spielst du auch.",
    "wt.tree.legend": "Besuche, über Welten geteilt",
    "wt.roll.h": "5. Er spielt die erfundene Runde zu Ende",
    "wt.roll.p":
      "Vom Ende eines Astes spielt er die erfundene Verteilung einfach bis zum letzten Stich durch und zählt die Punkte. Grob, und zwar mit Absicht: der Fehler eines zufälligen Ausspielens liegt gleich oft zu hoch wie zu tief und mittelt sich über Tausende weg. Eine klügere Schätzung, die <b>systematisch</b> danebenliegt, täte das nicht.",
    "wt.rollout.start": "von hier",
    "wt.rollout.end": "…bis zum letzten Stich",
    "wt.vote.h": "6. Die Karte, die er am häufigsten besucht hat",
    "wt.vote.p":
      "Nicht die mit dem besten Schnitt — die, zu der die Suche immer wieder zurückkam. Ein Zug, der in einer glücklichen Verteilung genial aussieht, wird einmal besucht; einer, der über Tausende hält, ständig. Das ist die Antwort.",
    "wt.votes.note": "Anteil der Besuche",
    "wt.endg.h": "7. Gegen Schluss hört das Raten auf",
    "wt.endg.p":
      "Bei fünf Karten pro Hand ist die Runde klein genug, um sie <b>exakt</b> zu lösen — jede Linie, beide Seiten perfekt. Kein Sampling, kein Fehler. Pro zusätzliche Karte kostet das rund fünfzehnmal mehr, deshalb ersetzt es die Suche, statt neben ihr zu laufen.",
    "wt.endgame.legend": "untersuchte Stellungen",

    "tab.play": "Wie es spielt",
    "tab.strength": "Ist es gut?",
    "tab.internals": "Unter der Haube",

    "play.doing.h": "Was es tut",
    "play.doing.p":
      "Es sieht deine Karten nicht. Also <b>stellt es sie sich vor</b> — es verteilt die " +
      "unbekannten Karten passend zu allem, was am Tisch zu sehen war, auf die drei anderen " +
      "Hände, bevorzugt Verteilungen, die erklären, wie die anderen gespielt und angesagt " +
      "haben, spielt diese erfundene " +
      "Verteilung tausendfach aus und wiederholt das mit einer neuen Vermutung. Gespielt " +
      "wird die Karte, die über all diese Vermutungen hinweg am besten abschneidet.",
    "play.knows.h": "Was es weiss — und was nicht",
    "play.knows.p":
      "Die eigene Hand, die bereits offen liegenden Karten und welche Züge erlaubt sind. " +
      "Sonst nichts — kein Blick in deine Hand, keine Kartenreihenfolge. Das steckt in einer " +
      "einzigen Funktion und wird von einem Test geprüft, der jede Beobachtung durchsucht " +
      "und nach einer Karte fahndet, die dort nicht sein dürfte.",
    "play.works.h": "Was es sich zusammenreimt",
    "play.works.p":
      "Es schliesst aus dem, was du spielst. Geh das hier durch — der letzte Schritt ist der " +
      "sehenswerte, weil er zeigt, dass der Schluss exakt ist und nicht ungefähr.",
    "play.void.1": "Sie bedienen, also weiss man noch nichts.",
    "play.void.2":
      "Sie werfen <b>Kreuz</b> ab auf ein <b>Pik</b>-Ausspiel — sie haben also kein Pik mehr.",
    "play.void.3":
      "Jetzt kommt <b>Herz</b> und sie werfen wieder ab. Herz ist Trumpf, sie haben also " +
      "keinen Trumpf — <b>ausser möglicherweise den Buben</b>, den sie zurückbehalten dürfen.",
    "play.void.next": "Weiter →",
    "play.void.restart": "Von vorn",
    "play.weak.h": "Wo es schwach ist",
    "play.weak.p": "Sein Spiel mit den eigenen Karten ist deutlich stärker als sein <b>Zusammenspiel</b>. Die Konventionen oben <b>spielt</b> er, <b>lesen</b> tut er sie noch nicht: Das Spielmodell, durch das er alle anderen liest, stammt aus Partien, in denen niemand sie spielte — ein Ass-dann-König des Partners sagt ihm darum weniger, als es sollte. Das Modell auf Partien mit Konventionen neu zu trainieren ist der nächste Schritt. Es passt ausserdem besser auf Bots als auf Menschen, und einen Partner zu lesen ist eine bekannte Grenze dieser Art von Suche — mehr Bedenkzeit ändert nichts daran.",
    "play.human.p":
      "Ausserdem wurde es <b>nie gegen Menschen gemessen</b>. Die veröffentlichte Arbeit zu " +
      "genau dieser Variante fand für einen vergleichbaren Bot {parity} — etwa auf Augenhöhe " +
      "mit starken Amateuren. Das ist die Zahl aus der Forschung, nicht unsere.",

    "strength.h": "Ist es wirklich gut?",
    "strength.intro":
      "Jede Zahl hier ist gemessen, datiert und trägt ihren Stichprobenumfang.",
    "strength.meta": "Gemessen am {date} · {machine} · {conditions}.",
    "strength.ladder.h": "Die Vergleichsleiter",
    "strength.ladder.p":
      "{deals} Doppelrunden pro Paarung. Punkte sind der Punkteanteil, Balken sind " +
      "95-Prozent-Vertrauensintervalle. Schneidet ein Intervall die Mittellinie, heisst " +
      "das: <b>die beiden lassen sich nicht unterscheiden</b>.",
    "strength.ladder.caption":
      "Beachte die oberste Zeile: <b>Greedy schneidet gleich ab wie Zufall</b>. „Spiel die " +
      "höchstwertige erlaubte Karte“ klingt vernünftig und bringt nichts — es wirft Asse in " +
      "Stiche, die ohnehin verloren waren.",
    "strength.double.h": "Warum jede Verteilung zweimal gespielt wird",
    "strength.double.p":
      "Die Verteilung dominiert. Der Punkteanteil pro Verteilung streut mit rund 8 Prozent, " +
      "ein kurzer Wettkampf kann einen Unterschied von 2 Prozent also gar nicht auflösen. " +
      "Darum wird jede Verteilung <b>zweimal</b> gespielt, mit vertauschten Seiten, und das " +
      "Paar wird verglichen — das hebt den grössten Teil des Glücks auf. Würde man die " +
      "Hälften als unabhängig testen, wäre der Gewinn wieder weg; der Test ist also gepaart.",
    "strength.budget.h": "Was mehr Nachdenken bringt",
    "strength.budget.p":
      "Beim Suchverfahren, das die Bots zuerst hatten, nichts mehr jenseits von etwa 2400 " +
      "Iterationen – die Kurve unten. Jedes Budget spielte {deals} Doppelrunden gegen einen " +
      "festen Gegner mit 2400 Iterationen.",
    "strength.budget.caption":
      "Am oberen Ende erreichten {a} Iterationen gegen {b} genau {share} über {n} " +
      "Verteilungen (p = {p}). <b>333-fache Rechenleistung, kein messbarer Gewinn.</b> Die " +
      "veröffentlichte Arbeit legt {claim} nahe. Der gemeinsame Suchbaum, der dieses " +
      "Verfahren ersetzt hat, profitiert dagegen weiter: {ships} Iterationen gegen 2400 " +
      "erreichten {now} über {nowdeals} Verteilungen – darum rechnen die Bots jetzt {ships} " +
      "Iterationen pro Zug.",
    "strength.trump.h": "Was die Trumpfwahl wert ist",
    "strength.trump.p":
      "Gleiches Kartenspiel auf beiden Seiten, nur die Trumpfwahl unterscheidet sich: " +
      "<b>{share}</b> über {deals} Doppelrunden — ein Abstand von {spread} Punkten. Die " +
      "Forschung sagte {claim} voraus. <b>Das liess sich reproduzieren.</b> Später wurden die " +
      "Gewichte durch Simulation jeder Ansage neu abgestimmt – die neuen gewannen <b>{games}</b> " +
      "der ganzen Partien gegen die alten.",
    "strength.gap.h": "Die wichtigste Zahl",
    "strength.gap.p":
      "Ein Bot, der <b>alle vier Hände sieht</b>, schlägt den echten mit {share} zu {other}. " +
      "Dieser Abstand – etwa 7 Punkte – ist der Preis verdeckter Information, und mehr " +
      "Bedenkzeit verschiebt ihn kaum. Was ihn verkleinert, ist den Tisch besser zu lesen: jede " +
      "vorgestellte Verteilung danach zu gewichten, wie wahrscheinlich die Karten und die Ansage " +
      "der anderen damit waren, bringt <b>+{beliefs} Punkte</b> Rundenanteil, zweimal gemessen.",
    "strength.caveat":
      "Ein Vorbehalt, der für alles gilt: Die älteren Zahlen wurden mit ausgeschaltetem Weis, " +
      "Stöck und Match-Bonus gemessen, weil diese die Punkte so stark schwanken lassen, dass der " +
      "Unterschied zwischen zwei Bots darin untergeht; die neueren mit den Regeln, mit denen du " +
      "spielst. Und jede Zahl hier ist Bot gegen Bot – gegen Menschen ist noch nichts gemessen.",

    "internals.h": "Wie es gebaut ist",
    "internals.p":
      "Die Engine rechnet mit Bitboards: eine Hand ist eine 36-Bit-Zahl, eine Farbe ein " +
      "9-Bit-Feld. Erlaubte Züge und Stichauswertung sind damit Tabellenzugriffe statt " +
      "Verzweigungslogik.",
    "internals.rust.h": "Warum die Suche in Rust läuft",
    "internals.rust.p":
      "Python schaffte rund 35 000 Suchiterationen pro Sekunde, womit ein Trainingskorpus " +
      "etwa einen Monat Dauerrechnen gekostet hätte. Die Profilierung zeigte, dass 73 " +
      "Prozent der Zeit im zufälligen Ausspielen steckten — nur dieses zu portieren hätte " +
      "den Gewinn bei rund 2,4-fach gedeckelt, der Suchbaum musste mit.",
    "internals.rust.caption":
      "Pro Zug bei 2400 Iterationen. Die Browser-Variante ist 1,39-mal so langsam wie die " +
      "native – schnell genug, dass die Bots auf dieser Seite jetzt 153 600 Iterationen pro Zug " +
      "rechnen, ohne Server dahinter.",
    "internals.rules.h": "Die drei Regeln, die Jass anders machen",
    "internals.rules.p":
      "Umsetzungen anderer Stichspiele machen genau hier Fehler. <b>Du darfst immer " +
      "trumpfen</b>, auch wenn du die ausgespielte Farbe hast. Hat jemand bereits getrumpft, " +
      "ist ein <b>tieferer Trumpf verboten</b>, ausser du hast nur noch Trümpfe. Und ist der " +
      "Bube dein einziger Trumpf, musst du ihn auf Trumpf-Ausspiel nicht spielen.",
    "internals.endgame.h": "Das Endspiel wird exakt gelöst",
    "internals.endgame.p":
      "Sobald wenige Karten übrig sind, wird die Suche durch eine exakte Berechnung " +
      "<b>ersetzt</b>. Der Aufwand wächst etwa um das 15-fache pro zusätzlicher Karte — " +
      "{costs} — und genau darum ersetzt sie die Suche, statt in ihr zu laufen.",
    "internals.honest.h": "Wie es ehrlich gehalten wird",
    "internals.honest.p":
      "Die Regeln existieren zweimal — in Python und in Rust — und ein drittes Mal in einer " +
      "bewusst naiven Referenz, die allein aus dem Regeltext geschrieben wurde und keine der " +
      "beiden importiert. Eigenschaftstests spielen ganze Zufallsrunden und vergleichen alle " +
      "drei bei jedem Zug. Zwei Umsetzungen können sich auf dasselbe Missverständnis einigen; " +
      "drei aus verschiedenen Quellen sehr viel seltener.",
    "internals.caveat":
      "Eine ehrliche Grenze <b>dieser</b> Variante: sie läuft vollständig in deinem Browser, " +
      "also liegen alle vier Hände im Speicher dieses Tabs. Die Bots sehen deine wirklich " +
      "nicht — es ist dieselbe Filterung wie in der Server-Variante — aber ein entschlossener " +
      "Mensch mit Entwicklerwerkzeugen kann es. Gegen Bots ist das in Ordnung, und genau " +
      "darum müsste Mehrspieler auf dem Server laufen.",

    "fig.flat": "ab hier flach",
    "fig.cards": "{n} Karten {ms} ms",
  },

  fr: {
    "play.conv.h": "Comme un partenaire suisse",
    "play.conv.p": "Là où la recherche trouve deux cartes presque aussi bonnes, il joue ce qu'un partenaire suisse attend. Du côté qui a fait l'atout, il tire d'abord l'atout (avec le Bauer dès qu'il en a trois) ; sinon il encaisse les as avant les rois avant les dames, évite les couleurs que son partenaire a défaussées, entame petit dans sa couleur forte, charge le pli de son partenaire et ne coupe jamais son partenaire. « Presque aussi bonne » veut dire : au plus 0,01 de la part d'une donne en moins selon sa propre estimation — mesuré, cela ne coûte rien, et dans {predictable} % des situations où une convention désigne une carte, il la joue désormais (avant : {before} % ; la recherche seule : {search} %).",
    "tab.rules": "Règles du Sidi",
    "rules.intro": "Le <b>Sidi Barrani</b> est un Schieber avec des enchères : après la donne, tout le monde a son mot à dire sur l'atout. Les plis se jouent exactement comme au Schieber.",
    "rules.bid.h": "Les enchères",
    "rules.bid.p": "Le joueur à droite du donneur commence, puis on tourne. Une enchère nomme un <b>jeu</b> (une couleur, Obenabe ou Undenufe) et un <b>nombre</b> : 40, 50 … 150, puis 157 (tous les points des cartes) et 257 (Match). « Cœur 100 » veut dire : avec cœur atout, mon partenaire et moi faisons au moins 100 points.",
    "rules.bid2.p": "Chaque enchère doit dépasser celle qui tient — le jeu ne compte pas : Cœur 100 bat Pique 90, pas Pique 100. Qui a passé peut revenir plus tard, et on peut surenchérir sur son propre partenaire.",
    "rules.end_auction.p": "Les enchères s'arrêtent quand trois joueurs passent de suite après une enchère, quand on annonce 257 ou quand quelqu'un double. Si les quatre passent, on redonne et le joueur suivant donne. <b>Le plus offrant entame.</b>",
    "rules.double.h": "Doubler",
    "rules.double.p": "Seuls les adversaires du plus offrant peuvent doubler, jusqu'à ce que la deuxième carte soit sur la table : pendant les enchères (ce qui les arrête) ou après l'entame, quand l'app le demande. Doubler double la mise. Il n'y a pas de surcontre.",
    "rules.score.h": "Décompte",
    "rules.score.p": "Les deux équipes écrivent leurs points de cartes — 157 par donne, 257 avec Match. Tout compte simple : pas de multiplicateur, pas de Weis, pas de Stöck. En plus, l'enchère est une <b>mise</b> : si l'équipe qui a annoncé atteint son nombre, elle l'écrit en plus ; sinon ce sont les adversaires. Doublée, la mise compte double.",
    "rules.ex.head": "Exemple|Preneurs|Adversaires",
    "rules.ex.1": "Cœur 100, 113 points faits|113 + 100 = 213|44",
    "rules.ex.2": "Cœur 120 doublé, 113 faits|113|44 + 240 = 284",
    "rules.ex.3": "Match (257) annoncé et fait|257 + 257 = 514|0",
    "rules.ex.4": "Match doublé, seulement 119 faits|119|38 + 514 = 552",
    "rules.end.h": "Fin de partie",
    "rules.end.p": "On joue jusqu'à 2000. Une donne est toujours jouée jusqu'au bout ; si une équipe a alors 2000 ou plus, l'équipe qui a le plus de points gagne. Une grosse enchère près du but fait partie de la tactique. Après chaque donne, le joueur à droite du preneur donne.",
    "rules.lang.h": "Le langage des enchères",
    "rules.lang.p": "Pas une règle mais une entente entre partenaires — les bots le parlent et le lisent :",
    "rules.lang.odd": "Dizaines <b>impaires</b> (50, 70, 90, 110) : le <b>Bauer</b> (valet d'atout) et 1, 2, 3, 4 atouts de plus.",
    "rules.lang.even": "Dizaines <b>paires</b> (40, 60, 80, 100) : le <b>Nell</b> (neuf d'atout) sans le Bauer, et 1, 2, 3, 4 atouts de plus.",
    "rules.lang.oben": "<b>Obenabe / Undenufe</b> : 40 = un as (un six), 50 = deux … on soutient avec +10 par as (six) en main.",
    "rules.lang.support": "<b>Soutenir</b> un Bauer avec le Nell et au moins un atout de plus, ou avec trois atouts ; un Nell seulement avec le Bauer. La parité montre sa propre carte.",
    "rules.lang.trust": "C'est la première annonce qu'on croit le plus. Ensuite la parité dit encore Bauer ou Nell, le nombre est une affaire de jugement — sauf après un grand saut (de 60 à 110). Jusqu'à 100, 110, tout est permis.",
    "rules.bots.h": "Comment les bots jouent le Sidi",
    "rules.bots.p": "Ils <b>annoncent</b> ce langage à la lettre Pour <b>doubler</b>, ils estiment la fréquence à laquelle les preneurs atteignent leur nombre : ils redistribuent les cartes inconnues de nombreuses fois, pondèrent chaque donne par les enchères et la jouent jusqu'au bout. En dessous d'environ un tiers, ils doublent. En <b>jouant</b>, ils comptent ce qui s'écrit : un point sous l'enchère coûte toute la mise, et la recherche voit ce bord. Ils lisent les <b>enchères</b> comme des affirmations sur les autres mains — jamais comme des faits : une enchère rend moins probables les donnes qui la contredisent, jamais impossibles.",
    "rules.bots.warn": "C'est une première version. Ce que valent la lecture des enchères et le jeu pour la mise est encore en cours de mesure, et les finesses (120 au lieu de 110 pour barrer, Obenabe 40 pour écouter d'abord) ne sont pas encore apprises.",
    "play.advice.h": "Envie de conna\u00eetre son avis ?",
    "play.advice.p":
      "Les r\u00e9glages ont un interrupteur <b>Recommandations</b>. Activez-le et vos propres " +
      "cartes re\u00e7oivent les num\u00e9ros 1\u20133 \u2014 ce qu'un quatri\u00e8me bot jouerait " +
      "\u00e0 votre place, la meilleure d'abord. C'est la m\u00eame recherche que celle de vos " +
      "trois adversaires, appliqu\u00e9e \u00e0 votre main : elle voit exactement ce que vous " +
      "voyez et devine comme eux. Un deuxi\u00e8me avis, pas un corrig\u00e9 \u2014 face \u00e0 qui " +
      "voit tout, elle perd un tiers des manches.",

    "tab.walk": "Nerd-Doc",
    "wt.h": "Une décision, de bout en bout",
    "wt.intro":
      "Sept étapes, dans l'ordre où le moteur les exécute vraiment — de « je ne vois pas tes cartes » à « je joue celle-ci ». Parcourez-les.",
    "wt.prev": "← Retour",
    "wt.next": "Suivant →",
    "wt.replay": "Rejouer",
    "wt.seat.left": "gauche",
    "wt.seat.partner": "partenaire",
    "wt.seat.right": "droite",
    "wt.info.h": "1. Ce qu'il a le droit de savoir",
    "wt.info.p":
      "Neuf cartes en main, et ce qui est visible sur la table. Les vingt-sept autres sont un <b>point d'interrogation</b> — trois quarts du jeu. Une seule fonction décide de ce qu'une place peut voir, et un test passe chaque observation au crible pour y chercher une carte qui ne devrait pas s'y trouver.",
    "wt.deal.h": "2. Il invente une donne",
    "wt.deal.p":
      "Faute de savoir, il <b>devine</b> : les cartes invisibles sont réparties au hasard entre les trois autres mains. Il tient alors une donne complète qu'il peut analyser parfaitement — et qui est presque certainement fausse. Appuyez sur <b>Rejouer</b> : il en sort une autre. Il en construira des milliers.",
    "wt.rule.h": "3. La plupart des suppositions sont déjà impossibles",
    "wt.rule.p":
      "Une supposition doit coller à ce que la table a montré. Qui n'a pas fourni n'a pas cette couleur. Un Weis retourné épingle ces cartes précises à cette main précise. Et qui n'a <b>rien</b> annoncé au premier pli n'a ni suite de trois ni carré — ce qui élimine {pct} des donnes que le moteur aurait sinon imaginées.",
    "wt.ruled.legend": "{pct} % contredisent ce qui a été annoncé",
    "wt.tree.h": "4. Un arbre, plusieurs mondes",
    "wt.tree.p":
      "Voilà ce qui en fait un joueur plutôt qu'une calculatrice. Toutes ces donnes imaginées partagent <b>un seul</b> arbre. Une branche est une carte, et ses statistiques sont mises en commun sur tous les mondes où cette carte était jouable — il doit donc choisir un coup qui serve chaque donne qu'il ne peut distinguer. C'est exactement votre contrainte à vous.",
    "wt.tree.legend": "visites, partagées entre les mondes",
    "wt.roll.h": "5. Il termine la manche imaginée",
    "wt.roll.p":
      "Depuis le bout d'une branche, il joue simplement la donne imaginée jusqu'au dernier pli et compte les points. Grossier, et volontairement : l'erreur d'une fin au hasard tombe aussi souvent trop haut que trop bas, et s'annule sur des milliers d'essais. Une estimation plus fine mais <b>systématiquement</b> biaisée, non.",
    "wt.rollout.start": "d'ici",
    "wt.rollout.end": "…jusqu'au dernier pli",
    "wt.vote.h": "6. La carte la plus visitée",
    "wt.vote.p":
      "Pas celle qui a la meilleure moyenne — celle sur laquelle la recherche est sans cesse revenue. Un coup brillant dans une donne chanceuse est visité une fois ; un coup qui tient sur des milliers l'est constamment. Voilà la réponse.",
    "wt.votes.note": "part des visites",
    "wt.endg.h": "7. Vers la fin, il cesse de deviner",
    "wt.endg.p":
      "À cinq cartes chacun, la manche est assez petite pour être résolue <b>exactement</b> — toutes les lignes, les deux camps parfaits. Aucun échantillonnage, aucune erreur. Chaque carte supplémentaire coûte environ quinze fois plus, d'où le remplacement de la recherche plutôt qu'une exécution en parallèle.",
    "wt.endgame.legend": "positions examinées",

    "tab.play": "Comment il joue",
    "tab.strength": "Est-il bon ?",
    "tab.internals": "Sous le capot",

    "play.doing.h": "Ce qu'il fait",
    "play.doing.p":
      "Il ne voit pas tes cartes. Alors il les <b>imagine</b> — il répartit les cartes " +
      "inconnues dans les trois autres mains selon tout ce que la table a montré, en " +
      "privilégiant les donnes qui expliquent le jeu et l'annonce des autres, joue cette donne imaginaire des " +
      "milliers de fois, puis recommence avec une autre hypothèse. La carte qui s'en sort le " +
      "mieux sur l'ensemble de ces hypothèses est celle qu'il joue.",
    "play.knows.h": "Ce qu'il sait, et ce qu'il ignore",
    "play.knows.p":
      "Sa propre main, les cartes déjà sur la table et les coups autorisés. Rien d'autre — " +
      "aucun coup d'œil dans ta main, aucun ordre du paquet. Cela tient dans une seule " +
      "fonction, vérifiée par un test qui passe chaque observation au crible à la recherche " +
      "d'une carte qui ne devrait pas s'y trouver.",
    "play.works.h": "Ce qu'il déduit",
    "play.works.p":
      "Il raisonne à partir de ce que tu joues. Parcours ceci — la dernière étape est celle " +
      "qui vaut le détour, parce qu'elle montre que la déduction est exacte et non " +
      "approximative.",
    "play.void.1": "Ils fournissent, donc on ne sait encore rien.",
    "play.void.2":
      "Ils se défaussent d'un <b>trèfle</b> sur une entame à <b>pique</b> — ils n'ont donc " +
      "plus de pique.",
    "play.void.3":
      "Maintenant on entame <b>cœur</b> et ils se défaussent encore. Cœur est atout, ils " +
      "n'ont donc plus d'atout — <b>sauf peut-être le valet</b>, qu'ils ont le droit de " +
      "garder.",
    "play.void.next": "Suite →",
    "play.void.restart": "Recommencer",
    "play.weak.h": "Où il est faible",
    "play.weak.p": "Son jeu de la carte est bien plus fort que son jeu <b>en équipe</b>. Il <b>joue</b> les conventions ci-dessus mais ne les <b>lit</b> pas encore : le modèle de jeu à travers lequel il lit tout le monde a été appris sur des parties où personne ne les jouait, si bien qu'un as-puis-roi du partenaire lui en dit moins qu'il ne devrait. Réentraîner ce modèle sur des parties avec les conventions est la prochaine étape. Le modèle est en outre plus fidèle aux bots qu'aux humains, et lire un partenaire est une limite connue de ce type de recherche — davantage de temps de réflexion n'y change rien.",
    "play.human.p":
      "Il n'a par ailleurs <b>jamais été mesuré contre des humains</b>. Les travaux publiés " +
      "sur cette variante précise ont relevé pour un bot comparable {parity} — à peu près au " +
      "niveau de bons amateurs. C'est le chiffre de la recherche, pas le nôtre.",

    "strength.h": "Est-il vraiment bon ?",
    "strength.intro":
      "Chaque chiffre ici est mesuré, daté et accompagné de sa taille d'échantillon.",
    "strength.meta": "Mesuré le {date} · {machine} · {conditions}.",
    "strength.ladder.h": "L'échelle de référence",
    "strength.ladder.p":
      "{deals} doubles manches par confrontation. Les points indiquent la part de points, " +
      "les barres des intervalles de confiance à 95 %. Un intervalle qui croise la ligne " +
      "centrale signifie que <b>l'on ne peut pas les départager</b>.",
    "strength.ladder.caption":
      "Regarde la première ligne : <b>le glouton fait aussi bien que le hasard</b>. « Joue " +
      "ta carte autorisée la plus forte » paraît raisonnable et ne vaut rien — cela jette " +
      "des as dans des plis déjà perdus.",
    "strength.double.h": "Pourquoi chaque donne est jouée deux fois",
    "strength.double.p":
      "La donne domine tout. La part de points par donne a un écart-type d'environ 8 %, si " +
      "bien qu'un match court ne peut pas trancher une différence de 2 %. Chaque donne est " +
      "donc jouée <b>deux fois</b>, les deux camps échangés, et la paire est comparée — ce " +
      "qui annule l'essentiel de la chance. Tester les deux moitiés comme si elles étaient " +
      "indépendantes gâcherait ce gain ; le test est donc apparié.",
    "strength.budget.h": "Ce qu'apporte plus de réflexion",
    "strength.budget.p":
      "Avec la première recherche des bots, plus rien au-delà d'environ 2400 itérations — " +
      "la courbe ci-dessous. Chaque budget a joué {deals} doubles manches contre un adversaire " +
      "fixé à 2400 itérations.",
    "strength.budget.caption":
      "Tout en haut, {a} itérations contre {b} ont obtenu {share} sur {n} donnes (p = {p}). " +
      "<b>333 fois le calcul, aucun gain mesurable.</b> Les travaux publiés suggèrent " +
      "{claim}. L'arbre de recherche partagé qui l'a remplacée continue pourtant de " +
      "progresser : {ships} itérations contre 2400 ont obtenu {now} sur {nowdeals} donnes — " +
      "c'est pourquoi les bots cherchent désormais {ships} itérations par coup.",
    "strength.trump.h": "Ce que vaut l'annonce",
    "strength.trump.p":
      "Jeu de la carte identique des deux côtés, seul le choix de l'atout diffère : " +
      "<b>{share}</b> sur {deals} doubles manches — un écart de {spread} points. La " +
      "recherche prédisait {claim}. <b>Celui-là s'est reproduit.</b> Réajustés plus tard en " +
      "simulant chaque annonce, les nouveaux poids ont gagné <b>{games}</b> des parties " +
      "complètes contre les anciens.",
    "strength.gap.h": "Le chiffre le plus important",
    "strength.gap.p":
      "Un bot qui <b>voit les quatre mains</b> bat le vrai par {share} contre {other}. Cet " +
      "écart — environ 7 points — est le prix de l'information cachée, et plus de réflexion ne " +
      "le déplace guère. Ce qui le réduit, c'est mieux lire la table : pondérer chaque donne " +
      "imaginée par la probabilité des cartes et de l'annonce des autres joueurs rapporte " +
      "<b>+{beliefs} points</b> de part de la manche, mesuré deux fois.",
    "strength.caveat":
      "Une réserve qui vaut pour tout : les mesures anciennes sont prises avec le Weis, le " +
      "Stöck et la prime de match désactivés, parce qu'ils font varier les scores au point de " +
      "noyer la différence entre deux bots ; les plus récentes avec les règles auxquelles tu " +
      "joues. Et chaque chiffre ici est bot contre bot — rien n'a encore été mesuré contre des " +
      "humains.",

    "internals.h": "Comment c'est construit",
    "internals.p":
      "Le moteur travaille en bitboards : une main est un entier de 36 bits et une couleur " +
      "un champ de 9 bits, si bien que les coups autorisés et la résolution des plis sont " +
      "des consultations de table plutôt que de la logique à branches.",
    "internals.rust.h": "Pourquoi la recherche est en Rust",
    "internals.rust.p":
      "Python tenait environ 35 000 itérations par seconde, ce qui mettait un corpus " +
      "d'entraînement à près d'un mois de calcul continu. Le profilage a montré que le " +
      "déroulement aléatoire représentait 73 % du temps — n'en porter que cette partie " +
      "aurait plafonné le gain vers 2,4×, et l'arbre de recherche devait suivre.",
    "internals.rust.caption":
      "Par coup, à 2400 itérations. La version navigateur est 1,39 fois plus lente que la " +
      "native — assez rapide pour que les bots de cette page cherchent désormais 153 600 " +
      "itérations par coup, sans serveur derrière.",
    "internals.rules.h": "Les trois règles qui distinguent le Jass",
    "internals.rules.p":
      "Les implémentations d'autres jeux de plis se trompent précisément là-dessus. <b>Tu " +
      "peux toujours couper</b>, même en ayant la couleur demandée. Dès que quelqu'un a " +
      "coupé, <b>couper plus bas est interdit</b>, sauf si ta main n'est plus que d'atouts. " +
      "Et si ton seul atout est le valet, tu n'es pas obligé de le fournir sur une entame à " +
      "l'atout.",
    "internals.endgame.h": "La fin de partie est résolue exactement",
    "internals.endgame.p":
      "Dès qu'il reste peu de cartes, la recherche est <b>remplacée</b> par un calcul exact. " +
      "Le coût est multiplié par environ 15 à chaque carte de plus — {costs} — et c'est bien " +
      "pour cela qu'il remplace la recherche au lieu de tourner dedans.",
    "internals.honest.h": "Comment on le garde honnête",
    "internals.honest.p":
      "Les règles existent deux fois — en Python et en Rust — et une troisième dans une " +
      "implémentation volontairement naïve, écrite à partir du texte des règles et " +
      "n'important ni l'une ni l'autre. Des tests de propriétés jouent des manches entières " +
      "au hasard et comparent les trois à chaque coup. Deux implémentations peuvent " +
      "s'accorder sur le même contresens ; trois, écrites depuis des points de départ " +
      "différents, beaucoup plus rarement.",
    "internals.caveat":
      "Une limite honnête de <b>cette</b> version : tout tourne dans ton navigateur, donc " +
      "les quatre mains sont en mémoire dans cet onglet. Les bots ne voient réellement pas " +
      "la tienne — c'est le même filtrage que la version serveur — mais un humain déterminé, " +
      "avec les outils de développement, le peut. C'est acceptable contre des bots, et c'est " +
      "exactement pourquoi le multijoueur devrait tourner côté serveur.",

    "fig.flat": "plat à partir d'ici",
    "fig.cards": "{n} cartes {ms} ms",
  },

  it: {
    "play.conv.h": "Come un compagno svizzero",
    "play.conv.p": "Dove la ricerca trova due carte quasi altrettanto buone, gioca ciò che un compagno svizzero si aspetta. Dalla parte che ha fatto la briscola tira prima le briscole (con il Bauer appena ne ha tre); altrimenti incassa gli assi prima dei re prima delle donne, evita i semi che il compagno ha scartato, esce basso nel suo seme forte, carica la presa del compagno e non taglia mai il compagno. «Quasi altrettanto buona» vuol dire: al massimo 0,01 della quota di una mano in meno secondo la sua stessa stima — misurato, non costa nulla, e nel {predictable}% delle situazioni in cui una convenzione indica una carta ora la gioca (prima: {before}%; la sola ricerca: {search}%).",
    "tab.rules": "Regole del Sidi",
    "rules.intro": "Il <b>Sidi Barrani</b> è uno Schieber con l'asta: dopo la distribuzione tutti dicono la loro sulla briscola. Le prese si giocano esattamente come nello Schieber.",
    "rules.bid.h": "L'asta",
    "rules.bid.p": "Comincia il giocatore alla destra di chi ha dato le carte, poi si gira. Una puntata nomina un <b>gioco</b> (un seme, Obenabe o Undenufe) e un <b>numero</b>: 40, 50 … 150, poi 157 (tutti i punti delle carte) e 257 (Match). «Cuori 100» vuol dire: con cuori briscola io e il mio compagno facciamo almeno 100 punti.",
    "rules.bid2.p": "Ogni puntata deve superare quella in piedi — il gioco non conta: Cuori 100 batte Picche 90, non Picche 100. Chi ha passato può rientrare più tardi, e si può rilanciare anche sul proprio compagno.",
    "rules.end_auction.p": "L'asta finisce quando tre giocatori passano di fila dopo una puntata, quando si punta 257 o quando qualcuno raddoppia. Se passano tutti e quattro, si ridà e dà il giocatore successivo. <b>Chi ha puntato di più esce per primo.</b>",
    "rules.double.h": "Raddoppiare",
    "rules.double.p": "Solo gli avversari di chi ha puntato di più possono raddoppiare, finché la seconda carta non è sul tavolo: durante l'asta (che così finisce) o dopo l'uscita, quando l'app lo chiede. Il raddoppio raddoppia la posta. Il controraddoppio non esiste.",
    "rules.score.h": "Conteggio",
    "rules.score.p": "Le due squadre scrivono i punti delle carte — 157 a mano, 257 con il Match. Tutto vale semplice: niente moltiplicatori, niente Weis, niente Stöck. In più la puntata è una <b>posta</b>: se la squadra che ha puntato raggiunge il suo numero, lo scrive in più; altrimenti lo scrivono gli avversari. Raddoppiata, la posta vale doppio.",
    "rules.ex.head": "Esempio|Chi ha puntato|Avversari",
    "rules.ex.1": "Cuori 100, fatti 113 punti|113 + 100 = 213|44",
    "rules.ex.2": "Cuori 120 raddoppiato, fatti 113|113|44 + 240 = 284",
    "rules.ex.3": "Match (257) puntato e fatto|257 + 257 = 514|0",
    "rules.ex.4": "Match raddoppiato, fatti solo 119|119|38 + 514 = 552",
    "rules.end.h": "Fine della partita",
    "rules.end.p": "Si gioca fino a 2000. Una mano si gioca sempre fino in fondo; se poi una squadra ha 2000 o più, vince la squadra con più punti. Una puntata alta vicino al traguardo fa parte della tattica. Dopo ogni mano dà il giocatore alla destra di chi ha puntato.",
    "rules.lang.h": "Il linguaggio dell'asta",
    "rules.lang.p": "Non una regola ma un'intesa tra compagni — i bot lo parlano e lo leggono:",
    "rules.lang.odd": "Decine <b>dispari</b> (50, 70, 90, 110): il <b>Bauer</b> (fante di briscola) e 1, 2, 3, 4 briscole in più.",
    "rules.lang.even": "Decine <b>pari</b> (40, 60, 80, 100): il <b>Nell</b> (nove di briscola) senza il Bauer, e 1, 2, 3, 4 briscole in più.",
    "rules.lang.oben": "<b>Obenabe / Undenufe</b>: 40 = un asso (un sei), 50 = due … si sostiene con +10 per ogni asso (sei) in mano.",
    "rules.lang.support": "<b>Sostenere</b> un Bauer con il Nell e almeno un'altra briscola, o con tre briscole; un Nell solo con il Bauer. La parità mostra la propria carta.",
    "rules.lang.trust": "Si crede di più alla prima puntata. Dopo, la parità dice ancora Bauer o Nell, il numero è questione di giudizio — tranne dopo un grande salto (da 60 a 110). Fino a 100, 110 tutto è permesso.",
    "rules.bots.h": "Come i bot giocano il Sidi",
    "rules.bots.p": "<b>Puntano</b> questo linguaggio alla lettera Per <b>raddoppiare</b> stimano quanto spesso chi ha puntato raggiunge il suo numero: ridistribuiscono molte volte le carte sconosciute, pesano ogni distribuzione con le puntate al tavolo e la giocano fino in fondo. Sotto circa un terzo, raddoppiano. <b>Giocando</b> contano ciò che si scrive: un punto sotto la puntata costa tutta la posta, e la ricerca vede quel bordo. Leggono l'<b>asta</b> come affermazioni sulle altre mani — mai come fatti: una puntata rende meno probabili le distribuzioni che la contraddicono, mai impossibili.",
    "rules.bots.warn": "È una prima versione. Quanto valgono la lettura dell'asta e il gioco per la posta si sta ancora misurando, e le finezze (120 invece di 110 per sbarrare, Obenabe 40 per ascoltare prima) non sono ancora apprese.",
    "play.advice.h": "Vuoi sapere che ne pensa?",
    "play.advice.p":
      "Nelle impostazioni c'\u00e8 un interruttore <b>Consigli</b>. Attivalo e le tue carte " +
      "ricevono i numeri 1\u20133 \u2014 quello che un quarto bot giocherebbe dal tuo posto, la " +
      "migliore per prima. \u00c8 la stessa ricerca dei tre contro cui giochi, applicata alla " +
      "tua mano: vede esattamente quello che vedi tu e tira a indovinare come loro. Un " +
      "secondo parere, non la soluzione \u2014 contro chi vede tutte le carte perde un terzo " +
      "dei giri.",

    "tab.walk": "Nerd-Doc",
    "wt.h": "Una decisione, dall'inizio alla fine",
    "wt.intro":
      "Sette passi, nell'ordine in cui il motore li esegue davvero — da «non vedo le tue carte» a «gioco questa». Scorrili.",
    "wt.prev": "← Indietro",
    "wt.next": "Avanti →",
    "wt.replay": "Di nuovo",
    "wt.seat.left": "sinistra",
    "wt.seat.partner": "compagno",
    "wt.seat.right": "destra",
    "wt.info.h": "1. Che cosa gli è permesso sapere",
    "wt.info.p":
      "Nove carte in mano e quello che è scoperto sul tavolo. Le altre ventisette sono un <b>punto interrogativo</b> — tre quarti del mazzo. Una sola funzione decide che cosa un posto può vedere, e un test setaccia ogni osservazione in cerca di una carta che non dovrebbe esserci.",
    "wt.deal.h": "2. Si inventa una distribuzione",
    "wt.deal.p":
      "Non potendo sapere, <b>tira a indovinare</b>: le carte non viste vengono distribuite a caso nelle altre tre mani. Ora ha una distribuzione completa su cui ragionare alla perfezione — e quasi certamente sbagliata. Premi <b>Di nuovo</b> e ne esce un'altra. Ne costruirà migliaia.",
    "wt.rule.h": "3. Gran parte delle ipotesi è già impossibile",
    "wt.rule.p":
      "Un'ipotesi deve stare con quello che il tavolo ha mostrato. Chi non ha risposto al seme non ce l'ha. Un Weis scoperto inchioda proprio quelle carte a quella mano. E chi non ha dichiarato <b>nulla</b> nella prima presa non ha né una sequenza di tre né un poker — il che esclude il {pct} delle distribuzioni che il motore avrebbe altrimenti immaginato.",
    "wt.ruled.legend": "il {pct}% contraddice quanto dichiarato",
    "wt.tree.h": "4. Un albero, molti mondi",
    "wt.tree.p":
      "Qui da calcolatrice diventa giocatore. Tutte le distribuzioni immaginate condividono <b>un solo</b> albero. Un ramo è una carta, e le sue statistiche sono messe in comune su ogni mondo in cui quella carta era giocabile — deve quindi scegliere una mossa che vada bene per ogni distribuzione che non sa distinguere. È esattamente il vincolo sotto cui giochi tu.",
    "wt.tree.legend": "visite, condivise tra i mondi",
    "wt.roll.h": "5. Finisce il giro immaginato",
    "wt.roll.p":
      "Dalla punta di un ramo gioca la distribuzione immaginata fino all'ultima presa e conta i punti. Grezzo, e di proposito: l'errore di un finale casuale cade tanto in alto quanto in basso e su migliaia di prove si annulla. Una stima più fine ma <b>sistematicamente</b> storta, no.",
    "wt.rollout.start": "da qui",
    "wt.rollout.end": "…fino all'ultima presa",
    "wt.vote.h": "6. La carta visitata più spesso",
    "wt.vote.p":
      "Non quella con la media migliore — quella su cui la ricerca è tornata di continuo. Una mossa che brilla in una distribuzione fortunata viene visitata una volta; una che regge su migliaia, di continuo. Questa è la risposta.",
    "wt.votes.note": "quota di visite",
    "wt.endg.h": "7. Verso la fine smette di indovinare",
    "wt.endg.p":
      "Con cinque carte a testa il giro è abbastanza piccolo da risolverlo <b>esattamente</b> — ogni linea, entrambe le parti perfette. Nessun campionamento, nessun errore. Ogni carta in più costa circa quindici volte tanto: per questo sostituisce la ricerca invece di affiancarla.",
    "wt.endgame.legend": "posizioni esaminate",

    "tab.play": "Come gioca",
    "tab.strength": "È forte?",
    "tab.internals": "Sotto il cofano",

    "play.doing.h": "Che cosa fa",
    "play.doing.p":
      "Non vede le tue carte. Quindi se le <b>immagina</b> — distribuisce le carte " +
      "sconosciute nelle altre tre mani secondo tutto ciò che il tavolo ha mostrato, " +
      "preferendo le distribuzioni che spiegano come gli altri hanno giocato e dichiarato, " +
      "gioca migliaia di volte quella distribuzione " +
      "immaginaria e ricomincia con un'altra ipotesi. La carta che se la cava meglio su " +
      "tutte queste ipotesi è quella che gioca.",
    "play.knows.h": "Che cosa sa e che cosa no",
    "play.knows.p":
      "La propria mano, le carte già scoperte e quali mosse sono lecite. Nient'altro — " +
      "nessuna occhiata alla tua mano, nessun ordine del mazzo. Tutto questo sta in una sola " +
      "funzione, verificata da un test che setaccia ogni osservazione in cerca di una carta " +
      "che non dovrebbe esserci.",
    "play.works.h": "Che cosa deduce",
    "play.works.p":
      "Ragiona da quello che giochi. Scorri questo — l'ultimo passaggio è quello che vale la " +
      "pena vedere, perché mostra che la deduzione è esatta e non approssimativa.",
    "play.void.1": "Rispondono al seme, quindi non si sa ancora nulla.",
    "play.void.2":
      "Scartano <b>fiori</b> su un attacco a <b>picche</b> — non hanno più picche.",
    "play.void.3":
      "Ora si attacca a <b>cuori</b> e scartano di nuovo. Cuori è briscola, quindi non hanno " +
      "briscole — <b>tranne forse il fante</b>, che possono tenersi.",
    "play.void.next": "Avanti →",
    "play.void.restart": "Ricomincia",
    "play.weak.h": "Dov'è debole",
    "play.weak.p": "Il suo gioco di carta è molto più forte del suo gioco <b>di squadra</b>. Le convenzioni qui sopra le <b>gioca</b>, ma non le <b>legge</b> ancora: il modello di gioco con cui legge tutti è stato appreso da partite in cui nessuno le giocava, così un asso-poi-re del compagno gli dice meno di quanto dovrebbe. Riaddestrare quel modello su partite con le convenzioni è il prossimo passo. Il modello è inoltre più fedele ai bot che alle persone, e leggere un compagno è un limite noto di questo tipo di ricerca — più tempo di riflessione non lo risolve.",
    "play.human.p":
      "Inoltre <b>non è mai stato misurato contro esseri umani</b>. Il lavoro pubblicato su " +
      "questa esatta variante ha rilevato per un bot paragonabile {parity} — più o meno alla " +
      "pari con buoni dilettanti. È il numero della ricerca, non il nostro.",

    "strength.h": "È davvero forte?",
    "strength.intro":
      "Ogni dato qui è misurato, datato e accompagnato dalla sua numerosità campionaria.",
    "strength.meta": "Misurato il {date} · {machine} · {conditions}.",
    "strength.ladder.h": "La scala di riferimento",
    "strength.ladder.p":
      "{deals} mani doppie per confronto. I punti indicano la quota di punti, le barre sono " +
      "intervalli di confidenza al 95%. Un intervallo che attraversa la linea centrale " +
      "significa che <b>i due non sono distinguibili</b>.",
    "strength.ladder.caption":
      "Guarda la prima riga: <b>l'avido fa quanto il caso</b>. «Gioca la carta lecita di " +
      "maggior valore» sembra ragionevole e non vale nulla — butta assi in prese già perse.",
    "strength.double.h": "Perché ogni distribuzione si gioca due volte",
    "strength.double.p":
      "La distribuzione domina. La quota di punti per mano ha una deviazione standard " +
      "attorno all'8%, quindi un incontro breve non può risolvere una differenza del 2%. " +
      "Perciò ogni distribuzione si gioca <b>due volte</b>, con i due schieramenti " +
      "scambiati, e si confronta la coppia — il che annulla gran parte della fortuna. " +
      "Trattare le due metà come indipendenti butterebbe via il vantaggio: il test è " +
      "appaiato.",
    "strength.budget.h": "Che cosa dà pensarci di più",
    "strength.budget.p":
      "Con la prima ricerca dei bot, nulla oltre le 2400 iterazioni circa — la curva qui " +
      "sotto. Ogni budget ha giocato {deals} mani doppie contro un avversario fisso a 2400 " +
      "iterazioni.",
    "strength.budget.caption":
      "In cima, {a} iterazioni contro {b} hanno ottenuto {share} su {n} distribuzioni " +
      "(p = {p}). <b>333 volte il calcolo, nessun guadagno misurabile.</b> Il lavoro " +
      "pubblicato suggerisce {claim}. L'albero di ricerca condiviso che l'ha sostituita " +
      "continua invece a migliorare: {ships} iterazioni contro 2400 hanno ottenuto {now} su " +
      "{nowdeals} distribuzioni — per questo i bot ora cercano {ships} iterazioni a mossa.",
    "strength.trump.h": "Quanto vale la scelta della briscola",
    "strength.trump.p":
      "Gioco di carta identico da entrambe le parti, cambia solo la scelta della briscola: " +
      "<b>{share}</b> su {deals} mani doppie — uno scarto di {spread} punti. La ricerca " +
      "prevedeva {claim}. <b>Quello si è riprodotto.</b> Ritarati poi simulando ogni " +
      "dichiarazione, i nuovi pesi hanno vinto <b>{games}</b> delle partite intere contro quelli " +
      "originali.",
    "strength.gap.h": "Il numero che conta di più",
    "strength.gap.p":
      "Un bot che <b>vede tutte e quattro le mani</b> batte quello vero {share} a {other}. " +
      "Quello scarto — circa 7 punti — è il prezzo dell'informazione nascosta, e pensarci di " +
      "più lo sposta appena. Ciò che lo riduce è leggere meglio il tavolo: pesare ogni " +
      "distribuzione immaginata per quanto erano probabili le carte e la dichiarazione degli " +
      "altri vale <b>+{beliefs} punti</b> di quota della mano, misurato due volte.",
    "strength.caveat":
      "Un'avvertenza che vale per tutto: le misure più vecchie sono prese con Weis, Stöck e " +
      "bonus match disattivati, perché fanno oscillare i punteggi al punto da coprire la " +
      "differenza fra due bot; quelle più recenti con le regole con cui giochi. E ogni numero " +
      "qui è bot contro bot — contro persone non è ancora stato misurato nulla.",

    "internals.h": "Com'è costruito",
    "internals.p":
      "Il motore lavora con bitboard: una mano è un intero a 36 bit e un seme un campo a 9 " +
      "bit, così le mosse lecite e la risoluzione della presa sono letture di tabella invece " +
      "che logica a rami.",
    "internals.rust.h": "Perché la ricerca è in Rust",
    "internals.rust.p":
      "Python reggeva circa 35 000 iterazioni al secondo, il che metteva un corpus di " +
      "addestramento a quasi un mese di calcolo continuo. Il profiling ha mostrato che lo " +
      "svolgimento casuale era il 73% del tempo — portare solo quello avrebbe fermato il " +
      "guadagno attorno a 2,4×, e l'albero di ricerca doveva seguirlo.",
    "internals.rust.caption":
      "Per mossa, a 2400 iterazioni. La versione browser è 1,39 volte più lenta di quella " +
      "nativa — abbastanza veloce perché i bot di questa pagina ora cerchino 153 600 " +
      "iterazioni a mossa, senza alcun server dietro.",
    "internals.rules.h": "Le tre regole che rendono lo Jass diverso",
    "internals.rules.p":
      "Le implementazioni di altri giochi di prese sbagliano proprio qui. <b>Puoi sempre " +
      "tagliare</b>, anche avendo il seme d'attacco. Una volta che qualcuno ha tagliato, " +
      "<b>tagliare più basso è vietato</b>, a meno che in mano ti restino solo briscole. E " +
      "se la tua unica briscola è il fante, non sei obbligato a giocarlo su un attacco a " +
      "briscola.",
    "internals.endgame.h": "Il finale viene risolto esattamente",
    "internals.endgame.p":
      "Quando restano poche carte, la ricerca viene <b>sostituita</b> da un calcolo esatto. " +
      "Il costo cresce di circa 15 volte per ogni carta in più — {costs} — ed è proprio per " +
      "questo che sostituisce la ricerca invece di girarci dentro.",
    "internals.honest.h": "Come lo si tiene onesto",
    "internals.honest.p":
      "Le regole esistono due volte — in Python e in Rust — e una terza in " +
      "un'implementazione volutamente ingenua, scritta dal testo delle regole e che non " +
      "importa né l'una né l'altra. Test di proprietà giocano intere mani casuali e " +
      "confrontano tutte e tre a ogni giocata. Due implementazioni possono concordare sullo " +
      "stesso fraintendimento; tre, scritte da punti di partenza diversi, molto più " +
      "raramente.",
    "internals.caveat":
      "Un limite onesto di <b>questa</b> versione: gira interamente nel tuo browser, quindi " +
      "tutte e quattro le mani sono nella memoria di questa scheda. I bot davvero non vedono " +
      "la tua — il filtro è lo stesso codice della versione server — ma un umano determinato, " +
      "con gli strumenti per sviluppatori, può. Contro i bot va bene, ed è esattamente il " +
      "motivo per cui il multigiocatore dovrebbe stare sul server.",

    "fig.flat": "piatto da qui",
    "fig.cards": "{n} carte {ms} ms",
  },
};

/** Look up a documentation string for the given language, falling back to English. */
export function about(lang, key, params = null) {
  let text = ABOUT[lang]?.[key];
  if (text === undefined) text = ABOUT.en[key];
  if (text === undefined) return key;
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (_, name) =>
    params[name] === undefined ? `{${name}}` : String(params[name])
  );
}
