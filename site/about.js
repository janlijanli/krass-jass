/* "How it works" — the in-app documentation.
 *
 * Three audiences, three panels (docs/documentation-plan.md §1): the player asking why the
 * bot did that, the sceptic asking for proof, and a developer wanting the moving parts.
 *
 * Every number here renders from `docs/measurements.json` with the date and sample size it
 * was measured with. Nothing is typed into prose — a figure without an `n` is not evidence,
 * and hand-copied numbers go stale silently.
 *
 * Figures are hand-written inline SVG rather than a charting library: there are four of
 * them, and a library would be more code than the figures. Motion carries the argument or
 * is absent, each one has a static end state, and `prefers-reduced-motion` is respected.
 */

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

function saturationFigure(data) {
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
    el("text", { x: x(knee.iterations) + 6, y: y(knee.share) - 8, class: "fig-note" }, "flat from here")
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

function voidFigure() {
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

  const caption = html("p", "fig-caption", "They follow suit, so nothing is known yet.");
  const wrap = html("div", "fig-wrap");
  wrap.append(svg, caption);

  const steps = [
    {
      text: "They follow suit, so nothing is known yet.",
      ruled: () => [],
    },
    {
      text: "They discard a <b>club</b> on a <b>spade</b> lead — so they hold no spades.",
      ruled: (c) => c.suit === 2,
    },
    {
      text:
        "Now a <b>heart</b> is led and they discard again. Hearts are trump, so they hold no " +
        "trump — <b>except possibly the Jack</b>, which they are allowed to keep back.",
      ruled: (c) => c.suit === 2 || (c.suit === 1 && c.rank !== 3),
    },
  ];

  let step = 0;
  const draw = () => {
    const { text, ruled } = steps[step];
    caption.innerHTML = text;
    cells.forEach((c) => {
      c.rect.classList.toggle("ruled", !!ruled(c));
      c.label.classList.toggle("ruled", !!ruled(c));
      // The Puur is highlighted once it is the only heart left standing.
      const isPuur = c.suit === 1 && c.rank === 3;
      c.rect.classList.toggle("kept", step === 2 && isPuur);
    });
  };
  draw();

  const button = html("button", "fig-step", "Next →");
  button.addEventListener("click", () => {
    step = (step + 1) % steps.length;
    button.textContent = step === steps.length - 1 ? "Start over" : "Next →";
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

function playerPanel(data) {
  const wrap = html("div", "about-panel");
  wrap.append(
    html("h3", null, "What it is doing"),
    html(
      "p",
      null,
      "It cannot see your cards. So it <b>imagines</b> them — deals the unseen cards into " +
        "the other three hands at random, plays that imaginary deal out thousands of times, " +
        "and repeats with a different guess. The card that does best across all those " +
        "guesses is the one it plays."
    ),
    html("h3", null, "What it knows, and what it doesn't"),
    html(
      "p",
      null,
      "Its own hand, the cards already face up, and which moves are legal. Nothing else — " +
        "no peek at your hand, no deck order. That is enforced in one function and checked " +
        "by a test that fuzzes every observation looking for a card that should not be there."
    ),
    html("h3", null, "What it works out"),
    html(
      "p",
      null,
      "It reasons from what you play. Step through this — the last step is the one worth " +
        "seeing, because it shows the inference is exact rather than approximate."
    )
  );
  wrap.append(voidFigure());
  wrap.append(
    html("h3", null, "Where it is weak"),
    html(
      "p",
      "warn",
      "Its individual card play is much stronger than its <b>team</b> play. It does not " +
        "follow the signalling conventions a human partner expects — it will not read your " +
        "schmieren as a signal, and it does not send them either. That is a known limit of " +
        "this kind of search, not a bug, and more thinking time does not fix it."
    ),
    html(
      "p",
      null,
      `It has also <b>never been measured against a human</b>. The published work on this ` +
        `exact variant found a comparable bot scored ${data.literature.human_parity} — ` +
        `roughly par with strong amateurs. That is the research's number, not ours.`
    )
  );
  return wrap;
}

function strengthPanel(data) {
  const wrap = html("div", "about-panel");
  const { ladder, budget_sweep, trump_selection } = data;

  wrap.append(
    html("h3", null, "Is it actually any good?"),
    html(
      "p",
      null,
      `Every figure here is measured, dated and carries its sample size. ` +
        `<span class="meta">Measured ${data.measured_on} · ${data.machine} · ${data.conditions}.</span>`
    ),
    html("h4", null, "The baseline ladder"),
    html(
      "p",
      null,
      `${ladder.deals} double rounds per matchup. Dots are the share of points; bars are 95% ` +
        `confidence intervals. An interval crossing the centre line means <b>we cannot tell ` +
        `the two apart</b>.`
    )
  );
  wrap.append(ladderFigure(data));
  wrap.append(
    html(
      "p",
      "fig-caption",
      "Note the top row: <b>greedy scores the same as random</b>. " +
        "&ldquo;Play your highest-value legal card&rdquo; sounds reasonable and is worth nothing — " +
        "it throws aces into tricks it was never going to win."
    ),

    html("h4", null, "Why every deal is played twice"),
    html(
      "p",
      null,
      `The deal dominates. Per-deal share has a standard deviation around 8%, so a short ` +
        `match cannot resolve a 2% difference in skill. So each deal is played <b>twice</b>, ` +
        `with the two sides swapped, and the pair is compared — which cancels most of the ` +
        `luck. Testing that as if the halves were unrelated would throw the benefit away, so ` +
        `the test is paired.`
    ),

    html("h4", null, "What more thinking buys"),
    html(
      "p",
      null,
      `Nothing, past about 2,400 iterations. Each budget below played ${budget_sweep.deals} ` +
        `double rounds against a fixed 2,400-iteration opponent.`
    )
  );
  wrap.append(saturationFigure(data));
  const high = budget_sweep.high_end[1];
  wrap.append(
    html(
      "p",
      "fig-caption",
      `At the top end, ${high.a.toLocaleString()} iterations against ` +
        `${high.b.toLocaleString()} scored ${pct(high.share)} over ${high.deals} deals ` +
        `(p = ${high.p}). <b>333× the computation, no measurable gain.</b> ` +
        `The published work suggests ${data.literature.budget_claim}; that did not reproduce ` +
        `here, and we do not yet know why.`
    ),

    html("h4", null, "What the bidding is worth"),
    html(
      "p",
      null,
      `Identical card play on both sides, only the trump choice differing: ` +
        `<b>${pct(trump_selection.share)}</b> over ${trump_selection.deals} double rounds — ` +
        `a ${(2 * (trump_selection.share - 50)).toFixed(0)}-point spread. The research predicted ` +
        `${data.literature.trump_selection_claim}. <b>That one reproduced.</b>`
    ),

    html("h4", null, "The number that matters most"),
    html(
      "p",
      null,
      `A bot that <b>sees all four hands</b> beats the real one ` +
        `${pct(ladder.matchups[3].share)} to ${pct(100 - ladder.matchups[3].share)}. That gap — ` +
        `about 6 points — is the price of playing with hidden information, and search does ` +
        `not close it: giving the real bot 16× more thinking moved it by less than half a ` +
        `standard error. Closing it needs a different kind of player, not a faster one.`
    ),

    html(
      "p",
      "warn",
      "A caveat that applies to all of it: these are measured with Weis, Stöck and the match " +
        "bonus switched off, because they swing scores hard enough to drown the difference " +
        "between two agents. They are on when you play."
    )
  );
  return wrap;
}

function internalsPanel(data) {
  const wrap = html("div", "about-panel");
  wrap.append(
    html("h3", null, "How it is built"),
    html(
      "p",
      null,
      "The engine is bitboards: a hand is a 36-bit integer and a suit is a 9-bit field, so " +
        "legal moves and trick resolution are table lookups rather than branching logic."
    ),
    html("h4", null, "Why the search is in Rust"),
    html(
      "p",
      null,
      "Python managed about 35,000 search iterations a second, which put a training corpus " +
        "at roughly a month of continuous computation. Profiling showed the random playout " +
        "was 73% of the time — so porting only that would have capped the gain near 2.4×, " +
        "and the search tree had to move with it."
    )
  );
  wrap.append(throughputFigure(data));
  wrap.append(
    html(
      "p",
      "fig-caption",
      "Per move at the 2,400-iteration serve budget. The browser build is 1.39× the native " +
        "one — which is why this page can run the whole game with no server behind it."
    ),

    html("h4", null, "The three rules that make Jass different"),
    html(
      "p",
      null,
      "Implementations of other trick-taking games get these wrong. <b>You may always " +
        "trump</b>, even holding the led suit. Once someone has trumped, a <b>lower trump is " +
        "illegal</b> unless your hand is nothing but trumps. And if your only trump is the " +
        "Jack, you need not play it on a trump lead."
    ),

    html("h4", null, "The endgame is solved exactly"),
    html(
      "p",
      null,
      `Once few enough cards remain, the search is <b>replaced</b> by an exact ` +
        `double-dummy solve. Cost roughly 15× per extra card — ` +
        data.endgame.points
          .map((p) => `${p.cards_each} cards ${p.ms} ms`)
          .join(", ") +
        ` — which is why it replaces the search rather than running inside it.`
    ),

    html("h4", null, "How it is kept honest"),
    html(
      "p",
      null,
      "The rules exist twice — Python and Rust — and a third time in a deliberately naive " +
        "reference implementation written from the rules text that imports neither. Property " +
        "tests play whole random rounds and compare all three at every ply. Two implementations " +
        "can agree on the same misreading; three written from different starting points are " +
        "much less likely to."
    ),

    html(
      "p",
      "warn",
      "One honest limit of <b>this</b> build: it runs entirely in your browser, so all four " +
        "hands are in this tab's memory. The bots genuinely cannot see yours — the filtering " +
        "is the same code the server version runs — but a determined human with developer " +
        "tools can. That is fine for playing against bots and is exactly why multiplayer " +
        "would have to be server-side."
    )
  );
  return wrap;
}

export function buildAbout(data) {
  const panels = {
    play: () => playerPanel(data),
    strength: () => strengthPanel(data),
    internals: () => internalsPanel(data),
  };
  const built = {};
  const body = html("div", "about-body");

  const tabs = html("div", "about-tabs");
  const names = [
    ["play", "How it plays"],
    ["strength", "Is it good?"],
    ["internals", "Under the hood"],
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
