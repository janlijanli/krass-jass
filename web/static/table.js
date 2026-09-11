/* Client. Holds a view, never a source of truth.
 *
 * Everything on screen is a fold over the event stream plus the derived `view` frame the
 * server sends after it. The client never decides whether a card is legal, whose turn it is
 * or what a trick is worth — it asks, and it renders the answer (docs/webapp-plan.md §1).
 */

import { cardFace, SUIT_GLYPHS, SUIT_IS_RED } from "./cards.js";
import { drawTafel } from "./tafel.js";

const MEASUREMENTS_URL = "/static/measurements.json";

const mySeat = Number(document.body.dataset.seat);
const el = {
  hand: document.getElementById("hand"),
  trick: document.getElementById("trick"),
  bidding: document.getElementById("bidding"),
  weis: document.getElementById("weis"),
  weisPrompt: document.getElementById("weis-prompt"),
  weisPoints: document.getElementById("weis-points"),
  scorecard: document.getElementById("scorecard"),
  scRows: document.getElementById("sc-rows"),
  scTitle: document.getElementById("sc-title"),
  scContract: document.getElementById("sc-contract"),
  scContinue: document.getElementById("sc-continue"),
  shove: document.getElementById("shove"),
  status: document.getElementById("status"),
  banner: document.getElementById("banner"),
  contract: document.getElementById("contract"),
  round: document.getElementById("round"),
  scoreUs: document.getElementById("score-us"),
  scoreThem: document.getElementById("score-them"),
  taken: document.getElementById("taken"),
  tafel: document.getElementById("tafel"),
  tafelSlate: document.getElementById("tafel-slate"),
};

let lifted = null;
let lastView = { seat: 0, scores: [0, 0] };
let socket = null;

function cardNode(code) {
  const node = document.createElement("div");
  node.className = "card" + (SUIT_IS_RED[code[0]] ? " red" : "");
  node.dataset.card = code;
  node.innerHTML = cardFace(code);
  return node;
}

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
}

/** Small element helper. Deliberately local: about.js has its own, and importing across for
 *  four lines would couple the game screen to the documentation panel. */
function html(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

/* The Jasstafel — the board on the wall.
 *
 * Rounds are recorded here as they finish rather than asked of the engine, because both
 * builds already deliver the same scorecard and neither keeps a history. Accumulating it
 * client-side means one implementation instead of two.
 */
const board = { rounds: [], target: null };

function recordRound(view) {
  const card = view.scorecard;
  if (!card) return;
  const last = board.rounds[board.rounds.length - 1];
  if (last && last.round === card.round) return;   // the same scorecard, shown again
  board.rounds.push({
    round: card.round,
    contract: card.contract,
    multiplier: card.multiplier,
    points: card.round_total.slice(),
    totals: card.scores.slice(),
  });
}

function renderTafel(view) {
  const mine = view.seat % 2;
  const scores = [view.scores[mine], view.scores[1 - mine]];
  const slate = el.tafelSlate;
  slate.replaceChildren();

  // Read the target off the view rather than a remembered copy — one less piece of state to
  // be stale, and the view always has it.
  drawTafel(slate, scores, { target: view.target ?? board.target, rounds: board.rounds });

  // What the marks mean, because a notation nobody can read is decoration.
  const legend = document.createElement("p");
  legend.className = "tafel-legend";
  legend.innerHTML =
    "strokes by band &nbsp;·&nbsp; <b>X</b> 1000 &nbsp;·&nbsp; <b>V</b> 500 &nbsp;·&nbsp; " +
    "the rest written out";
  slate.append(legend);
}

const openTafel = () => {
  renderTafel(lastView);
  el.tafel.hidden = false;
};
const closeTafel = () => { el.tafel.hidden = true; };

document.getElementById("scoreboard").addEventListener("click", openTafel);
document.getElementById("scoreboard").addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openTafel(); }
});
document.getElementById("tafel-x").addEventListener("click", closeTafel);
el.tafel.addEventListener("click", (e) => { if (e.target === el.tafel) closeTafel(); });

const CONTRACT_PIPS = { DIAMONDS: "♦", HEARTS: "♥", SPADES: "♠", CLUBS: "♣" };

function renderContract(contract, multiplier) {
  // Always visible while a contract is live — you cannot judge a card without knowing
  // whether you are in trumps, Obenabe or Undenufe.
  if (!contract) {
    el.contract.className = "contract none";
    el.contract.textContent = "—";
    return;
  }
  el.contract.className = "contract";
  const pip = CONTRACT_PIPS[contract];
  const name = contract[0] + contract.slice(1).toLowerCase();
  const red = contract === "HEARTS" || contract === "DIAMONDS";
  el.contract.innerHTML =
    (pip ? `<span class="pip${red ? " red" : ""}">${pip}</span>` : "") +
    `<span>${pip ? name : contract[0] + contract.slice(1).toLowerCase()}</span>` +
    (multiplier ? `<span class="mult">×${multiplier}</span>` : "");
}

function renderHand(view) {
  const legal = new Set(view.legal);
  const myTurn = view.to_act === view.seat && view.phase === "playing";
  el.hand.replaceChildren();

  view.hand.forEach((code, i) => {
    const node = cardNode(code);
    if (code === view.puur) node.classList.add("puur");
    // Fan: rotate about a point below the card so the arc reads as held cards.
    const spread = Math.min(4, 26 / Math.max(view.hand.length, 1));
    node.style.transform = `rotate(${(i - (view.hand.length - 1) / 2) * spread}deg)`;
    if (myTurn && !legal.has(code)) node.classList.add("illegal");

    node.addEventListener("click", () => {
      if (!myTurn || !legal.has(code)) return;
      // Two taps: the first lifts so you can see what you picked on a small screen,
      // the second commits. Prevents fat-finger plays, which are unrecoverable.
      if (lifted === code) {
        node.classList.add("played");
        send({ type: "play", card: code });
        lifted = null;
      } else {
        el.hand.querySelectorAll(".lifted").forEach((n) => n.classList.remove("lifted"));
        node.classList.add("lifted");
        lifted = code;
      }
    });
    el.hand.appendChild(node);
  });
}

function renderTrick(view) {
  el.trick.replaceChildren();
  // Swiss Jass runs anticlockwise, so rel 1 (next to play) sits to your right. The CSS
  // owns the mapping; here we only say who played what.
  for (const { seat, card } of view.trick) {
    const node = cardNode(card);
    node.dataset.rel = String((seat - view.seat + 4) % 4);
    if (view.trick_complete && seat === view.trick_winner) node.classList.add("winner");
    el.trick.appendChild(node);
  }
  // A finished trick stays on the table until it is tapped — otherwise four cards appear
  // and vanish faster than they can be read.
  el.trick.classList.toggle("complete", !!view.trick_complete);
}

const WEIS_LABEL = { 20: "Dreiblatt", 50: "Vierblatt", 100: "Hundert", 150: "150", 200: "200" };

function renderWeis(view) {
  // What each seat announced, positioned on the same anticlockwise rotation as the trick.
  // Losing announcements stay visible but struck through — seeing that your partner's 50
  // was beaten is most of what makes Weis legible at the table.
  el.weis.replaceChildren();
  if (view.phase === "bidding" || view.phase === "weis") return;
  // Stöck can fire in any trick, so it is rendered whether or not Weis is still showing.

  for (const entry of view.weis || []) {
    const bubble = document.createElement("div");
    // Three states, and the difference matters. `best` is the one Weis that had to be
    // proved. `counts` is a partner's — it scores, but is never shown. `lost` scores
    // nothing at all.
    const state = entry.best ? "best" : entry.winner ? "counts" : "lost";
    bubble.className = `weis-bubble ${state}`;
    bubble.dataset.rel = String((entry.seat - view.seat + 4) % 4);

    // Card codes read fine compressed: "♣A ♣K ♣Q" rather than "CA CK CQ".
    const cards = entry.cards
      ? entry.cards.map((c) => `${SUIT_GLYPHS[c[0]]}${c[1] === "T" ? "10" : c[1]}`).join(" ")
      : "";
    // Until the calls are all in, a player says a number and nothing else.
    const label = cards ? `${WEIS_LABEL[entry.points] || "Weis"} ${entry.points}` : entry.points;
    bubble.innerHTML =
      `<span class="value">${label}</span>` +
      (cards ? `<span class="cards">${cards}</span>` : "");
    el.weis.appendChild(bubble);
  }
  for (const entry of view.stoeck || []) {
    const bubble = document.createElement("div");
    bubble.className = "weis-bubble stoeck";
    bubble.dataset.rel = String((entry.seat - view.seat + 4) % 4);
    bubble.innerHTML = `<span class="value">Stöck ${entry.points}</span>`;
    el.weis.appendChild(bubble);
  }
}

function renderScorecard(view) {
  const card = view.scorecard;
  if (!card) { el.scorecard.hidden = true; return; }

  const mine = view.seat % 2;
  const pick = (pair) => [pair[mine], pair[1 - mine]];
  const rows = [
    ["Tricks", pick(card.trick_points)],
    ["Last trick", pick(card.last_trick)],
    ["Weis", pick(card.weis)],
    ["Stöck", pick(card.stoeck)],
    ["Match", pick(card.match)],
  ];

  const add = (label, us, them, cls) => {
    const tr = document.createElement("tr");
    if (cls) tr.className = cls;
    tr.innerHTML = `<td>${label}</td><td>${us}</td><td>${them}</td>`;
    el.scRows.appendChild(tr);
  };

  el.scRows.replaceChildren();
  for (const [label, [us, them]] of rows) {
    // Keep empty lines visible but faded rather than hiding them — a row that disappears
    // makes the arithmetic impossible to follow.
    add(label, us || "—", them || "—", !us && !them ? "zero" : "");
  }

  // Tricks + last trick is always 157 between the two teams. Say so, because it is the
  // number that tells a player whether they had a good round.
  const cardPoints = card.trick_points[0] + card.trick_points[1] + card.last_trick[0] + card.last_trick[1];
  add(`of ${cardPoints} card points`, "", "", "note");

  const [ru, rt] = pick(card.round_total);
  const [tu, tt] = pick(card.scores);

  if (card.multiplier > 1) {
    // Show the raw subtotal and the multiplication explicitly. Without it the rows sum to
    // one number and "This round" shows another, which reads as an error.
    const raw = rows.reduce((acc, [, pair]) => [acc[0] + pair[0], acc[1] + pair[1]], [0, 0]);
    add("Subtotal", raw[0], raw[1], "subtotal");
    add(`× ${card.multiplier} (${card.contract[0] + card.contract.slice(1).toLowerCase()})`, "", "", "note");
  }
  add("This round", ru, rt, "subtotal");
  add("Total", tu, tt, "total");

  el.scTitle.textContent =
    view.phase === "game_over" ? "Final score" : `Round ${card.round + 1}`;
  el.scContract.textContent = card.contract
    ? card.contract[0] + card.contract.slice(1).toLowerCase()
    : "";
  el.scContinue.textContent = view.phase === "game_over" ? "New game" : "Next round";
  el.scorecard.hidden = false;
}

function renderSeats(view) {
  document.querySelectorAll(".seat-marker").forEach((marker) => {
    const seat = (view.seat + Number(marker.dataset.seat)) % 4;
    marker.classList.toggle("active", view.to_act === seat && view.phase !== "round_over");
  });
}

function seatName(view, seat) {
  const rel = (seat - view.seat + 4) % 4;
  return ["You", "Right", "Partner", "Left"][rel];
}

function statusText(view) {
  if (view.phase === "round_over" || view.phase === "game_over") return "Round complete";
  if (view.phase === "weis") {
    return view.to_act === view.seat && view.weis_offer
      ? "Announce your Weis?"
      : "Weis…";
  }
  if (view.trick_complete) {
    const mine = (view.trick_winner - view.seat + 4) % 4;
    const who = mine === 0 ? "You take it" : mine === 2 ? "Partner takes it" : "They take it";
    return `${who} — tap the trick`;
  }
  if (view.phase === "game_over") return "Game over";
  if (view.phase === "round_over") return "Round over — tap to continue";
  if (view.to_act === view.seat) {
    if (view.phase === "bidding") {
      return view.declarer === view.seat && view.can_shove
        ? "Your bid — or push it to your partner"
        : "Your partner pushed — you must choose";
    }
    return lifted ? "Tap again to play" : "Your turn";
  }
  if (view.to_act === null) return "";
  const who = seatName(view, view.to_act);
  return view.phase === "bidding" ? `${who} is bidding…` : `${who} is thinking…`;
}

function render(view) {
  lastView = view;
  recordRound(view);
  if (view.target) board.target = view.target;
  if (!el.tafel.hidden) renderTafel(view);
  renderHand(view);
  renderTrick(view);
  renderSeats(view);
  renderWeis(view);
  renderScorecard(view);

  const mine = view.seat % 2;
  el.scoreUs.textContent = view.scores[mine];
  el.scoreThem.textContent = view.scores[1 - mine];
  renderContract(view.contract, view.multiplier);
  el.round.textContent = `Round ${view.round + 1}`;

  // Running card points. 157 is the whole round — tricks plus the five for the last one.
  const playing = view.phase === "playing";
  el.taken.hidden = !playing;
  if (playing) {
    const taken = view.round_points || [0, 0];
    el.taken.textContent = `${taken[mine]} – ${taken[1 - mine]} of ${view.points_in_play}`;
  }

  const bidding = view.phase === "bidding" && view.to_act === view.seat;
  el.bidding.hidden = !bidding;

  const askingWeis = view.phase === "weis" && view.to_act === view.seat && view.weis_offer;
  el.weisPrompt.hidden = !askingWeis;
  if (askingWeis) el.weisPoints.textContent = `${view.weis_offer} in Weis`;
  el.shove.hidden = !view.can_shove;
  el.status.textContent = statusText(view);

  // The scorecard is the round-end surface now; the banner only covers the moment between
  // the last card and the scorecard appearing.
  el.banner.hidden = true;
}

// Tap the finished trick to clear it. Anywhere on the felt works, because a 190px target
// on a phone is not generous.
document.querySelector(".felt").addEventListener("click", () => {
  if (el.trick.classList.contains("complete")) send({ type: "ack_trick" });
});
el.scContinue.addEventListener("click", () => {
  if (el.scContinue.textContent === "New game") { document.querySelector(".menu").submit(); return; }
  el.scorecard.hidden = true;
  send({ type: "next_round" });
});
document.querySelectorAll(".bid[data-bid]").forEach((button) =>
  button.addEventListener("click", () => send({ type: "bid", action: button.dataset.bid }))
);
document.getElementById("weis-yes").addEventListener("click", () =>
  send({ type: "weis", announce: true })
);
document.getElementById("weis-no").addEventListener("click", () =>
  send({ type: "weis", announce: false })
);

import { initMenu } from "./menu.js";

initMenu({ measurementsUrl: MEASUREMENTS_URL });

function connect() {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${location.host}/ws`);

  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.type === "view") { render(event); return; }
    if (event.type === "rejected") { el.status.textContent = event.message; return; }
    if (event.type === "error") { el.status.textContent = event.message; return; }
    if (event.type === "trick_won") {
      const mine = (event.seat - mySeat + 4) % 4 === 0;
      el.status.textContent = mine ? "You took it" : "Trick to seat " + event.seat;
    }
  };
  socket.onclose = () => {
    el.status.textContent = "Disconnected — reconnecting…";
    setTimeout(connect, 1200);
  };
  socket.onopen = () => { el.status.textContent = "Connected"; };
}

connect();
