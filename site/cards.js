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
const SUIT_RED = { D: true, H: true, S: false, C: false };
const RANK_LABEL = { A: "A", K: "K", Q: "Q", J: "J", T: "10", 9: "9", 8: "8", 7: "7", 6: "6" };

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

function pip(x, y, glyph, size = 22) {
  // Pips in the lower half sit upside down on a real card.
  const flip = y > 70 ? ` transform="rotate(180 ${x} ${y})"` : "";
  return `<text x="${x}" y="${y}" class="pip-mark" font-size="${size}"${flip}>${glyph}</text>`;
}

function courtFace(rank, glyph) {
  // A framed monogram. Deliberately high-contrast so the trump Jack is unmistakable.
  return `
    <rect x="24" y="26" width="52" height="88" rx="5" class="court-frame"/>
    <rect x="28" y="30" width="44" height="80" rx="3" class="court-inner"/>
    <text x="50" y="64" class="court-letter">${rank}</text>
    <text x="50" y="96" class="court-pip">${glyph}</text>`;
}

export function cardFace(code) {
  const suit = code[0];
  const rank = code[1];
  const glyph = SUIT_GLYPH[suit];
  const label = RANK_LABEL[rank];

  let middle;
  if (rank === "A") {
    middle = pip(50, 78, glyph, 46);
  } else if (PIPS[rank]) {
    middle = PIPS[rank].map(([x, y]) => pip(x, y, glyph)).join("");
  } else {
    middle = courtFace(rank, glyph);
  }

  const index = (x, y, cls) =>
    `<g class="${cls}">
       <text x="${x}" y="${y}" class="idx-rank">${label}</text>
       <text x="${x}" y="${y + 15}" class="idx-pip">${glyph}</text>
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
