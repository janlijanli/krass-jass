/* The hamburger menu: settings, and "How it works".
 *
 * Shared by both builds. The hosted version and the offline one differ only in where the
 * measurements artifact lives and what "start a new game" means, so those are parameters
 * rather than a reason to keep two copies.
 */

import { LANGS, LANG_NAMES, applyStatic, getLang, setLang, t } from "./i18n.js";

/* Advice mode — off by default, and remembered.
 *
 * It sits outside the settings form on purpose. Everything in that form takes effect on a
 * *new game*; this takes effect on the next card, and burying a live switch among six that
 * are not would train the player to distrust the form.
 *
 * Only the offline build can offer it: the advice is a fourth search run in this tab, and
 * the hosted build has no engine on the page to run it with.
 */
const ADVICE_KEY = "kj_advice";
let advice = false;
try {
  advice = localStorage.getItem(ADVICE_KEY) === "on";
} catch {
  advice = false;      // private windows and blocked site data are not an error here
}

export const adviceOn = () => advice;

/* Jass-Sprüche — the table talking. **On** by default, unlike advice mode: it is
 * atmosphere rather than assistance, it tells you nothing about the cards, and a silent
 * table is the poorer default. Remembered like the rest. */
const TALK_KEY = "kj_talk";
let talk = true;
try {
  talk = localStorage.getItem(TALK_KEY) !== "off";
} catch {
  talk = true;
}

export const talkOn = () => talk;

/** The language chips. Browser detection is a guess; this is how a wrong guess is fixed. */
function buildLanguagePicker(onChange) {
  const host = document.getElementById("lang-chips");
  if (!host) return;
  host.replaceChildren();
  for (const lang of LANGS) {
    const label = document.createElement("label");
    label.className = "chip";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "lang";
    input.value = lang;
    input.checked = lang === getLang();
    const span = document.createElement("span");
    span.textContent = LANG_NAMES[lang];
    label.append(input, span);
    input.addEventListener("change", () => {
      setLang(lang);
      applyStatic();
      buildLanguagePicker(onChange);
      onChange?.();
    });
    host.append(label);
  }
}

export function initMenu({
  measurementsUrl,
  onNewGame = null,
  onLanguageChange = null,
  onAdviceChange = null,
  onTalkChange = null,
}) {
  const menu = document.getElementById("menu");
  const opener = document.getElementById("menu-open");

  const open = () => {
    menu.hidden = false;
    opener.setAttribute("aria-expanded", "true");
  };
  const close = () => {
    menu.hidden = true;
    opener.setAttribute("aria-expanded", "false");
  };

  opener.addEventListener("click", open);
  document.getElementById("settings-open").addEventListener("click", open);
  document.getElementById("menu-close").addEventListener("click", close);
  document.getElementById("menu-x").addEventListener("click", close);
  menu.addEventListener("click", (e) => {
    if (e.target === menu) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !menu.hidden) close();
  });

  // Built lazily, and from an artifact rather than typed prose — see about.js and
  // docs/measurements.json.
  let built = false;
  let aboutData = null;
  async function showMode(mode) {
    document
      .querySelectorAll(".menu-mode")
      .forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
    document.getElementById("mode-settings").hidden = mode !== "settings";
    const panel = document.getElementById("mode-about");
    panel.hidden = mode !== "about";

    if (mode === "about" && !built) {
      built = true;
      panel.textContent = t("menu.loading");
      try {
        const [{ buildAbout }, data] = await Promise.all([
          import("./about.js"),
          fetch(measurementsUrl).then((r) => r.json()),
        ]);
        aboutData = data;   // kept so the panel can be rebuilt in another language
        panel.replaceChildren(buildAbout(data));
      } catch (err) {
        // Better to say the numbers are missing than to render a page of blanks that looks
        // like measurements.
        built = false;
        panel.textContent = t("menu.loadFailed");
      }
    }
  }

  document
    .querySelectorAll(".menu-mode")
    .forEach((b) => b.addEventListener("click", () => showMode(b.dataset.mode)));

  if (onNewGame) {
    // The offline build has no server to post to.
    document.querySelector("#mode-settings").addEventListener("submit", (event) => {
      event.preventDefault();
      close();
      onNewGame();
    });
  }

  /** Rebuild the documentation in the new language, if it has been opened. */
  const relocalise = async () => {
    if (!aboutData) return;
    const { buildAbout } = await import("./about.js");
    document.getElementById("mode-about").replaceChildren(buildAbout(aboutData));
  };

  // Wired here rather than left to the caller: the offline build forgot to call it, so the
  // chrome switched language and the documentation stayed behind in the old one.
  // Present only where it can work, so the offline build shows it and the hosted one
  // simply has no such control rather than a dead one.
  const adviceHost = document.getElementById("advice-toggle");
  if (adviceHost && onAdviceChange) {
    adviceHost.hidden = false;
    adviceHost.querySelectorAll('input[name="advice"]').forEach((input) => {
      input.checked = (input.value === "on") === advice;
      input.addEventListener("change", () => {
        advice = input.value === "on";
        try {
          localStorage.setItem(ADVICE_KEY, advice ? "on" : "off");
        } catch {
          /* not being able to remember it is not a reason to refuse to do it */
        }
        onAdviceChange();
      });
    });
  }

  const talkHost = document.getElementById("talk-toggle");
  if (talkHost) {
    talkHost.hidden = false;
    talkHost.querySelectorAll('input[name="talk"]').forEach((input) => {
      input.checked = (input.value === "on") === talk;
      input.addEventListener("change", () => {
        talk = input.value === "on";
        try {
          localStorage.setItem(TALK_KEY, talk ? "on" : "off");
        } catch {
          /* forgetting the preference is not a reason to refuse it */
        }
        // Silence takes effect now, not after the current bubble times out.
        if (!talk) document.querySelectorAll(".speech").forEach((n) => n.remove());
        onTalkChange?.();
      });
    });
  }

  buildLanguagePicker(() => {
    relocalise();
    onLanguageChange?.();
  });

  // The Sidi rules are one tap away from the table: the bidding panel and the settings note
  // ask for them with this event rather than knowing how the menu is built.
  document.addEventListener("kj:open-rules", async () => {
    open();
    await showMode("about");
    document.querySelector('.about-tab[data-panel="rules"]')?.click();
  });

  // The game decides which settings exist. Sidi Barrani counts every contract once and has
  // no Weis, so those two sections go while it is chosen, and its usual target is 2000.
  const form = document.getElementById("mode-settings");
  const TARGET_FOR = { sidi: "2000", schieber: "1000" };
  const syncMode = (changed) => {
    const mode = form?.querySelector('input[name="mode"]:checked')?.value || "sidi";
    form?.querySelectorAll("[data-schieber-only]").forEach((n) => { n.hidden = mode === "sidi"; });
    if (changed) {
      const target = form.querySelector(`input[name="target"][value="${TARGET_FOR[mode]}"]`);
      if (target) target.checked = true;
    }
  };
  form?.querySelectorAll('input[name="mode"]').forEach((input) =>
    input.addEventListener("change", () => syncMode(true))
  );
  syncMode(false);

  return { open, close, showMode, relocalise };
}
