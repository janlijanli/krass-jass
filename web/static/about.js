/* "How it works" — the in-app documentation.
 *
 * Three audiences, three panels (docs/documentation-plan.md §1): the player asking why the
 * bot did that, the sceptic asking for proof, and a developer wanting the moving parts.
 *
 * Every number here renders from `docs/measurements.json` with the date and sample size it
 * was measured with. Nothing is typed into prose — a figure without an `n` is not evidence,
 * and hand-copied numbers go stale silently. That holds across languages too: the prose
 * lives in about-i18n.js with placeholders, so a re-measurement updates all four at once.
 *
 * Figures are hand-written inline SVG rather than a charting library: there are four of
 * them, and a library would be more code than the figures. Motion carries the argument or
 * is absent, each one has a static end state, and `prefers-reduced-motion` is respected.
 */

import { getLang } from "./i18n.js";
import { about } from "./about-i18n.js";
import { walkthroughPanel } from "./walkthrough.js";

const NS = "http://www.w3.org/2000/svg";

const el = (tag, attrs = {}, ...children) => {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  for (const c of children) node.append(c);
  return node;
};

const html = (tag, cls, content) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (content !== undefined) node.innerHTML = content;
  return node;
};

const pct = (v) => `${v.toFixed(2)}%`;

/* ---------- figure 1: the ladder, as a forest plot ----------------------- */

function ladderFigure(data) {
  const { matchups, deals } = data.ladder;
  const W = 320;
  const rowH = 30;
  const H = matchups.length * rowH + 34;
  // Reserve the right-hand strip for the value labels — at 65%+ the dots ran straight into
  // them on the full width.
  const PLOT_RIGHT = W - 76;
  const x = (share) => 20 + ((share - 44) / 28) * (PLOT_RIGHT - 20);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "fig" });
  // 50% is the line that matters: an interval crossing it is inconclusive, and saying so
  // is more honest than a bar chart that implies a result.
  svg.append(el("line", { x1: x(50), y1: 14, x2: x(50), y2: H - 20, class: "axis-line" }));
  svg.append(el("text", { x: x(50), y: 10, class: "fig-tick", "text-anchor": "middle" }, "50%"));
  svg.append(el("text", { x: PLOT_RIGHT, y: 10, class: "fig-tick", "text-anchor": "middle" }, "72%"));

  matchups.forEach((m, i) => {
    const y = 26 + i * rowH;
    // 95% CI on the mean: 1.96 standard errors.
    const se = m.std / Math.sqrt(deals);
    const lo = m.share - 1.96 * se;
    const hi = m.share + 1.96 * se;
    const inconclusive = lo < 50 && hi > 50;

    svg.append(
      el("text", { x: 20, y: y - 6, class: "fig-label" }, `${m.a} vs ${m.b}`)
    );
    svg.append(
      el("line", {
        x1: x(lo), y1: y + 4, x2: x(hi), y2: y + 4,
        class: `ci ${inconclusive ? "ci-null" : ""}`,
      })
    );
    svg.append(
      el("circle", {
        cx: x(m.share), cy: y + 4, r: 3.5,
        class: `dot ${inconclusive ? "dot-null" : ""}`,
      })
    );
    svg.append(
      el("text", { x: W - 8, y: y + 8, class: "fig-value", "text-anchor": "end" }, pct(m.share))
    );
  });
  return svg;
}

/* ---------- figure 2: the saturation curve ------------------------------ */

function saturationFigure(data, L) {
  const pts = data.budget_sweep.points;
  const W = 320;
  const H = 150;
  const xs = pts.map((p) => Math.log10(p.iterations));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const x = (it) => 34 + ((Math.log10(it) - minX) / (maxX - minX)) * (W - 54);
  const y = (share) => H - 26 - ((share - 42) / 10) * (H - 46);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "fig" });
  svg.append(el("line", { x1: 30, y1: y(50), x2: W - 14, y2: y(50), class: "axis-line" }));
  svg.append(el("text", { x: 26, y: y(50) + 3, class: "fig-tick", "text-anchor": "end" }, "50%"));
  svg.append(el("text", { x: 26, y: y(44) + 3, class: "fig-tick", "text-anchor": "end" }, "44%"));

  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(p.iterations)},${y(p.share)}`).join(" ");
  const line = el("path", { d: path, class: "curve" });
  svg.append(line);

  pts.forEach((p) => {
    svg.append(el("circle", { cx: x(p.iterations), cy: y(p.share), r: 3.5, class: "dot" }));
    svg.append(
      el(
        "text",
        { x: x(p.iterations), y: H - 10, class: "fig-tick", "text-anchor": "middle" },
        p.iterations >= 1000 ? `${p.iterations / 1000}k` : String(p.iterations)
      )
    );
  });

  // The knee is the whole point of the figure, so it is marked rather than left to be read.
  const knee = pts.find((p) => p.iterations === 2400);
  svg.append(
    el("text", { x: x(knee.iterations) + 6, y: y(knee.share) - 8, class: "fig-note" }, about(L, "fig.flat"))
  );

  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const len = 600;
    line.style.strokeDasharray = len;
    line.style.strokeDashoffset = len;
    line.style.transition = "stroke-dashoffset 1.1s ease-out";
    requestAnimationFrame(() => requestAnimationFrame(() => (line.style.strokeDashoffset = "0")));
  }
  return svg;
}

/* ---------- figure 3: void inference ------------------------------------ */

const SUITS = ["♦", "♥", "♠", "♣"];
const RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6"];

function voidFigure(L) {
  /* The single most legible piece of bot reasoning, and the Puur case is what shows it is
     precise rather than approximate. Hearts are trump; the opponent discards a club on a
     heart lead, which rules out every heart they could hold EXCEPT the Jack. */
  const W = 320;
  const cell = 26;
  const H = 4 * cell + 46;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "fig" });
  const left = 26;

  const cells = [];
  SUITS.forEach((suit, s) => {
    svg.append(
      el("text", { x: 16, y: 22 + s * cell + 14, class: "fig-tick", "text-anchor": "end" }, suit)
    );
    RANKS.forEach((rank, r) => {
      const g = el("g");
      const rect = el("rect", {
        x: left + r * cell, y: 22 + s * cell, width: cell - 3, height: cell - 3,
        rx: 3, class: "cardcell",
      });
      const label = el(
        "text",
        {
          x: left + r * cell + (cell - 3) / 2, y: 22 + s * cell + (cell - 3) / 2 + 4,
          class: "cardcell-label", "text-anchor": "middle",
        },
        rank
      );
      g.append(rect, label);
      svg.append(g);
      // s === 1 is hearts, r === 3 is the Jack — the Puur.
      cells.push({ suit: s, rank: r, rect, label });
    });
  });

  const caption = html("p", "fig-caption", about(L, "play.void.1"));
  const wrap = html("div", "fig-wrap");
  wrap.append(svg, caption);

  const steps = [
    { key: "play.void.1", ruled: () => [] },
    { key: "play.void.2", ruled: (c) => c.suit === 2 },
    { key: "play.void.3", ruled: (c) => c.suit === 2 || (c.suit === 1 && c.rank !== 3) },
  ];

  let step = 0;
  const draw = () => {
    const { key, ruled } = steps[step];
    caption.innerHTML = about(L, key);
    cells.forEach((c) => {
      c.rect.classList.toggle("ruled", !!ruled(c));
      c.label.classList.toggle("ruled", !!ruled(c));
      // The Puur is highlighted once it is the only heart left standing.
      const isPuur = c.suit === 1 && c.rank === 3;
      c.rect.classList.toggle("kept", step === 2 && isPuur);
    });
  };
  draw();

  const button = html("button", "fig-step", about(L, "play.void.next"));
  button.addEventListener("click", () => {
    step = (step + 1) % steps.length;
    button.textContent = about(L, step === steps.length - 1 ? "play.void.restart" : "play.void.next");
    draw();
  });
  wrap.append(button);
  return wrap;
}

/* ---------- figure 4: throughput ---------------------------------------- */

function throughputFigure(data) {
  const rows = data.throughput.rows;
  const W = 320;
  const barH = 26;
  const H = rows.length * (barH + 10) + 18;
  const max = Math.max(...rows.map((r) => r.iterations_per_sec));

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "fig" });
  rows.forEach((r, i) => {
    const y = 8 + i * (barH + 10);
    const w = Math.max(2, (r.iterations_per_sec / max) * (W - 120));
    svg.append(el("text", { x: 4, y: y + 16, class: "fig-label" }, r.engine));
    svg.append(
      el("rect", { x: 92, y, width: w, height: barH, rx: 3, class: `bar bar-${i}` })
    );
    svg.append(
      el("text", { x: 96 + w, y: y + 17, class: "fig-value" }, `${r.ms_per_move} ms`)
    );
  });
  return svg;
}

/* ---------- the panels --------------------------------------------------- */

function playerPanel(data, L) {
  const wrap = html("div", "about-panel");
  wrap.append(
    html("h3", null, about(L, "play.doing.h")),
    html("p", null, about(L, "play.doing.p")),
    html("h3", null, about(L, "play.knows.h")),
    html("p", null, about(L, "play.knows.p")),
    html("h3", null, about(L, "play.works.h")),
    html("p", null, about(L, "play.works.p"))
  );
  wrap.append(voidFigure(L));
  wrap.append(
    html("h3", null, about(L, "play.advice.h")),
    html("p", null, about(L, "play.advice.p")),
    html("h3", null, about(L, "play.weak.h")),
    html("p", "warn", about(L, "play.weak.p")),
    html("p", null, about(L, "play.human.p", { parity: data.literature.human_parity }))
  );
  return wrap;
}

function strengthPanel(data, L) {
  const wrap = html("div", "about-panel");
  const { ladder, budget_sweep, trump_selection } = data;

  wrap.append(
    html("h3", null, about(L, "strength.h")),
    html(
      "p",
      null,
      about(L, "strength.intro") +
        ` <span class="meta">` +
        about(L, "strength.meta", {
          date: data.measured_on,
          machine: data.machine,
          conditions: data.conditions,
        }) +
        `</span>`
    ),
    html("h4", null, about(L, "strength.ladder.h")),
    html("p", null, about(L, "strength.ladder.p", { deals: ladder.deals }))
  );
  wrap.append(ladderFigure(data));
  const high = budget_sweep.high_end[1];
  wrap.append(
    html("p", "fig-caption", about(L, "strength.ladder.caption")),

    html("h4", null, about(L, "strength.double.h")),
    html("p", null, about(L, "strength.double.p")),

    html("h4", null, about(L, "strength.budget.h")),
    html("p", null, about(L, "strength.budget.p", { deals: budget_sweep.deals }))
  );
  wrap.append(saturationFigure(data, L));
  wrap.append(
    html(
      "p",
      "fig-caption",
      about(L, "strength.budget.caption", {
        a: high.a.toLocaleString(L),
        b: high.b.toLocaleString(L),
        share: pct(high.share),
        n: high.deals,
        p: high.p,
        claim: data.literature.budget_claim,
      })
    ),

    html("h4", null, about(L, "strength.trump.h")),
    html(
      "p",
      null,
      about(L, "strength.trump.p", {
        share: pct(trump_selection.share),
        deals: trump_selection.deals,
        spread: (2 * (trump_selection.share - 50)).toFixed(0),
        claim: data.literature.trump_selection_claim,
      })
    ),

    html("h4", null, about(L, "strength.gap.h")),
    html(
      "p",
      null,
      about(L, "strength.gap.p", {
        share: pct(ladder.matchups[3].share),
        other: pct(100 - ladder.matchups[3].share),
      })
    ),

    html("p", "warn", about(L, "strength.caveat"))
  );
  return wrap;
}

function internalsPanel(data, L) {
  const wrap = html("div", "about-panel");
  wrap.append(
    html("h3", null, about(L, "internals.h")),
    html("p", null, about(L, "internals.p")),
    html("h4", null, about(L, "internals.rust.h")),
    html("p", null, about(L, "internals.rust.p"))
  );
  wrap.append(throughputFigure(data));
  const costs = data.endgame.points
    .map((p) => about(L, "fig.cards", { n: p.cards_each, ms: p.ms }))
    .join(", ");
  wrap.append(
    html("p", "fig-caption", about(L, "internals.rust.caption")),

    html("h4", null, about(L, "internals.rules.h")),
    html("p", null, about(L, "internals.rules.p")),

    html("h4", null, about(L, "internals.endgame.h")),
    html("p", null, about(L, "internals.endgame.p", { costs })),

    html("h4", null, about(L, "internals.honest.h")),
    html("p", null, about(L, "internals.honest.p")),

    html("p", "warn", about(L, "internals.caveat"))
  );
  return wrap;
}

export function buildAbout(data) {
  // Read once per build: menu.js rebuilds the whole panel when the language changes, so a
  // half-translated panel is not reachable.
  const L = getLang();
  const panels = {
    play: () => playerPanel(data, L),
    strength: () => strengthPanel(data, L),
    internals: () => internalsPanel(data, L),
    walk: () => walkthroughPanel(data, L),
  };
  const built = {};
  const body = html("div", "about-body");

  const tabs = html("div", "about-tabs");
  const names = [
    ["play", about(L, "tab.play")],
    ["strength", about(L, "tab.strength")],
    ["internals", about(L, "tab.internals")],
    ["walk", about(L, "tab.walk")],
  ];
  let active = "play";

  const show = (key) => {
    active = key;
    if (!built[key]) built[key] = panels[key]();
    body.replaceChildren(built[key]);
    tabs.querySelectorAll("button").forEach((b) =>
      b.classList.toggle("on", b.dataset.panel === key)
    );
    body.scrollTop = 0;
  };

  for (const [key, label] of names) {
    const button = html("button", "about-tab", label);
    button.type = "button";
    button.dataset.panel = key;
    button.addEventListener("click", () => show(key));
    tabs.append(button);
  }

  const wrap = html("div", "about");
  wrap.append(tabs, body);
  show(active);
  return wrap;
}
