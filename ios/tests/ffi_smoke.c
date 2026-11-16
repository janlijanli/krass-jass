/* Plays whole games through ios/Engine/include/krass_jass_core.h, the way GameController.swift
 * drives them: one seat "human" (here: the first legal option every time), three bots.
 *
 * It exists because the header is kept in step with wasm_api.rs by hand. A drifted signature
 * shows up here as a game that does not finish. Run on any machine with cargo and a C compiler:
 *
 *   ios/tests/run-ffi-smoke.sh
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "krass_jass_core.h"

static char view[1 << 16];
/* With KJ_DUMP=<file>, every view is also written there, one per line ("V <json>", and
 * "A <json>" for the advice payload) — what check_views.py holds TableState.swift against. */
static FILE *dump;

static const char *read_buffer(size_t len, char tag) {
    if (len >= sizeof view) { fprintf(stderr, "view too large: %zu\n", len); exit(2); }
    memcpy(view, view_ptr(), len);
    view[len] = 0;
    if (dump) fprintf(dump, "%c %s\n", tag, view);
    return view;
}

static const char *read_view(size_t len) { return read_buffer(len, 'V'); }

/* The value after "key": as a pointer into the view, or NULL. Top-level keys come first in the
 * view, so the first match is the right one for the keys used here. */
static const char *field(const char *json, const char *key) {
    char needle[64];
    snprintf(needle, sizeof needle, "\"%s\":", key);
    const char *at = strstr(json, needle);
    return at ? at + strlen(needle) : NULL;
}

static int field_is(const char *json, const char *key, const char *value) {
    const char *at = field(json, key);
    return at && strncmp(at, value, strlen(value)) == 0;
}

static int card_index(const char *code) {
    const char *suits = "DHSC", *ranks = "AKQJT9876";
    return (int)(strchr(suits, code[0]) - suits) * 9 + (int)(strchr(ranks, code[1]) - ranks);
}

static int play_game(uint32_t mode, uint32_t seed, int32_t target) {
    uint32_t h = game_new(seed, 0, target, 1, 1, 1, 2, 1, 2, 3, 4, mode, 0x3f, 0, mode == 1 ? 0xA : 0);
    uint32_t acked = 0;
    int rounds = 0;
    for (int guard = 0; guard < 200000; guard++) {
        const char *v = read_view(game_view(h, 0, acked));
        if (field_is(v, "phase", "\"game_over\"")) {
            /* The last trick is acknowledged like any other before the scorecard shows. */
            if (field_is(v, "trick_complete", "true")) { acked++; continue; }
            if (field_is(v, "scorecard", "null")) { fprintf(stderr, "no final scorecard\n"); return 1; }
            printf("  mode %u seed %u: over after %d rounds, %s\n", mode, seed, rounds,
                   field(v, "scores") ? strndup(field(v, "scores"), 12) : "?");
            game_free(h);
            return 0;
        }
        if (field_is(v, "trick_complete", "true")) { acked++; continue; }
        if (field_is(v, "phase", "\"round_over\"")) {
            if (game_next_round(h)) { fprintf(stderr, "next_round rejected\n"); return 1; }
            acked = 0; rounds++;
            continue;
        }
        const char *to_act = field(v, "to_act");
        if (!to_act || *to_act == 'n') { fprintf(stderr, "nobody to act: %s\n", v); return 1; }
        uint32_t seat = (uint32_t)(*to_act - '0');
        uint32_t rejected = 0;
        if (field_is(v, "phase", "\"bidding\"") && mode == 2) {
            rejected = game_choose(h, seat, bot_choose(h, seat));
        } else if (field_is(v, "phase", "\"block\"")) {
            rejected = game_block(h, seat, (uint32_t)bot_block(h, seat));
        } else if (field_is(v, "phase", "\"bidding\"") && mode == 1) {
            rejected = game_call(h, seat, bot_call(h, seat));
        } else if (field_is(v, "phase", "\"doubling\"")) {
            rejected = game_double(h, seat, bot_double(h, seat));
        } else if (field_is(v, "phase", "\"bidding\"")) {
            rejected = game_bid(h, seat, bot_bid(h, seat));
        } else if (field_is(v, "phase", "\"weis\"")) {
            rejected = game_choose_weis(h, seat, 1);
        } else if (field_is(v, "phase", "\"playing\"")) {
            int32_t card;
            if (seat == 0) {
                /* The advice search answers on the player's seat (and is dumped). */
                if (dump && guard % 7 == 0) {
                    read_buffer(bot_rank(h, 0, 2, 100, 1), 'A');
                    v = read_view(game_view(h, 0, acked));
                }
                /* The "human": the first card the view offers as legal. */
                const char *legal = field(v, "legal");
                if (!legal || legal[1] != '"') { fprintf(stderr, "no legal card: %s\n", v); return 1; }
                card = card_index(legal + 2);
            } else {
                card = bot_play(h, seat, 4, 200, decision_seed(h, seat, (uint32_t)rounds));
            }
            if (card < 0) { fprintf(stderr, "bot has no card\n"); return 1; }
            rejected = game_play(h, seat, (uint32_t)card);
        } else {
            fprintf(stderr, "unknown phase: %s\n", v);
            return 1;
        }
        if (rejected) { fprintf(stderr, "move rejected in: %s\n", v); return 1; }
    }
    fprintf(stderr, "game did not finish\n");
    return 1;
}

int main(void) {
    int failed = 0;
    const char *path = getenv("KJ_DUMP");
    if (path && !(dump = fopen(path, "w"))) { perror(path); return 2; }
    /* A dump wants every kind of view, not long games: short targets. */
    int32_t target = dump ? 300 : 1000;
    uint32_t games = dump ? 1 : 3;
    printf("schieber\n");
    for (uint32_t seed = 1; seed <= games; seed++) failed |= play_game(0, seed, target);
    printf("sidi\n");
    for (uint32_t seed = 1; seed <= games; seed++) failed |= play_game(1, seed, target);
    printf("coiffeur\n");
    for (uint32_t seed = 1; seed <= (dump ? 1u : 2u); seed++) failed |= play_game(2, seed, target);

    /* The advice view and the card values answer too. */
    uint32_t h = game_new(7, 0, 1000, 1, 1, 1, 2, 1, 2, 3, 4, 0, 0, 0, 0);
    printf("view: %.120s…\n", read_view(game_view(h, 0, 0)));
    game_free(h);
    if (dump) fclose(dump);
    printf(failed ? "FAILED\n" : "ok\n");
    return failed;
}
