/* The hamburger menu: settings, and "How it works".
 *
 * Shared by both builds. The hosted version and the offline one differ only in where the
 * measurements artifact lives and what "start a new game" means, so those are parameters
 * rather than a reason to keep two copies.
 */

export function initMenu({ measurementsUrl, onNewGame = null }) {
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
  async function showMode(mode) {
    document
      .querySelectorAll(".menu-mode")
      .forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
    document.getElementById("mode-settings").hidden = mode !== "settings";
    const panel = document.getElementById("mode-about");
    panel.hidden = mode !== "about";

    if (mode === "about" && !built) {
      built = true;
      panel.textContent = "Loading…";
      try {
        const [{ buildAbout }, data] = await Promise.all([
          import("./about.js?v=49f276d4"),
          fetch(measurementsUrl).then((r) => r.json()),
        ]);
        panel.replaceChildren(buildAbout(data));
      } catch (err) {
        // Better to say the numbers are missing than to render a page of blanks that looks
        // like measurements.
        built = false;
        panel.textContent = "Could not load the measurements.";
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

  return { open, close, showMode };
}
