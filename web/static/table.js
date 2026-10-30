/* Client. Holds a view, never a source of truth.
 *
 * Everything on screen is a fold over the event stream plus the derived `view` frame the
 * server sends after it. The client never decides whether a card is legal, whose turn it is
 * or what a trick is worth — it asks, and it renders the answer (docs/webapp-plan.md §1).
 */

import { cardFace, SUIT_GLYPHS, SUIT_IS_RED } from "./cards.js";
import { applyStatic, contractName, getLang, t } from "./i18n.js";
import { drawTafel } from "./tafel.js";
import { dealAiTitles, dealNames } from "./names.js";
import { maybeSay, resetTalk } from "./talk.js";

const MEASUREMENTS_URL = "/static/measurements.json";

const mySeat = Number(document.body.dataset.seat);
//: Only the bots talk. Putting words in the player's mouth is a different feature.
const BOT_SEATS = [0, 1, 2, 3].filter((s) => s !== mySeat);
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
  trickTake: document.getElementById("trick-take"),
  tafel: document.getElementById("tafel"),
  tafelSlate: document.getElementById("tafel-slate"),
  beliefs: document.getElementById("beliefs"),
  beliefsBody: document.getElementById("beliefs-body"),
  beliefsOpen: document.getElementById("beliefs-open"),
  auction: document.getElementById("auction"),
  sidiBidding: document.getElementById("sidi-bidding"),
  sidiPrompt: document.getElementById("sidi-prompt"),
  sidiValues: document.getElementById("sidi-values"),
  sidiDouble: document.getElementById("sidi-double"),
  doublePrompt: document.getElementById("double-prompt"),
  doubleText: document.getElementById("double-text"),
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

/* AI mode — a display mode, and only that.
 *
 * It paints the table: the other three seats glow blue and wear a silly AI title for the
 * game ("Turbo-Sepp 3000"). It changes **nothing** about how the bots decide a card —
 * no flag reaches the engine, no budget changes, `botPlay` is called exactly as before.
 *
 * The bots have always been running a search (ISMCTS, `docs/measurements.md` §5h), so the
 * banner is not inventing an AI that was not there. It is still only a paint job, and this
 * comment is where that is written down — the banner says nothing about it by request.
 */
const AI_KEY = "kj_ai";
let aiOn = false;
try {
  aiOn = localStorage.getItem(AI_KEY) === "on";
} catch {
  aiOn = false;
}

function applyAi(announce) {
  document.body.classList.toggle("ai-mode", aiOn);
  const button = document.getElementById("ai-toggle");
  if (button) {
    button.setAttribute("aria-pressed", aiOn ? "true" : "false");
    button.classList.toggle("on", aiOn);
  }
  const banner = document.getElementById("ai-banner");
  if (!banner || !announce) return;
  if (!aiOn) {
    banner.hidden = true;
    return;
  }
  banner.replaceChildren(html("strong", null, t("ai.banner")));
  banner.hidden = false;
  clearTimeout(applyAi.timer);
  applyAi.timer = setTimeout(() => { banner.hidden = true; }, 3600);
}

document.getElementById("ai-toggle")?.addEventListener("click", () => {
  aiOn = !aiOn;
  try {
    localStorage.setItem(AI_KEY, aiOn ? "on" : "off");
  } catch {
    /* not remembering it is not a reason to refuse it */
  }
  applyAi(true);
  if (lastView?.hand) render(lastView);      // the titles are in every seat name on screen
});
applyAi(false);

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
  const slate = el.tafelSlate;
  slate.replaceChildren();

  // The board is written up round by round, so it gets the history rather than the totals.
  const history = [
    board.rounds.map((r) => r.points[mine]),
    board.rounds.map((r) => r.points[1 - mine]),
  ];
  drawTafel(slate, history, { target: view.target ?? board.target, t });
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
el.beliefsOpen.addEventListener("click", () => { el.beliefs.hidden = false; renderBeliefs(lastView); });
document.getElementById("beliefs-x").addEventListener("click", () => { el.beliefs.hidden = true; });
el.beliefs.addEventListener("click", (e) => { if (e.target === el.beliefs) el.beliefs.hidden = true; });
el.tafel.addEventListener("click", (e) => { if (e.target === el.tafel) closeTafel(); });

const CONTRACT_PIPS = { DIAMONDS: "♦", HEARTS: "♥", SPADES: "♠", CLUBS: "♣" };
// The no-trump contracts by direction: Obenabe runs from the top down, Undenufe from the
// bottom up.
const CONTRACT_ARROWS = { OBENABE: "↓", UNDENUFE: "↑" };

/* ---------- test mode: what the bot believes -----------------------------
 *
 * The search's own belief pool, published rather than sampled (`rust/src/belief.rs`): for every
 * card it cannot see, how likely it is at each of the other three seats. Read off this seat's
 * hand and the public history, so it shows the reasoning without showing a card.
 *
 * Two displays of the same thing, each behind its own switch: the panel (a grid of suit by
 * seat) and the overlay (the likely cards drawn beside each player's hidden fan). Both show
 * one *likely deal*, so they always agree with each other.
 */

// Set by the controller from the menu switches. The rendering code sits above the menu import
// (the offline build is cut there), so it is told rather than asking.
let beliefDisplay = { panel: true, overlay: false };
export function setBeliefDisplay(flags) {
  beliefDisplay = { ...beliefDisplay, ...flags };
  if (lastView) { renderBeliefs(lastView); renderLikely(lastView); }
}

// Same order as your own hand (the engine's HAND_SUIT_ORDER): red and black alternating.
const SUIT_ORDER = ["C", "D", "S", "H"];
const CONTRACT_SUIT = { DIAMONDS: "D", HEARTS: "H", SPADES: "S", CLUBS: "C" };
const PLAIN_ORDER = ["A", "K", "Q", "J", "T", "9", "8", "7", "6"];
const TRUMP_ORDER = ["J", "9", "A", "K", "Q", "T", "8", "7", "6"];
const rankLabel = (code) => (code.slice(1) === "T" ? "10" : code.slice(1));

/** Suits in display order with trump first, and a strongest-first sort key for each card. */
function strength(view) {
  const trump = CONTRACT_SUIT[view.contract] ?? null;
  const suits = trump ? [trump, ...SUIT_ORDER.filter((x) => x !== trump)] : SUIT_ORDER;
  const key = (code) => {
    const rank = code.slice(1);
    if (code[0] === trump) return TRUMP_ORDER.indexOf(rank);
    const i = PLAIN_ORDER.indexOf(rank);
    return view.contract === "UNDENUFE" ? 8 - i : i;
  };
  return { trump, suits, key };
}

/**
 * The likeliest deal the marginals allow: every unseen card goes to the seat that most
 * probably holds it, but no seat gets more cards than it has in its hand. Greedy, highest
 * probability first. A product of per-card guesses is not the single likeliest deal, but it
 * is the one a player would write down, and it respects the counts.
 */
function likelyDeal(view) {
  const cap = [1, 2, 3].map((rel) => view.hand_sizes?.[(view.seat + rel) % 4] ?? Infinity);
  const pairs = [];
  for (const { card, seats } of view.beliefs.cards) {
    seats.forEach((p, i) => pairs.push({ card, seat: i, p, seats }));
  }
  pairs.sort((a, b) => b.p - a.p);
  const hands = [[], [], []];
  const placed = new Set();
  for (const { card, seat, p, seats } of pairs) {
    if (placed.has(card) || cap[seat] <= 0) continue;
    placed.add(card);
    cap[seat] -= 1;
    hands[seat].push({ card, p, seats });
  }
  return hands;
}

function renderBeliefs(view) {
  const on = !!view.beliefs && beliefDisplay.panel;
  el.beliefsOpen.hidden = !on;
  if (!on) { el.beliefs.hidden = true; return; }
  if (el.beliefs.hidden) return;              // built when opened, and on every frame after

  const { trump, suits, key } = strength(view);
  const hands = likelyDeal(view);
  // Which suits a seat has been shown to be out of: none of that suit's unseen cards can be
  // there. Said as a dash, because "nothing here" and "out of it" are different news.
  const unseen = new Map(suits.map((x) => [x, []]));
  for (const entry of view.beliefs.cards) unseen.get(entry.card[0])?.push(entry);

  const grid = html("div", "belief-grid");
  grid.append(html("span", "bg-corner"));
  // As you sit: Left, Partner, Right. `seats[i]` is relative seat i + 1, so the columns are
  // indices 2, 1, 0.
  const COLUMNS = [2, 1, 0];
  for (const i of COLUMNS) grid.append(html("span", "bg-seat", seatShort(view, (view.seat + i + 1) % 4)));

  for (const suit of suits) {
    if (!unseen.get(suit).length) continue;   // every card of it is out or in your hand
    const label = html("span", `bg-suit${SUIT_IS_RED[suit] ? " red" : ""}`, SUIT_GLYPHS[suit]);
    if (suit === trump) label.append(html("em", null, t("beliefs.trump")));
    grid.append(label);
    for (const seat of COLUMNS) {
      const cell = html("span", "bg-cell");
      const out = unseen.get(suit).every((e) => e.seats[seat] < 0.005);
      if (out) {
        cell.classList.add("void");
        cell.textContent = "—";
      } else {
        hands[seat]
          .filter((e) => e.card[0] === suit)
          .sort((a, b) => key(a.card) - key(b.card))
          .forEach(({ card, p, seats }) => {
            const chip = html("span", `bg-card ${confidence(p)}${SUIT_IS_RED[suit] ? " red" : ""}`);
            chip.append(html("b", null, rankLabel(card)), html("i", null, `${Math.round(p * 100)}`));
            chip.title = COLUMNS
              .map((i) => `${seatName(view, (view.seat + i + 1) % 4)} ${Math.round(seats[i] * 100)}%`)
              .join(" · ");
            cell.append(chip);
          });
      }
      grid.append(cell);
    }
  }

  el.beliefsBody.replaceChildren(
    html("p", "intro", t("beliefs.intro")),
    grid,
    html("p", "legend", t("beliefs.legend")),
    html("p", "note", t("beliefs.note", { n: Math.round(view.beliefs.ess) })),
  );
}

const confidence = (p) => (p >= 0.85 ? "c-sure" : p >= 0.5 ? "c-likely" : "c-guess");

/* The overlay: the likely deal laid beside each player's face-down cards. Off by default — it
 * is the bot's guess, and next to the real backs it is easy to forget that it is one. */
function renderLikely(view) {
  const felt = document.querySelector(".felt");
  const show = !!view.beliefs && beliefDisplay.overlay;
  felt.querySelectorAll(".likely").forEach((n) => { n.hidden = !show; });
  if (!show) return;

  const { suits, key } = strength(view);
  const hands = likelyDeal(view);
  const where = { 1: "east", 2: "north", 3: "west" };
  for (const rel of [1, 2, 3]) {
    let host = felt.querySelector(`.likely.${where[rel]}`);
    if (!host) {
      host = html("div", `likely ${where[rel]}`);
      host.setAttribute("aria-hidden", "true");
      felt.append(host);
    }
    const cards = hands[rel - 1]
      .slice()
      .sort((a, b) => suits.indexOf(a.card[0]) - suits.indexOf(b.card[0]) || key(a.card) - key(b.card));
    host.replaceChildren(
      ...cards.map(({ card, p }, i) => {
        const chip = html("span", `mini ${confidence(p)}${SUIT_IS_RED[card[0]] ? " red" : ""}`,
          `${rankLabel(card)}${SUIT_GLYPHS[card[0]]}`);
        if (i > 0 && cards[i - 1].card[0] !== card[0]) chip.classList.add("gap");
        return chip;
      }),
    );
  }
}

/* ---------- Sidi Barrani ---------- */

/** "♥ 100", "Obenabe 60", "Pass", "Double" — a call as a player would say it. */
function callLabel(call) {
  if (call === "PASS") return t("sidi.pass");
  if (call === "DOUBLE") return t("sidi.double");
  const [contract, value] = call.split(" ");
  const arrow = CONTRACT_ARROWS[contract] ? `${CONTRACT_ARROWS[contract]} ` : "";
  return `${CONTRACT_PIPS[contract] ?? arrow + contractName(contract)} ${value}`;
}

/** The bid being put together: a value from the ladder and a contract. Neither is picked for
 *  you — a pre-selected value is a bid made by accident — and the call goes out once both
 *  are chosen, in either order. Cleared when the turn changes. */
let sidiValue = null;
let sidiContract = null;
let sidiTurn = null;

function sendSidiBid() {
  if (sidiValue === null || sidiContract === null) return;
  const action = `${sidiContract} ${sidiValue}`;
  sidiValue = null;
  sidiContract = null;
  send({ type: "bid", action });
}

function legalValues(view) {
  const values = new Set();
  for (const call of view.legal_calls || []) {
    const [, value] = call.split(" ");
    if (value) values.add(Number(value));
  }
  return [...values].sort((a, b) => a - b);
}

// How much of the auction was on screen last time, so only a call that has just been made
// plays its gesture — the auction is redrawn on every view.
let auctionSeen = { round: null, count: 0 };

function renderAuction(view) {
  const show = view.mode === "sidi" && (view.phase === "bidding" || view.phase === "doubling");
  el.auction.hidden = !show || !view.auction.length;
  if (!show) return;
  el.auction.replaceChildren();
  // Only the calls of this deal: after a throw-in the engine starts a fresh auction.
  let highIndex = -1;
  view.auction.forEach((entry, i) => { if (!["PASS", "DOUBLE"].includes(entry.call)) highIndex = i; });
  const seen = auctionSeen.round === view.round ? auctionSeen.count : 0;
  auctionSeen = { round: view.round, count: view.auction.length };
  view.auction.forEach((entry, i) => {
    const node = html("span", "call" + (i === highIndex ? " high" : ""));
    if (i >= seen) node.classList.add("fresh");
    const [contract, value] = entry.call.split(" ");
    node.append(html("span", "who", seatName(view, entry.seat)));
    if (CONTRACT_PIPS[contract]) {
      // A suit call carries its pip in card colours, like the bid button it came from.
      node.dataset.contract = contract;
      node.append(html("span", "pip", CONTRACT_PIPS[contract]), value);
    } else if (CONTRACT_ARROWS[contract]) {
      node.dataset.contract = contract;
      node.append(html("span", "arrow", CONTRACT_ARROWS[contract]), `${contractName(contract)} ${value}`);
    } else if (entry.call === "PASS" || entry.call === "DOUBLE") {
      // The table gestures: a wave for pass, a knock for double.
      node.classList.add(entry.call === "DOUBLE" ? "doubled-call" : "pass-call");
      node.append(
        html("span", `gesture ${entry.call === "DOUBLE" ? "knock" : "wave"}`, entry.call === "DOUBLE" ? "👊" : "👋"),
        callLabel(entry.call),
      );
    } else {
      node.append(callLabel(entry.call));
    }
    el.auction.append(node);
  });
}

function renderSidi(view) {
  const bidding = view.mode === "sidi" && view.phase === "bidding" && view.to_act === view.seat;
  el.sidiBidding.hidden = !bidding;
  if (bidding) {
    const values = legalValues(view);
    const turn = `${view.round}|${view.auction?.length ?? 0}`;
    if (turn !== sidiTurn) { sidiTurn = turn; sidiValue = null; sidiContract = null; }
    if (!values.includes(sidiValue)) sidiValue = null;
    el.sidiValues.replaceChildren();
    for (const value of values) {
      const button = html("button", value === sidiValue ? "on" : "", String(value));
      button.type = "button";
      button.addEventListener("click", () => {
        sidiValue = sidiValue === value ? null : value;
        renderSidi(lastView);
        sendSidiBid();
      });
      el.sidiValues.append(button);
    }
    const contract = sidiContract ? CONTRACT_PIPS[sidiContract] ?? contractName(sidiContract) : null;
    el.sidiPrompt.textContent = !values.length
      ? t("sidi.promptNoBid")
      : sidiValue !== null ? t("sidi.prompt", { n: sidiValue })
      : contract ? t("sidi.pickValue", { c: contract })
      : t("sidi.pickBoth");
    document.querySelectorAll("[data-sidi]").forEach((b) => {
      b.disabled = !values.length;
      b.classList.toggle("on", b.dataset.sidi === sidiContract);
    });
    el.sidiDouble.hidden = !(view.legal_calls || []).includes("DOUBLE");
  }

  // Two moments to knock: after the lead (the engine's own phase), and the instant an opponent
  // bids in the auction, before anyone else speaks (`knock`).
  el.doublePrompt.hidden = !view.double_pending && !view.knock;
  if (view.double_pending) {
    el.doubleText.textContent = t("sidi.doubleAsk", {
      who: seatName(view, view.declarer),
      bid: callLabel(`${view.contract} ${view.bid}`),
    });
  } else if (view.knock) {
    el.doubleText.textContent = t("sidi.knockAsk", {
      who: seatName(view, view.knock.seat),
      bid: callLabel(view.knock.call),
    });
  }
}

function renderContract(contract, multiplier) {
  // Always visible while a contract is live — you cannot judge a card without knowing
  // whether you are in trumps, Obenabe or Undenufe.
  if (!contract) {
    el.contract.className = "contract none";
    delete el.contract.dataset.contract;
    el.contract.textContent = "—";
    return;
  }
  el.contract.className = "contract";
  el.contract.dataset.contract = contract;     // a suit's pip in card colours, as on its bid
  const pip = CONTRACT_PIPS[contract];
  const name = contractName(contract);
  const red = contract === "HEARTS" || contract === "DIAMONDS";
  const sidi = lastView.mode === "sidi" && lastView.bid;
  el.contract.innerHTML =
    (pip ? `<span class="pip${red ? " red" : ""}">${pip}</span>` : "") +
    (CONTRACT_ARROWS[contract] ? `<span class="arrow">${CONTRACT_ARROWS[contract]}</span>` : "") +
    `<span>${name}</span>` +
    (sidi
      ? `<span class="sidi-bid">${lastView.bid}</span>` +
        (lastView.doubled ? `<span class="doubled">${t("sidi.doubled")}</span>` : "")
      : multiplier ? `<span class="mult">×${multiplier}</span>` : "");
}

// Which deal the fan last showed, so the cards are dealt in once per round, not per redraw.
let dealtRound = null;

function renderHand(view) {
  const legal = new Set(view.legal);
  const myTurn = view.to_act === view.seat && view.phase === "playing";
  el.hand.replaceChildren();
  const deal = view.hand.length === 9 && dealtRound !== view.round;
  if (deal) dealtRound = view.round;

  view.hand.forEach((code, i) => {
    const node = cardNode(code);
    if (code === view.puur) node.classList.add("puur");
    // Fan: rotate about a point below the card so the arc reads as held cards.
    const spread = Math.min(4, 26 / Math.max(view.hand.length, 1));
    node.style.transform = `rotate(${(i - (view.hand.length - 1) / 2) * spread}deg)`;
    if (myTurn && !legal.has(code)) node.classList.add("illegal");
    if (deal) {
      node.classList.add("dealt");
      node.style.animationDelay = `${i * 45}ms`;
    }

    // Advice mode: a fourth bot on your own seat, so the badge means "this is what it
    // would play from what it can see" — not "this is right". It knows no more than the
    // three you are playing against. Only ever shown on your own turn.
    const rank = myTurn ? (view.advice ?? []).indexOf(code) : -1;
    if (rank >= 0) {
      node.classList.add("advised", `advised-${rank + 1}`);
      const badge = document.createElement("span");
      badge.className = "advice-rank";
      badge.textContent = String(rank + 1);
      node.append(badge);
    }

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

/* A saying, over the seat that said it.
 *
 * Positioned against the seat marker rather than the covered fan, because the marker is
 * where your eye already is when you are wondering whose turn it is. It clears itself; no
 * state is kept in the view, so a redraw never resurrects a remark that has faded.
 */
let talkTimer = null;

function showTalk(view, remark) {
  const rel = (remark.seat - view.seat + 4) % 4;
  // Onto the felt, not onto the seat pill. The pills carry a `translate(-50%)` to centre
  // them, and a transformed element becomes the containing block for absolutely- and
  // fixed-positioned descendants — so a bubble anchored to the pill could not be placed
  // relative to the felt at all, and ran off the right edge on a phone.
  const host = document.querySelector(".felt");
  if (!host) return;
  clearTimeout(talkTimer);
  document.querySelectorAll(".speech").forEach((n) => n.remove());

  // Light up the speaker's nameplate for as long as the bubble is there. The felt has room
  // for only three bubble positions and none of them is *on* a seat, so the pill is what
  // makes it unambiguous who is talking.
  document.querySelectorAll(".seat-marker.talking").forEach((n) => n.classList.remove("talking"));
  document.querySelector(`.seat-marker[data-seat="${rel}"]`)?.classList.add("talking");

  const bubble = html("div", `speech speech-${rel}`);
  // Who said it, because the bubble no longer sits on its speaker. The felt is 260px tall
  // and the trick fills most of it, so there is no corner near the partner that a bubble
  // can occupy without covering a played card — naming the seat is better than obscuring
  // the cards the remark is about.
  bubble.append(html("span", "speech-who", seatName(view, remark.seat)));
  bubble.append(html("span", "speech-say", remark.say));
  // The gloss explains the dialect to a reader who does not have it. In German it would be
  // explaining Swiss German in High German to someone who just read it fine — so the saying
  // stands on its own there, the way it does at a table.
  const why = getLang() === "de" ? "" : t(remark.why);
  if (why && why !== remark.why) bubble.append(html("span", "speech-why", why));
  host.append(bubble);
  requestAnimationFrame(() => bubble.classList.add("in"));
  talkTimer = setTimeout(() => {
    bubble.classList.remove("in");
    document.querySelectorAll(".seat-marker.talking").forEach((n) => n.classList.remove("talking"));
    setTimeout(() => bubble.remove(), 350);
  }, 4200);
}

// The cards drawn on the table last time. Every view redraws the trick from scratch, so
// without this each repaint would replay the slide-in of cards that are already lying there.
let shownTrick = new Set();

function renderTrick(view) {
  el.trick.replaceChildren();
  el.trick.classList.remove("collect");
  const now = new Set(view.trick.map(({ card }) => card));
  // Swiss Jass runs anticlockwise, so rel 1 (next to play) sits to your right. The CSS
  // owns the mapping; here we only say who played what.
  for (const { seat, card } of view.trick) {
    const node = cardNode(card);
    node.dataset.rel = String((seat - view.seat + 4) % 4);
    if (!shownTrick.has(card)) node.classList.add("enter");
    if (view.trick_complete && seat === view.trick_winner) node.classList.add("winner");
    else if (!view.trick_complete && seat === view.trick_taker) node.classList.add("leading");
    el.trick.appendChild(node);
  }
  // A finished trick stays on the table until it is tapped — otherwise four cards appear
  // and vanish faster than they can be read.
  el.trick.classList.toggle("complete", !!view.trick_complete);
  if (view.trick_complete) el.trick.dataset.to = String((view.trick_winner - view.seat + 4) % 4);
  shownTrick = now;
  renderTake(view);
}

/** Which team the cards on the table go to as it stands.
 *
 * Which side, and not what it is worth: the comparison that decides who takes the trick is
 * the one a screen genuinely hides, while adding up the card points on the table is
 * arithmetic the player is there to do.
 */
function renderTake(view) {
  const taker = view.trick_taker;
  if (taker === null || taker === undefined || !view.trick.length) {
    el.trickTake.hidden = true;
    return;
  }
  const ours = (taker - view.seat + 4) % 4 % 2 === 0;
  el.trickTake.hidden = false;
  el.trickTake.className = `trick-take ${ours ? "us" : "them"}`;
  el.trickTake.innerHTML = `<span class="side">${ours ? t("team.us") : t("team.them")}</span>`;
}


const weisLabel = (points) =>
  ["20", "50", "100", "150", "200"].includes(String(points))
    ? t(`weis.${points}`)
    : t("weis.generic");

function renderWeis(view) {
  // What the winning team holds, positioned on the same anticlockwise rotation as the
  // trick.
  el.weis.replaceChildren();

  // Only the Weis that actually scores, and only once the first trick is over.
  //
  // Two reasons it waits. The table does not know who won until everyone has called, and
  // at a real table the losing holdings are never turned over at all — a value is called,
  // the best one shows its cards, the rest stay in the hand. Showing every announcement at
  // once, struck through, told you things the table would not have.
  // It belongs to the first trick's cards, and lives exactly as long as they do: it appears
  // when that trick completes and leaves the table together with them. Keyed to the trick
  // count *and* to the finished trick still being on the felt, because the count alone
  // stays at one for the whole of the second trick — which left the Weis hanging over a
  // table whose first trick had already been cleared away.
  const tricksDone = (view.tricks_won || [0, 0]).reduce((a, b) => a + b, 0);
  const showing = tricksDone === 1 && !!view.trick_complete;
  const weis = view.phase === "bidding" || view.phase === "weis" || !showing
    ? []
    : (view.weis || []).filter((entry) => entry.winner);

  for (const entry of weis) {
    const bubble = document.createElement("div");
    // Three states, and the difference matters. `best` is the one Weis that had to be
    // proved. `counts` is a partner's — it scores, but is never shown. `lost` scores
    // nothing at all.
    // Only two states survive the filter above: the one Weis that had to be proved, and a
    // partner's, which scores without ever being shown.
    const state = entry.best ? "best" : "counts";
    bubble.className = `weis-bubble ${state}`;
    bubble.dataset.rel = String((entry.seat - view.seat + 4) % 4);

    // Card codes read fine compressed: "♣A ♣K ♣Q" rather than "CA CK CQ".
    const cards = entry.cards
      ? entry.cards.map((c) => `${SUIT_GLYPHS[c[0]]}${c[1] === "T" ? "10" : c[1]}`).join(" ")
      : "";
    // Until the calls are all in, a player says a number and nothing else.
    // `WEIS_LABEL` was a hardcoded German table that the i18n change replaced with
    // `weis.<points>` keys — but this reference survived the deletion, so rendering a Weis
    // with cards threw a ReferenceError and took the whole redraw down with it. It almost
    // never fired, because the old display window was the pause after the first trick and
    // players tap straight through that.
    const name = t(`weis.${entry.points}`);
    const label = cards
      ? `${name === `weis.${entry.points}` ? t("weis.generic") : name} ${entry.points}`
      : entry.points;
    // Colour alone did not say which one won. The rule is unusual enough to be worth
    // spelling out: the single best Weis at the table decides, and then that player's whole
    // *team* scores everything it holds — a partner's smaller Weis included, even when the
    // losing side held a bigger one.
    const tag = cards ? t(`weis.tag.${state}`) : "";
    bubble.innerHTML =
      `<span class="value">${label}</span>` +
      (cards ? `<span class="cards">${cards}</span>` : "") +
      (tag ? `<span class="tag">${tag}</span>` : "");
    el.weis.appendChild(bubble);
  }
  // Stöck is on its own clock: it is announced when the second of King and Queen is played,
  // which can be any trick, and it is not part of the Weis contest at all.
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
  if (card.bid !== undefined) { renderSidiScorecard(view, card, pick); return; }
  const rows = [
    [t("score.tricks"), pick(card.trick_points)],
    [t("score.lastTrick"), pick(card.last_trick)],
    [t("score.weis"), pick(card.weis)],
    [t("score.stoeck"), pick(card.stoeck)],
    [t("score.match"), pick(card.match)],
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
  add(t("score.cardPoints", { n: cardPoints }), "", "", "note");

  const [ru, rt] = pick(card.round_total);
  const [tu, tt] = pick(card.scores);

  if (card.multiplier > 1) {
    // Show the raw subtotal and the multiplication explicitly. Without it the rows sum to
    // one number and "This round" shows another, which reads as an error.
    const raw = rows.reduce((acc, [, pair]) => [acc[0] + pair[0], acc[1] + pair[1]], [0, 0]);
    add(t("score.subtotal"), raw[0], raw[1], "subtotal");
    add(
      t("score.multiplier", { n: card.multiplier, contract: contractName(card.contract) }),
      "", "", "note"
    );
  }
  add(t("score.thisRound"), ru, rt, "subtotal");
  add(t("score.total"), tu, tt, "total");

  el.scTitle.textContent =
    view.phase === "game_over" ? t("score.final") : t("round.n", { n: card.round + 1 });
  el.scContract.textContent = contractName(card.contract);
  // The flag, not the label: reading the button's own text to decide what it does made the
  // behaviour depend on the language it happened to be written in.
  const over = view.phase === "game_over";
  el.scContinue.dataset.over = over ? "1" : "";
  el.scContinue.textContent = over ? t("score.newGame") : t("score.nextRound");
  el.scorecard.hidden = false;
}

/** Sidi: the cards, then the stake on its own line, marked made or failed. */
function renderSidiScorecard(view, card, pick) {
  el.scRows.replaceChildren();
  const add = (label, us, them, cls) => {
    const tr = document.createElement("tr");
    if (cls) tr.className = cls;
    tr.innerHTML = `<td>${label}</td><td>${us}</td><td>${them}</td>`;
    el.scRows.appendChild(tr);
  };
  for (const [label, pair] of [
    [t("score.tricks"), card.trick_points],
    [t("score.lastTrick"), card.last_trick],
    [t("score.match"), card.match],
  ]) {
    const [us, them] = pick(pair);
    add(label, us || "—", them || "—", !us && !them ? "zero" : "");
  }
  const stake = t(card.made ? "sidi.made" : "sidi.failed", {
    bid: card.bid, x: card.doubled ? " ×2" : "",
  });
  const [bu, bt] = pick(card.bonus);
  add(stake, bu || "—", bt || "—", "subtotal");
  const [ru, rt] = pick(card.round_total);
  const [tu, tt] = pick(card.scores);
  add(t("score.thisRound"), ru, rt, "subtotal");
  add(t("score.total"), tu, tt, "total");

  el.scTitle.textContent =
    view.phase === "game_over" ? t("score.final") : t("round.n", { n: card.round + 1 });
  el.scContract.textContent = `${contractName(card.contract)} ${card.bid}`;
  const over = view.phase === "game_over";
  el.scContinue.dataset.over = over ? "1" : "";
  el.scContinue.textContent = over ? t("score.newGame") : t("score.nextRound");
  el.scorecard.hidden = false;
}

/** Called by the controller when a trick completes. Kept off the render path on purpose:
 *  a remark is an event, and folding it into a redraw would repeat it on every repaint. */
export function speak(remark) {
  if (remark) showTalk(lastView, remark);
}

/** The pip that marks who chose trump: the suit itself, or the direction for a no-trump
 *  contract. Empty while nobody has chosen yet. */
function declarerPip(view) {
  if (view.contract === null || view.contract === undefined) return "";
  return CONTRACT_PIPS[view.contract] ?? CONTRACT_ARROWS[view.contract] ?? "";
}

function renderSeats(view) {
  // Who made trump, on the corner of their own nameplate. Without it the new opening rule —
  // whoever holds the Ecken 10 starts the first round, so it is not always the same seat —
  // is invisible: the bidding happens before you can see anything and then nothing on the
  // table says who won it.
  const pip = declarerPip(view);
  document.querySelectorAll(".seat-marker").forEach((marker) => {
    const seat = (view.seat + Number(marker.dataset.seat)) % 4;
    const label = marker.querySelector("span");
    if (label) {
      label.textContent = seatName(view, seat);
      label.title = label.textContent;
    }
    marker.classList.toggle("active", view.to_act === seat && view.phase !== "round_over");

    const isDeclarer = pip !== "" && view.declarer === seat;
    let badge = marker.querySelector(".declarer-pip");
    if (isDeclarer && !badge) {
      badge = html("span", "declarer-pip");
      marker.append(badge);
    }
    if (badge) {
      badge.textContent = pip;
      badge.title = t("seat.trumpMaker");
      badge.hidden = !isDeclarer;
    }
  });

  // And on the status line when it was you, since you have no pill to put it on.
  const mine = document.getElementById("my-declarer");
  if (mine) {
    mine.textContent = pip;
    mine.title = t("seat.trumpMaker");
    mine.hidden = !(pip !== "" && view.declarer === view.seat);
  }
  renderCovered(view);
}

/* The other three hands, face down.
 *
 * A real table tells you how many cards everybody still holds — you watch the fan shrink —
 * and this was the one thing the app hid that it had no reason to. These are backs and
 * nothing else: the count comes from `hand_sizes`, which the engine publishes as a number
 * per seat and never as a hand. Reading the DOM tells you how many cards Left holds, which
 * is exactly what sitting opposite them would.
 */
function renderCovered(view) {
  const sizes = view.hand_sizes;
  document.querySelectorAll(".covered").forEach((host) => {
    const seat = (view.seat + Number(host.dataset.seat)) % 4;
    const want = Array.isArray(sizes) ? sizes[seat] : 0;
    const have = host.childElementCount;
    if (want === have) return;            // nothing to redraw between tricks
    if (want < have) {
      // Take from the front, so the cards that remain keep their place in the fan instead
      // of every one of them shifting each time a card is played.
      for (let i = 0; i < have - want; i++) host.firstElementChild?.remove();
      return;
    }
    for (let i = have; i < want; i++) {
      const back = document.createElement("div");
      back.className = "card-back";
      host.appendChild(back);
    }
  });
}

/* The bots' names: dealt per game, kept for the tab's lifetime so a reload of the hosted
 * page (the game lives on the server) keeps the same faces. A new game deals new ones. */
const NAMES_KEY = "kj_names";
const TITLES_KEY = "kj_ai_titles";
let tableNames = null;
let aiTitles = null;
try {
  tableNames = JSON.parse(sessionStorage.getItem(NAMES_KEY) || "null");
  aiTitles = JSON.parse(sessionStorage.getItem(TITLES_KEY) || "null");
} catch {
  tableNames = null;
}

/** Deal three new names, and their AI-mode titles — called when a new game starts. */
export function rollNames() {
  tableNames = dealNames();
  aiTitles = dealAiTitles();
  try {
    sessionStorage.setItem(NAMES_KEY, JSON.stringify(tableNames));
    sessionStorage.setItem(TITLES_KEY, JSON.stringify(aiTitles));
  } catch {
    /* names for this page only, then */
  }
}

/** A seat's name alone: "Sepp". You are "you". */
function seatShort(view, seat) {
  // Anticlockwise: the next seat to play is to your right.
  const rel = (seat - view.seat + 4) % 4;
  if (rel === 0) return t("seat.you");
  if (!Array.isArray(tableNames) || tableNames.length !== 3) rollNames();
  return tableNames[rel - 1];
}

/** A seat as the table calls it: the name, in AI mode its title, and your partner marked. */
function seatName(view, seat) {
  const rel = (seat - view.seat + 4) % 4;
  let name = seatShort(view, seat);
  if (aiOn && rel !== 0) {
    if (!Array.isArray(aiTitles) || aiTitles.length !== 3) aiTitles = dealAiTitles();
    const [prefix, suffix] = aiTitles[rel - 1];
    name = `${prefix}${name}${suffix}`;
  }
  return rel === 2 ? `${name} (${t("seat.partnerTag")})` : name;
}

function statusText(view) {
  if (view.phase === "round_over" || view.phase === "game_over") return t("status.roundComplete");
  if (view.phase === "weis") {
    return view.to_act === view.seat && view.weis_offer
      ? t("status.weisAsk")
      : t("status.weisWait");
  }
  if (view.trick_complete) {
    const rel = (view.trick_winner - view.seat + 4) % 4;
    const who =
      rel === 0 ? t("status.youTake") : rel === 2 ? t("status.partnerTakes") : t("status.theyTake");
    return t("status.tapTrick", { who });
  }
  if (view.phase === "game_over") return "Game over";
  if (view.phase === "round_over") return "Round over — tap to continue";
  if (view.mode === "sidi" && view.phase === "doubling") {
    return view.double_pending ? t("sidi.doubleYours") : t("sidi.doubleWait");
  }
  if (view.mode === "sidi" && view.knock) return t("sidi.doubleYours");
  if (view.mode === "sidi" && view.phase === "bidding") {
    return view.to_act === view.seat
      ? t("sidi.yourCall")
      : t("sidi.calling", { who: seatName(view, view.to_act) });
  }
  if (view.to_act === view.seat) {
    if (view.phase === "bidding") {
      return view.declarer === view.seat && view.can_shove
        ? t("status.yourBid")
        : t("status.mustChoose");
    }
    return lifted ? t("status.tapAgain") : t("status.yourTurn");
  }
  if (view.to_act === null) return "";
  const who = seatName(view, view.to_act);
  return view.phase === "bidding"
    ? t("status.bidding", { who })
    : t("status.thinking", { who });
}

function setScore(node, value) {
  const text = String(value);
  if (node.textContent === text) return;
  node.textContent = text;
  node.classList.remove("bump");
  void node.offsetWidth;  // restart the animation if it is still running
  node.classList.add("bump");
}

/** Which seat doubled between the last view and this one, or null.
 *
 *  A double in the auction is a call with a seat on it; a double after the lead is only
 *  `doubled` turning true, and then it was the seat that had just been asked. */
function newDouble(prev, view) {
  if (view.mode !== "sidi" || !view.doubled || prev?.doubled || prev?.round !== view.round) return null;
  const call = (view.auction ?? []).find((c) => c.call === "DOUBLE");
  if (call) return call.seat;
  return prev?.phase === "doubling" ? prev.to_act : null;
}

/** A fist pounding the table at the seat that doubled, and the table jumping with it. */
function poundAt(view, seat) {
  const rel = (seat - view.seat + 4) % 4;
  if (rel === 0) return;                       // your own double: the button already knocked
  const felt = document.querySelector(".felt");
  const fx = html("div", `pound pound-${rel}`);
  fx.setAttribute("aria-hidden", "true");
  fx.append(html("span", "ring"), html("span", "fist", "👊"), html("span", "word", `${seatName(view, seat)}: ${t("sidi.doubled")}!`));
  felt.append(fx);
  felt.classList.remove("jolt");
  void felt.offsetWidth;
  felt.classList.add("jolt");
  setTimeout(() => { fx.remove(); felt.classList.remove("jolt"); }, 2200);
}

function render(view) {
  const doubler = newDouble(lastView, view);
  lastView = view;
  if (doubler !== null && doubler !== undefined) poundAt(view, doubler);
  recordRound(view);
  if (view.target) board.target = view.target;
  if (!el.tafel.hidden) renderTafel(view);
  renderHand(view);
  renderTrick(view);
  renderSeats(view);
  renderWeis(view);
  renderScorecard(view);

  const mine = view.seat % 2;
  setScore(el.scoreUs, view.scores[mine]);
  setScore(el.scoreThem, view.scores[1 - mine]);
  renderContract(view.contract, view.multiplier);
  el.round.textContent = t("round.n", { n: view.round + 1 });

  const bidding = view.mode !== "sidi" && view.phase === "bidding" && view.to_act === view.seat;
  el.bidding.hidden = !bidding;
  renderAuction(view);
  renderSidi(view);
  renderBeliefs(view);
  renderLikely(view);

  const askingWeis = view.phase === "weis" && view.to_act === view.seat && view.weis_offer;
  el.weisPrompt.hidden = !askingWeis;
  if (askingWeis) el.weisPoints.textContent = t("weis.prompt.amount", { n: view.weis_offer });
  el.shove.hidden = !view.can_shove;
  el.status.textContent = statusText(view);

  // The scorecard is the round-end surface now; the banner only covers the moment between
  // the last card and the scorecard appearing.
  el.banner.hidden = true;
}

// Tap the finished trick to clear it. Anywhere on the felt works, because a 190px target
// on a phone is not generous.
document.querySelector(".felt").addEventListener("click", () => {
  if (!el.trick.classList.contains("complete") || el.trick.classList.contains("collect")) return;
  el.trick.classList.add("collect");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  setTimeout(() => send({ type: "ack_trick" }), reduced ? 0 : 260);
});
el.scContinue.addEventListener("click", () => {
  if (el.scContinue.dataset.over) {
    // By id, and `requestSubmit` rather than `submit`: `.menu` also matches the menu's outer
    // shell, which cannot be submitted, and `submit()` skips the offline build's handler.
    document.getElementById("mode-settings").requestSubmit();
    return;
  }
  el.scorecard.hidden = true;
  send({ type: "next_round" });
});
document.querySelectorAll(".bid[data-bid]").forEach((button) =>
  button.addEventListener("click", () => send({ type: "bid", action: button.dataset.bid }))
);
document.querySelectorAll("[data-sidi]").forEach((button) =>
  button.addEventListener("click", () => {
    sidiContract = sidiContract === button.dataset.sidi ? null : button.dataset.sidi;
    renderSidi(lastView);
    sendSidiBid();
  })
);
document.querySelectorAll("[data-sidi-call]").forEach((button) =>
  button.addEventListener("click", () => send({ type: "bid", action: button.dataset.sidiCall }))
);
document.querySelectorAll("[data-open-rules]").forEach((button) =>
  button.addEventListener("click", () => document.dispatchEvent(new Event("kj:open-rules")))
);
document.getElementById("double-yes").addEventListener("click", () =>
  send({ type: "double", double: true })
);
document.getElementById("double-no").addEventListener("click", () =>
  send({ type: "double", double: false })
);
document.getElementById("weis-yes").addEventListener("click", () =>
  send({ type: "weis", announce: true })
);
document.getElementById("weis-no").addEventListener("click", () =>
  send({ type: "weis", announce: false })
);

// Above the cut on purpose: scripts/make_site.py slices this file at the menu import, so
// anything below here is absent from the offline build. It sat below, and the static markup
// on the serverless page stayed in its English placeholder text.
applyStatic();

import { initMenu, adviceOn, beliefsOn, overlayOn, talkOn } from "./menu.js";

/** Both belief displays read the same pool, so the server computes it if either is on. */
function syncBeliefs() {
  setBeliefDisplay({ panel: beliefsOn(), overlay: overlayOn() });
  send({ type: "beliefs", on: beliefsOn() || overlayOn() });
}

initMenu({
  measurementsUrl: MEASUREMENTS_URL,
  // The hosted build runs the fourth bot on the server — the same search, on your own hand.
  onAdviceChange: () => send({ type: "advice", on: adviceOn() }),
  onBeliefsChange: syncBeliefs,
  onOverlayChange: syncBeliefs,
  // Switching language has to redraw everything already on screen, not just the chrome.
  onLanguageChange: () => {
    if (lastView) render(lastView);
  },
});

function connect() {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${location.host}/ws`);

  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.type === "view") { render(event); return; }
    if (event.type === "rejected") { el.status.textContent = event.message; return; }
    if (event.type === "error") { el.status.textContent = event.message; return; }
    if (event.type === "trick_won") {
      const rel = (event.seat - mySeat + 4) % 4;
      el.status.textContent =
        rel === 0 ? t("status.youTake") : rel === 2 ? t("status.partnerTakes") : t("status.theyTake");
      // A remark belongs to the pause after a trick, when nobody is waiting on you. From the
      // event, not from a redraw, so it is said once rather than on every repaint.
      if (talkOn()) speak(maybeSay(event.trick, BOT_SEATS));
    }
    if (event.type === "round_started") resetTalk();   // a new deal starts the talk fresh
  };
  socket.onclose = () => {
    el.status.textContent = t("status.disconnected");
    setTimeout(connect, 1200);
  };
  socket.onopen = () => {
    el.status.textContent = t("status.connected");
    // Both are per-browser settings, and both are computed where the game is.
    syncBeliefs();
    send({ type: "advice", on: adviceOn() });
  };
}

connect();
