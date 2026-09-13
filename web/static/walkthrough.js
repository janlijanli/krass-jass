/* The Nerd-Doc: one decision, start to finish.
 *
 * The other three panels answer "what does it do", "is it any good" and "what is it built
 * from". None of them answers the question a curious player actually asks, which is *how a
 * card gets chosen* — the path from "I cannot see your hand" to "I play this one".
 *
 * So this is a single worked example in seven steps, in the order the engine runs them.
 * Each step owns one figure and one idea, and the figure animates only where the motion
 * *is* the idea: cards being dealt into imagined hands, worlds being struck out, a tree
 * filling up with visits. Anything that would animate for decoration is drawn static.
 *
 * Every figure is hand-written SVG, like about.js and for the same reason: there are seven
 * of them and a charting library would be more code than the figures. They share the
 * `.fig` styling already in table.css.
 *
 * `prefers-reduced-motion` is honoured throughout — every step has a static end state that
 * carries the whole argument, and the animation only gets it there more legibly.
 */

import { about } from "./about-i18n.js";

const NS = "http://www.w3.org/2000/svg";
const REDUCED = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  for (const c of kids) n.append(c);
  return n;
};
const html = (tag, cls, content) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (content !== undefined) n.innerHTML = content;
  return n;
};

const W = 320;
const svg = (h) => el("svg", { viewBox: `0 0 ${W} ${h}`, class: "fig" });

/** A small card glyph. The walkthrough never needs a readable face, only a countable
 *  object in a place — so these are chips, not the card fronts `cards.js` draws. */
function chip(x, y, cls = "", label = "") {
  const g = el("g", { class: `wt-chip ${cls}` });
  g.append(el("rect", { x, y, width: 13, height: 18, rx: 2.5 }));
  if (label) {
    g.append(el("text", { x: x + 6.5, y: y + 12.5, "text-anchor": "middle", class: "wt-chip-t" }, label));
  }
  return g;
}

/* ---- 1. the information set ------------------------------------------- */

function figInfoSet() {
  const s = svg(132);
  // Nine cards it holds, twenty-seven it cannot see. Drawn to scale, because the ratio is
  // the point: three quarters of the deck is a guess.
  for (let i = 0; i < 36; i++) {
    const col = i % 12;
    const row = (i / 12) | 0;
    const mine = i < 9;
    s.append(chip(14 + col * 24, 24 + row * 30, mine ? "wt-mine" : "wt-hidden", mine ? "" : "?"));
  }
  s.append(el("text", { x: 14, y: 16, class: "fig-label" }, "9 / 36"));
  s.append(el("text", { x: W - 12, y: 16, class: "fig-value", "text-anchor": "end" }, "27 ?"));
  return s;
}

/* ---- 2. one imagined world -------------------------------------------- */

function figDeal(L) {
  const s = svg(150);
  const seats = [
    { x: 22, label: about(L, "wt.seat.left") },
    { x: 122, label: about(L, "wt.seat.partner") },
    { x: 222, label: about(L, "wt.seat.right") },
  ];
  seats.forEach((seat) => {
    s.append(el("text", { x: seat.x + 36, y: 16, class: "fig-label", "text-anchor": "middle" }, seat.label));
    s.append(el("rect", { x: seat.x, y: 22, width: 74, height: 104, rx: 5, class: "wt-seat" }));
  });

  const chips = [];
  for (let i = 0; i < 27; i++) {
    const seat = (i / 9) | 0;
    const k = i % 9;
    const c = chip(seats[seat].x + 8 + (k % 3) * 20, 32 + ((k / 3) | 0) * 30, "wt-dealt");
    chips.push(c);
    s.append(c);
  }

  // The deal is the animation: cards leave one pile and land in three hands. Replaying it
  // gives a *different* deal, which is the thing worth showing — one world is a guess.
  const run = () => {
    if (REDUCED()) return;
    chips.forEach((c, i) => {
      const order = Math.random();
      c.style.opacity = "0";
      c.style.transform = "translate(0px, 40px)";
      c.style.transition = "none";
      requestAnimationFrame(() => {
        c.style.transition = `opacity .28s ease-out ${order * 0.5}s, transform .38s ease-out ${order * 0.5}s`;
        c.style.opacity = "1";
        c.style.transform = "translate(0px, 0px)";
      });
    });
  };
  run();
  return { node: s, replay: run };
}

/* ---- 3. worlds the table has ruled out -------------------------------- */

function figRuledOut(data, L) {
  const s = svg(136);
  const pct = Math.round((data.called_weis?.worlds_contradicting_the_calls ?? 0.804) * 100);
  // Twenty-five worlds, of which ~80% are struck out. A proportion is easier to believe as
  // a grid you can count than as a number in a sentence.
  const kept = [];
  for (let i = 0; i < 25; i++) {
    const x = 18 + (i % 5) * 58;
    const y = 22 + ((i / 5) | 0) * 20;
    const bad = i % 5 !== 0;
    const row = el("rect", { x, y, width: 48, height: 13, rx: 2.5, class: bad ? "wt-world-bad" : "wt-world-ok" });
    s.append(row);
    if (!bad) kept.push(row);
    if (bad) s.append(el("line", { x1: x + 3, y1: y + 6.5, x2: x + 45, y2: y + 6.5, class: "wt-strike" }));
  }
  s.append(el("text", { x: 18, y: 14, class: "fig-label" }, about(L, "wt.ruled.legend", { pct })));
  s.append(el("text", { x: W - 12, y: 130, class: "fig-value", "text-anchor": "end" }, `${pct}%`));
  return s;
}

/* ---- 4. one tree, many worlds ----------------------------------------- */

function figTree(L) {
  const s = svg(160);
  const root = { x: W / 2, y: 24 };
  const kids = [70, 130, 190, 250].map((x) => ({ x, y: 78 }));
  const leaves = [];
  kids.forEach((k, i) => {
    [0, 1].forEach((j) => leaves.push({ x: k.x - 14 + j * 28, y: 132, parent: i }));
  });

  kids.forEach((k) => s.append(el("line", { x1: root.x, y1: root.y + 9, x2: k.x, y2: k.y - 9, class: "wt-edge" })));
  leaves.forEach((l) =>
    s.append(el("line", { x1: kids[l.parent].x, y1: kids[l.parent].y + 9, x2: l.x, y2: l.y - 9, class: "wt-edge wt-edge-thin" }))
  );

  // Visit counts are what a node *is* here: the same node is reached from many different
  // imagined worlds, and its statistics are shared across all of them. That sharing is the
  // difference between ISMCTS and voting, so the bars are the figure.
  const bars = kids.map((k, i) => {
    const bar = el("rect", { x: k.x - 16, y: k.y + 12, width: 0, height: 6, rx: 3, class: `wt-visits wt-visits-${i}` });
    s.append(bar);
    return bar;
  });
  const widths = [32, 12, 20, 6];

  s.append(el("circle", { cx: root.x, cy: root.y, r: 9, class: "wt-node wt-node-root" }));
  kids.forEach((k) => s.append(el("circle", { cx: k.x, cy: k.y, r: 9, class: "wt-node" })));
  leaves.forEach((l) => s.append(el("circle", { cx: l.x, cy: l.y, r: 6, class: "wt-node wt-node-leaf" })));
  s.append(el("text", { x: 12, y: 14, class: "fig-label" }, about(L, "wt.tree.legend")));

  const run = () => {
    bars.forEach((b, i) => {
      if (REDUCED()) { b.setAttribute("width", widths[i]); return; }
      b.setAttribute("width", 0);
      b.style.transition = "none";
      requestAnimationFrame(() => {
        b.style.transition = "width 1.2s ease-out";
        b.setAttribute("width", widths[i]);
      });
    });
  };
  run();
  return { node: s, replay: run };
}

/* ---- 5. playing an imagined deal out to the end ------------------------ */

function figRollout(L) {
  const s = svg(104);
  const y = 52;
  // Nine tricks, then a score. The line is drawn rather than the cards, because what
  // matters is that the imagined deal is finished, not what was played in it.
  const path = el("path", {
    d: `M 20 ${y} ${Array.from({ length: 9 }, (_, i) => `L ${20 + (i + 1) * 28} ${y + (i % 2 ? -9 : 9)}`).join(" ")}`,
    class: "wt-rollout",
  });
  s.append(path);
  for (let i = 0; i <= 9; i++) {
    s.append(el("circle", { cx: 20 + i * 28, cy: y + (i === 0 ? 0 : (i - 1) % 2 ? -9 : 9), r: 3, class: "dot" }));
  }
  s.append(el("text", { x: 20, y: 22, class: "fig-label" }, about(L, "wt.rollout.start")));
  s.append(el("text", { x: W - 12, y: 96, class: "fig-value", "text-anchor": "end" }, about(L, "wt.rollout.end")));

  const run = () => {
    const len = 300;
    if (REDUCED()) { path.style.strokeDasharray = "none"; return; }
    path.style.strokeDasharray = len;
    path.style.strokeDashoffset = len;
    path.style.transition = "none";
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        path.style.transition = "stroke-dashoffset 1s ease-out";
        path.style.strokeDashoffset = "0";
      })
    );
  };
  run();
  return { node: s, replay: run };
}

/* ---- 6. the answer: visits per candidate ------------------------------ */

const CANDIDATES = [
  { card: "♥ J", visits: 0.44 },
  { card: "♦ A", visits: 0.27 },
  { card: "♠ 9", visits: 0.19 },
  { card: "♣ 7", visits: 0.10 },
];

function figVotes(L) {
  const s = svg(150);
  const bars = CANDIDATES.map((c, i) => {
    const y = 20 + i * 32;
    s.append(el("text", { x: 10, y: y + 15, class: "fig-label" }, c.card));
    const bar = el("rect", { x: 52, y, width: 0, height: 20, rx: 3, class: `bar bar-${i}` });
    s.append(bar);
    s.append(el("text", { x: W - 10, y: y + 15, class: "fig-value", "text-anchor": "end" }, `${Math.round(c.visits * 100)}%`));
    return { bar, w: c.visits * (W - 120) };
  });
  s.append(el("text", { x: 52, y: 144, class: "fig-note" }, about(L, "wt.votes.note")));

  const run = () => {
    bars.forEach(({ bar, w }, i) => {
      if (REDUCED()) { bar.setAttribute("width", w); return; }
      bar.setAttribute("width", 0);
      bar.style.transition = "none";
      requestAnimationFrame(() => {
        bar.style.transition = `width .8s ease-out ${i * 0.08}s`;
        bar.setAttribute("width", w);
      });
    });
  };
  run();
  return { node: s, replay: run };
}

/* ---- 7. the endgame stops guessing ------------------------------------ */

function figEndgame(data, L) {
  const s = svg(140);
  const pts = data.endgame.points;
  const max = Math.max(...pts.map((p) => p.nodes));
  // Log scale: the whole point is that the cost multiplies by ~15 a card, which a linear
  // axis renders as three invisible bars and one tall one.
  pts.forEach((p, i) => {
    const y = 24 + i * 28;
    const w = Math.max(3, (Math.log10(p.nodes) / Math.log10(max)) * (W - 130));
    s.append(el("text", { x: 10, y: y + 14, class: "fig-label" }, about(L, "fig.cards", { n: p.cards_each, ms: p.ms })));
    s.append(el("rect", { x: 96, y, width: w, height: 18, rx: 3, class: `bar bar-${i}` }));
    s.append(el("text", { x: 100 + w, y: y + 14, class: "fig-value" }, p.nodes.toLocaleString(L)));
  });
  s.append(el("text", { x: 10, y: 16, class: "fig-label" }, about(L, "wt.endgame.legend")));
  return s;
}

/* ---- the stepper ------------------------------------------------------- */

export function walkthroughPanel(data, L) {
  const wrap = html("div", "about-panel");
  wrap.append(html("h3", null, about(L, "wt.h")), html("p", null, about(L, "wt.intro")));

  const steps = [
    { key: "info", build: () => ({ node: figInfoSet() }) },
    { key: "deal", build: () => figDeal(L) },
    { key: "rule", build: () => ({ node: figRuledOut(data, L) }) },
    { key: "tree", build: () => figTree(L) },
    { key: "roll", build: () => figRollout(L) },
    { key: "vote", build: () => figVotes(L) },
    { key: "endg", build: () => ({ node: figEndgame(data, L) }) },
  ];

  const stage = html("div", "wt-stage");
  const title = html("h4", "wt-title");
  const body = html("p", "wt-body");
  const figure = html("div", "wt-figure");
  const counter = html("span", "wt-counter");

  const dots = html("div", "wt-dots");
  const dotNodes = steps.map((_, i) => {
    const d = html("button", "wt-dot");
    d.type = "button";
    d.setAttribute("aria-label", String(i + 1));
    d.addEventListener("click", () => show(i));
    dots.append(d);
    return d;
  });

  let at = 0;
  let current = null;

  const show = (i) => {
    at = (i + steps.length) % steps.length;
    const step = steps[at];
    title.innerHTML = about(L, `wt.${step.key}.h`);
    body.innerHTML = about(L, `wt.${step.key}.p`);
    current = step.build();
    figure.replaceChildren(current.node);
    counter.textContent = `${at + 1} / ${steps.length}`;
    dotNodes.forEach((d, k) => d.classList.toggle("on", k === at));
    replay.hidden = !current.replay;
  };

  const prev = html("button", "wt-nav", about(L, "wt.prev"));
  const next = html("button", "wt-nav wt-nav-main", about(L, "wt.next"));
  const replay = html("button", "wt-nav", about(L, "wt.replay"));
  for (const b of [prev, next, replay]) b.type = "button";
  prev.addEventListener("click", () => show(at - 1));
  next.addEventListener("click", () => show(at + 1));
  // Replaying matters most on the deal: a second run shows a *different* imagined world,
  // which is the step's whole claim.
  replay.addEventListener("click", () => current?.replay?.());

  const nav = html("div", "wt-nav-row");
  nav.append(prev, next, replay, counter);
  stage.append(title, body, figure, dots, nav);
  wrap.append(stage);

  show(0);
  return wrap;
}
