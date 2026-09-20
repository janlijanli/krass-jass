/* Controller for the serverless build.
 *
 * Everything the web service used to do — drive the turn loop, pace the bots, hold a
 * finished trick until it is tapped — happens here instead. The engine is the same Rust
 * crate the server runs, compiled to wasm.
 *
 * One honest difference from the hosted version: all four hands are in this tab's memory.
 * The engine still only *reports* your own, so the bots cannot cheat, but a determined
 * human can read the others out of devtools. That is a fair trade for a single-player game
 * with no server; it is why multiplayer stays server-side.
 */

import { loadEngine, CARD_INDEX } from "./engine.js";
import { render, setSender, speak } from "./render.js";
import { initMenu, adviceOn, talkOn, beliefsOn } from "./menu.js";
import { maybeSay, resetTalk } from "./talk.js";

const HUMAN_SEAT = 0;
//: Only the bots talk. Putting words in the player's mouth is a different feature.
const BOT_SEATS = [1, 2, 3];
// 153,600 iterations — `docs/measurements.md` §3b. §3 measured this search saturating at
// 2,400 and that finding does not transfer here: it was taken under EVAL, where Weis does
// not exist, so the belief constraints that make extra worlds worth drawing were not there
// to sharpen. Under HOUSE the same 64x is worth +0.56 of a round's share over 3,000 deals.
// 256x buys nothing more and is visibly slower, so this is the top of the curve, not a
// ceiling imposed by patience.
const DETERMINIZATIONS = 40;
const ITERATIONS = 3840;
// The search used to answer in milliseconds, which reads as a spreadsheet rather than an
// opponent. It now takes a good fraction of a second, and that is *real* thinking — so the
// pause below is what is left of the target after the search, never added on top of it.
const THINK_MIN = 550;
const THINK_MAX = 1500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const settings = () => {
  const form = document.getElementById("mode-settings");
  const value = (name) => form.querySelector(`input[name="${name}"]:checked`)?.value;
  return {
    mode: value("mode") === "schieber" ? "schieber" : "sidi",
    target: Number(value("target") || 1000),
    weis: value("weis") !== "off",
    multipliers: ["diamonds", "hearts", "spades", "clubs", "obenabe", "undenufe"].map(
      (k) => Number(value(`mult_${k}`) || 1)
    ),
  };
};

const engine = await loadEngine();
let handle = null;
let acked = 0;
let busy = false;

// Sidi: the last knock the player let pass, as "round|calls", so each opposing bid asks once.
let knockDeclined = null;

/** Sidi: an opponent has just bid and the player may knock before anyone else speaks — the
 *  same rule as `Table.knock_offer` in web/app.py, since a double may come at any time. */
function knockOffer(v) {
  if (v.mode !== "sidi" || v.phase !== "bidding" || !v.auction?.length) return null;
  const last = v.auction[v.auction.length - 1];
  const key = `${v.round}|${v.auction.length}`;
  const opponent = (last.seat - HUMAN_SEAT + 4) % 2 === 1;
  if (["PASS", "DOUBLE"].includes(last.call) || !opponent || v.to_act === HUMAN_SEAT) return null;
  if (v.auction.some((c) => c.call === "DOUBLE") || knockDeclined === key) return null;
  return { seat: last.seat, call: last.call, key };
}

function view() {
  const v = engine.view(handle, HUMAN_SEAT, acked);
  v.knock = knockOffer(v);
  // Test mode: what a bot on this seat believes about the other three hands. Computed here
  // rather than sent, because here the engine is in the tab.
  v.beliefs = beliefsOn() && v.phase === "playing" ? engine.beliefs(handle, HUMAN_SEAT) : null;
  return v;
}

/* Advice mode.
 *
 * A fourth bot, run on the human's own seat with the same budget and the same search the
 * other three use — so it sees exactly what you see and guesses like they do.
 *
 * At 153,600 iterations that is most of a second, which must not be spent on the main
 * thread before the hand is on screen: the switch would look like the app freezing. So the
 * table renders first, the search is scheduled after it, and the badges arrive a moment
 * later. Cached per position, because the answer cannot change until a card is played.
 */
let adviceKey = null;
let advice = [];
let advicePending = false;

const wantsAdvice = (v) =>
  adviceOn() &&
  v.phase === "playing" &&
  v.to_act === HUMAN_SEAT &&
  // One legal card is not advice, and `bot_rank` reports that case as no moves at all.
  (v.legal?.length ?? 0) >= 2;

const positionKey = (v) =>
  `${v.round}|${v.hand.join("")}|${v.trick.map((c) => c.card).join("")}`;

function draw() {
  const v = view();
  const key = wantsAdvice(v) ? positionKey(v) : null;
  if (key === null) {
    adviceKey = null;
    advice = [];
  }
  v.advice = key !== null && key === adviceKey ? advice : [];
  render(v);

  if (key === null || key === adviceKey || advicePending) return;
  advicePending = true;
  // A macrotask, not a microtask: the browser has to get a paint in between, and a promise
  // continuation would run before one.
  setTimeout(() => {
    try {
      // The decision seed this seat would really have used, so the advice is the move that
      // seat would have played rather than a second, differently-seeded search.
      const seed = engine.decisionSeed(handle, HUMAN_SEAT, Math.max(0, v.round));
      advice = engine
        .botRank(handle, HUMAN_SEAT, DETERMINIZATIONS, ITERATIONS, seed)
        .moves.map((m) => m.card);
      adviceKey = key;
    } finally {
      advicePending = false;
    }
    draw();
  }, 0);
}

function newGame() {
  if (handle !== null) engine.free(handle);
  acked = 0;
  knockDeclined = null;
  botsKnockedKey = null;
  handle = engine.newGame({ seed: Math.floor(Math.random() * 2 ** 48), ...settings() });
  draw();
  drive();
}

// Sidi: the bid the bots have already been asked about, so each bid asks once.
let botsKnockedKey = null;

/** Every bot opposing the standing bid knocks or not, the moment the bid is made — the rule
 *  the player plays by, so the bots play by it too. Returns true if one of them doubled. */
async function botsKnock(v) {
  if (v.mode !== "sidi" || v.phase !== "bidding" || !v.auction?.length) return false;
  const bids = v.auction.filter((c) => !["PASS", "DOUBLE"].includes(c.call));
  const key = `${v.round}|${v.auction.length}`;
  if (!bids.length || v.auction.some((c) => c.call === "DOUBLE") || botsKnockedKey === key) return false;
  botsKnockedKey = key;
  const bidder = bids[bids.length - 1].seat;
  for (const step of [1, 3]) {
    const seat = (bidder + step) % 4;
    if (seat === HUMAN_SEAT || (seat - bidder + 4) % 2 !== 1) continue;
    if (engine.botKnock(handle, seat)) {
      await sleep(300 + Math.random() * 300);
      engine.call(handle, seat, "DOUBLE");
      return true;
    }
  }
  return false;
}

/** Let the bots act until it is the human's turn again. */
async function drive() {
  if (busy) return;
  busy = true;
  try {
    for (let guard = 0; guard < 500; guard++) {
      const v = view();
      if (v.trick_complete) {
        // A remark belongs to the pause after a trick, when nobody is waiting on you.
        // Driven from here rather than from render(), because a redraw must not repeat it.
        if (talkOn()) speak(maybeSay(acked, BOT_SEATS));
        break;                                // waiting on a tap
      }
      if (v.to_act === null || v.to_act === HUMAN_SEAT) break;
      if (v.knock) break;                     // the player is being asked whether to knock
      if (await botsKnock(v)) { draw(); continue; }
      const seat = v.to_act;
      const trick = Math.max(0, v.round);

      if (v.phase === "bidding" && v.mode === "sidi") {
        await sleep(500 + Math.random() * 600);
        // A bot's call is validated like its cards; a pass is always legal.
        if (!engine.call(handle, seat, engine.botCall(handle, seat))) engine.call(handle, seat, "PASS");
      } else if (v.phase === "doubling") {
        await sleep(400 + Math.random() * 400);
        engine.double(handle, seat, engine.botDouble(handle, seat));
      } else if (v.phase === "bidding") {
        await sleep(400 + Math.random() * 500);
        engine.bid(handle, seat, engine.botBid(handle, seat));
      } else if (v.phase === "weis") {
        await sleep(200 + Math.random() * 250);
        engine.chooseWeis(handle, seat, true);   // bots always announce
      } else if (v.phase === "playing") {
        const seed = engine.decisionSeed(handle, seat, trick);
        const started = performance.now();
        const card = engine.botPlay(handle, seat, DETERMINIZATIONS, ITERATIONS, seed);
        if (card < 0) break;
        // Pace by how much of a decision it was: a forced card comes back fast.
        const choices = view().legal.length || 4;
        const span = Math.min(1, Math.max(0, choices - 1) / 6);
        const target = (THINK_MIN + span * (THINK_MAX - THINK_MIN)) * (0.75 + Math.random() * 0.25);
        // Subtract what the search really took. The pause exists so a bot does not answer
        // instantly; time spent actually thinking serves that purpose already, and adding
        // the two would make a stronger bot feel like a slower one for no reason.
        await sleep(Math.max(0, target - (performance.now() - started)));
        engine.play(handle, seat, card);
      } else {
        break;
      }
      draw();
    }
  } finally {
    busy = false;
  }
  draw();
}

setSender((message) => {
  if (handle === null) return;
  switch (message.type) {
    case "bid":
      if (view().mode === "sidi") engine.call(handle, HUMAN_SEAT, message.action);
      else engine.bid(handle, HUMAN_SEAT, message.action === "SHOVE" ? -1 : CONTRACTS[message.action]);
      break;
    case "double": {
      const v = view();
      if (v.phase === "doubling") engine.double(handle, HUMAN_SEAT, !!message.double);
      else if (v.knock && message.double) engine.call(handle, HUMAN_SEAT, "DOUBLE");
      else if (v.knock) knockDeclined = v.knock.key;
      break;
    }
    case "weis":
      engine.chooseWeis(handle, HUMAN_SEAT, !!message.announce);
      break;
    case "play":
      engine.play(handle, HUMAN_SEAT, CARD_INDEX(message.card));
      break;
    case "ack_trick":
      acked = Math.max(acked, ackTarget());
      break;
    case "next_round":
      engine.nextRound(handle);
      acked = 0;
      resetTalk();        // a new deal starts the table's conversation fresh
      break;
    default:
      return;
  }
  draw();
  drive();
});

const CONTRACTS = { DIAMONDS: 0, HEARTS: 1, SPADES: 2, CLUBS: 3, OBENABE: 4, UNDENUFE: 5 };

function ackTarget() {
  // The view hides the count, so infer it: acknowledging clears whatever is on the table.
  const v = view();
  return v.trick_complete ? acked + 1 : acked;
}

initMenu({
  measurementsUrl: "measurements.json",
  onNewGame: newGame,
  // The chrome is static text, the table is not — redraw it in the new language too.
  onLanguageChange: () => draw(),
  onAdviceChange: () => draw(),
  onTalkChange: () => {},
  onBeliefsChange: () => draw(),
});

newGame();
