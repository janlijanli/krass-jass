/* Names for the three bots at the table.
 *
 * Dealt fresh for every game, three different ones, from a list of good old Swiss first names
 * — the kind you hear at a Jass table in a Beiz — with a few Swiss personalities mixed in for
 * the occasional surprise. Presentation only: the engine and the bots never see a name, and
 * a seat is still a seat.
 */

const CLASSIC = [
  // women
  "Irma", "Elisabeth", "Rösli", "Vreni", "Trudi", "Heidi", "Margrit", "Erika", "Hedi",
  "Frieda", "Anneli", "Gritli", "Lisbeth", "Verena", "Klärli", "Martha", "Berta", "Hulda",
  "Rosmarie", "Theres", "Emmi", "Ida", "Agathe", "Dorli", "Elsbeth", "Greti", "Hanni",
  "Käthi", "Lotti", "Nelli", "Olga", "Ursula", "Vroni", "Zita", "Bethli", "Marili",
  "Annelies", "Josefine", "Mina", "Babette", "Frida", "Leni", "Resli", "Sophie", "Wilma",
  // men
  "Sepp", "Urs", "Hansruedi", "Ueli", "Köbi", "Fritz", "Heiri", "Godi", "Ruedi", "Walti",
  "Kari", "Werni", "Housi", "Alois", "Fridolin", "Gottfried", "Jakob", "Ernst", "Xaver",
  "Balz", "Chrigu", "Dölf", "Edi", "Fredi", "Gusti", "Hene", "Noldi", "Pius", "Röbi",
  "Sämi", "Toni", "Wisi", "Zeno", "Migg", "Beat", "Otto", "Willi", "Bruno", "Kurt", "Paul",
  "Vinzenz", "Emil", "Gody", "Seppli", "Hämpu", "Ruedl", "Fridu", "Res",
];

const FAMOUS = [
  "DJ Bobo", "Albert Rösti", "Roger Federer", "Martina Hingis", "Bernhard Russi",
  "Vreni Schneider", "Pirmin Zurbriggen", "Lara Gut-Behrami", "Marco Odermatt",
  "Beni Thurnheer", "Emil Steinberger", "Ueli Maurer", "Doris Leuthard",
  "Simonetta Sommaruga", "Alain Berset", "Karin Keller-Sutter", "Guy Parmelin",
  "Viola Amherd", "Ignazio Cassis", "Simon Ammann", "Didier Cuche", "Dario Cologna",
  "Wendy Holdener", "Stan Wawrinka", "Belinda Bencic", "Michelle Hunziker", "Gölä",
  "Trauffer", "Francine Jordi", "Polo Hofer", "Stephan Eicher", "Kurt Aeschbacher",
  "Sven Epiney", "Ursula Andress", "Viktor Giacobbo", "Mike Müller", "Marco Rima",
  "Peach Weber", "Massimo Rocchi", "Lys Assia", "Nella Martinetti", "Beat Breu",
];

/** How often a famous name turns up among the three: now and then, not every game. */
const FAMOUS_SHARE = 0.25;

export const ALL_NAMES = [...CLASSIC, ...FAMOUS];

/** Three different names, in seat order: right, partner, left. */
export function dealNames(random = Math.random) {
  const picked = [];
  while (picked.length < 3) {
    const pool = random() < FAMOUS_SHARE ? FAMOUS : CLASSIC;
    const name = pool[Math.floor(random() * pool.length)];
    if (!picked.includes(name)) picked.push(name);
  }
  return picked;
}

/* AI mode's titles. Pure decoration, like the mode itself: a prefix for every bot, and now and
 * then a suffix as well, dealt per game so "Turbo-Sepp 3000" stays Turbo-Sepp 3000. Each
 * piece carries its own joiner, so ".exe" hangs on the name and "Pro Max" stands apart. */
const AI_PREFIXES = [
  "AI-enhanced ", "Neural-", "Turbo-", "Quantum-", "Deep-", "Cyber-", "Hyper-", "Robo-",
  "Mega-", "Smart-", "Overclocked ", "Self-learning ", "Cloud-", "Blockchain-", "Nano-",
  "Meta-", "Algo-", "Big-Data-", "Hologram-", "Laser-", "Supercomputer ", "Prompt-tuned ",
];
const AI_SUFFIXES = [
  " 3000", ".exe", " GPT", " Pro Max", " v2.0", " (beta)", "™", " XL", " 9000", " Deluxe",
  " Prime", " Ultra", " 2.0", " Plus", " Neo", ".zip", " (offline)", " Turbo", " 4K", " HD",
];
const AI_SUFFIX_SHARE = 0.5;

/** One AI title per bot seat (right, partner, left): `[prefix, suffix]`. */
export function dealAiTitles(random = Math.random) {
  const pick = (list) => list[Math.floor(random() * list.length)];
  const used = new Set();
  return [0, 1, 2].map(() => {
    let prefix = pick(AI_PREFIXES);
    while (used.has(prefix)) prefix = pick(AI_PREFIXES);
    used.add(prefix);
    return [prefix, random() < AI_SUFFIX_SHARE ? pick(AI_SUFFIXES) : ""];
  });
}
