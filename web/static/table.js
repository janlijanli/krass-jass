/* Client. Holds a view, never a source of truth.
 *
 * Everything on screen is a fold over the event stream plus the derived `view` frame the
 * server sends after it. The client never decides whether a card is legal, whose turn it is
 * or what a trick is worth — it asks, and it renders the answer (docs/webapp-plan.md §1).
 */

const SUITS = { D: { pip: "♦", red: true }, H: { pip: "♥", red: true },
                S: { pip: "♠", red: false }, C: { pip: "♣", red: false } };
const RANKS = { A: "A", K: "K", Q: "Q", J: "J", T: "10", 9: "9", 8: "8", 7: "7", 6: "6" };

const mySeat = Number(document.body.dataset.seat);
const el = {
  hand: document.getElementById("hand"),
  trick: document.getElementById("trick"),
  bidding: document.getElementById("bidding"),
  shove: document.getElementById("shove"),
  status: document.getElementById("status"),
  banner: document.getElementById("banner"),
  contract: document.getElementById("contract"),
  round: document.getElementById("round"),
  scoreUs: document.getElementById("score-us"),
  scoreThem: document.getElementById("score-them"),
};

let lifted = null;
let socket = null;

function cardNode(code) {
  const suit = SUITS[code[0]];
  const node = document.createElement("div");
  node.className = "card" + (suit.red ? " red" : "");
  node.dataset.card = code;
  node.innerHTML =
    `<span class="inner"><span class="rank">${RANKS[code[1]]}</span><span class="pip">${suit.pip}</span></span>`;
  return node;
}

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
}

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

function renderSeats(view) {
  document.querySelectorAll(".seat-marker").forEach((marker) => {
    const seat = (view.seat + Number(marker.dataset.seat)) % 4;
    marker.classList.toggle("active", view.to_act === seat && view.phase !== "round_over");
  });
}

function statusText(view) {
  if (view.trick_complete) {
    const mine = (view.trick_winner - view.seat + 4) % 4;
    const who = mine === 0 ? "You take it" : mine === 2 ? "Partner takes it" : "They take it";
    return `${who} — tap the trick`;
  }
  if (view.phase === "game_over") return "Game over";
  if (view.phase === "round_over") return "Round over — tap to continue";
  if (view.to_act === view.seat) {
    return view.phase === "bidding" ? "Your bid" : lifted ? "Tap again to play" : "Your turn";
  }
  return "Thinking…";
}

function render(view) {
  renderHand(view);
  renderTrick(view);
  renderSeats(view);

  const mine = view.seat % 2;
  el.scoreUs.textContent = view.scores[mine];
  el.scoreThem.textContent = view.scores[1 - mine];
  renderContract(view.contract, view.multiplier);
  el.round.textContent = `Round ${view.round + 1}`;

  const bidding = view.phase === "bidding" && view.to_act === view.seat;
  el.bidding.hidden = !bidding;
  el.shove.hidden = !view.can_shove;
  el.status.textContent = statusText(view);

  if (view.trick_complete) {
    // Hold the banner back until the trick has been acknowledged, so the round result does
    // not cover the cards the player is still looking at.
    el.banner.hidden = true;
  } else if (view.phase === "round_over" || view.phase === "game_over") {
    el.banner.hidden = false;
    el.banner.textContent =
      view.phase === "game_over"
        ? `Final ${view.scores[mine]} – ${view.scores[1 - mine]}`
        : `Round over · ${view.scores[mine]} – ${view.scores[1 - mine]} · tap to continue`;
  } else {
    el.banner.hidden = true;
  }
}

// Tap the finished trick to clear it. Anywhere on the felt works, because a 190px target
// on a phone is not generous.
document.querySelector(".felt").addEventListener("click", () => {
  if (el.trick.classList.contains("complete")) send({ type: "ack_trick" });
});
el.banner.addEventListener("click", () => send({ type: "next_round" }));
document.querySelectorAll(".bid").forEach((button) =>
  button.addEventListener("click", () => send({ type: "bid", action: button.dataset.bid }))
);

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
