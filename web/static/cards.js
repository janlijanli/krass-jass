/* Card faces, drawn as SVG.
 *
 * Generated rather than shipped as images: no assets to license, no sprite sheet to keep in
 * sync with 36 card codes, and they stay crisp at any size. Cards remain real DOM nodes, so
 * the fan, hit targets and accessibility are unaffected.
 *
 * Layout follows a real French deck: corner indices top-left and bottom-right (the second
 * rotated, so the card reads either way up), standard pip arrangements for 6–10, and pips
 * below the midline inverted. Court cards get a framed monogram rather than fake portrait
 * art — being able to pick the Puur out of a fanned hand at a glance matters more here than
 * decoration, since the trump Jack is the strongest card in the game.
 */

const SUIT_GLYPH = { D: "♦", H: "♥", S: "♠", C: "♣" };

/* The suits, drawn rather than typed.
 *
 * They used to be the font's ♠ ♣ ♥ ♦, and at the size of a corner index the two black suits
 * came out as much the same dark blob — how a spade or a club looked was up to whatever font
 * the phone had. These follow the Swiss French-suited Jass cards instead (AGMüller, as shown
 * on jassverzeichnis.ch): the spade one solid pointed blade on a short flared foot, the club
 * three clearly separate round lobes on a thin stem. Told apart by silhouette, not by colour.
 *
 * Drawn in a box from -1 to 1 around the origin; `suitMark` places and scales it.
 */
const SUIT_PATH = {
  H: "M0 0.92 C-0.12 0.8 -1 0.22 -1 -0.34 C-1 -0.74 -0.72 -0.96 -0.46 -0.96 " +
     "C-0.22 -0.96 -0.06 -0.8 0 -0.6 C0.06 -0.8 0.22 -0.96 0.46 -0.96 " +
     "C0.72 -0.96 1 -0.74 1 -0.34 C1 0.22 0.12 0.8 0 0.92 Z",
  D: "M0 -1 L0.74 0 L0 1 L-0.74 0 Z",
  S: "M0 -1 C0.18 -0.72 1 -0.3 1 0.18 C1 0.52 0.74 0.7 0.47 0.7 " +
     "C0.28 0.7 0.12 0.6 0.05 0.46 Q0.1 0.78 0.36 1 L-0.36 1 Q-0.1 0.78 -0.05 0.46 " +
     "C-0.12 0.6 -0.28 0.7 -0.47 0.7 C-0.74 0.7 -1 0.52 -1 0.18 C-1 -0.3 -0.18 -0.72 0 -1 Z",
  // Three lobes that do not touch, and a stem that flares only at its foot.
  C: "M0 -1 A0.35 0.35 0 1 1 0 -0.3 A0.35 0.35 0 1 1 0 -1 Z " +
     "M-0.6 -0.2 A0.35 0.35 0 1 1 -0.6 0.5 A0.35 0.35 0 1 1 -0.6 -0.2 Z " +
     "M0.6 -0.2 A0.35 0.35 0 1 1 0.6 0.5 A0.35 0.35 0 1 1 0.6 -0.2 Z " +
     "M-0.05 -0.3 L0.05 -0.3 Q0.07 0.74 0.32 1 L-0.32 1 Q-0.07 0.74 -0.05 -0.3 Z",
};

/** A suit symbol centred on (x, y), `half` units from centre to edge, upside down if asked. */
function suitMark(suit, x, y, half, cls = "pip-mark", flip = false) {
  const turn = flip ? " rotate(180)" : "";
  return `<path class="${cls}" d="${SUIT_PATH[suit]}" ` +
    `transform="translate(${x} ${y})${turn} scale(${half})"/>`;
}
const SUIT_RED = { D: true, H: true, S: false, C: false };
/* Swiss French cards call the court cards König, Dame, Bauer — so K, D, B, not K, Q, J. */
const RANK_LABEL = { A: "A", K: "K", Q: "D", J: "B", T: "10", 9: "9", 8: "8", 7: "7", 6: "6" };

/* Standard pip positions on a 100x140 face. Left/right columns, centre column.
   Anything below y=70 is drawn inverted, as on a real card. */
const PIPS = {
  6: [[30, 38], [30, 70], [30, 102], [70, 38], [70, 70], [70, 102]],
  7: [[30, 38], [30, 70], [30, 102], [70, 38], [70, 70], [70, 102], [50, 54]],
  8: [[30, 38], [30, 70], [30, 102], [70, 38], [70, 70], [70, 102], [50, 54], [50, 86]],
  9: [[30, 34], [30, 58], [30, 82], [30, 106], [70, 34], [70, 58], [70, 82], [70, 106], [50, 70]],
  T: [[30, 34], [30, 58], [30, 82], [30, 106], [70, 34], [70, 58], [70, 82], [70, 106],
      [50, 46], [50, 94]],
};

function pip(x, y, suit, half = 8.5) {
  // Pips in the lower half sit upside down on a real card.
  return suitMark(suit, x, y, half, "pip-mark", y > 70);
}

/* Court figures, after the Swiss French-suited Jass cards.
 *
 * The real ones (AGMüller; jassverzeichnis.ch shows all twelve) are double-headed half-length
 * figures that fill the frame, split by a line across the middle, with a large suit symbol in
 * the frame's top-left corner — in red, blue, gold and pale blue, outlined in black. The King
 * wears a crown, a beard and an ermine collar and holds a sceptre; the Dame a small crown, her
 * hair up, a pale veil, and a red flower; the Bauer a beret with a red feather, a moustache, a
 * laced doublet and a halberd. These are our own drawings of those features — the printed art
 * is not ours to copy — simplified so that at 62px wide in a fanned hand the three still read
 * apart by silhouette: a crown and a beard, a veil and a flower, a hat and a blade.
 */

const INK = "#1b1b1b";
const SKIN = "#f2d3b3";
const GOLD = "#e7b53c";
const RED = "#c7312c";
const BLUE = "#2f5d9b";
const PALE = "#b9d5ee";
const WHITE = "#fbf8f1";

/* The costume colours change from suit to suit, as they do on the printed cards. */
const COSTUME = {
  S: { robe: BLUE, sleeve: RED, panel: GOLD },
  C: { robe: RED, sleeve: BLUE, panel: GOLD },
  H: { robe: RED, sleeve: GOLD, panel: BLUE },
  D: { robe: BLUE, sleeve: GOLD, panel: RED },
};

const o = `stroke="${INK}" stroke-width=".8" stroke-linejoin="round"`;

/* Head at (55, 31): face, then what each figure wears and carries. */
function head(rank) {
  const face = `<ellipse cx="55" cy="31.5" rx="6.6" ry="8" fill="${SKIN}" ${o}/>
    <circle cx="52.6" cy="30.3" r=".75" fill="${INK}"/><circle cx="57.4" cy="30.3" r=".75" fill="${INK}"/>
    <path d="M55 31 L54.3 34 L55.4 34.2" fill="none" ${o}/>`;
  if (rank === "K") {
    return `${face}
      <path d="M48.8 33.5 Q48.5 42.5 55 44.5 Q61.5 42.5 61.2 33.5 Q58.5 37.5 55 37.8 Q51.5 37.5 48.8 33.5 Z" fill="#9b8f84" ${o}/>
      <path d="M52.2 36.4 Q55 35.2 57.8 36.4" fill="none" ${o}/>
      <path d="M47.5 25 L48.5 15.5 L51.5 20 L55 13.5 L58.5 20 L61.5 15.5 L62.5 25 Z" fill="${GOLD}" ${o}/>
      <rect x="47.5" y="23.2" width="15" height="3.2" fill="${RED}" ${o}/>
      <circle cx="55" cy="13.6" r="1.2" fill="${RED}" ${o}/>`;
  }
  if (rank === "Q") {
    return `<path d="M47.4 34 Q45.5 20 55 21 Q64.5 20 62.6 34 Q60 25 55 25.5 Q50 25 47.4 34 Z" fill="#8a5a33" ${o}/>
      <path d="M61.5 26 Q70 34 66 52 L61 52 Q64 38 59 30 Z" fill="${PALE}" ${o}/>
      ${face}
      <path d="M52.8 36 Q55 37.2 57.2 36" fill="none" stroke="${RED}" stroke-width=".9"/>
      <path d="M50.5 22 L51.5 17.5 L53.5 20.2 L55 16.5 L56.5 20.2 L58.5 17.5 L59.5 22 Z" fill="${GOLD}" ${o}/>`;
  }
  // Bauer
  return `${face}
    <path d="M51.5 36.4 Q55 34.6 58.5 36.4 Q55 35.8 51.5 36.4 Z" fill="#6b4a2e" ${o}/>
    <path d="M46.5 24.5 Q47 17.5 56 17.5 Q65 17.5 64.5 23.5 Q56 21.5 46.5 24.5 Z" fill="${BLUE}" ${o}/>
    <path d="M46.3 24.8 Q55 22 64.6 23.8 L64.4 25.4 Q55 23.8 46.5 26.4 Z" fill="${RED}" ${o}/>
    <path d="M49 19.5 Q42 16 40.5 22.5 Q45 19.5 49.5 21.5 Z" fill="${RED}" ${o}/>`;
}

/* The body from the shoulders to the dividing line at y = 70, and what the hands hold. */
function body(rank, suit) {
  const c = COSTUME[suit];
  const robe = `<path d="M20 70 L20 54 Q23 44.5 40 43 L70 43 Q84 44.5 85 54 L85 70 Z" fill="${c.robe}" ${o}/>
    <path d="M20 70 L20 57 Q25 49 36 47.5 L39 70 Z" fill="${c.sleeve}" ${o}/>
    <path d="M85 70 L85 57 Q80 49 72 47.5 L69 70 Z" fill="${c.sleeve}" ${o}/>`;
  if (rank === "K") {
    return `${robe}
      <path d="M47 43.5 L63 43.5 L64.5 70 L45.5 70 Z" fill="${c.panel}" ${o}/>
      <path d="M40 43.2 Q55 50.5 70 43.2 L70 47 Q55 54 40 47 Z" fill="${WHITE}" ${o}/>
      <circle cx="45" cy="47" r=".7" fill="${INK}"/><circle cx="52" cy="49.4" r=".7" fill="${INK}"/>
      <circle cx="58" cy="49.4" r=".7" fill="${INK}"/><circle cx="65" cy="47" r=".7" fill="${INK}"/>
      <rect x="72.8" y="27" width="2.4" height="43" fill="${GOLD}" ${o}/>
      <circle cx="74" cy="25" r="3" fill="${GOLD}" ${o}/>
      <path d="M74 22 L74 20 M72.6 21 L75.4 21" ${o}/>
      <ellipse cx="74" cy="56" rx="3.4" ry="2.8" fill="${SKIN}" ${o}/>`;
  }
  if (rank === "Q") {
    return `${robe}
      <path d="M46 44 L64 44 L66 70 L44 70 Z" fill="${c.panel}" ${o}/>
      <path d="M46 44 Q55 49 64 44" fill="none" ${o}/>
      <rect x="44.6" y="62" width="21" height="2.6" fill="${RED}" ${o}/>
      <path d="M35.5 64 Q36 55 38 46" fill="none" stroke="#3d7a3a" stroke-width="1.1"/>
      <path d="M36.5 55 Q33 53 32.5 50.5 Q35.5 51.5 36.8 54 Z" fill="#3d7a3a"/>
      <circle cx="38.2" cy="44.6" r="2.8" fill="${RED}" ${o}/>
      <circle cx="38.2" cy="44.6" r="1" fill="${GOLD}"/>
      <ellipse cx="36" cy="58" rx="3.2" ry="2.6" fill="${SKIN}" ${o}/>`;
  }
  // Bauer: a laced doublet, and a halberd on the right.
  return `${robe}
    <path d="M47 43.5 L63 43.5 L63.5 70 L46.5 70 Z" fill="${c.panel}" ${o}/>
    <path d="M49 47 L61 55 M61 47 L49 55 M49 55 L61 63 M61 55 L49 63" stroke="${RED}" stroke-width="1"/>
    <path d="M46 43.2 Q55 47.5 64 43.2" fill="${WHITE}" ${o}/>
    <rect x="73.3" y="20" width="2" height="50" fill="${GOLD}" ${o}/>
    <path d="M74.3 12 L76.5 19 L81 17 Q82 23 76 25 L74.3 26 L72.6 25 Q67 23 68 17 L72.2 19 Z" fill="${PALE}" ${o}/>
    <ellipse cx="74.3" cy="55" rx="3.4" ry="2.8" fill="${SKIN}" ${o}/>`;
}

function courtHalf(rank, suit) {
  // The head is drawn at a modest size and then enlarged: on the printed cards it is the
  // biggest thing in the frame, and it is what the eye finds first in a fanned hand.
  return `<g>${body(rank, suit)}
    <g transform="translate(55 33.5) scale(1.3) translate(-55 -31.5)">${head(rank)}</g>
    ${suitMark(suit, 29, 21, 6, "court-pip")}</g>`;
}

function courtFace(rank, suit) {
  // Clipped to the frame, so the figure fills it the way the printed one does.
  const id = `f${suit}${rank}`;
  return `
    <clipPath id="${id}"><rect x="21" y="9" width="62" height="122" rx="3.5"/></clipPath>
    <rect x="21" y="9" width="62" height="122" rx="3.5" fill="#fff"/>
    <g clip-path="url(#${id})">
      ${courtHalf(rank, suit)}
      <g transform="rotate(180 52 70)">${courtHalf(rank, suit)}</g>
    </g>
    <line x1="21" y1="70" x2="83" y2="70" stroke="${INK}" stroke-width=".7"/>
    <rect x="21" y="9" width="62" height="122" rx="3.5" class="court-frame"/>`;
}

export function cardFace(code) {
  const suit = code[0];
  const rank = code[1];
  const label = RANK_LABEL[rank];

  let middle;
  if (rank === "A") {
    middle = suitMark(suit, 50, 72, 19);
  } else if (PIPS[rank]) {
    middle = PIPS[rank].map(([x, y]) => pip(x, y, suit)).join("");
  } else {
    middle = courtFace(rank, suit);
  }

  const index = (x, y, cls) =>
    `<g class="${cls}">
       <text x="${x}" y="${y}" class="idx-rank">${label}</text>
       ${suitMark(suit, x, y + 10, 6.4, "idx-pip")}
     </g>`;

  return `<svg viewBox="0 0 100 140" class="face ${SUIT_RED[suit] ? "red" : "black"}"
               xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    ${index(13, 22, "idx tl")}
    <g transform="rotate(180 50 70)">${index(13, 22, "idx br")}</g>
    ${middle}
  </svg>`;
}

export const SUIT_IS_RED = SUIT_RED;
export const SUIT_GLYPHS = SUIT_GLYPH;
