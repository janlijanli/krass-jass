/* The Jasstafel — chalk on stone, written the way a Swiss board is written.
 *
 * Layout, per team (jassverzeichnis.ch/schreiben-jassen-uebersicht):
 *
 *   ┌──────────────────┬──────┐
 *   │ 100s  ||||/ ||    │      │
 *   ├──────────────────┤      │
 *   │  50s  |          │      │
 *   ├──────────────────┼──────┤
 *   │  20s  | |        │   13 │   ← the remainder, as a number
 *   └──────────────────┴──────┘
 *
 * Portrait, the two teams either side of a line down the middle, strokes running left to
 * right within their band.
 *
 * Everything above 20 is strokes — no X or V shorthand — so a large score is a lot of marks,
 * which is what makes the bundling rule matter rather than being decoration: the fifth
 * stroke of a 100 or 20 band is drawn crosswise over the four before it, and in the 50 band
 * two strokes are crossed, two fifties being a hundred. Bands wrap when they run out of
 * width and the board grows downward, the way a real one fills up over an evening.
 *
 * Chalk is an SVG filter — turbulence displaces the stroke edges so they wobble, and a
 * second turbulence layer knocks dust holes through the fill so it reads as chalk rather
 * than paint. Every mark takes a seed from its own position, so the board is stable across
 * re-renders instead of shimmering whenever something else on it changes.
 */

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};

/** The bands, top to bottom. */
export const BANDS = [
  { value: 100, label: "100", crossAt: 5 },
  { value: 50, label: "50", crossAt: 2 },
  { value: 20, label: "20", crossAt: 5 },
];
/**
 * Break a score into what goes on the board.
 *
 * Largest band first. The remainder is whatever is left under 20 and is written out as a
 * number — real scores are not multiples of twenty, and rounding them would put the wrong
 * total on the board.
 */
export function decompose(score) {
  let left = Math.max(0, Math.round(score));
  const bands = BANDS.map(({ value }) => {
    const n = Math.floor(left / value);
    left -= n * value;
    return n;
  });
  return { bands, remainder: left };
}

/* Deterministic jitter, so a mark wobbles the same way every time it is drawn. */
function wobble(seed, amount = 1) {
  const x = Math.sin(seed * 127.1) * 43758.5453;
  return (x - Math.floor(x) - 0.5) * 2 * amount;
}

function chalkDefs() {
  const defs = svg("defs");
  defs.innerHTML = `
    <filter id="chalk" x="-25%" y="-25%" width="150%" height="150%">
      <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="3" seed="7" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.2"
        xChannelSelector="R" yChannelSelector="G" result="rough"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3" result="grain"/>
      <feColorMatrix in="grain" type="matrix"
        values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.1 1.05" result="mask"/>
      <feComposite in="rough" in2="mask" operator="in"/>
    </filter>`;
  return defs;
}

/** One chalk stroke: slightly off-straight, slightly uneven, like a hand drew it. */
function stroke(x1, y1, x2, y2, seed, width = 3) {
  const p = svg("path", {
    d:
      `M${(x1 + wobble(seed, 0.9)).toFixed(2)},${(y1 + wobble(seed + 1, 0.9)).toFixed(2)} ` +
      `Q${((x1 + x2) / 2 + wobble(seed + 2, 1.4)).toFixed(2)},` +
      `${((y1 + y2) / 2 + wobble(seed + 3, 1.4)).toFixed(2)} ` +
      `${(x2 + wobble(seed + 4, 0.9)).toFixed(2)},${(y2 + wobble(seed + 5, 0.9)).toFixed(2)}`,
    class: "chalk-stroke",
  });
  p.setAttribute("stroke-width", (width + wobble(seed + 6, 0.3)).toFixed(2));
  return p;
}

function chalkText(x, y, text, cls, seed) {
  const t = svg("text", {
    x, y, class: cls, "text-anchor": "middle",
    transform: `rotate(${wobble(seed, 2).toFixed(2)} ${x} ${y})`,
  });
  t.textContent = text;
  return t;
}

const GAP = 9;
const ROW_H = 22;

/** How many stroke-groups fit across one band. */
function groupsPerRow(width, crossAt) {
  return Math.max(1, Math.floor(width / ((crossAt - 1) * GAP + 10)));
}

/**
 * One band of strokes, bundling every `crossAt` with a crossing stroke and wrapping when it
 * runs out of width. Returns the height it used.
 */
function drawBand(g, x0, y, width, count, crossAt, seedBase) {
  const groupWidth = (crossAt - 1) * GAP + 10;
  const perRow = groupsPerRow(width, crossAt);
  const groups = Math.ceil(count / crossAt);

  for (let i = 0; i < count; i++) {
    const group = Math.floor(i / crossAt);
    const place = i % crossAt;
    const gx = x0 + (group % perRow) * groupWidth;
    const top = y + Math.floor(group / perRow) * ROW_H;
    const bottom = top + 17;
    if (place === crossAt - 1) {
      g.append(stroke(gx - 3, bottom, gx + (crossAt - 2) * GAP + 3, top, seedBase + i * 13));
    } else {
      g.append(stroke(gx + place * GAP, top, gx + place * GAP, bottom, seedBase + i * 13));
    }
  }
  return Math.max(1, Math.ceil(groups / perRow)) * ROW_H;
}

/**
 * Draw one team's strokes into bands whose positions are fixed for the whole board.
 *
 * The bands are ruled across the slate, so both teams' 50s sit on the same line. Sizing each
 * half independently let them drift apart, which no real board does.
 */
function halfStrokes(root, x0, width, score, rows, seedBase) {
  const { bands, remainder } = decompose(score);
  const g = svg("g");
  const columnX = x0 + width - 34;
  const strokeX = x0 + 26;
  const strokeWidth = columnX - strokeX - 6;

  let y = BAND_TOP;
  BANDS.forEach((b, i) => {
    drawBand(g, strokeX, y, strokeWidth, bands[i], b.crossAt, seedBase + i * 200 + 5);
    y += rows[i] * ROW_H + 6;
  });

  g.append(chalkText(x0 + width - 16, y - 14, String(remainder), "chalk-number", seedBase + 400));
  g.append(stroke(columnX, 8, columnX, y - 6, seedBase + 500, 1.3));
  root.append(g);
}

/** Rows each band needs for a score, so both halves can be laid out to the same grid. */
function rowsFor(score, width) {
  const { bands } = decompose(score);
  return BANDS.map((b, i) => {
    const groups = Math.ceil(bands[i] / b.crossAt);
    return Math.max(1, Math.ceil(groups / groupsPerRow(width, b.crossAt)));
  });
}

const BAND_TOP = 22;

/** Render the board. `scores` is `[us, them]`. */
export function drawTafel(container, scores, { target = null } = {}) {
  const W = 320;
  const mid = W / 2;
  const root = svg("svg", { class: "slate-svg" });
  root.append(chalkDefs());
  const body = svg("g", { filter: "url(#chalk)" });
  root.append(body);

  body.append(chalkText(mid / 2, 13, "Wir", "chalk-head", 1));
  body.append(chalkText(mid + mid / 2, 13, "Sie", "chalk-head", 2));

  // Bands are ruled across the whole slate, so each one is as tall as the fuller side needs.
  const halfWidth = mid - 8;
  const strokeWidth = halfWidth - 66;
  const rowsA = rowsFor(scores[0], strokeWidth);
  const rowsB = rowsFor(scores[1], strokeWidth);
  const rows = BANDS.map((_, i) => Math.max(rowsA[i], rowsB[i]));

  // Band labels and the rules between them, drawn once across the board.
  let y = BAND_TOP;
  BANDS.forEach((b, i) => {
    body.append(chalkText(15, y + 13, b.label, "chalk-band", 700 + i));
    body.append(chalkText(mid + 15, y + 13, b.label, "chalk-band", 750 + i));
    y += rows[i] * ROW_H + 6;
    if (i < BANDS.length - 1) {
      body.append(stroke(5, y - 3, W - 5, y - 3, 900 + i, 1));
    }
  });
  const h = y;

  halfStrokes(body, 4, halfWidth, scores[0], rows, 11);
  halfStrokes(body, mid + 4, halfWidth, scores[1], rows, 91);

  // The line down the middle, drawn last so it spans whatever the bands needed.
  body.append(stroke(mid, 4, mid, h - 4, 3, 2.6));
  root.setAttribute("viewBox", `0 0 ${W} ${h + 4}`);

  container.replaceChildren(root);

  // Always written: the running total is what a player actually wants off a board, and
  // making it conditional on knowing the target meant it vanished when that did not arrive.
  const note = document.createElement("p");
  note.className = "slate-note";
  note.textContent =
    `${scores[0]} – ${scores[1]}` + (target ? `  ·  playing to ${target}` : "");
  container.append(note);
}
