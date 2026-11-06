# Jass-Sprüche: what the table says, and when

The three bot seats now and then say a Jass saying in the pause after a trick
(`web/static/talk.js`). This note lists each saying, what it means, the moment it is said at,
and where that comes from. The picker uses only what everyone at the table has seen: the cards
of the finished trick, who took it, the contract and declarer, Weis and Stöck as they were
shown, and tricks won. It never reads a hand, and a bubble never stays up over the human's turn.

## Sources

- **[JV]** Schweizer Jassverzeichnis, *Jass-Sprüche*:
  <https://www.jassverzeichnis.ch/jass-spruch-zitate>. A crowdsourced list of eleven sayings,
  each with a one-line meaning. It is the only source we found that gives meanings for
  sayings. It names no game moment; the triggers below are worked out from its meanings.
- **[JW1–4]** jasswelt.ch, *ABC der Jassausdrücke*, parts 1–4:
  <https://www.jasswelt.ch/blogs/neuigkeiten/abc-der-jassausdruecke-teil-1-von-4> (and
  `-teil-2-von-4`, `-teil-3-von-4`, `-teil-4-von-4`). Vocabulary: Bockkarte, schmieren,
  anziehen, verwerfen, Stöck, schieben, Kontermatch, Puur.
- **[JL]** jasvel.org, *Jass-Lexikon*: <https://jasvel.org/de/jass-lexikon/>. Puur, Nell, Stöck
  (said when the second card goes down), Match (+100), the last trick (+5), schieben.
- **[JK]** jasswiki.ch, *Jassen*: <https://jasswiki.ch/jassen/>. Schmieren (valuable cards to
  your partner), Matsch, the order Stöck–Wys–Stich.

Searches of Swiss papers, dialect dictionaries and Jass shops turned up no list of sayings tied
to game moments: a sentence such as "said after being trumped" appears nowhere we looked. So:

- the **documented** sayings (the first table) have a recorded meaning from [JV], and the
  trigger follows from that meaning;
- the **table phrases** (the second table) are not documented proverbs. They are short
  remarks in the same idiom, built from vocabulary the glossaries define, and each fires on
  the moment its vocabulary names. We do not claim them as folk sayings;
- the **general chatter** (the third table) fits no game moment. It fills a quiet trick, rarely.

No new sayings were added: the existing ones now cover every common moment the view can
show, and the research gave us no further sayings with a recorded meaning to add.

### Glosses corrected

Several documented sayings had been glossed from their wording rather than their meaning.
"Meh gschnorred als gjasset" was glossed as "more talking than playing"; [JV] says it means a
round with very many Weis points. "Hälfercharte", "Zähner mached s Spiel verruckt", "Chasch go
lerne mischle", "Ufem Tisch müend si verrecke" and "Du seisch dinere Grossmueter no Bock" were
corrected the same way. The `talk.why.*` keys keep their names, and the English, French and
Italian texts changed. German shows no gloss on purpose (`table.js`, `showTalk`): it would be
explaining Swiss German in High German to a reader who has just read it. So the German table
has no `talk.why.*` keys.

## Who says it

Each moment has a *subject*, the seat it happened to, and each saying says which seat may
voice it: the subject (**self**), its **partner**, either of them (**team**), an opponent
(**opp**), or anyone (**any**). Only bot seats speak.

## Documented sayings

| Saying | Meaning ([JV]) | Moment (`talk.js` tag) | Who |
|---|---|---|---|
| Ufem Tisch müend si verrecke | At last the good cards are played, so they can be trumped | An Ace or Ten of the suit led is trumped by the other side (`stab`) | the side that trumped |
| Do chasch de Chnächt schicke | Cards so good they play themselves | One side takes four tricks in a row (`streak`), or all nine (`match`) | that side |
| Meh gschnorred als gjasset | There were very many Weis points | The winning Weis shown in the first trick totals 100 or more (`weis_big`) | anyone |
| Du seisch dinere Grossmueter no Bock | Said when a card was wrongly touted as a Bock | A lead of the suit's best card (the Ace; the Six in Undenufe) loses the trick (`bock_beaten`) | an opponent of the leader |
| Du bisch en Wändlijasser | Someone who mostly plays one suit | A seat leads the same suit for the third time in a round (`wandli`) | an opponent |
| Machsch s Chalb | Leading the others around by the nose | A small card (6–8, not trump) takes a trick worth 15 or more (`small_win`) | an opponent of the winner |
| Ich ha Hälfercharte | Cards that help in the Schieber whatever is chosen | Schieber, first trick: the forehand shoved (`shoved`) | the forehand who shoved |
| Zähner mached s Spiel verruckt | Lead a ten to tempt the opponent into trumping | A led Ten is trumped by the other side (`ten_drew_trump`) | the leader |
| Chasch go lerne mischle | Someone always deals bad cards | A side loses every trick (`matched`) or makes 30 points or fewer (`round_crushed`) | the losing side |
| Mit dine Brättli baisch en Hasestall | Only low cards that are no use | A side has no trick after six (`dry`) | that side's partner seat |

[JV] also lists a shuffling joke about someone shuffling too long. The bots never shuffle on
screen, so it is left out.

## Table phrases (our own, in the same idiom)

| Saying | Meaning | Moment | Who | Vocabulary source |
|---|---|---|---|---|
| Trumpf use, Bure zue | Lead trumps, draw them out | The declaring side leads trump in the first three tricks (`trump_lead`) | the leader's partner | [JL] Puur |
| De Puur schticht ellei | The Puur takes it alone | The trump Jack takes the trick (`puur`) | the winner | [JL], [JK] |
| De Näll macht de Underschid | The Näll makes the difference | The trump Nine takes the trick (`nell`) | the winner's side | [JL] Nell |
| Es Ass gaht nie verlore | An Ace keeps | A side-suit Ace takes the trick (`ace`) | the winner | — |
| Mit em Ass fahrt mer nie schlecht | You never go wrong with the Ace | same (`ace`) | the winner's side | — |
| De Sächser tuet au sin Dienscht | Even the Six does its job | A Six takes the trick, outside Undenufe (`six`) | the winner | — |
| Es Bäuerli chunnt sälte ellei | A Jack rarely comes alone | Two or more Jacks fall in one trick (`two_jacks`) | anyone | — |
| Ohni Trumpf gaht nüt | Nothing happens without trumps | `stab`, as above | the winner | — |
| Nöd jede Stich isch dine | Not every trick is yours | `stab` or `bock_beaten` | the winner's side | — |
| Wer schmiert, der fahrt | Smear and it runs | The winner's partner, playing after the winner, smears an Ace or Ten (`smear`) | the partner who smeared | [JW3], [JK] schmieren |
| Schmier mer eis | Put some points on it, partner | The winner's partner, playing after the winner, gives nothing to a trick worth 6 or less (`bare`) | the winner | [JW3], [JK] |
| Wer stichlet, mues au zelle | Take the trick, then count it | A trick worth 35 or more (`big`) | the winner | — |
| De Schtill gwinnt de Schtich | The quiet one takes the trick | A side's first trick comes at trick five or later (`first_late`) | the winner's partner | — |
| Stöck, Wys, Stich | The order of claiming | Stöck is called, when the second of King and Queen of trumps goes down (`stoeck`) | the seat that called it | [JL], [JK] |
| Zwänzg isch au öppis | Twenty is still something | `stoeck`, or a winning Weis of exactly 20 (`weis20`) | that side | [JL] |
| Wer schiebt, het nüt | Whoever shoves has nothing | `shoved` | an opponent | [JW3], [JL] schieben |
| Gschobe isch nöd gwunne | Shoved is not won | `shoved` | an opponent | [JW3] |
| Obenabe für d Ässe | Obenabe is for the Aces | First trick of an Obenabe (`obenabe`) | the declaring side | [JL] |
| Undenufe isch au es Spiel | Undenufe is a game too | First trick of an Undenufe (`undenufe`) | the declaring side | [JL] |
| De Letscht macht föif | The last trick makes five | The ninth trick (`last`) | the winner | [JL], [JK] +5 |
| Match isch Match | A Match is a Match | One side takes all nine (`match`) | that side | [JL], [JK] |
| Emol gwünne, emol lehre | Win one, learn one | A round lost with fewer than 70 points (`round_lost`) | the losing side | — |
| D Hoffnig stirbt zletscht | Hope dies last | `round_lost`, or `dry` | the losing side | — |
| S Glück sitzt immer gägenüber | Luck always sits across the table | `round_lost` | the losing side | — |
| Es git kei schlechti Charte, nur schlechti Spieler | No bad cards, only bad players | `round_lost` | the winning side | — |
| Bi eus wird nöd gmotzt | No moaning at this table | `round_crushed` | the winning side | — |
| Wer lachet, het scho gwunne | Whoever laughs has won | `round_won` (the other side made fewer than 70) | the winning side | — |
| Wer zellt, gwinnt | Whoever counts, wins | `round_won` | the winning side | — |
| Am Schluss zellt de Strich | In the end only the chalk counts | `round_won` | the losing side | [JW3] Strich |
| Nach em Jass isch vor em Jass | After the Jass is before the Jass | `round_won` / `round_lost` | anyone | — |

Round points are counted from the nine tricks the table saw (cards plus 5 for the last). Weis,
Stöck and a Sidi bid are left out: the moment is about the play. After a reload in mid-round
the totals are not judged at all.

## General chatter (no game moment)

Wer nöd stichlet, gwinnt nöd · S Blatt isch wies isch · Zerscht dänke, dänn läge · Guet
gmischlet isch halb gwunne · Nöd zünde, wenn s brennt · De Tisch vergisst nüt · Chunnt Zit,
chunnt Trumpf · Wer wartet, verliert de Stich · Jasse isch Chopfsach · Ei Charte, ei Entscheid.

These fire only on a trick where nothing else happened (`quiet`), at a 6% chance.

## How often

Every moment has its own chance (`CHANCE` in `talk.js`): a Match 90%, a big Weis or a
crushed round 60%, Stöck 50%, an ordinary trick-taking card 10–25%. After a remark, three
tricks pass before an ordinary moment can speak again. A moment of 60% or more speaks through
that pause. A saying is not heard again until twelve others have been, across rounds. On
492 tricks of random-play Schieber this came to **1.2 remarks a round**, over 25 different
moments, with no saying repeated inside twelve.

In a Coiffeur Misère, taking a trick is bad news, so the trick boasts are muted there. Only
Stöck, a big Weis and the chatter remain.
