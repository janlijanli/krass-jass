/* The Jasstafel — chalk on slate.
 *
 * Two things make a board read as a Jass board: the vertical line down the middle, and
 * chalk. Both are done properly here rather than approximated with borders and a sans-serif
 * font — a tidy table is legible but it is not a Jasstafel.
 *
 * Chalk is an SVG filter: turbulence displaces the stroke edges so they wobble, and a second
 * turbulence layer knocks holes in the fill so it looks dusty rather than painted. Every
 * stroke is drawn with a per-mark random seed derived from its position, so the board is
 * stable across re-renders instead of shimmering.
 *
 * NOTATION: regional conventions differ and I could not confirm the Bernese one, so the
 * marks are a data table (`NOTATION`) rather than logic. Correcting it is editing six lines.
 */

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};

/** Units a score is broken into, largest first. Each is drawn as one chalk mark. */
export const NOTATION = [
  { value: 100, mark: "hundred" },
  { value: 50, mark: "fifty" },
  { value: 20, mark: "twenty" },
];

/* Deterministic jitter: the same mark wobbles the same way every time it is drawn, so the
   board does not shimmer when the score changes. */
function wobble(seed, amount = 1) {
  const x = Math.sin(seed * 127.1) * 43758.5453;
  return ((x - Math.floor(x)) - 0.5) * 2 * amount;
}

function chalkDefs() {
  const defs = svg("defs");
  defs.innerHTML = `
    <filter id="chalk" x="-30%" y="-30%" width="160%" height="160%">
      <!-- rough the edges -->
      <feTurbulence type="fractalNoise" baseFrequency="0.055" numOctaves="3" seed="7" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.4" xChannelSelector="R" yChannelSelector="G" result="rough"/>
      <!-- knock dust holes through it so it reads as chalk rather than paint -->
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3" result="grain"/>
      <feColorMatrix in="grain" type="matrix"
        values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.1 1.05" result="mask"/>
      <feComposite in="rough" in2="mask" operator="in"/>
    </filter>`;
  return defs;
}

/** One chalk stroke, hand-drawn: slightly off-straight, slightly uneven. */
function stroke(x1, y1, x2, y2, seed, width = 3) {
  const mx = (x1 + x2) / 2 + wobble(seed, 1.6);
  const my = (y1 + y2) / 2 + wobble(seed + 1, 1.6);
  const p = svg("path", {
    d: `M${x1 + wobble(seed + 2)},${y1 + wobble(seed + 3)} Q${mx},${my} ${
      x2 + wobble(seed + 4)
    },${y2 + wobble(seed + 5)}`,
    class: "chalk-stroke",
  });
  p.setAttribute("stroke-width", (width + wobble(seed + 6, 0.4)).toFixed(2));
  return p;
}

/* The marks. Kept deliberately simple and separable so a different regional notation is a
   change of shapes, not a change of structure. */
const MARKS = {
  // 100 — a full-height stroke.
  hundred: (g, x, top, bottom, seed) => g.append(stroke(x, top, x, bottom, seed, 3.4)),
  // 50 — half height, hanging from the top.
  fifty: (g, x, top, bottom, seed) =>
    g.append(stroke(x, top, x, (top + bottom) / 2, seed, 3.2)),
  // 20 — a short tick on the baseline.
  twenty: (g, x, top, bottom, seed) =>
    g.append(stroke(x, bottom - (bottom - top) * 0.3, x, bottom, seed, 3)),
};

/** Break a score into marks, largest unit first, and return the remainder. */
export function toMarks(score) {
  const marks = [];
  let left = score;
  for (const { value, mark } of NOTATION) {
    while (left >= value) {
      marks.push(mark);
      left -= value;
    }
  }
  return { marks, remainder: left };
}

/**
 * Draw one team's column.
 *
 * Marks wrap into rows. The remainder — whatever is left under the smallest unit — is
 * written as a chalk numeral, because real scores are not multiples of twenty and pretending
 * otherwise would show the wrong total.
 */
function column(root, x0, width, score, seedBase) {
  const { marks, remainder } = toMarks(score);
  const perRow = Math.max(4, Math.floor((width - 16) / 13));
  const rowH = 30;
  const g = svg("g");

  marks.forEach((mark, i) => {
    const row = Math.floor(i / perRow);
    const col = i % perRow;
    const x = x0 + 12 + col * 13;
    const top = 16 + row * rowH;
    MARKS[mark](g, x, top, top + 22, seedBase + i * 17);
  });

  const rows = Math.ceil(marks.length / perRow);
  if (remainder > 0 || marks.length === 0) {
    const t = svg("text", {
      x: x0 + width / 2,
      y: 16 + rows * rowH + 18,
      class: "chalk-number",
      "text-anchor": "middle",
      transform: `rotate(${wobble(seedBase, 1.4).toFixed(2)} ${x0 + width / 2} ${
        16 + rows * rowH + 18
      })`,
    });
    t.textContent = marks.length ? `+ ${remainder}` : String(remainder);
    g.append(t);
  }
  root.append(g);
  return 16 + rows * rowH + (remainder > 0 || !marks.length ? 26 : 8);
}

/** Render the whole board. `scores` is [us, them]. */
export function drawTafel(container, scores, { target = null, rounds = [] } = {}) {
  const W = 300;
  const half = W / 2;
  const root = svg("svg", { viewBox: `0 0 ${W} 10`, class: "slate-svg" });
  root.append(chalkDefs());

  const body = svg("g", { filter: "url(#chalk)" });
  root.append(body);

  // Headings, hand-written.
  for (const [label, cx] of [["Wir", half / 2], ["Sie", half + half / 2]]) {
    const t = svg("text", { x: cx, y: 0, class: "chalk-head", "text-anchor": "middle" });
    t.textContent = label;
    body.append(t);
  }

  const marksTop = 12;
  const gUs = svg("g", { transform: `translate(0 ${marksTop})` });
  const gThem = svg("g", { transform: `translate(0 ${marksTop})` });
  body.append(gUs, gThem);
  const hUs = column(gUs, 6, half - 14, scores[0], 11);
  const hThem = column(gThem, half + 8, half - 14, scores[1], 91);

  const height = Math.max(hUs, hThem) + marksTop + 12;
  // The divider, last, so it spans whatever height the marks needed.
  body.append(stroke(half, 2, half, height - 4, 3, 2.6));
  root.setAttribute("viewBox", `0 0 ${W} ${height}`);

  container.replaceChildren(root);
  // Always written: the running total is the thing a player actually wants off a board, and
  // making it conditional on knowing the target meant it silently vanished when the target
  // did not arrive.
  const note = document.createElement("p");
  note.className = "slate-note";
  note.textContent =
    `${scores[0]} – ${scores[1]}` + (target ? `  ·  playing to ${target}` : "");
  container.append(note);
  return { height };
}
