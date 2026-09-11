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
  // Inline style, not a `font-size` attribute: the stylesheet sets a size for `.pip-mark`
  // and a presentation attribute loses to it, which quietly shrank the ace to pip size.
  return `<text x="${x}" y="${y}" class="pip-mark" style="font-size:${size}px"${flip}>${glyph}</text>`;
}

/* Court figures.
 *
 * Real court cards are *mirrored*: an upright half-figure on top, the same rotated 180° on
 * the bottom, so the card reads either way up. That symmetry is most of what makes a card
 * look like a card, so it is worth the extra geometry rather than drawing a single portrait.
 *
 * Heraldic rather than illustrative — flat shapes, no shading. At 62px wide on a phone,
 * detail turns to mud, and the thing that actually matters is telling a King from an Ober
 * from an Under at a glance in a fanned hand.
 */

const HEADWEAR = {
  // King: a three-pointed crown on a band.
  K: `<path d="M37 33 L40 24 L45 30 L50 21 L55 30 L60 24 L63 33 Z" class="court-ink"/>
      <rect x="37" y="33" width="26" height="4" rx="1.5" class="court-ink"/>
      <circle cx="50" cy="20" r="1.8" class="court-ink"/>`,
  // Ober: a lower coronet, three lobes — clearly not the King's spikes.
  Q: `<path d="M38 34 Q39 26 44 28 Q50 22 56 28 Q61 26 62 34 Z" class="court-ink"/>
      <rect x="38" y="34" width="24" height="3.5" rx="1.5" class="court-ink"/>`,
  // Under: a soft cap with a feather, deliberately unlike the other two.
  J: `<path d="M38 35 Q37 27 45 26 Q52 22 60 27 Q63 30 62 35 Z" class="court-ink"/>
      <path d="M60 27 Q67 20 69 13 Q64 18 58 24 Z" class="court-ink"/>
      <rect x="38" y="35" width="24" height="3.5" rx="1.5" class="court-ink"/>`,
};

/* One half of the figure, drawn to finish well clear of the midline at y=70 — the mirrored
   copy starts there, and figures that run right up to it merge into a blob. */
function courtHalf(rank, glyph) {
  return `
    <g>
      ${HEADWEAR[rank]}
      <ellipse cx="50" cy="45" rx="7.5" ry="8.5" class="court-face"/>
      <circle cx="47.2" cy="43.5" r=".9" class="court-ink"/>
      <circle cx="52.8" cy="43.5" r=".9" class="court-ink"/>
      <path d="M47.4 48.5 Q50 50.4 52.6 48.5" class="court-line"/>
      <path d="M50 54 Q39 55.5 36 65 L64 65 Q61 55.5 50 54 Z" class="court-robe"/>
      <path d="M50 54 L50 65" class="court-line"/>
      <text x="41.5" y="63.5" class="court-pip">${glyph}</text>
    </g>`;
}

function courtFace(rank, glyph) {
  return `
    <rect x="19" y="16" width="62" height="108" rx="4" class="court-frame"/>
    ${courtHalf(rank, glyph)}
    <g transform="rotate(180 50 70)">${courtHalf(rank, glyph)}</g>`;
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
