/* The hamburger menu: settings, and "How it works".
 *
 * Shared by both builds. The hosted version and the offline one differ only in where the
 * measurements artifact lives and what "start a new game" means, so those are parameters
 * rather than a reason to keep two copies.
 */

import { LANGS, LANG_NAMES, applyStatic, getLang, setLang, t } from "./i18n.js";

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

export function initMenu({ measurementsUrl, onNewGame = null, onLanguageChange = null }) {
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
  buildLanguagePicker(() => {
    relocalise();
    onLanguageChange?.();
  });

  return { open, close, showMode, relocalise };
}
