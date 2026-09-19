/* Client. Holds a view, never a source of truth.
 *
 * Everything on screen is a fold over the event stream plus the derived `view` frame the
 * server sends after it. The client never decides whether a card is legal, whose turn it is
 * or what a trick is worth — it asks, and it renders the answer (docs/webapp-plan.md §1).
 */

import { cardFace, SUIT_GLYPHS, SUIT_IS_RED } from "./cards.js";
import { applyStatic, contractName, getLang, t } from "./i18n.js";
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
  trickTake: document.getElementById("trick-take"),
  tafel: document.getElementById("tafel"),
  tafelSlate: document.getElementById("tafel-slate"),
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
 * It paints the table: the viewport gets a pulsing blue frame and each of the other three
 * seats gets a rotating blue ring. It changes **nothing** about how the bots decide a card —
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

  // What the marks mean, because a notation nobody can read is decoration.
  const legend = document.createElement("p");
  legend.className = "tafel-legend";
  legend.innerHTML = t("tafel.legend");
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

/* ---------- Sidi Barrani ---------- */

/** "♥ 100", "Obenabe 60", "Pass", "Double" — a call as a player would say it. */
function callLabel(call) {
  if (call === "PASS") return t("sidi.pass");
  if (call === "DOUBLE") return t("sidi.double");
  const [contract, value] = call.split(" ");
  return `${CONTRACT_PIPS[contract] ?? contractName(contract)} ${value}`;
}

/** The value the player has picked on the ladder. Kept between repaints, reset when it is
 *  no longer a legal bid. */
let sidiValue = null;

function legalValues(view) {
  const values = new Set();
  for (const call of view.legal_calls || []) {
    const [, value] = call.split(" ");
    if (value) values.add(Number(value));
  }
  return [...values].sort((a, b) => a - b);
}

function renderAuction(view) {
  const show = view.mode === "sidi" && (view.phase === "bidding" || view.phase === "doubling");
  el.auction.hidden = !show || !view.auction.length;
  if (!show) return;
  el.auction.replaceChildren();
  // Only the calls of this deal: after a throw-in the engine starts a fresh auction.
  let highIndex = -1;
  view.auction.forEach((entry, i) => { if (!["PASS", "DOUBLE"].includes(entry.call)) highIndex = i; });
  view.auction.forEach((entry, i) => {
    const node = html("span", "call" + (i === highIndex ? " high" : ""));
    node.append(html("span", "who", seatName(view, entry.seat)), callLabel(entry.call));
    el.auction.append(node);
  });
}

function renderSidi(view) {
  const bidding = view.mode === "sidi" && view.phase === "bidding" && view.to_act === view.seat;
  el.sidiBidding.hidden = !bidding;
  if (bidding) {
    const values = legalValues(view);
    if (!values.includes(sidiValue)) sidiValue = values[0] ?? null;
    el.sidiValues.replaceChildren();
    for (const value of values) {
      const button = html("button", value === sidiValue ? "on" : "", String(value));
      button.type = "button";
      button.addEventListener("click", () => { sidiValue = value; renderSidi(lastView); });
      el.sidiValues.append(button);
    }
    el.sidiPrompt.textContent = values.length
      ? t("sidi.prompt", { n: sidiValue })
      : t("sidi.promptNoBid");
    document.querySelectorAll("[data-sidi]").forEach((b) => { b.disabled = sidiValue === null; });
    el.sidiDouble.hidden = !(view.legal_calls || []).includes("DOUBLE");
  }

  el.doublePrompt.hidden = !view.double_pending;
  if (view.double_pending) {
    el.doubleText.textContent = t("sidi.doubleAsk", {
      who: seatName(view, view.declarer),
      bid: callLabel(`${view.contract} ${view.bid}`),
    });
  }
}

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
  const name = contractName(contract);
  const red = contract === "HEARTS" || contract === "DIAMONDS";
  const sidi = lastView.mode === "sidi" && lastView.bid;
  el.contract.innerHTML =
    (pip ? `<span class="pip${red ? " red" : ""}">${pip}</span>` : "") +
    `<span>${name}</span>` +
    (sidi
      ? `<span class="sidi-bid">${lastView.bid}</span>` +
        (lastView.doubled ? `<span class="doubled">${t("sidi.doubled")}</span>` : "")
      : multiplier ? `<span class="mult">×${multiplier}</span>` : "");
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

function renderTrick(view) {
  el.trick.replaceChildren();
  // Swiss Jass runs anticlockwise, so rel 1 (next to play) sits to your right. The CSS
  // owns the mapping; here we only say who played what.
  for (const { seat, card } of view.trick) {
    const node = cardNode(card);
    node.dataset.rel = String((seat - view.seat + 4) % 4);
    if (view.trick_complete && seat === view.trick_winner) node.classList.add("winner");
    else if (!view.trick_complete && seat === view.trick_taker) node.classList.add("leading");
    el.trick.appendChild(node);
  }
  // A finished trick stays on the table until it is tapped — otherwise four cards appear
  // and vanish faster than they can be read.
  el.trick.classList.toggle("complete", !!view.trick_complete);
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
  return CONTRACT_PIPS[view.contract] ?? (view.contract === "UNDENUFE" ? "↓" : "↑");
}

function renderSeats(view) {
  // Who made trump, on the corner of their own nameplate. Without it the new opening rule —
  // whoever holds the Ecken 10 starts the first round, so it is not always the same seat —
  // is invisible: the bidding happens before you can see anything and then nothing on the
  // table says who won it.
  const pip = declarerPip(view);
  document.querySelectorAll(".seat-marker").forEach((marker) => {
    const seat = (view.seat + Number(marker.dataset.seat)) % 4;
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

function seatName(view, seat) {
  // Anticlockwise: the next seat to play is to your right.
  const rel = (seat - view.seat + 4) % 4;
  return [t("seat.you"), t("seat.right"), t("seat.partner"), t("seat.left")][rel];
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
  el.round.textContent = t("round.n", { n: view.round + 1 });

  const bidding = view.mode !== "sidi" && view.phase === "bidding" && view.to_act === view.seat;
  el.bidding.hidden = !bidding;
  renderAuction(view);
  renderSidi(view);

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
  if (el.trick.classList.contains("complete")) send({ type: "ack_trick" });
});
el.scContinue.addEventListener("click", () => {
  if (el.scContinue.dataset.over) {
    document.querySelector(".menu").submit();
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
    if (sidiValue !== null) send({ type: "bid", action: `${button.dataset.sidi} ${sidiValue}` });
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

import { initMenu } from "./menu.js";

initMenu({
  measurementsUrl: MEASUREMENTS_URL,
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
    }
  };
  socket.onclose = () => {
    el.status.textContent = t("status.disconnected");
    setTimeout(connect, 1200);
  };
  socket.onopen = () => { el.status.textContent = t("status.connected"); };
}

connect();
