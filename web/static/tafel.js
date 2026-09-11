/* The Jasstafel.
 *
 * Layout follows the board a Jass app actually draws: the two teams face each other across a
 * horizontal centre strip rather than sitting side by side, and the far team's half is turned
 * upside down so each player reads their own marks the right way up from their seat. The
 * strip carries both totals and the target.
 *
 *   ┌───────────────────────────┐
 *   │  ‖   X   ‖‖‖              │   ← their half, rotated 180°
 *   │  ────────────╱────────    │      (a full row is struck through)
 *   │                        0  │   ← the remainder, written out
 *   ├─── 790 ──── 2500 ─── 1119 ┤   ← totals either side, target in the middle
 *   │  9                        │
 *   │  ────╱───────────────     │
 *   │  ‖‖‖   XXX                │   ← your half
 *   └───────────────────────────┘
 *
 * Marks accumulate round by round and are never redrawn — see `accumulate`. A row holds five
 * marks; completing one strikes it through, which is the bundling rule the notation calls for
 * (jassverzeichnis.ch/schreiben-jassen-uebersicht) drawn at row scale rather than per group.
 *
 * Strokes are roughed with an SVG filter — turbulence displaces the edges so they wobble, and
 * a second turbulence layer knocks holes through the fill so they read as drawn rather than
 * printed. Every mark takes a seed from its own position, so the board is stable across
 * re-renders instead of shimmering whenever something else on it changes.
 */

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};

/**
 * The marks, largest first.
 *
 * The glyphs have to be unmistakable at a glance, which is the whole job: a first attempt
 * used a double upright for 100 and a single for 20, and on a real board they read as four
 * identical vertical lines with no way to tell 140 from 400. Height and shape now carry the
 * value, not stroke count:
 *
 *   100  a full-height upright
 *    50  a cross
 *    20  a short tick on the baseline
 *
 * Changing the notation is changing this table, not the drawing code.
 */
export const MARKS = [
  { value: 100, glyph: "tall" },
  { value: 50, glyph: "cross" },
  { value: 20, glyph: "tick" },
];

/** Marks per row before it is struck through. */
export const PER_ROW = 5;

/** Break one amount into marks, largest first. The leftover under 20 is written as a number. */
export function decompose(score) {
  let left = Math.max(0, Math.round(score));
  const counts = MARKS.map(({ value }) => {
    const n = Math.floor(left / value);
    left -= n * value;
    return n;
  });
  return { counts, remainder: left };
}

/**
 * The board as it actually gets written: round by round, marks accumulating.
 *
 * Chalk is not rubbed out and rewritten each round — marks stay where they were put. Only the
 * remainder is a number in the corner, and that is the one thing that does get wiped and
 * written again, because each round's leftover joins it and may become a new mark.
 *
 * So a team can end with three 50-marks where a redrawn total would show a hundred and a
 * fifty. That is not an error, it is what a board that has been written on looks like.
 *
 * The invariant: marks plus remainder always equal the cumulative score.
 */
export function accumulate(roundPoints) {
  const counts = MARKS.map(() => 0);
  let remainder = 0;
  for (const points of roundPoints) {
    let pending = remainder + Math.max(0, Math.round(points));
    MARKS.forEach(({ value }, i) => {
      const n = Math.floor(pending / value);
      counts[i] += n;
      pending -= n * value;
    });
    remainder = pending;
  }
  return { counts, remainder };
}

/** What the marks add up to — used to check the board against the real score. */
export function markedTotal({ counts, remainder }) {
  return counts.reduce((sum, n, i) => sum + n * MARKS[i].value, 0) + remainder;
}

/** The marks in the order they are written: hundreds, then fifties, then twenties. */
function sequence({ counts }) {
  const out = [];
  MARKS.forEach((m, i) => {
    for (let n = 0; n < counts[i]; n++) out.push(m.glyph);
  });
  return out;
}

/* Deterministic jitter, so a mark wobbles the same way every time it is drawn. */
function wobble(seed, amount = 1) {
  const x = Math.sin(seed * 127.1) * 43758.5453;
  return (x - Math.floor(x) - 0.5) * 2 * amount;
}

function defs() {
  const d = svg("defs");
  d.innerHTML = `
    <filter id="chalk" x="-25%" y="-25%" width="150%" height="150%">
      <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="3" seed="7" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="1.8"
        xChannelSelector="R" yChannelSelector="G" result="rough"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="3" result="grain"/>
      <feColorMatrix in="grain" type="matrix"
        values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.15 1.08" result="mask"/>
      <feComposite in="rough" in2="mask" operator="in"/>
    </filter>`;
  return d;
}

function line(x1, y1, x2, y2, seed, width = 2.6, cls = "chalk-stroke") {
  const p = svg("path", {
    d:
      `M${(x1 + wobble(seed, 0.8)).toFixed(2)},${(y1 + wobble(seed + 1, 0.8)).toFixed(2)} ` +
      `Q${((x1 + x2) / 2 + wobble(seed + 2, 1.3)).toFixed(2)},` +
      `${((y1 + y2) / 2 + wobble(seed + 3, 1.3)).toFixed(2)} ` +
      `${(x2 + wobble(seed + 4, 0.8)).toFixed(2)},${(y2 + wobble(seed + 5, 0.8)).toFixed(2)}`,
    class: cls,
  });
  p.setAttribute("stroke-width", (width + wobble(seed + 6, 0.25)).toFixed(2));
  return p;
}

function text(x, y, content, cls, seed = 0) {
  const t = svg("text", {
    x, y, class: cls, "text-anchor": "middle",
    transform: `rotate(${wobble(seed, 1.6).toFixed(2)} ${x} ${y})`,
  });
  t.textContent = content;
  return t;
}

const MARK_W = 16;
const MARK_H = 24;
const ROW_H = 36;
/** Space left between runs of different marks, so the groups read apart. */
const GROUP_GAP = 10;

/** One mark: full-height upright for 100, a cross for 50, a short tick for 20. */
function drawMark(g, glyph, x, y, seed) {
  const top = y;
  const bottom = y + MARK_H;
  if (glyph === "cross") {
    g.append(line(x - 6, top, x + 6, bottom, seed));
    g.append(line(x + 6, top, x - 6, bottom, seed + 40));
  } else if (glyph === "tick") {
    g.append(line(x, bottom - MARK_H * 0.45, x, bottom, seed));
  } else {
    g.append(line(x, top, x, bottom, seed));
  }
}

/**
 * One team's half: rows of marks, each completed row struck through.
 *
 * `flip` turns the half upside down for the team sitting opposite, so both read their own
 * side the right way up.
 */
function drawHalf(root, x0, y0, width, marks, rows, flip, seedBase) {
  const g = svg("g");
  if (flip) g.setAttribute("transform", `rotate(180 ${x0 + width / 2} ${y0 + rows * ROW_H / 2})`);

  const glyphs = sequence(marks);
  const left = x0 + 16;

  // A run of one kind of mark is followed by a gap, so 100s, 50s and 20s read as groups
  // rather than as one undifferentiated line of strokes.
  let offset = 0;
  for (let i = 0; i < glyphs.length; i++) {
    const row = Math.floor(i / PER_ROW);
    const col = i % PER_ROW;
    if (col === 0) offset = 0;
    else if (glyphs[i] !== glyphs[i - 1]) offset += GROUP_GAP;
    drawMark(g, glyphs[i], left + col * MARK_W + offset + 8, y0 + 6 + row * ROW_H, seedBase + i * 17);
  }

  // A full row is struck through — the bundling rule, at row scale.
  const fullRows = Math.floor(glyphs.length / PER_ROW);
  for (let r = 0; r < fullRows; r++) {
    const y = y0 + 6 + r * ROW_H;
    g.append(
      line(left - 4, y + MARK_H + 3, left + PER_ROW * MARK_W + 6, y - 3, seedBase + 900 + r, 2.2)
    );
  }

  // The remainder, written where the marks are not.
  g.append(
    text(x0 + width - 20, y0 + 6 + Math.max(1, fullRows) * ROW_H - 6,
      String(marks.remainder), "chalk-number", seedBase + 500)
  );
  root.append(g);
}

/** Rows a half needs, at least `min` so the board keeps a stable shape. */
function rowsFor(marks, min) {
  return Math.max(min, Math.ceil(sequence(marks).length / PER_ROW) + 1);
}

/**
 * Render the board.
 *
 * `history` is `[[us per round], [them per round]]` — the rounds as they were scored, not the
 * totals, because the board is written up one round at a time.
 */
export function drawTafel(container, history, { target = null, t = null } = {}) {
  const say = t || ((k, p) => (p ? `playing to ${p.n}` : ""));
  const W = 264;
  const PAD = 8;
  const marks = history.map(accumulate);
  const scores = marks.map(markedTotal);

  const rowsThem = rowsFor(marks[1], 3);
  const rowsUs = rowsFor(marks[0], 3);
  const topH = rowsThem * ROW_H;
  const bottomH = rowsUs * ROW_H;
  const stripY = PAD + topH + 14;
  const H = stripY + 14 + bottomH + PAD;

  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "slate-svg" });
  root.append(defs());
  const body = svg("g", { filter: "url(#chalk)" });
  root.append(body);

  // Their half on top, turned round; yours below, the right way up.
  drawHalf(body, PAD, PAD, W - PAD * 2, marks[1], rowsThem, true, 91);
  drawHalf(body, PAD, stripY + 14, W - PAD * 2, marks[0], rowsUs, false, 11);

  // The centre strip: the rule runs across with gaps left for the numbers, so nothing is
  // written over a line.
  //
  // Each total sits on the side its own marks are on. Rotating the top half flips its marks
  // to the right, so the top team's total belongs on the right — putting it on the left, as
  // a "them on the left, us on the right" reading suggests, sets every total beside the
  // *other* team's marks and makes the board unreadable.
  const themX = W - PAD - 24;
  const usX = PAD + 24;
  const gap = (x, w) => [x - w, x + w];
  const cuts = [gap(usX, 22), gap(W / 2, 22), gap(themX, 22)];
  // Segments shorter than this are stubs left either side of a number — not worth drawing.
  const MIN_SEGMENT = 8;
  let from = PAD;
  for (const [a, b] of cuts) {
    if (a - from >= MIN_SEGMENT) body.append(line(from, stripY, a, stripY, 3 + from, 2.4));
    from = b;
  }
  if (W - PAD - from >= MIN_SEGMENT) {
    body.append(line(from, stripY, W - PAD, stripY, 3 + from, 2.4));
  }

  const onLine = stripY + 5;
  body.append(text(themX, onLine, String(scores[1]), "chalk-total", 7));
  body.append(text(usX, onLine, String(scores[0]), "chalk-total", 8));
  if (target) body.append(text(W / 2, onLine, String(target), "chalk-target", 9));

  container.replaceChildren(root);
}
