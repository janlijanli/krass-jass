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
