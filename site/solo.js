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
import { render, setSender } from "./render.js";

const HUMAN_SEAT = 0;
// docs/measurements.md §3: indistinguishable from 800,000 iterations, ~2 ms in wasm.
const DETERMINIZATIONS = 40;
const ITERATIONS = 60;
// The search answers in milliseconds, which reads as a spreadsheet rather than an opponent.
const THINK_MIN = 550;
const THINK_MAX = 1500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const settings = () => {
  const form = document.querySelector(".menu");
  const value = (name) => form.querySelector(`input[name="${name}"]:checked`)?.value;
  return {
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

function view() {
  return engine.view(handle, HUMAN_SEAT, acked);
}

function draw() {
  render(view());
}

function newGame() {
  if (handle !== null) engine.free(handle);
  acked = 0;
  handle = engine.newGame({ seed: Math.floor(Math.random() * 2 ** 48), ...settings() });
  draw();
  drive();
}

/** Let the bots act until it is the human's turn again. */
async function drive() {
  if (busy) return;
  busy = true;
  try {
    for (let guard = 0; guard < 500; guard++) {
      const v = view();
      if (v.trick_complete) break;            // waiting on a tap
      if (v.to_act === null || v.to_act === HUMAN_SEAT) break;
      const seat = v.to_act;
      const trick = Math.max(0, v.round);

      if (v.phase === "bidding") {
        await sleep(400 + Math.random() * 500);
        engine.bid(handle, seat, engine.botBid(handle, seat));
      } else if (v.phase === "weis") {
        await sleep(200 + Math.random() * 250);
        engine.chooseWeis(handle, seat, true);   // bots always announce
      } else if (v.phase === "playing") {
        const seed = engine.decisionSeed(handle, seat, trick);
        const card = engine.botPlay(handle, seat, DETERMINIZATIONS, ITERATIONS, seed);
        if (card < 0) break;
        // Pace by how much of a decision it was: a forced card comes back fast.
        const choices = view().legal.length || 4;
        const span = Math.min(1, Math.max(0, choices - 1) / 6);
        await sleep((THINK_MIN + span * (THINK_MAX - THINK_MIN)) * (0.75 + Math.random() * 0.25));
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
      engine.bid(handle, HUMAN_SEAT, message.action === "SHOVE" ? -1 : CONTRACTS[message.action]);
      break;
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

document.querySelector(".menu").addEventListener("submit", (event) => {
  event.preventDefault();
  document.getElementById("menu").hidden = true;
  newGame();
});

newGame();
