/**
 * The engine report. Every number renders from `measurements.json` — docs/documentation-plan.md
 * §3: figures come from an artifact, never from typed prose. What lives here is only *which*
 * measurement answers which question (a path into the file) and how to draw it.
 */

const DATA_URL = "measurements.json";
const $ = (id) => document.getElementById(id);

/** `get(d, "ismcts.vs_dmcts.2")` — dotted path, numeric parts index arrays. */
function get(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[/^\d+$/.test(k) ? Number(k) : k]), obj);
}

/** A match row as an effect in points of a round's share, with a 95% interval. */
function effect(row, fallbackN) {
  const n = row.deals ?? fallbackN;
  const se = row.se ?? row.std / Math.sqrt(n);
  const d = row.share - 50;
  return { d, se, lo: d - 1.96 * se, hi: d + 1.96 * se, n, p: row.p };
}

const signed = (x, digits = 2) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(digits)}`;
const int = (x) => Math.round(x).toLocaleString("en-US");
function fmtP(p) {
  if (p == null) return "—";
  if (p === 0) return "&lt; 1e-16";
  if (p < 0.001) return p.toExponential(1).replace("e-", "e−");
  return p.toFixed(p < 0.01 ? 3 : 2);
}
const pEq = (p) => (p === 0 ? "p &lt; 1e-16" : `p = ${fmtP(p)}`);
const KIND_LABEL = { gain: "ships", null: "null", loss: "harmful", built: "built" };
const tag = (kind, text = KIND_LABEL[kind]) => `<span class="tag ${kind}">${text}</span>`;

/* ------------------------------------------------------------------ tooltip */

function initTooltip() {
  const tip = $("tip");
  let current = null;
  const place = (e) => {
    const pad = 14;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - pad;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
    tip.style.left = `${Math.max(8, x)}px`;
    tip.style.top = `${Math.max(8, y)}px`;
  };
  document.addEventListener("pointerover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el === current) return;
    current = el;
    if (!el) { tip.hidden = true; return; }
    tip.innerHTML = el.dataset.tip;
    tip.hidden = false;
    place(e);
  });
  document.addEventListener("pointermove", (e) => { if (current) place(e); });
  document.addEventListener("scroll", () => { tip.hidden = true; current = null; }, { passive: true });
}

/* ------------------------------------------------------------ row charts */

/**
 * A horizontal chart built from HTML rows: the label stays HTML (readable at phone width), the
 * marks are positioned by percentage. `mode` is "dot" (point + 95% interval) or "bar" (from zero).
 */
function rowChart(el, { domain, zero = 0, ticks, fmtTick = String, groups, mode = "dot", unit = "" }) {
  const [lo, hi] = domain;
  const pct = (x) => Math.max(0, Math.min(100, ((x - lo) / (hi - lo)) * 100));
  const gridlines = ticks.map((t) => `<i class="rc-grid" style="left:${pct(t)}%"></i>`).join("")
    + `<i class="rc-zero" style="left:${pct(zero)}%"></i>`;
  let html = `<div class="rc"><div class="rc-row rc-axis"><div></div><div class="rc-track">${
    ticks.map((t) => `<span style="left:${pct(t)}%">${fmtTick(t)}</span>`).join("")
  }</div><div></div></div>`;
  for (const g of groups) {
    if (g.title) html += `<div class="rc-group">${g.title}</div>`;
    for (const it of g.items) {
      let marks = "";
      if (mode === "bar") {
        const a = pct(Math.min(zero, it.v));
        const b = pct(Math.max(zero, it.v));
        marks += `<i class="rc-bar ${it.cls}" style="left:${a}%;width:${Math.max(0.6, b - a)}%"></i>`;
      }
      if (it.lo != null) {
        marks += `<i class="rc-ci ${it.cls}" style="left:${pct(it.lo)}%;width:${pct(it.hi) - pct(it.lo)}%"></i>`;
      }
      if (mode === "dot") {
        // Off the axis: pin to the edge and say so, rather than stretch the axis for one row.
        const off = it.v < lo || it.v > hi;
        marks += `<i class="rc-dot ${it.cls}${off ? " off" : ""}" style="left:${pct(it.v)}%"></i>`;
        if (off) marks += `<i class="rc-off" style="${it.v < lo ? "left:14px" : "right:14px"}">${it.v < lo ? "◀ off scale" : "off scale ▶"}</i>`;
      }
      html += `<div class="rc-row" data-tip="${(it.tip ?? "").replace(/"/g, "&quot;")}">
        <div class="rc-lbl">${it.label}${it.sub ? `<small>${it.sub}</small>` : ""}</div>
        <div class="rc-track">${gridlines}${marks}</div>
        <div class="rc-val">${it.text ?? ""}${unit}</div></div>`;
    }
  }
  el.innerHTML = html + "</div>";
}

/* ----------------------------------------------------------- line charts */

/** SVG line/step chart. One y-axis, always. */
function lineChart(el, opts) {
  // Drawn at the width it is shown at, so the text is real size on a phone rather than a
  // desktop chart scaled down. Redrawn when that width changes.
  const draw = () => drawLine(el, { ...opts, w: Math.max(300, Math.min(opts.w ?? 480, el.clientWidth - 12 || 480)) });
  draw();
  let last = el.clientWidth;
  new ResizeObserver(() => { if (el.clientWidth !== last) { last = el.clientWidth; draw(); } }).observe(el);
}

function drawLine(el, { w, h = 260, x, y, series = [], marks = [], ref, aria }) {
  const m = { l: 46, r: 18, t: 16, b: 40 };
  const iw = w - m.l - m.r;
  const ih = h - m.t - m.b;
  const tx = (v) => {
    const [a, b] = x.domain;
    const f = x.log ? (Math.log(v) - Math.log(a)) / (Math.log(b) - Math.log(a)) : (v - a) / (b - a);
    return m.l + f * iw;
  };
  const ty = (v) => m.t + (1 - (v - y.domain[0]) / (y.domain[1] - y.domain[0])) * ih;
  let s = "";
  for (const t of y.ticks) {
    s += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${ty(t)}" y2="${ty(t)}"/>`;
    s += `<text x="${m.l - 8}" y="${ty(t) + 4}" text-anchor="end">${y.fmt ? y.fmt(t) : t}</text>`;
  }
  // Thin the labels when they would collide; the gridless x-axis keeps every position anyway.
  const every = Math.ceil(46 / (iw / x.ticks.length));
  for (const [i, t] of x.ticks.entries()) {
    if (i % every) continue;
    s += `<text x="${tx(t)}" y="${h - m.b + 16}" text-anchor="middle">${x.fmt ? x.fmt(t) : t}</text>`;
  }
  s += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  if (x.label) s += `<text x="${m.l + iw / 2}" y="${h - 6}" text-anchor="middle">${x.label}</text>`;
  if (y.label) s += `<text x="12" y="${m.t + ih / 2}" text-anchor="middle" transform="rotate(-90 12 ${m.t + ih / 2})">${y.label}</text>`;
  if (ref != null) s += `<line class="zero" x1="${m.l}" x2="${w - m.r}" y1="${ty(ref)}" y2="${ty(ref)}"/>`;

  const dot = (p, cls, r = 4.5) => {
    let g = "";
    if (p.lo != null) g += `<line class="ci ${cls}" x1="${tx(p.x)}" x2="${tx(p.x)}" y1="${ty(p.lo)}" y2="${ty(p.hi)}"/>`;
    g += `<circle class="dot ${cls}" cx="${tx(p.x)}" cy="${ty(p.y)}" r="${r}"/>`;
    return `<g data-tip="${(p.tip ?? "").replace(/"/g, "&quot;")}"><circle class="hit" cx="${tx(p.x)}" cy="${ty(p.y)}" r="13"/>${g}</g>`;
  };
  for (const se of series) {
    const pts = se.pts;
    let d = "";
    pts.forEach((p, i) => {
      if (i === 0) d += `M${tx(p.x)},${ty(p.y)}`;
      else if (se.step) d += `H${tx(p.x)}V${ty(p.y)}`;
      else d += `L${tx(p.x)},${ty(p.y)}`;
    });
    if (se.stepTo != null) d += `H${tx(se.stepTo)}`;
    s += `<path class="line ${se.cls}" d="${d}" fill="none"/>`;
    s += pts.filter((p) => !p.hidden).map((p) => dot(p, se.cls)).join("");
    if (se.label) {
      const last = pts[pts.length - 1];
      const lx = se.stepTo != null ? tx(se.stepTo) : tx(last.x);
      s += `<text class="lbl" x="${lx}" y="${ty(last.y) - 10}" text-anchor="end">${se.label}</text>`;
    }
  }
  for (const mk of marks) {
    s += dot(mk, mk.cls, 5.5);
    if (mk.label) s += `<text class="lbl" x="${tx(mk.x) + (mk.dx ?? 9)}" y="${ty(mk.y) + (mk.dy ?? 4)}" text-anchor="${mk.anchor ?? "start"}">${mk.label}</text>`;
  }
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${aria ?? ""}">${s}</svg>`;
}

function legend(el, items) {
  el.innerHTML = items.map(([cls, text, line]) =>
    `<span><i class="${line ? "line " : ""}" style="background:var(--${cls})"></i>${text}</span>`).join("");
}

/* ------------------------------------------------------------- sections */

function renderHeader(d) {
  $("meta").innerHTML = `Measured ${d.measured_on} and after · ${d.machine} · ${d.conditions}.`;
  const gap = d.post_ismcts_recheck.cheating_gap;
  const conv = d.convention_price;
  const tiles = [
    [int(d.budget_under_house.ships), "search iterations a move", "40 imagined deals × 3,840 iterations (§3b)"],
    [`${signed(stackedGain(d), 1)}`, "points of a round's share, the shipped steps summed", "each step measured against the bot of its day"],
    [`${d.trump_fit.games.a_wins.toFixed(1)}%`, "of games won by the tuned trump weights", `vs the hand-written ones, ${int(d.trump_fit.games.games)} games (§5n)`],
    [`~${(gap.share - 50).toFixed(1)}`, "points behind a bot that sees all four hands", `${int(gap.deals)} deals, before the belief work (§3f)`],
    [`${conv.predictable.toFixed(0)}%`, "of convention decisions play the card a Swiss partner expects", `from ${conv.predictable_search_only.toFixed(0)}% for the search alone, at no cost (§5u)`],
  ];
  $("tiles").innerHTML = tiles.map(([v, l, s]) =>
    `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div><div class="s">${s}</div></div>`).join("");
}

/* When each thing happened. Dates are the commit that landed it (git log); the effect is a path
   into measurements.json. `games` marks a result measured in games won rather than points. */
const EVENTS = [
  { day: 9, kind: "built", title: "Rules engine on bitboards, with property tests", ref: "M0–M1" },
  { day: 9, kind: "built", title: "Search core ported to Rust", ref: "PyO3" },
  { day: 10, kind: "built", title: "Voting search (DMCTS), void inference, the arena with double rounds", ref: "M4" },
  { day: 10, kind: "built", title: "Rule-based trump selection and bidding", ref: "M3" },
  { day: 10, kind: "built", title: "Playable web app; bots in isolated containers", ref: "M2" },
  { day: 10, kind: "null", title: "Budget looks saturated at 2,400 iterations", ref: "§3", path: "budget_sweep.points.4", n: 500, aside: "true only of the voting search" },
  { day: 11, kind: "built", title: "The whole game in the browser, compiled to wasm", ref: "site" },
  { day: 11, kind: "null", title: "Table conventions, on ties only", ref: "§5b", path: "conventions" },
  { day: 11, kind: "null", title: "Reading the partner's discard signal", ref: "§5c", path: "signal_reading.runs.2" },
  { day: 11, kind: "null", title: "Playing for the game rather than the round", ref: "§5d", games: "game_objective.runs.4" },
  { day: 11, kind: "null", title: "Risk-averse reward", ref: "§5f", path: "risk_aversion.points.0", n: 600 },
  { day: 11, kind: "loss", title: "Linear leaf evaluator instead of random playouts", ref: "§5g", path: "leaf_evaluator.points.0", n: 600 },
  { day: 11, kind: "gain", title: "Information Set MCTS — one tree shared across imagined deals", ref: "§5h", path: "ismcts.vs_dmcts.2", stack: true },
  { day: 11, kind: "null", title: "Hand-written policy prior in the selection rule", ref: "§5i", path: "policy_prior.points.6" },
  { day: 11, kind: "null", title: "Policy prior learned from the search's own play", ref: "§5j", path: "learned_prior.control.2" },
  { day: 11, kind: "built", title: "Oracle experiment: what better beliefs would be worth", ref: "§5k" },
  { day: 11, kind: "gain", title: "Shown Weis cards pinned to the seat that showed them", ref: "§5l", pool: "shown_weis.rounds", stack: true },
  { day: 13, kind: "gain", title: "Called Weis values — and a sampler bug they exposed", ref: "§5m", path: "called_weis.rounds_pooled", stack: true },
  { day: 13, kind: "gain", title: "64× the search budget: 153,600 iterations", ref: "§3b", path: "budget_under_house.points.2", stack: true },
  { day: 14, kind: "gain", title: "Exact endgame solver switched off", ref: "§3e", path: "endgame_depth.rows.2", stack: true },
  { day: 14, kind: "loss", title: "Signal reading, re-run on the shared tree", ref: "§3f", path: "post_ismcts_recheck.rows.0" },
  { day: 15, kind: "gain", title: "Trump weights tuned against simulated contract values", ref: "§5n", games: "trump_fit.games" },
  { day: 15, kind: "gain", title: "Beliefs: imagined deals weighted by the other seats' plays and bid", ref: "§5o", path: "belief_offline.match", stack: true },
  { day: 15, kind: "null", title: "Exploration constant 0.7, 1.0, 2.5 against 1.5", ref: "§5p", path: "exploration.matchups.0" },
  { day: 15, kind: "null", title: "Belief network trained on the true deals", ref: "§5q", path: "belief_network.match" },
  { day: 16, kind: "null", title: "Sharper belief settings; play model retrained on today's bot", ref: "§5r", path: "belief_round_two.belief_settings" },
  { day: 16, kind: "gain", title: "The other seats move by the play model inside the tree", ref: "§5p", path: "tree_policy_shipped.pooled", stack: true },
  { day: 16, kind: "loss", title: "A policy network playing without search", ref: "§5s", path: "policy_network.heads.1.vs_search" },
  { day: 18, kind: "null", title: "A value network at the leaves", ref: "§5t", path: "value_network.matches.0" },
  { day: 19, kind: "gain", title: "Swiss conventions, allowed to cost up to 0.01", ref: "§5u", path: "convention_price", aside: (d) => `free, and ${d.convention_price.predictable.toFixed(0)}% conventional` },
  { day: 20, kind: "gain", title: "Play model retrained on self-play with the conventions on", ref: "§5w", pool: "play_model_conventions.runs", stack: true },
];

function eventEffect(d, ev) {
  if (ev.pool) {
    const rows = get(d, ev.pool);
    const parent = get(d, ev.pool.split(".").slice(0, -1).join(".") || ev.pool);
    const nOf = (r) => r.deals ?? parent.deals;
    const n = rows.reduce((a, r) => a + nOf(r), 0);
    const share = rows.reduce((a, r) => a + r.share * nOf(r), 0) / n;
    const v = rows.reduce((a, r) => a + r.std ** 2 * nOf(r), 0) / n;
    return effect({ share, std: Math.sqrt(v), deals: n });
  }
  if (ev.path) {
    const row = get(d, ev.path);
    return effect(row, ev.n ?? get(d, ev.path.split(".")[0]).deals);
  }
  return null;
}

function stackedGain(d) {
  return EVENTS.filter((e) => e.stack).reduce((a, e) => a + eventEffect(d, e).d, 0);
}

function renderTimeline(d) {
  // Cumulative step chart of the shipped increments.
  let acc = 0;
  const pts = [{ x: 9, y: 0, hidden: true }];
  for (const ev of EVENTS.filter((e) => e.stack)) {
    const fx = eventEffect(d, ev);
    acc += fx.d;
    pts.push({
      x: ev.day, y: acc,
      tip: `<b>Sep ${ev.day} · ${ev.title}</b><br>${signed(fx.d)} ± ${(1.96 * fx.se).toFixed(2)} (95% CI), ${int(fx.n)} deals · ${ev.ref}<br>running sum ${signed(acc)}`,
    });
  }
  lineChart($("chart-cumulative"), {
    w: 720, h: 250,
    x: { domain: [9, 20.6], ticks: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], fmt: (t) => `Sep ${t}`, label: "2026" },
    y: { domain: [0, Math.ceil(acc)], ticks: Array.from({ length: Math.ceil(acc) + 1 }, (_, i) => i), fmt: (t) => (t ? `+${t}` : "0"), label: "points" },
    series: [{ cls: "gain", pts, step: true, stepTo: 20.6, label: `sum of shipped steps ${signed(acc, 1)}` }],
    aria: "Cumulative shipped gains by date",
  });
  legend($("legend-timeline"), [["gain", "ships"], ["null", "null — measured, no effect"], ["loss", "harmful"], ["built", "built — infrastructure and instruments"]]);

  const days = [...new Set(EVENTS.map((e) => e.day))];
  $("timeline-list").innerHTML = days.map((day) => {
    const evs = EVENTS.filter((e) => e.day === day).map((ev) => {
      let fx = "";
      if (ev.games) {
        const g = get(d, ev.games);
        fx = `${(g.a_wins ?? g.wins).toFixed(1)}% of games`;
      } else {
        const e = eventEffect(d, ev);
        if (e) fx = `${signed(e.d)}`;
      }
      return `<li class="ev">${tag(ev.kind)}<span class="t"><b>${ev.title}</b> <small>${ev.ref}${ev.aside ? ` · ${typeof ev.aside === "function" ? ev.aside(d) : ev.aside}` : ""}</small></span><span class="fx">${fx}</span></li>`;
    }).join("");
    return `<li class="day"><div class="date">Sep ${day}, 2026</div><ul>${evs}</ul></li>`;
  }).join("");
}

function renderPower() {
  const ns = [600, 1000, 2000, 3000, 6000];
  const sds = [[5, "card play, EVAL rules"], [6.5, "card play, HOUSE rules"], [9.6, "bidding changes"]];
  $("power").innerHTML = `<thead><tr><th>per-deal sd</th>${ns.map((n) => `<th class="num">${int(n)} deals</th>`).join("")}</tr></thead><tbody>${
    sds.map(([sd, what]) => `<tr><td>${sd} <small>(${what})</small></td>${
      ns.map((n) => `<td class="num">${(2.8 * sd / Math.sqrt(n)).toFixed(2)}</td>`).join("")}</tr>`).join("")
  }</tbody>`;
}

const FOREST = [
  ["gain", "Ships", [
    ["ISMCTS vs the voting search", "equal iterations, third seed · §5h", "ismcts.vs_dmcts.2"],
    ["ISMCTS vs the voting search", "equal wall-clock · §5h", "ismcts.vs_dmcts.3"],
    ["Shown Weis cards pinned", "seed 8802 · §5l", "shown_weis.rounds.1"],
    ["Called Weis values", "pooled over four seeds · §5m", "called_weis.rounds_pooled"],
    ["153,600 vs 2,400 iterations", "HOUSE rules · §3b", "budget_under_house.points.2"],
    ["Endgame solver off", "vs 5 cards · §3e", "endgame_depth.rows.2"],
    ["Beliefs from plays and bid", "replication, fresh seed · §5o", "belief_offline.replication"],
    ["Play model inside the tree", "pooled over two seeds · §5p", "tree_policy_shipped.pooled"],
    ["Tuned trump weights", "rounds, HOUSE · §5n", "trump_fit.rounds"],
    ["Swiss conventions within 0.01", "a price, not a gain · §5u", "convention_price"],
    ["Play model fitted with conventions on", "replication, seed 94 · §5w", "play_model_conventions.runs.1"],
  ]],
  ["null", "Measured null — not shipped", [
    ["Exploration constant 0.7", "vs 1.5 · §5p", "exploration.matchups.0"],
    ["Exploration constant 2.5", "vs 1.5 · §5p", "exploration.matchups.2"],
    ["Resample every iteration", "vs every 4 · §3c", "levers_at_the_new_budget.rows.0"],
    ["Belief network", "on top of plays and bid · §5q", "belief_network.match"],
    ["Sharper belief settings", "§5r", "belief_round_two.belief_settings"],
    ["Play model retrained, 64 hidden", "§5r", "belief_round_two.play_model_retrained.match"],
    ["Bidding read into the deals", "§5e", "bidding_prior"],
    ["Opponents searched as adversaries", "replication · §5d", "adversarial_search.runs.1"],
    ["Risk-averse reward, λ = 0.25", "§5f", "risk_aversion.points.0", 600],
    ["Hand-written PUCT prior, c = 2", "replication · §5i", "policy_prior.points.6"],
    ["Learned policy prior, c = 1", "fresh seed · §5j", "learned_prior.control.2"],
    ["Play model inside the tree, equal time", "14,400 vs 153,600 · §5p", "play_model_in_search.equal_time.0"],
    ["Value network at the leaves", "2,400 iterations · §5t", "value_network.matches.0"],
    ["Value network at the leaves", "153,600 iterations, 1.6× the time · §5t", "value_network.matches.1"],
  ]],
  ["loss", "Harmful", [
    ["Signal reading on the shared tree", "§3f", "post_ismcts_recheck.rows.0"],
    ["Endgame solver at 6 cards", "vs 5 · §3d", "endgame_depth.rows.0"],
    ["Hand-written PUCT prior, c = 4", "§5i", "policy_prior.points.4", 1000],
    ["Policy network, no search", "vs the shipped search · §5s", "policy_network.heads.1.vs_search"],
    ["Linear leaf evaluator", "40 × 60 · §5g", "leaf_evaluator.points.0", 600],
  ]],
];

function renderForest(d) {
  const groups = FOREST.map(([cls, title, rows]) => ({
    title: `${tag(cls)} ${title}`,
    items: rows.map(([label, sub, path, n]) => {
      const row = get(d, path);
      const e = effect(row, n ?? get(d, path.split(".")[0]).deals);
      return {
        label, sub, cls, v: e.d, lo: e.lo, hi: e.hi, text: signed(e.d),
        tip: `<b>${label}</b><br>${sub}<br>${signed(e.d)} points, 95% CI ${signed(e.lo)} to ${signed(e.hi)}<br>${int(e.n)} deals · ${pEq(e.p)}`,
        e, path,
      };
    }),
  }));
  rowChart($("chart-forest"), {
    domain: [-5, 2.5], ticks: [-4, -3, -2, -1, 0, 1, 2], fmtTick: (t) => (t > 0 ? `+${t}` : `${t}`.replace("-", "−")), groups,
  });
  legend($("legend-forest"), [["gain", "ships"], ["null", "null"], ["loss", "harmful"]]);
  $("forest-table").innerHTML = `<thead><tr><th>experiment</th><th></th><th class="num">effect</th><th class="num">95% CI</th><th class="num">deals</th><th class="num">p</th></tr></thead><tbody>${
    groups.flatMap((g) => g.items.map((it) => `<tr><td>${it.label}<br><small>${it.sub}</small></td><td>${tag(it.cls)}</td><td class="num">${signed(it.e.d)}</td><td class="num">${signed(it.e.lo)} … ${signed(it.e.hi)}</td><td class="num">${int(it.e.n)}</td><td class="num">${fmtP(it.e.p)}</td></tr>`)).join("")
  }</tbody>`;
}

const kfmt = (t) => (t >= 1000 ? `${t / 1000}k` : `${t}`);

function renderSearch(d) {
  const bu = d.budget_under_house;
  const bs = d.budget_sweep;
  const pt = (x, row, n, what) => {
    const e = effect(row, n);
    return { x, y: row.share, lo: row.share - 1.96 * e.se, hi: row.share + 1.96 * e.se,
      tip: `<b>${what}, ${int(x)} iterations</b><br>${row.share.toFixed(2)}% vs 2,400 · ${int(e.n)} deals · ${pEq(row.p)}` };
  };
  const ref = { x: 2400, y: 50, tip: "<b>Reference</b><br>2,400 iterations — both curves are measured against it" };
  lineChart($("chart-budget"), {
    x: { log: true, domain: [50, 800000], ticks: [60, 600, 2400, 38400, 153600, 614400], fmt: kfmt, label: "iterations a move (log)" },
    y: { domain: [43, 52], ticks: [44, 46, 48, 50, 52], fmt: (t) => `${t}%` },
    ref: 50,
    series: [
      { cls: "s2", pts: [ref, ...bs.points.filter((p) => !p.is_reference).map((p) => pt(p.iterations, p, bs.deals, "Voting search, EVAL"))].sort((a, b) => a.x - b.x) },
      { cls: "s1", pts: [ref, ...bu.points.map((p) => pt(p.iterations, p, p.deals, "Shared tree, HOUSE"))], label: "shared tree (ships)" },
    ],
    marks: [{ ...pt(bu.pimc_control.iterations, bu.pimc_control, bu.pimc_control.deals, "Voting search, HOUSE control"), cls: "s2", label: "voting, 64×", dx: 0, dy: 20, anchor: "middle" }],
    aria: "Search budget against strength for the two search algorithms",
  });
  legend($("legend-budget"), [["series-1", "shared tree (ISMCTS)", true], ["series-2", "voting search (DMCTS), replaced", true]]);

  const sp = d.split_sweep;
  const spPts = [...sp.points.map((p) => {
    const e = effect(p, sp.deals);
    return { x: p.determinizations, y: p.share, lo: p.share - 1.96 * e.se, hi: p.share + 1.96 * e.se,
      tip: `<b>${p.determinizations} deals × ${p.iterations} iterations</b><br>${p.share.toFixed(2)}% vs 40 × 60 · ${pEq(p.p)}` };
  }), { x: 40, y: 50, tip: "<b>Reference</b><br>40 deals × 60 iterations" }].sort((a, b) => a.x - b.x);
  lineChart($("chart-split"), {
    x: { log: true, domain: [3, 800], ticks: [4, 10, 20, 40, 80, 240, 600], label: "imagined deals (log) — iterations = 2,400 / deals" },
    y: { domain: [40, 52], ticks: [40, 44, 48, 52], fmt: (t) => `${t}%` },
    ref: 50, series: [{ cls: "s1", pts: spPts }], aria: "Split of a fixed budget",
  });

  const rs = d.ismcts.resample_every;
  rowChart($("chart-resample"), {
    domain: [-1, 2], ticks: [-1, 0, 1, 2], fmtTick: (t) => (t > 0 ? `+${t}` : `${t}`.replace("-", "−")),
    groups: [{ items: rs.points.map((p) => {
      const e = effect(p, rs.deals);
      const cls = e.lo > 0 ? "gain" : "null";
      return { label: `every ${p.k}`, sub: `${p.cost_vs_dmcts}× the voting search's time`, cls, v: e.d, lo: e.lo, hi: e.hi, text: signed(e.d),
        tip: `<b>New world every ${p.k} iteration${p.k > 1 ? "s" : ""}</b><br>ISMCTS vs the voting search: ${signed(e.d)} (95% CI ${signed(e.lo)} to ${signed(e.hi)})<br>${pEq(p.p)}` };
    }) }],
  });

  const eg = d.endgame_depth;
  const egItems = [
    ...eg.rows.filter((r) => !r.at_budget).map((r) => ({ r, k: r.endgame_cards })),
    { r: null, k: eg.baseline },
  ].sort((a, b) => b.k - a.k).map(({ r, k }) => {
    if (!r) return { label: `${k} cards`, sub: "reference", cls: "null", v: 0, text: "0.00", tip: `<b>${k} cards</b><br>the reference` };
    const e = effect(r);
    const cls = e.lo > 0 ? "gain" : e.hi < 0 ? "loss" : "null";
    return { label: k ? `${k} cards` : "off", sub: k ? "" : "ships", cls, v: e.d, lo: e.lo, hi: e.hi, text: signed(e.d),
      tip: `<b>Solver from ${k} cards each</b><br>${signed(e.d)} vs 5 cards, ${int(e.n)} deals · ${pEq(r.p)}` };
  });
  rowChart($("chart-endgame"), { domain: [-1, 2], ticks: [-1, 0, 1, 2], fmtTick: (t) => (t > 0 ? `+${t}` : `${t}`.replace("-", "−")), groups: [{ items: egItems }] });
}

function renderBeliefs(d) {
  const bv = d.belief_value;
  const pts = [{ x: 0, y: 0, tip: "<b>No oracle</b><br>the search's own beliefs" }, ...bv.points.map((p) => {
    const se = p.std / Math.sqrt(bv.deals);
    return { x: p.p, y: p.gain, lo: p.gain - 1.96 * se, hi: p.gain + 1.96 * se,
      tip: `<b>${Math.round(p.p * 100)}% of imagined deals are the true deal</b><br>${signed(p.gain)} points, ${int(bv.deals)} deals` };
  })];
  const bo = d.belief_offline;
  const shipped = bo.rows.find((r) => r.alpha === 1 && r.beta === 1);
  const bn = d.belief_network;
  const r2 = d.belief_round_two.belief_settings;
  const mk = (x, row, cls, label, what, extra = {}) => {
    const e = effect(row);
    return { x, y: e.d, lo: e.lo, hi: e.hi, cls, label, ...extra,
      tip: `<b>${what}</b><br>offline: ${(x * 100).toFixed(1)}% of an oracle<br>in play: ${signed(e.d)}, ${int(e.n)} deals, ${pEq(row.p)}` };
  };
  lineChart($("chart-oracle"), {
    w: 720, h: 300,
    x: { domain: [0, 1], ticks: [0, 0.2, 0.4, 0.6, 0.8, 1], fmt: (t) => `${Math.round(t * 100)}%`, label: "oracle-equivalent information p" },
    y: { domain: [-0.6, 8.5], ticks: [0, 2, 4, 6, 8], fmt: (t) => (t ? `+${t}` : "0"), label: "points gained" },
    series: [{ cls: "ref", pts }],
    marks: [
      mk(shipped.p_bots, bo.match, "gain", "", "Beliefs from plays and bid"),
      mk(bn.more_data.with_plays_bid_full, bn.match, "null", "", "+ belief network"),
      mk(r2.offline_p, r2, "null", "", "Sharper belief settings"),
    ],
    aria: "Value of information about the hidden cards",
  });
  legend($("legend-oracle"), [
    ["ink-2", "the true deal mixed in with probability p", true],
    ["gain", "reading plays and bid — ships, measured in play"],
    ["null", "later belief steps — higher offline, null in play"],
  ]);

  const rt = d.belief_round_two.play_model_retrained;
  const rows = [
    ["Plays and bid (ships)", `${(shipped.p_bots * 100).toFixed(1)}%`, bo.match, "gain"],
    ["Plays and bid, fresh seed", "", bo.replication, "gain"],
    ["+ belief network", `${(bn.more_data.with_plays_bid_full * 100).toFixed(1)}%`, bn.match, "null"],
    ["Sharper settings, pool 8,192", `${(r2.offline_p * 100).toFixed(1)}%`, r2, "null"],
    ["Play model retrained", `top-1 ${rt.h64.top1}% (from ${d.play_model.top1}%)`, rt.match, "null"],
  ];
  $("belief-table").innerHTML = `<thead><tr><th>step</th><th class="num">offline</th><th class="num">in play</th><th class="num">p</th></tr></thead><tbody>${
    rows.map(([s, off, m, k]) => `<tr><td>${s}</td><td class="num">${off}</td><td class="num">${tag(k, signed(m.share - 50))}</td><td class="num">${fmtP(m.p)}</td></tr>`).join("")
  }</tbody>`;
}

function renderTrump(d) {
  const t = d.trump_fit;
  const tiles = [
    [`${t.games.a_wins.toFixed(1)}%`, "of whole games won by the tuned weights", `${int(t.games.games)} games to ${int(t.games.target)}, ${pEq(t.games.p)}`],
    [signed(t.rounds.share - 50), "points of a round's share", `${int(t.rounds.deals)} deals, HOUSE, ${pEq(t.rounds.p)}`],
    [`+${t.fit_held_out.gain.toFixed(1)}`, "game points a round, on held-out hands", `± ${t.fit_held_out.se} SE, ${int(t.fit_held_out.deals)} deals`],
    [`${t.regret.regret.toFixed(1)}`, "game points a round left on the table", `vs the best call per hand, cross-fitted, ± ${t.regret.regret_se}`],
  ];
  $("trump-tiles").innerHTML = tiles.map(([v, l, s]) =>
    `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div><div class="s">${s}</div></div>`).join("");
}

function renderNetworks(d) {
  const vn = d.value_network;
  rowChart($("chart-rmse"), {
    domain: [0, 0.36], ticks: [0, 0.1, 0.2, 0.3], fmtTick: (t) => t.toFixed(1), mode: "bar",
    groups: [{ items: vn.rmse.map((r) => ({
      label: r.estimator, cls: r.estimator === "value network" ? "s1" : "null", v: r.rmse, text: r.rmse.toFixed(3),
      tip: `<b>${r.estimator}</b><br>RMSE ${r.rmse.toFixed(3)} against the real outcome`,
    })) }],
  });
  const pn = d.policy_network;
  rowChart($("chart-policy"), {
    domain: [35, 70], zero: 50, ticks: [40, 50, 60, 70], fmtTick: (t) => `${t}%`, mode: "bar",
    groups: pn.heads.map((h) => ({
      title: `${h.head} head · top-1 ${h.top1}%`,
      items: [["random", h.vs_random], ["greedy", h.vs_greedy], ["the search", h.vs_search.share]].map(([who, s]) => ({
        label: `vs ${who}`, cls: s >= 50 ? "s1" : "loss", v: s, text: `${s.toFixed(1)}%`,
        tip: `<b>${h.head} head vs ${who}</b><br>${s.toFixed(2)}% of the points, 1,000 deals`,
      })),
    })),
  });
}

function renderLadder(d) {
  const L = d.ladder;
  rowChart($("chart-ladder"), {
    domain: [45, 72], zero: 50, ticks: [50, 55, 60, 65, 70], fmtTick: (t) => `${t}%`, mode: "bar",
    groups: [{ items: L.matchups.map((m) => {
      const e = effect(m, L.deals);
      return { label: `${m.a}`, sub: `vs ${m.b}`, cls: m.a === "cheating" ? "s2" : e.lo > 0 ? "s1" : "null",
        v: m.share, lo: m.share - 1.96 * e.se, hi: m.share + 1.96 * e.se, text: `${m.share.toFixed(1)}%`,
        tip: `<b>${m.a} vs ${m.b}</b><br>${m.share.toFixed(2)}% ± ${m.std} sd · ${L.deals} deals · ${pEq(m.p)}` };
    }) }],
  });
  const T = d.throughput.rows;
  rowChart($("chart-throughput"), {
    domain: [0, 1.8e6], ticks: [0, 5e5, 1e6, 1.5e6], fmtTick: (t) => (t ? `${t / 1e6}M` : "0"), mode: "bar",
    groups: [{ items: T.map((r) => ({
      label: r.engine, sub: `${r.ms_per_move} ms a move`, cls: r.engine === "Python" ? "null" : "s1",
      v: r.iterations_per_sec, text: r.iterations_per_sec >= 1e6 ? `${(r.iterations_per_sec / 1e6).toFixed(2)}M/s` : `${Math.round(r.iterations_per_sec / 1000)}k/s`,
      tip: `<b>${r.engine}</b><br>${int(r.iterations_per_sec)} iterations/s · ${r.ms_per_move} ms per 2,400-iteration move`,
    })) }],
  });
}

function renderArtifacts(d) {
  $("pp-decisions").textContent = `${int(d.play_model.decisions)} decisions · top-1 ${d.play_model.top1}%`;
  $("bn-decisions").textContent = `${int(d.belief_network.more_data.decisions)} decisions`;
}

async function main() {
  // Back to the table: the page sits next to index.html on the static site and under /static/
  // on the server, where the table is at /.
  if (location.pathname.includes("/static/")) document.querySelector(".kicker a").href = "/";
  initTooltip();
  renderPower();
  let d;
  try {
    d = await fetch(DATA_URL).then((r) => r.json());
  } catch (err) {
    document.querySelector(".lede").insertAdjacentHTML("afterend", `<p><b>Could not load ${DATA_URL}.</b> ${err}</p>`);
    return;
  }
  for (const fn of [renderHeader, renderTimeline, renderForest, renderSearch, renderBeliefs, renderTrump, renderNetworks, renderLadder, renderArtifacts]) {
    try { fn(d); } catch (err) { console.error(fn.name, err); }
  }
}

main();
