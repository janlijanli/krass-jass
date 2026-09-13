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
      "the other three hands at random, plays that imaginary deal out thousands of times, " +
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
    "play.weak.p":
      "Its individual card play is much stronger than its <b>team</b> play. It <b>sends</b> " +
      "one signal now — throwing the sister suit of the one it wants led, and cashing out " +
      "when the opponents are proven out of trump — but it does not <b>read</b> yours: play " +
      "the convention at it and it will not notice. Reading a partner is a known limit of " +
      "this kind of search, not a bug, and more thinking time does not fix it.",
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
      "Nothing, past about 2,400 iterations. Each budget below played {deals} double rounds " +
      "against a fixed 2,400-iteration opponent.",
    "strength.budget.caption":
      "At the top end, {a} iterations against {b} scored {share} over {n} deals (p = {p}). " +
      "<b>333× the computation, no measurable gain.</b> The published work suggests {claim}; " +
      "that did not reproduce here, and we do not yet know why.",
    "strength.trump.h": "What the bidding is worth",
    "strength.trump.p":
      "Identical card play on both sides, only the trump choice differing: <b>{share}</b> " +
      "over {deals} double rounds — a {spread}-point spread. The research predicted {claim}. " +
      "<b>That one reproduced.</b>",
    "strength.gap.h": "The number that matters most",
    "strength.gap.p":
      "A bot that <b>sees all four hands</b> beats the real one {share} to {other}. That gap " +
      "— about 6 points — is the price of playing with hidden information, and search does " +
      "not close it: giving the real bot 16× more thinking moved it by less than half a " +
      "standard error. Closing it needs a different kind of player, not a faster one.",
    "strength.caveat":
      "A caveat that applies to all of it: these are measured with Weis, Stöck and the match " +
      "bonus switched off, because they swing scores hard enough to drown the difference " +
      "between two agents. They are on when you play.",

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
      "Per move at the 2,400-iteration serve budget. The browser build is 1.39× the native " +
      "one — which is why this page can run the whole game with no server behind it.",
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
      "unbekannten Karten zufällig auf die drei anderen Hände, spielt diese erfundene " +
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
    "play.weak.p":
      "Sein Spiel mit den eigenen Karten ist deutlich stärker als sein <b>Zusammenspiel</b>. " +
      "Ein Zeichen <b>gibt</b> es inzwischen — es wirft die Schwesterfarbe jener Farbe ab, " +
      "die es gespielt haben will, und zieht durch, sobald die Gegner nachweislich keinen " +
      "Trumpf mehr haben — deine <b>liest</b> es aber nicht: Spielst du die Konvention, " +
      "merkt es das nicht. Einen Partner zu lesen ist eine bekannte Grenze dieser Art von " +
      "Suche, kein Fehler, und mehr Bedenkzeit ändert nichts daran.",
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
      "Nichts mehr, jenseits von etwa 2400 Iterationen. Jedes Budget unten spielte {deals} " +
      "Doppelrunden gegen einen festen Gegner mit 2400 Iterationen.",
    "strength.budget.caption":
      "Am oberen Ende erreichten {a} Iterationen gegen {b} genau {share} über {n} " +
      "Verteilungen (p = {p}). <b>333-fache Rechenleistung, kein messbarer Gewinn.</b> Die " +
      "veröffentlichte Arbeit legt {claim} nahe; das liess sich hier nicht reproduzieren, " +
      "und wir wissen noch nicht, warum.",
    "strength.trump.h": "Was die Trumpfwahl wert ist",
    "strength.trump.p":
      "Gleiches Kartenspiel auf beiden Seiten, nur die Trumpfwahl unterscheidet sich: " +
      "<b>{share}</b> über {deals} Doppelrunden — ein Abstand von {spread} Punkten. Die " +
      "Forschung sagte {claim} voraus. <b>Das liess sich reproduzieren.</b>",
    "strength.gap.h": "Die wichtigste Zahl",
    "strength.gap.p":
      "Ein Bot, der <b>alle vier Hände sieht</b>, schlägt den echten mit {share} zu {other}. " +
      "Dieser Abstand — etwa 6 Punkte — ist der Preis dafür, mit verdeckter Information zu " +
      "spielen, und Suche schliesst ihn nicht: 16-fache Bedenkzeit für den echten Bot " +
      "verschob ihn um weniger als einen halben Standardfehler. Ihn zu schliessen braucht " +
      "einen anderen Spieler, keinen schnelleren.",
    "strength.caveat":
      "Ein Vorbehalt, der für alles gilt: gemessen wurde mit ausgeschaltetem Weis, Stöck und " +
      "Match-Bonus, weil diese die Punkte so stark schwanken lassen, dass der Unterschied " +
      "zwischen zwei Bots darin untergeht. Beim Spielen sind sie eingeschaltet.",

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
      "Pro Zug beim Spielbudget von 2400 Iterationen. Die Browser-Variante ist 1,39-mal so " +
      "langsam wie die native — darum kann diese Seite das ganze Spiel ohne Server ausführen.",
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
      "Il ne voit pas tes cartes. Alors il les <b>imagine</b> — il répartit au hasard les " +
      "cartes inconnues dans les trois autres mains, joue cette donne imaginaire des " +
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
    "play.weak.p":
      "Son jeu de la carte est bien plus fort que son jeu <b>en équipe</b>. Il <b>envoie</b> " +
      "désormais un signal — il défausse la couleur sœur de celle qu'il veut voir jouer, et " +
      "il encaisse dès que les adversaires n'ont prouvablement plus d'atout — mais il ne " +
      "<b>lit</b> pas les tiens : joue la convention, il ne la remarquera pas. Lire un " +
      "partenaire est une limite connue de ce type de recherche, pas un défaut, et davantage " +
      "de temps de réflexion n'y change rien.",
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
      "Rien, au-delà d'environ 2400 itérations. Chaque budget ci-dessous a joué {deals} " +
      "doubles manches contre un adversaire fixé à 2400 itérations.",
    "strength.budget.caption":
      "Tout en haut, {a} itérations contre {b} ont obtenu {share} sur {n} donnes (p = {p}). " +
      "<b>333 fois le calcul, aucun gain mesurable.</b> Les travaux publiés suggèrent " +
      "{claim} ; cela ne s'est pas reproduit ici, et nous ne savons pas encore pourquoi.",
    "strength.trump.h": "Ce que vaut l'annonce",
    "strength.trump.p":
      "Jeu de la carte identique des deux côtés, seul le choix de l'atout diffère : " +
      "<b>{share}</b> sur {deals} doubles manches — un écart de {spread} points. La " +
      "recherche prédisait {claim}. <b>Celui-là s'est reproduit.</b>",
    "strength.gap.h": "Le chiffre le plus important",
    "strength.gap.p":
      "Un bot qui <b>voit les quatre mains</b> bat le vrai par {share} contre {other}. Cet " +
      "écart — environ 6 points — est le prix de l'information cachée, et la recherche ne le " +
      "comble pas : donner au vrai bot 16 fois plus de réflexion l'a déplacé de moins d'une " +
      "demi-erreur type. Le combler demande un joueur d'une autre nature, pas un joueur plus " +
      "rapide.",
    "strength.caveat":
      "Une réserve qui vaut pour tout : ces mesures sont prises avec le Weis, le Stöck et la " +
      "prime de match désactivés, parce qu'ils font varier les scores au point de noyer la " +
      "différence entre deux bots. Ils sont actifs quand tu joues.",

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
      "Par coup, au budget de jeu de 2400 itérations. La version navigateur est 1,39 fois " +
      "plus lente que la native — c'est pourquoi cette page fait tourner toute la partie " +
      "sans serveur derrière.",
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
      "Non vede le tue carte. Quindi se le <b>immagina</b> — distribuisce a caso le carte " +
      "sconosciute nelle altre tre mani, gioca migliaia di volte quella distribuzione " +
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
    "play.weak.p":
      "Il suo gioco di carta è molto più forte del suo gioco <b>di squadra</b>. Un segnale " +
      "ora lo <b>manda</b> — scarta il seme gemello di quello che vuole si giochi, e incassa " +
      "appena gli avversari sono provatamente senza briscola — ma i tuoi non li <b>legge</b>: " +
      "gioca la convenzione e non se ne accorgerà. Leggere un compagno è un limite noto di " +
      "questo tipo di ricerca, non un difetto, e più tempo di riflessione non lo risolve.",
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
      "Nulla, oltre le 2400 iterazioni circa. Ogni budget qui sotto ha giocato {deals} mani " +
      "doppie contro un avversario fisso a 2400 iterazioni.",
    "strength.budget.caption":
      "In cima, {a} iterazioni contro {b} hanno ottenuto {share} su {n} distribuzioni " +
      "(p = {p}). <b>333 volte il calcolo, nessun guadagno misurabile.</b> Il lavoro " +
      "pubblicato suggerisce {claim}; qui non si è riprodotto, e non sappiamo ancora perché.",
    "strength.trump.h": "Quanto vale la scelta della briscola",
    "strength.trump.p":
      "Gioco di carta identico da entrambe le parti, cambia solo la scelta della briscola: " +
      "<b>{share}</b> su {deals} mani doppie — uno scarto di {spread} punti. La ricerca " +
      "prevedeva {claim}. <b>Quello si è riprodotto.</b>",
    "strength.gap.h": "Il numero che conta di più",
    "strength.gap.p":
      "Un bot che <b>vede tutte e quattro le mani</b> batte quello vero {share} a {other}. " +
      "Quello scarto — circa 6 punti — è il prezzo di giocare con informazione nascosta, e " +
      "la ricerca non lo colma: dare al bot vero 16 volte più riflessione lo ha spostato di " +
      "meno di mezzo errore standard. Colmarlo richiede un giocatore di altro tipo, non uno " +
      "più veloce.",
    "strength.caveat":
      "Un'avvertenza che vale per tutto: queste misure sono prese con Weis, Stöck e bonus " +
      "match disattivati, perché fanno oscillare i punteggi al punto da coprire la " +
      "differenza fra due bot. Quando giochi sono attivi.",

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
      "Per mossa, al budget di gioco di 2400 iterazioni. La versione browser è 1,39 volte " +
      "più lenta di quella nativa — ed è per questo che questa pagina fa girare l'intera " +
      "partita senza alcun server dietro.",
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
