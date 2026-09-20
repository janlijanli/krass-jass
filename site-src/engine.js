/* The engine, running in this tab.
 *
 * Talks to the wasm module through plain integer calls; the only thing coming back is a JSON
 * view, written into a buffer inside wasm memory that we decode here. No bindgen, no glue.
 *
 * The view has the same shape the server sends, so the rendering code does not know or care
 * which produced it.
 */

const decoder = new TextDecoder();

export async function loadEngine(url = "krass_jass_core.wasm") {
  const { instance } = await WebAssembly.instantiateStreaming(fetch(url), {});
  const w = instance.exports;

  const readView = (len) =>
    JSON.parse(decoder.decode(new Uint8Array(w.memory.buffer, w.view_ptr(), len)));

  return {
    newGame({ seed, target = 1000, weis = true, weisManual = true, multipliers = [1, 2, 1, 2, 3, 4], mode = "schieber" }) {
      const lo = seed >>> 0;
      const hi = Math.floor(seed / 2 ** 32) >>> 0;
      return w.game_new(lo, hi, target, weis ? 1 : 0, weisManual ? 1 : 0, ...multipliers,
                        mode === "sidi" ? 1 : 0);
    },
    free: (h) => w.game_free(h),
    view: (h, seat, acked) => readView(w.game_view(h, seat, acked)),
    bid: (h, seat, action) => w.game_bid(h, seat, action) === 0,
    chooseWeis: (h, seat, yes) => w.game_choose_weis(h, seat, yes ? 1 : 0) === 0,
    play: (h, seat, card) => w.game_play(h, seat, card) === 0,
    nextRound: (h) => w.game_next_round(h) === 0,
    botBid: (h, seat) => w.bot_bid(h, seat),
    botPlay: (h, seat, dets, iters, seed) => w.bot_play(h, seat, dets, iters, seed),
    // The same search `botPlay` runs, published instead of played — advice mode.
    botRank: (h, seat, dets, iters, seed) => readView(w.bot_rank(h, seat, dets, iters, seed)),
    decisionSeed: (h, seat, trick) => w.decision_seed(h, seat, trick),
    // Sidi Barrani. A call crosses as one integer (see wasm_api.rs); these speak its wire form.
    call: (h, seat, text) => w.game_call(h, seat, callCode(text)) === 0,
    double: (h, seat, yes) => w.game_double(h, seat, yes ? 1 : 0) === 0,
    botCall: (h, seat) => callText(w.bot_call(h, seat)),
    botDouble: (h, seat) => w.bot_double(h, seat) === 1,
    botKnock: (h, seat) => w.bot_knock(h, seat) === 1,
    // Test mode: the search's own belief pool, summarised — see wasm_api.rs.
    beliefs: (h, seat) => readView(w.belief_marginals(h, seat)),
  };
}

const CONTRACT_NAMES = ["DIAMONDS", "HEARTS", "SPADES", "CLUBS", "OBENABE", "UNDENUFE"];

/** "PASS" → -1, "DOUBLE" → -2, "HEARTS 100" → 1100. */
export function callCode(text) {
  if (text === "PASS") return -1;
  if (text === "DOUBLE") return -2;
  const [name, value] = text.split(" ");
  const contract = CONTRACT_NAMES.indexOf(name);
  return contract < 0 ? -3 : contract * 1000 + Number(value);
}

export function callText(code) {
  if (code === -1) return "PASS";
  if (code === -2) return "DOUBLE";
  return `${CONTRACT_NAMES[Math.floor(code / 1000)]} ${code % 1000}`;
}

export const CARD_INDEX = (code) => {
  const suit = "DHSC".indexOf(code[0]);
  const rank = "AKQJT9876".indexOf(code[1]);
  return suit * 9 + rank;
};
