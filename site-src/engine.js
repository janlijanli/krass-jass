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
    newGame({ seed, target = 1000, weis = true, weisManual = true, multipliers = [1, 2, 1, 2, 3, 4] }) {
      const lo = seed >>> 0;
      const hi = Math.floor(seed / 2 ** 32) >>> 0;
      return w.game_new(lo, hi, target, weis ? 1 : 0, weisManual ? 1 : 0, ...multipliers);
    },
    free: (h) => w.game_free(h),
    view: (h, seat, acked) => readView(w.game_view(h, seat, acked)),
    bid: (h, seat, action) => w.game_bid(h, seat, action) === 0,
    chooseWeis: (h, seat, yes) => w.game_choose_weis(h, seat, yes ? 1 : 0) === 0,
    play: (h, seat, card) => w.game_play(h, seat, card) === 0,
    nextRound: (h) => w.game_next_round(h) === 0,
    botBid: (h, seat) => w.bot_bid(h, seat),
    botPlay: (h, seat, dets, iters, seed) => w.bot_play(h, seat, dets, iters, seed),
    decisionSeed: (h, seat, trick) => w.decision_seed(h, seat, trick),
  };
}

export const CARD_INDEX = (code) => {
  const suit = "DHSC".indexOf(code[0]);
  const rank = "AKQJT9876".indexOf(code[1]);
  return suit * 9 + rank;
};
