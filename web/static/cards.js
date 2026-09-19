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

function pip(x, y, suit, half = 8.5) {
  // Pips in the lower half sit upside down on a real card.
  return suitMark(suit, x, y, half, "pip-mark", y > 70);
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
function courtHalf(rank, suit) {
  return `
    <g>
      ${HEADWEAR[rank]}
      <ellipse cx="50" cy="45" rx="7.5" ry="8.5" class="court-face"/>
      <circle cx="47.2" cy="43.5" r=".9" class="court-ink"/>
      <circle cx="52.8" cy="43.5" r=".9" class="court-ink"/>
      <path d="M47.4 48.5 Q50 50.4 52.6 48.5" class="court-line"/>
      <path d="M50 54 Q39 55.5 36 65 L64 65 Q61 55.5 50 54 Z" class="court-robe"/>
      <path d="M50 54 L50 65" class="court-line"/>
      ${suitMark(suit, 41.5, 59.5, 4.6, "court-pip")}
    </g>`;
}

function courtFace(rank, suit) {
  return `
    <rect x="19" y="16" width="62" height="108" rx="4" class="court-frame"/>
    ${courtHalf(rank, suit)}
    <g transform="rotate(180 50 70)">${courtHalf(rank, suit)}</g>`;
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
