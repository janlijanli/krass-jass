/* The splash: a few cards dealt onto the felt as the app opens, then what to play.
 *
 * Shown once per session (a cold start of the home-screen app is a new session), over the
 * table, which is drawn underneath and simply revealed. "Continue" is offered when there is a
 * game to go back to; each game mode starts a new one. The caller decides what those mean —
 * the offline build resumes or deals locally, the hosted one posts to the server — so this
 * module only lays out, animates and reports the choice.
 *
 * A tap during the deal skips to the choice. With reduced motion the choice is simply there.
 */
import { cardFace, SUIT_IS_RED } from "./cards.js";
import { t } from "./i18n.js";

const SEEN_KEY = "kj_splashed";

/** The cards dealt in: the Ecken 10 that opens a game, flanked by the Puur and Nell and two Aces. */
const CARDS = ["SA", "HJ", "DT", "C9", "HA"];
/** Where each lands in the fan, from the centre: offset in card widths, and its tilt. */
const FAN = [[-1.5, -14], [-0.75, -7], [0, 0], [0.75, 7], [1.5, 14]];

export const MODES = ["schieber", "sidi", "coiffeur"];

/** Whether this session has shown the splash already. Storage may be blocked: then it shows. */
export function splashSeen() {
  try {
    return sessionStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

function markSeen() {
  try {
    sessionStorage.setItem(SEEN_KEY, "1");
  } catch {
    /* the splash shows again next load, which is harmless */
  }
}

function el(tag, cls, html) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

/**
 * Show the splash. `resume` is null when there is nothing to continue, else
 * `{ mode, round }` for the line under "Continue". Resolves to "continue" or a mode name once
 * the splash has gone.
 */
export function showSplash({ resume = null } = {}) {
  markSeen();
  const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const root = el("div", "splash" + (still ? " still ready" : ""));
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.setAttribute("aria-label", "Krass Jass");

  const stage = el("div", "splash-stage");
  const fan = el("div", "splash-fan");
  CARDS.forEach((code, i) => {
    const [x, r] = FAN[i];
    const card = el("div", "splash-card");
    card.style.setProperty("--x", x);
    card.style.setProperty("--r", `${r}deg`);
    card.style.setProperty("--i", i);
    const inner = el("div", "splash-flip");
    inner.append(
      el("div", "card splash-face" + (SUIT_IS_RED[code[0]] ? " red" : ""), cardFace(code)),
      el("div", "splash-back"),
    );
    card.append(inner);
    fan.append(card);
  });
  stage.append(fan, el("h1", "splash-title", "Krass <span>Jass</span>"));

  const menu = el("nav", "splash-menu");
  let step = 0;
  const option = (key, title, note, primary = false) => {
    const button = el("button", "splash-option" + (primary ? " primary" : ""));
    button.type = "button";
    button.dataset.choice = key;
    button.style.setProperty("--n", step++);
    button.append(el("span", "splash-option-title", title), el("span", "splash-option-note", note));
    menu.append(button);
  };
  if (resume) {
    option("continue", t("splash.continue"),
      t("splash.continueNote", { mode: t(`splash.mode.${resume.mode}`), n: resume.round + 1 }), true);
  }
  const heading = el("p", "splash-heading", t("splash.newGame"));
  heading.style.setProperty("--n", step++);
  menu.append(heading);
  for (const mode of MODES) option(mode, t(`splash.mode.${mode}`), t(`splash.note.${mode}`), !resume && mode === "sidi");

  root.append(stage, menu);
  document.body.append(root);

  return new Promise((resolve) => {
    // The deal takes ~1.7s; then the fan rises and the choice comes in. A tap brings it now.
    const reveal = () => root.classList.add("ready");
    const timer = setTimeout(reveal, still ? 0 : 1700);
    root.addEventListener("pointerdown", () => {
      clearTimeout(timer);
      reveal();
    }, { once: true });

    menu.addEventListener("click", (event) => {
      const button = event.target.closest(".splash-option");
      if (!button || root.classList.contains("leaving")) return;
      root.classList.add("leaving");
      button.classList.add("chosen");
      const done = () => {
        root.remove();
        resolve(button.dataset.choice);
      };
      if (still) done();
      else setTimeout(done, 420);
    });
  });
}
