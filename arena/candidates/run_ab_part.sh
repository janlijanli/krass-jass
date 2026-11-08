#!/usr/bin/env bash
# One part of the Coiffeur A/B (docs/coiffeur-plan.md, 2026-11-07): the refit candidate (A) against the
# shipped weights (B), pairs FIRST .. FIRST+COUNT-1, in pieces of 20 pairs so a restart loses at most one.
# Usage: arena/candidates/run_ab_part.sh FIRST COUNT OUT.jsonl
set -u
cd "$(dirname "$0")/../.."
first=$1; count=$2; out=$3
for start in $(seq "$first" 20 $((first + count - 1))); do
  n=$(( first + count - start < 20 ? first + count - start : 20 ))
  done_here=$(python3 -c "import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and $start <= json.loads(l)['pair'] < $start + $n))" "$out" 2>/dev/null || echo 0)
  [ "$done_here" = "$n" ] && continue
  python3 -m arena.coiffeur_ab --first "$start" --games "$n" --seed 1 --iterations 2400 --workers 4 \
    --weights arena/candidates/coiffeur_weights_refit_2026-11-07.json \
    --baseline-weights krass_jass/data/coiffeur_weights.json --out "$out.tmp" \
    && cat "$out.tmp" >> "$out"; rm -f "$out.tmp"
done
echo "PART DONE $first $count"
