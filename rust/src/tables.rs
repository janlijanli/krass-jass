//! Precomputed value and strength tables, mirroring `krass_jass/tables.py`.
//!
//! Everything is `const` — built at compile time with while-loops — so the hot paths index
//! into static arrays and the search never recomputes a rule.

use crate::cards::*;

pub const NUM_CONTRACTS: usize = 6;
pub const OBENABE: usize = 4;
pub const UNDENUFE: usize = 5;

const VAL_PLAIN: [i32; NUM_RANKS] = [11, 4, 3, 2, 10, 0, 0, 0, 0];
const VAL_TRUMP: [i32; NUM_RANKS] = [11, 4, 3, 20, 10, 14, 0, 0, 0];
const VAL_OBENABE: [i32; NUM_RANKS] = [11, 4, 3, 2, 10, 0, 8, 0, 0];
/// Undenufe inverts the values along with the order: the 6 is worth 11, the ace 0.
const VAL_UNDENUFE: [i32; NUM_RANKS] = [0, 4, 3, 2, 10, 0, 8, 0, 11];

/// J > 9 > A > K > Q > 10 > 8 > 7 > 6
const STR_TRUMP: [i32; NUM_RANKS] = [6, 5, 4, 8, 3, 7, 2, 1, 0];

const fn str_plain(r: usize) -> i32 {
    (NUM_RANKS - 1 - r) as i32
}

/// `TRUMP_HIGHER[s]` — mask of trump *ranks* strictly stronger than trump strength `s`.
/// Shift by `trump * 9` for a card mask. Makes the undertrump rule a lookup.
const fn build_trump_higher() -> [u64; NUM_RANKS] {
    let mut out = [0u64; NUM_RANKS];
    let mut s = 0;
    while s < NUM_RANKS {
        let mut r = 0;
        while r < NUM_RANKS {
            if STR_TRUMP[r] > s as i32 {
                out[s] |= 1u64 << r;
            }
            r += 1;
        }
        s += 1;
    }
    out
}

pub const TRUMP_HIGHER: [u64; NUM_RANKS] = build_trump_higher();

const fn trump_of(contract: usize) -> i32 {
    if contract < 4 {
        contract as i32
    } else {
        -1
    }
}

const fn build_values() -> [[i32; NUM_CARDS]; NUM_CONTRACTS] {
    let mut out = [[0i32; NUM_CARDS]; NUM_CONTRACTS];
    let mut k = 0;
    while k < NUM_CONTRACTS {
        let trump = trump_of(k);
        let mut c = 0;
        while c < NUM_CARDS {
            let s = c / NUM_RANKS;
            let r = c % NUM_RANKS;
            out[k][c] = if k == OBENABE {
                VAL_OBENABE[r]
            } else if k == UNDENUFE {
                VAL_UNDENUFE[r]
            } else if s as i32 == trump {
                VAL_TRUMP[r]
            } else {
                VAL_PLAIN[r]
            };
            c += 1;
        }
        k += 1;
    }
    out
}

pub const CARD_VALUES: [[i32; NUM_CARDS]; NUM_CONTRACTS] = build_values();

/// `STRENGTH[contract][led][card]`, banded so one `max` decides the trick:
/// trump 100+, led suit 10+, anything else 0.
const fn build_strength() -> [[[i32; NUM_CARDS]; NUM_SUITS]; NUM_CONTRACTS] {
    let mut out = [[[0i32; NUM_CARDS]; NUM_SUITS]; NUM_CONTRACTS];
    let mut k = 0;
    while k < NUM_CONTRACTS {
        let trump = trump_of(k);
        let mut led = 0;
        while led < NUM_SUITS {
            let mut c = 0;
            while c < NUM_CARDS {
                let s = c / NUM_RANKS;
                let r = c % NUM_RANKS;
                out[k][led][c] = if s as i32 == trump {
                    100 + STR_TRUMP[r]
                } else if s == led {
                    // Undenufe reverses the order: the 6 is high
                    10 + if k == UNDENUFE { r as i32 } else { str_plain(r) }
                } else {
                    0
                };
                c += 1;
            }
            led += 1;
        }
        k += 1;
    }
    out
}

pub const STRENGTH: [[[i32; NUM_CARDS]; NUM_SUITS]; NUM_CONTRACTS] = build_strength();

/// `SUIT_ORDER[contract][suit]` — the nine card indices of that suit, strongest first.
///
/// Used by the endgame solver's equivalence reduction, which needs the ranking *within* a
/// suit independent of what was led.
const fn build_suit_order() -> [[[usize; NUM_RANKS]; NUM_SUITS]; NUM_CONTRACTS] {
    let mut out = [[[0usize; NUM_RANKS]; NUM_SUITS]; NUM_CONTRACTS];
    let mut k = 0;
    while k < NUM_CONTRACTS {
        let trump = trump_of(k);
        let mut suit = 0;
        while suit < NUM_SUITS {
            // insertion sort by strength, descending
            let mut n = 0;
            while n < NUM_RANKS {
                let mut best_r = usize::MAX;
                let mut best_s = -1i32;
                let mut r = 0;
                while r < NUM_RANKS {
                    // skip ranks already placed
                    let mut placed = false;
                    let mut i = 0;
                    while i < n {
                        if out[k][suit][i] == suit * NUM_RANKS + r {
                            placed = true;
                        }
                        i += 1;
                    }
                    if !placed {
                        let st = if suit as i32 == trump {
                            STR_TRUMP[r]
                        } else if k == UNDENUFE {
                            r as i32
                        } else {
                            str_plain(r)
                        };
                        if st > best_s {
                            best_s = st;
                            best_r = r;
                        }
                    }
                    r += 1;
                }
                out[k][suit][n] = suit * NUM_RANKS + best_r;
                n += 1;
            }
            suit += 1;
        }
        k += 1;
    }
    out
}

pub const SUIT_ORDER: [[[usize; NUM_RANKS]; NUM_SUITS]; NUM_CONTRACTS] = build_suit_order();
