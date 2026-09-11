/* The Jasstafel — chalk on stone, written the way a Swiss board is written.
 *
 * Layout, per team (jassverzeichnis.ch/schreiben-jassen-uebersicht):
 *
 *   ┌──────────────────┬──────┐
 *   │ 100s  | | | |    │  X V │   ← upper right: X = 1000, V = 500
 *   ├──────────────────┤      │
 *   │  50s  |          │      │
 *   ├──────────────────┼──────┤
 *   │  20s  | |        │   13 │   ← lower right: the remainder, as a number
 *   └──────────────────┴──────┘
 *
 * Portrait, the two teams either side of a line down the middle, strokes running left to
 * right within their band.
 *
 * The source's own rule is to pick the notation needing the fewest strokes, so the running
 * total is decomposed greedily — thousands and five-hundreds become X and V rather than ten
 * or five hundred-strokes. Under that decomposition a band rarely fills, but the bundling
 * rule is implemented anyway: the fifth stroke of a 100 or 20 band is drawn crosswise over
 * the four before it, and in the 50 band two strokes are crossed, two fifties being a
 * hundred.
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
/** The right-hand column, largest first. */
export const SYMBOLS = [
  { value: 1000, glyph: "X" },
  { value: 500, glyph: "V" },
];

/**
 * Break a score into what actually goes on the board.
 *
 * Greedy, largest first, because the board's own guidance is fewest strokes. The remainder
 * is whatever is left under 20 and is written out as a number — real scores are not
 * multiples of twenty, and rounding them would put the wrong total on the board.
 */
export function decompose(score) {
  let left = Math.max(0, Math.round(score));
  const symbols = [];
  for (const { value, glyph } of SYMBOLS) {
    while (left >= value) {
      symbols.push(glyph);
      left -= value;
    }
  }
  const bands = BANDS.map(({ value }) => {
    const n = Math.floor(left / value);
    left -= n * value;
    return n;
  });
  return { symbols, bands, remainder: left };
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

/** One band of strokes, bundling every `crossAt` with a crossing stroke. */
function drawBand(g, x0, y, count, crossAt, seedBase) {
  const gap = 10;
  const groupWidth = (crossAt - 1) * gap + 9;
  const top = y;
  const bottom = y + 19;
  for (let i = 0; i < count; i++) {
    const place = i % crossAt;
    const gx = x0 + Math.floor(i / crossAt) * groupWidth;
    if (place === crossAt - 1) {
      g.append(stroke(gx - 3, bottom, gx + (crossAt - 2) * gap + 3, top, seedBase + i * 13));
    } else {
      g.append(stroke(gx + place * gap, top, gx + place * gap, bottom, seedBase + i * 13));
    }
  }
}

/** One team's half. Returns the height used. */
function half(root, x0, width, score, seedBase) {
  const { symbols, bands, remainder } = decompose(score);
  const g = svg("g");
  const columnX = x0 + width - 36;
  const rightX = x0 + width - 17;

  BANDS.forEach((b, i) => {
    const y = 22 + i * 29;
    g.append(chalkText(x0 + 12, y + 15, b.label, "chalk-band", seedBase + i));
    drawBand(g, x0 + 28, y, bands[i], b.crossAt, seedBase + i * 200 + 5);
    if (i < BANDS.length - 1) {
      g.append(stroke(x0 + 5, y + 24, columnX - 4, y + 24, seedBase + 900 + i, 1));
    }
  });

  symbols.slice(0, 4).forEach((glyph, i) => {
    g.append(chalkText(rightX, 36 + i * 20, glyph, "chalk-symbol", seedBase + 300 + i));
  });
  g.append(chalkText(rightX, 103, String(remainder), "chalk-number", seedBase + 400));

  // The rule separating the right-hand column from the bands.
  g.append(stroke(columnX, 8, columnX, 110, seedBase + 500, 1.3));
  root.append(g);
  return 114;
}

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

  const h = Math.max(
    half(body, 4, mid - 8, scores[0], 11),
    half(body, mid + 4, mid - 8, scores[1], 91)
  );

  // The line down the middle, drawn last so it spans whatever the halves needed.
  body.append(stroke(mid, 4, mid, h + 2, 3, 2.6));
  root.setAttribute("viewBox", `0 0 ${W} ${h + 8}`);

  container.replaceChildren(root);

  // Always written: the running total is what a player actually wants off a board, and
  // making it conditional on knowing the target meant it vanished when that did not arrive.
  const note = document.createElement("p");
  note.className = "slate-note";
  note.textContent =
    `${scores[0]} – ${scores[1]}` + (target ? `  ·  playing to ${target}` : "");
  container.append(note);
}
