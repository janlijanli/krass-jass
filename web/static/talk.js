/* Jass-Sprüche: the table talking.
 *
 * A Jass table is not silent. Somebody comments on the trick, somebody quotes the same
 * proverb they quote every week, and the game has a rhythm the cards alone do not carry.
 * This is the smallest honest version of that: occasionally, one of the three bots says
 * something.
 *
 * # About the material
 *
 * These are **traditional Swiss Jass sayings** — folk phrases in common circulation at any
 * table, not authored quotations. jassverzeichnis.ch/jass-spruch-zitate is a crowdsourced
 * archive of the same oral tradition and is what pointed us at several of them; the
 * selection here and the glosses in the tooltips are our own, and their collection is not
 * reproduced.
 *
 * They stay in dialect in every language the app speaks, for the same reason Weis, Stöck
 * and Obenabe do: translating "Ufem Tisch müend si verrecke" into French produces a
 * sentence no Jass player has ever said. The `why` line is translated, so a reader who does
 * not have the dialect still gets the joke.
 *
 * # When it fires
 *
 * Only after a completed trick, at most once every few tricks, never two in a row from the
 * same seat, and never while it is the human's turn to act — a bubble that appears over the
 * card you are about to play is an interruption, not atmosphere.
 */

//: `say` is the dialect phrase; `why` is a key into i18n so the gloss translates.
//:
//: The first ten are **documented** folk sayings — the ones jassverzeichnis.ch collects and
//: Swiss papers quote. The remaining forty are ordinary table phrases written in the same
//: idiom: Jass vocabulary (Stöck, Wys, Stich, Puur, Näll, schmiere, schiebe) in the shape a
//: table actually uses it. They are not claimed as documented proverbs, and they are not a
//: copy of anyone's collection.
export const SAYINGS = [
  // Documented folk sayings.
  { say: "Ufem Tisch müend si verrecke", why: "talk.why.table" },
  { say: "Do chasch de Chnächt schicke", why: "talk.why.chnacht" },
  { say: "Meh gschnorred als gjasset", why: "talk.why.talk" },
  { say: "Du seisch dinere Grossmueter no Bock", why: "talk.why.bock" },
  { say: "Du bisch en Wändlijasser", why: "talk.why.wandli" },
  { say: "Machsch s Chalb", why: "talk.why.chalb" },
  { say: "Ich ha Hälfercharte", why: "talk.why.helfer" },
  { say: "Zähner mached s Spiel verruckt", why: "talk.why.zehner" },
  { say: "Chasch go lerne mischle", why: "talk.why.mischle" },
  { say: "Mit dine Brättli baisch en Hasestall", why: "talk.why.bretli" },
  // Table phrases in the same idiom.
  { say: "Trumpf use, Bure zue", why: "talk.why.trumps" },
  { say: "Wer nöd stichlet, gwinnt nöd", why: "talk.why.stich" },
  { say: "S Blatt isch wies isch", why: "talk.why.hand" },
  { say: "Zerscht dänke, dänn läge", why: "talk.why.think" },
  { say: "Es Ass gaht nie verlore", why: "talk.why.ace" },
  { say: "Emol gwünne, emol lehre", why: "talk.why.lose" },
  { say: "Guet gmischlet isch halb gwunne", why: "talk.why.shuffle" },
  { say: "De Puur schticht ellei", why: "talk.why.puur" },
  { say: "Stöck, Wys, Stich", why: "talk.why.stoeck" },
  { say: "Undenufe isch au es Spiel", why: "talk.why.under" },
  { say: "Obenabe für d Ässe", why: "talk.why.oben" },
  { say: "Schmier mer eis", why: "talk.why.schmier" },
  { say: "Wer schiebt, het nüt", why: "talk.why.schiebe" },
  { say: "De Näll macht de Underschid", why: "talk.why.nell" },
  { say: "Nöd zünde, wenn s brennt", why: "talk.why.zuende" },
  { say: "Es git kei schlechti Charte, nur schlechti Spieler", why: "talk.why.nobad" },
  { say: "Gschobe isch nöd gwunne", why: "talk.why.notyet" },
  { say: "Zwänzg isch au öppis", why: "talk.why.twenty" },
  { say: "Wer zellt, gwinnt", why: "talk.why.count" },
  { say: "Ohni Trumpf gaht nüt", why: "talk.why.notrump" },
  { say: "De Letscht macht föif", why: "talk.why.last" },
  { say: "Match isch Match", why: "talk.why.match" },
  { say: "Bi eus wird nöd gmotzt", why: "talk.why.motz" },
  { say: "De Tisch vergisst nüt", why: "talk.why.memory" },
  { say: "Wer lachet, het scho gwunne", why: "talk.why.laugh" },
  { say: "Chunnt Zit, chunnt Trumpf", why: "talk.why.patience" },
  { say: "Es Bäuerli chunnt sälte ellei", why: "talk.why.pair" },
  { say: "Wer wartet, verliert de Stich", why: "talk.why.wait" },
  { say: "Nöd jede Stich isch dine", why: "talk.why.notyours" },
  { say: "Mit em Ass fahrt mer nie schlecht", why: "talk.why.withace" },
  { say: "De Sächser tuet au sin Dienscht", why: "talk.why.six" },
  { say: "Jasse isch Chopfsach", why: "talk.why.head" },
  { say: "Wer schmiert, der fahrt", why: "talk.why.greasy" },
  { say: "S Glück sitzt immer gägenüber", why: "talk.why.luck" },
  { say: "Am Schluss zellt de Strich", why: "talk.why.stroke" },
  { say: "Wer stichlet, mues au zelle", why: "talk.why.payup" },
  { say: "Ei Charte, ei Entscheid", why: "talk.why.one" },
  { say: "D Hoffnig stirbt zletscht", why: "talk.why.hope" },
  { say: "Nach em Jass isch vor em Jass", why: "talk.why.again" },
  { say: "De Schtill gwinnt de Schtich", why: "talk.why.quiet" },
];

//: Tricks that must pass before anybody speaks again. Nine tricks a round, so this is
//: roughly one or two remarks per round — company, not a commentary track.
const COOLDOWN = 3;
//: Chance of speaking once the cooldown is up. With the cooldown this lands at roughly
//: **1.4 remarks per nine-trick round** — company, not a commentary track. Measured, not
//: guessed: at 0.45 it was 2.3 a round and started to feel like a chatbot.
const CHANCE = 0.28;

let lastTrick = -99;
let lastSeat = -1;
let recent = [];

/** Reset between rounds so a new deal does not inherit a cooldown or a repeat guard. */
export function resetTalk() {
  lastTrick = -99;
  lastSeat = -1;
  recent = [];
}

/**
 * A remark, or null. `trickNo` counts completed tricks so one trick yields one chance.
 *
 * `seats` are the seats that may speak — the caller passes the bots, never the human,
 * because putting words in the player's mouth is a different feature and a worse one.
 */
export function maybeSay(trickNo, seats, random = Math.random) {
  if (!seats.length || trickNo - lastTrick < COOLDOWN) return null;
  if (random() > CHANCE) return null;

  const pool = seats.filter((s) => s !== lastSeat);
  const seat = (pool.length ? pool : seats)[Math.floor(random() * (pool.length || seats.length))];

  // Do not repeat inside half the deck of sayings: hearing the same line twice in a round
  // is what makes a feature like this feel mechanical rather than lived-in.
  const fresh = SAYINGS.filter((s) => !recent.includes(s.say));
  const choice = (fresh.length ? fresh : SAYINGS)[
    Math.floor(random() * (fresh.length || SAYINGS.length))
  ];
  recent = [...recent, choice.say].slice(-Math.ceil(SAYINGS.length / 2));

  lastTrick = trickNo;
  lastSeat = seat;
  return { seat, ...choice };
}
