// Export the web UI's strings for the iOS app.
//
//   node ios/scripts/make-strings.mjs
//
// web/static/i18n.js is the one place the table's wording lives; the app reads the same keys
// from KrassJass/Resources/strings.json, generated here. Edit i18n.js and re-run — never the
// JSON. The long-form pages (about, report, walkthrough) are not part of the app and are left out.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const source = readFileSync(join(root, "web/static/i18n.js"), "utf8");

// The module touches the browser at load (language detection); give it just enough of one.
const sandbox = {
  localStorage: { getItem: () => null, setItem: () => {} },
  navigator: { language: "en", languages: ["en"] },
  document: { documentElement: {}, querySelectorAll: () => [] },
};
const script = source.replace(/^export /gm, "") + "\n;({ STRINGS, LANGS, LANG_NAMES })";
const { STRINGS, LANGS, LANG_NAMES } = vm.runInNewContext(script, sandbox);

const SKIP = /^(about|report|nerd|walk|tour|talk|beliefs|menu\.install|status\.(connect|disconnect))/;
const out = { languages: LANGS, names: LANG_NAMES, strings: {} };
for (const lang of LANGS) {
  out.strings[lang] = Object.fromEntries(
    Object.entries(STRINGS[lang]).filter(([key]) => !SKIP.test(key)).sort(([a], [b]) => a.localeCompare(b))
  );
}
const target = join(root, "ios/KrassJass/Resources/strings.json");
writeFileSync(target, JSON.stringify(out, null, 1) + "\n");
console.log(`${target}: ${LANGS.map((l) => `${l} ${Object.keys(out.strings[l]).length}`).join(", ")}`);
