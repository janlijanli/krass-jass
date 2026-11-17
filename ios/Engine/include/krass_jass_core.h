/* C interface of the krass-jass engine (rust/src/wasm_api.rs).
 *
 * The same `extern "C"` functions the browser build calls through wasm, linked natively.
 * Arguments are small integers; the only thing coming back is a JSON view, written into a
 * buffer the engine owns: a call that returns a length has put that many bytes at `view_ptr()`,
 * valid until the next such call.
 *
 * The games live in a thread-local registry, so EVERY call must come from the same thread.
 * `Engine.swift` owns that thread.
 *
 * Keep in step with wasm_api.rs by hand; `ios/tests/ffi_smoke.c` plays whole games through
 * this header and is what catches a signature that drifted.
 */
#ifndef KRASS_JASS_CORE_H
#define KRASS_JASS_CORE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

const uint8_t *view_ptr(void);

/* mode: 0 Schieber, 1 Sidi Barrani, 2 Coiffeur. extra_rows / bid_styles are bitmasks. */
uint32_t game_new(uint32_t seed_lo, uint32_t seed_hi, int32_t target_score,
                  uint32_t weis_enabled, uint32_t weis_manual,
                  int32_t m0, int32_t m1, int32_t m2, int32_t m3, int32_t m4, int32_t m5,
                  uint32_t mode, uint32_t extra_rows, uint32_t discard_sister,
                  uint32_t bid_styles);
void game_free(uint32_t handle);

/* Mutators: 0 = ok, 1 = rejected. */
uint32_t game_bid(uint32_t handle, uint32_t seat, int32_t action);       /* -1 = shove */
uint32_t game_choose_weis(uint32_t handle, uint32_t seat, uint32_t announce);
uint32_t game_play(uint32_t handle, uint32_t seat, uint32_t card);
uint32_t game_next_round(uint32_t handle);
uint32_t game_choose(uint32_t handle, uint32_t seat, int32_t index);     /* Coiffeur; -1 = shove */
uint32_t game_block(uint32_t handle, uint32_t seat, uint32_t contract);  /* Coiffeur 3x3 */
uint32_t game_call(uint32_t handle, uint32_t seat, int32_t code);        /* Sidi; -1 pass, -2 double, contract*1000+value */
uint32_t game_double(uint32_t handle, uint32_t seat, uint32_t dbl);      /* Sidi, after the lead */

/* Bots. */
int32_t  bot_bid(uint32_t handle, uint32_t seat);                        /* contract, -1 = shove */
int32_t  bot_play(uint32_t handle, uint32_t seat, uint32_t determinizations,
                  uint32_t iterations, uint32_t seed);                   /* card, -1 = none */
size_t   bot_rank(uint32_t handle, uint32_t seat, uint32_t determinizations,
                  uint32_t iterations, uint32_t seed);                   /* JSON length */
int32_t  bot_choose(uint32_t handle, uint32_t seat);                     /* index, -1 shove, -2 nothing */
int32_t  bot_block(uint32_t handle, uint32_t seat);                      /* contract, -1 none */
int32_t  bot_call(uint32_t handle, uint32_t seat);                       /* as game_call */
uint32_t bot_knock(uint32_t handle, uint32_t seat);                      /* 1 = double */
uint32_t bot_double(uint32_t handle, uint32_t seat);                     /* 1 = double */

/* Views: JSON length, payload at view_ptr(). */
size_t   game_view(uint32_t handle, uint32_t seat, uint32_t acked_tricks);
size_t   belief_marginals(uint32_t handle, uint32_t seat);

uint32_t decision_seed(uint32_t handle, uint32_t seat, uint32_t trick);
int32_t  card_value(uint32_t handle, uint32_t card);

#ifdef __cplusplus
}
#endif

#endif
