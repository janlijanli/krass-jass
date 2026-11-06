/* Jass-Sprüche: the table talking.
 *
 * A Jass table is not silent. Somebody comments on the trick, somebody quotes the same
 * proverb they quote every week, and the game has a rhythm the cards alone do not carry.
 * This is the smallest honest version of that: now and then, one of the three bots says
 * something — and what it says fits what just happened.
 *
 * # About the material
 *
 * See `docs/jass-sprueche.md` for every saying, what it means, when it is said and where
 * that comes from. In short: the first ten are **documented** folk sayings; their meanings
 * are the ones jassverzeichnis.ch/jass-spruch-zitate gives, and their triggers follow from
 * those meanings. The rest are ordinary table phrases in the same idiom, built from Jass
 * vocabulary the glossaries define (Puur, Näll, Stöck, schmiere, schiebe, Match, de Letscht).
 * They are not claimed as documented proverbs.
 *
 * They stay in dialect in every language the app speaks, for the same reason Weis, Stöck
 * and Obenabe do. The `why` line is translated, so a reader who does not have the dialect
 * still gets the joke.
 *
 * # When it fires
 *
 * Only in the pause after a completed trick (nobody is on turn then, the human included),
 * only about what the trick, the round or the table showed everyone, and rarely: each kind
 * of moment has its own chance, a few tricks must pass between remarks unless the moment is
 * a big one, and a saying is not heard again until a dozen others have been.
 *
 * # What it may look at
 *
 * Only the public view: the cards on the table, who took them, the contract, the declarer,
 * Weis and Stöck as they were shown, tricks won. A remark is atmosphere and must never say
 * anything about a card nobody has seen — so nothing here reads a hand.
 */

//: `say` is the dialect phrase; `why` is a key into i18n so the gloss translates.
//: `on` lists the moments it fits; `who` says which seat, relative to the moment's subject,
//: may say it: "self" (the subject), "partner", "team" (either), "opp" (an opponent of the
//: subject) or "any".
export const SAYINGS = [
  // Documented folk sayings (meanings: jassverzeichnis.ch/jass-spruch-zitate).
  { say: "Ufem Tisch müend si verrecke", why: "talk.why.table", on: ["stab"], who: "team" },
  { say: "Do chasch de Chnächt schicke", why: "talk.why.chnacht", on: ["streak", "match"], who: "team" },
  { say: "Meh gschnorred als gjasset", why: "talk.why.talk", on: ["weis_big"], who: "any" },
  { say: "Du seisch dinere Grossmueter no Bock", why: "talk.why.bock", on: ["bock_beaten"], who: "opp" },
  { say: "Du bisch en Wändlijasser", why: "talk.why.wandli", on: ["wandli"], who: "opp" },
  { say: "Machsch s Chalb", why: "talk.why.chalb", on: ["small_win"], who: "opp" },
  { say: "Ich ha Hälfercharte", why: "talk.why.helfer", on: ["shoved"], who: "self" },
  { say: "Zähner mached s Spiel verruckt", why: "talk.why.zehner", on: ["ten_drew_trump"], who: "self" },
  { say: "Chasch go lerne mischle", why: "talk.why.mischle", on: ["matched", "round_crushed"], who: "team" },
  { say: "Mit dine Brättli baisch en Hasestall", why: "talk.why.bretli", on: ["dry"], who: "partner" },
  // Table phrases in the same idiom, each tied to the moment its vocabulary names.
  { say: "Trumpf use, Bure zue", why: "talk.why.trumps", on: ["trump_lead"], who: "partner" },
  { say: "De Puur schticht ellei", why: "talk.why.puur", on: ["puur"], who: "self" },
  { say: "De Näll macht de Underschid", why: "talk.why.nell", on: ["nell"], who: "team" },
  { say: "Es Ass gaht nie verlore", why: "talk.why.ace", on: ["ace"], who: "self" },
  { say: "Mit em Ass fahrt mer nie schlecht", why: "talk.why.withace", on: ["ace"], who: "team" },
  { say: "De Sächser tuet au sin Dienscht", why: "talk.why.six", on: ["six"], who: "self" },
  { say: "Es Bäuerli chunnt sälte ellei", why: "talk.why.pair", on: ["two_jacks"], who: "any" },
  { say: "Ohni Trumpf gaht nüt", why: "talk.why.notrump", on: ["stab"], who: "self" },
  { say: "Nöd jede Stich isch dine", why: "talk.why.notyours", on: ["stab", "bock_beaten"], who: "team" },
  { say: "Wer schmiert, der fahrt", why: "talk.why.greasy", on: ["smear"], who: "self" },
  { say: "Schmier mer eis", why: "talk.why.schmier", on: ["bare"], who: "self" },
  { say: "Wer stichlet, mues au zelle", why: "talk.why.payup", on: ["big"], who: "self" },
  { say: "De Schtill gwinnt de Schtich", why: "talk.why.quiet", on: ["first_late"], who: "partner" },
  { say: "Stöck, Wys, Stich", why: "talk.why.stoeck", on: ["stoeck"], who: "self" },
  { say: "Zwänzg isch au öppis", why: "talk.why.twenty", on: ["stoeck", "weis20"], who: "team" },
  { say: "Wer schiebt, het nüt", why: "talk.why.schiebe", on: ["shoved"], who: "opp" },
  { say: "Gschobe isch nöd gwunne", why: "talk.why.notyet", on: ["shoved"], who: "opp" },
  { say: "Obenabe für d Ässe", why: "talk.why.oben", on: ["obenabe"], who: "team" },
  { say: "Undenufe isch au es Spiel", why: "talk.why.under", on: ["undenufe"], who: "team" },
  { say: "De Letscht macht föif", why: "talk.why.last", on: ["last"], who: "self" },
  { say: "Match isch Match", why: "talk.why.match", on: ["match"], who: "team" },
  { say: "Emol gwünne, emol lehre", why: "talk.why.lose", on: ["round_lost"], who: "team" },
  { say: "D Hoffnig stirbt zletscht", why: "talk.why.hope", on: ["round_lost", "dry"], who: "team" },
  { say: "S Glück sitzt immer gägenüber", why: "talk.why.luck", on: ["round_lost"], who: "team" },
  { say: "Es git kei schlechti Charte, nur schlechti Spieler", why: "talk.why.nobad", on: ["round_lost"], who: "opp" },
  { say: "Bi eus wird nöd gmotzt", why: "talk.why.motz", on: ["round_crushed"], who: "opp" },
  { say: "Wer lachet, het scho gwunne", why: "talk.why.laugh", on: ["round_won"], who: "team" },
  { say: "Wer zellt, gwinnt", why: "talk.why.count", on: ["round_won"], who: "team" },
  { say: "Am Schluss zellt de Strich", why: "talk.why.stroke", on: ["round_won"], who: "opp" },
  { say: "Nach em Jass isch vor em Jass", why: "talk.why.again", on: ["round_won", "round_lost"], who: "any" },
  // General chatter: fits no particular moment, so it only ever fills a quiet stretch.
  { say: "Wer nöd stichlet, gwinnt nöd", why: "talk.why.stich", on: ["quiet"], who: "any" },
  { say: "S Blatt isch wies isch", why: "talk.why.hand", on: ["quiet"], who: "any" },
  { say: "Zerscht dänke, dänn läge", why: "talk.why.think", on: ["quiet"], who: "any" },
  { say: "Guet gmischlet isch halb gwunne", why: "talk.why.shuffle", on: ["quiet"], who: "any" },
  { say: "Nöd zünde, wenn s brennt", why: "talk.why.zuende", on: ["quiet"], who: "any" },
  { say: "De Tisch vergisst nüt", why: "talk.why.memory", on: ["quiet"], who: "any" },
  { say: "Chunnt Zit, chunnt Trumpf", why: "talk.why.patience", on: ["quiet"], who: "any" },
  { say: "Wer wartet, verliert de Stich", why: "talk.why.wait", on: ["quiet"], who: "any" },
  { say: "Jasse isch Chopfsach", why: "talk.why.head", on: ["quiet"], who: "any" },
  { say: "Ei Charte, ei Entscheid", why: "talk.why.one", on: ["quiet"], who: "any" },
];

//: How likely a remark is when this moment happens, before the cooldown. The rare, loud
//: moments of a round nearly always get one; the ordinary ones only now and then, which is
//: what keeps this at one or two remarks a round rather than a commentary track.
export const CHANCE = {
  match: 0.9, matched: 0.9, round_crushed: 0.6, weis_big: 0.6, stoeck: 0.5, shoved: 0.3,
  stab: 0.3, ten_drew_trump: 0.45, bock_beaten: 0.35, wandli: 0.35, dry: 0.4,
  round_lost: 0.3, round_won: 0.3, last: 0.2, puur: 0.25, nell: 0.25, big: 0.25,
  smear: 0.25, weis20: 0.25, obenabe: 0.2, undenufe: 0.2, streak: 0.3,
  first_late: 0.3, small_win: 0.2, two_jacks: 0.15, six: 0.2, ace: 0.1, bare: 0.1,
  trump_lead: 0.1, quiet: 0.06,
};
//: Moments this loud may speak through the cooldown.
const LOUD = 0.6;
//: Tricks that must pass after a remark before an ordinary moment gets another one.
const COOLDOWN = 3;
//: A saying is not heard again until this many others have been.
const NO_REPEAT = 12;

const SUIT_OF = { DIAMONDS: "D", HEARTS: "H", SPADES: "S", CLUBS: "C" };
//: Card points by rank, as a trick is counted. Only used to tell a fat trick from a thin
//: one and a lost round from a close one, so a Coiffeur extra row is counted as its trick's
//: own contract.
const PLAIN = { A: 11, T: 10, K: 4, Q: 3, J: 2 };
const TRUMP = { J: 20, 9: 14, A: 11, T: 10, K: 4, Q: 3 };
const UNDEN = { 6: 11, T: 10, 8: 8, K: 4, Q: 3, J: 2 };

function points(card, contract) {
  const [suit, rank] = card;
  if (contract === "OBENABE") return rank === "8" ? 8 : PLAIN[rank] || 0;
  if (contract === "UNDENUFE") return UNDEN[rank] || 0;
  if (SUIT_OF[contract] === suit) return TRUMP[rank] || 0;
  return PLAIN[rank] || 0;
}

const team = (seat) => seat % 2;
const partnerOf = (seat) => (seat + 2) % 4;

/** The seats that may say a saying about a moment whose subject is `seat`. */
function speakers(who, seat) {
  if (who === "self") return [seat];
  if (who === "partner") return [partnerOf(seat)];
  if (who === "team") return [seat, partnerOf(seat)];
  if (who === "opp") return [(seat + 1) % 4, (seat + 3) % 4];
  return [0, 1, 2, 3];
}

/** What the table has seen this round. All of it public: the tricks were played face up. */
export function newMemory(id) {
  return { id, seen: new Set(), points: [0, 0], leads: {}, firsts: {},
           streak: 0, streakTeam: -1, complete: true };
}

let memory = null;
let tricksSeen = 0;    // completed tricks seen, across rounds
let lastSpoke = -99;   // `tricksSeen` at the last remark
let lastSeat = -1;
let recent = [];

/** Reset between rounds. The repeat guard survives: the same line twice in two rounds is
 *  still the same line twice. */
export function resetTalk() {
  memory = null;
}

/**
 * What the finished trick on the table showed everyone: a list of `{ tag, seat }` moments,
 * `seat` being whose moment it is (for a team moment, a seat of that team). `memory` has
 * already counted this trick's points. Exported for the tests.
 */
export function moments(view, memory) {
  const out = [];
  const add = (tag, seat) => out.push({ tag, seat });
  const trick = view.trick || [];
  const winner = view.trick_winner;
  const contract = view.contract;
  if (trick.length !== 4 || winner === null || winner === undefined) return out;

  const tw = view.tricks_won || [0, 0];
  const number = tw[0] + tw[1];
  const trumpSuit = SUIT_OF[contract];
  const lead = trick[0];
  const led = lead.card[0];
  const won = trick.find((p) => p.seat === winner);
  let worth = trick.reduce((sum, p) => sum + points(p.card, contract), 0);
  if (number === 9) worth += 5;

  // The trick itself.
  if (trumpSuit && won.card[0] === trumpSuit && led !== trumpSuit) {
    // Stabbed: somebody on the other side had put a high card of the suit led into it.
    const victim = trick.find(
      (p) => team(p.seat) !== team(winner) && p.card[0] === led && "AT".includes(p.card[1])
    );
    if (victim) add("stab", winner);
    if (lead.card[1] === "T" && team(lead.seat) !== team(winner)) add("ten_drew_trump", lead.seat);
  }
  // The Bock — the best card of a suit, which a player leads as a sure winner.
  const bockRank = contract === "UNDENUFE" ? "6" : "A";
  if (lead.card[1] === bockRank && led !== trumpSuit && team(winner) !== team(lead.seat)) {
    add("bock_beaten", lead.seat);
  }
  if (trumpSuit && won.card === trumpSuit + "J") add("puur", winner);
  if (trumpSuit && won.card === trumpSuit + "9") add("nell", winner);
  if (won.card[1] === "A" && won.card[0] !== trumpSuit && contract !== "UNDENUFE") add("ace", winner);
  if (won.card[1] === "6" && contract !== "UNDENUFE") add("six", winner);
  if ("678".includes(won.card[1]) && won.card[0] !== trumpSuit && contract !== "UNDENUFE" && worth >= 15) {
    add("small_win", winner);
  }
  if (trick.filter((p) => p.card[1] === "J").length >= 2) add("two_jacks", winner);
  if (worth >= 35) add("big", winner);

  // What the winner's partner gave, once the winner's card was down.
  const order = trick.map((p) => p.seat);
  const partner = trick.find((p) => p.seat === partnerOf(winner));
  const after = order.indexOf(partner.seat) > order.indexOf(winner);
  if (after && partner.card[0] !== trumpSuit && "AT".includes(partner.card[1])) {
    add("smear", partner.seat);
  } else if (after && points(partner.card, contract) === 0 && worth <= 6) {
    add("bare", winner);
  }
  if (trumpSuit && led === trumpSuit && team(lead.seat) === team(view.declarer) && number <= 3) {
    add("trump_lead", lead.seat);
  }

  if (memory) {
    // The third time one seat leads the same suit this round.
    const key = `${lead.seat}${led}`;
    memory.leads[key] = (memory.leads[key] || 0) + 1;
    if (memory.leads[key] === 3) add("wandli", lead.seat);
    // Four tricks running to one side.
    memory.streak = memory.streakTeam === team(winner) ? memory.streak + 1 : 1;
    memory.streakTeam = team(winner);
    if (memory.streak === 4 && number < 9) add("streak", winner);
    // A side's first trick, late in the round.
    if (memory.firsts[team(winner)] === undefined) {
      memory.firsts[team(winner)] = number;
      if (number >= 5) add("first_late", winner);
    }
  }
  for (const t of [0, 1]) {
    if (number === 6 && tw[t] === 0) add("dry", t);   // seat t is on team t
  }

  // The first trick: the contract, a shove, the Weis that has been shown.
  if (number === 1) {
    // In the Schieber the forehand leads the first trick, so a declarer who is the
    // forehand's partner was shoved to. Public: the shove was said aloud.
    if (view.mode === "schieber" && view.declarer === partnerOf(lead.seat)) add("shoved", lead.seat);
    if (contract === "OBENABE") add("obenabe", view.declarer);
    if (contract === "UNDENUFE") add("undenufe", view.declarer);
    const shown = (view.weis || []).filter((w) => w.winner);
    const total = shown.reduce((sum, w) => sum + w.points, 0);
    if (total >= 100) add("weis_big", shown[0].seat);
    else if (total === 20) add("weis20", shown[0].seat);
  }
  for (const s of view.stoeck || []) add("stoeck", s.seat);

  // The end of the round.
  if (number === 9) {
    add("last", winner);
    if (tw[0] === 9 || tw[1] === 9) {
      add("match", winner);
      add("matched", (winner + 1) % 4);
    } else if (memory && memory.complete) {
      const pts = memory.points;
      const loser = pts[0] < pts[1] ? 0 : 1;
      if (pts[loser] <= 30) add("round_crushed", loser);
      else if (pts[loser] < 70) {
        add("round_lost", loser);
        add("round_won", 1 - loser);
      }
    }
  }
  if (!out.length) add("quiet", winner);
  return out;
}

/**
 * A remark about the finished trick on the table, or null.
 *
 * Call it whenever a view with `trick_complete` arrives; each trick yields one chance however
 * often it is called. `seats` are the seats that may speak — the bots, never the human,
 * because putting words in the player's mouth is a different feature and a worse one.
 */
export function maybeSay(view, seats, random = Math.random) {
  if (!view || !view.trick_complete || !seats.length || !view.trick?.length) return null;
  const tw = view.tricks_won || [0, 0];
  const number = tw[0] + tw[1];
  if (!memory || memory.id !== view.round) {
    memory = newMemory(view.round);
    // Joined mid-round (a reload): the totals of the round are not ours to judge.
    if (number !== 1) memory.complete = false;
  }
  if (memory.seen.has(number)) return null;
  if (number !== memory.seen.size + 1) memory.complete = false;
  memory.seen.add(number);
  tricksSeen += 1;
  const worth = view.trick.reduce((sum, p) => sum + points(p.card, view.contract), 0);
  memory.points[team(view.trick_winner)] += worth + (number === 9 ? 5 : 0);

  let found = moments(view, memory);
  // Coiffeur Misère turns the reward round: taking tricks is the bad news there, so the
  // trick-by-trick boasts would read backwards. Keep to what is not a boast.
  if (view.coiffeur?.schedule?.misere) {
    found = found.filter((m) => ["stoeck", "weis_big", "quiet"].includes(m.tag));
  }

  const quietFor = tricksSeen - lastSpoke;
  const candidates = [];
  for (const m of found) {
    const chance = CHANCE[m.tag] ?? 0;
    if (chance < LOUD && quietFor <= COOLDOWN) continue;
    for (const s of SAYINGS) {
      if (!s.on.includes(m.tag) || recent.includes(s.say)) continue;
      for (const seat of speakers(s.who, m.seat)) {
        if (seats.includes(seat)) candidates.push({ m, s, seat, chance });
      }
    }
  }
  if (!candidates.length) return null;

  // The loudest moment speaks; a dice roll decides whether it speaks at all.
  const top = Math.max(...candidates.map((c) => c.chance));
  if (random() >= top) return null;
  let pool = candidates.filter((c) => c.chance === top);
  const others = pool.filter((c) => c.seat !== lastSeat);
  if (others.length) pool = others;
  const pick = pool[Math.floor(random() * pool.length)];

  recent = [...recent, pick.s.say].slice(-NO_REPEAT);
  lastSpoke = tricksSeen;
  lastSeat = pick.seat;
  return { seat: pick.seat, say: pick.s.say, why: pick.s.why, moment: pick.m.tag };
}
