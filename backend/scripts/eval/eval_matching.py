#!/usr/bin/env python3
"""Benchmark rapidfuzz scorers/cutoffs against the catalog — FALSE-POSITIVE-FIRST.

A false positive (matching the WRONG product) silently corrupts inventory and erodes
trust; a miss is a cheap human follow-up. So scorers are ranked by false positives first,
recall only as a tiebreaker, and every accepted match reports its margin (top-1 minus
top-2) — a thin margin is a false positive waiting to happen.

This calls production matching (`match_text` over `get_match_units`) via harness.py, so it
can never diverge from what production runs.

Usage:
    cd backend
    python scripts/eval/eval_matching.py            # full run (calls AWS for uncached images, then caches)
    python scripts/eval/eval_matching.py --no-aws   # cached + text/negative cases only, no AWS

Add cases with scripts/eval/capture.py or by editing scripts/eval/dataset.json.
"""

import argparse

from rapidfuzz import fuzz

from harness import (
    build_cases,
    catalog_version,
    evaluate,
    load_catalog,
    load_dataset,
    pipeline_version,
    rank,
)

# Production currently uses fuzz.partial_ratio at cutoff 80.
SCORERS = {
    "partial_ratio (current)": fuzz.partial_ratio,
    "WRatio": fuzz.WRatio,
    "ratio": fuzz.ratio,
    "token_sort_ratio": fuzz.token_sort_ratio,
    "token_set_ratio": fuzz.token_set_ratio,
    "token_ratio": fuzz.token_ratio,
    "partial_token_sort_ratio": fuzz.partial_token_sort_ratio,
    "partial_token_set_ratio": fuzz.partial_token_set_ratio,
}

PRODUCTION_CUTOFF = 80.0
CUTOFF_SWEEP = [70, 75, 80, 85, 90, 95]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-aws",
        action="store_true",
        help="skip images without cached OCR (no AWS calls)",
    )
    args = parser.parse_args()
    allow_aws = not args.no_aws

    labeled, _ = load_catalog()
    dataset = load_dataset()
    cases, skipped = build_cases(dataset, allow_aws=allow_aws)

    print(
        f"Catalog: {len(labeled)} labeled products (products.json v{catalog_version()})"
    )
    print(f"OCR pipeline version: {pipeline_version()}")
    print(f"Cases: {len(cases)} usable", end="")
    if skipped:
        print(f"  ({len(skipped)} image(s) skipped — no cached OCR: {skipped})")
    else:
        print()

    n_exhaustive = sum(1 for c in cases if c.exhaustive)
    print(
        f"False positives measured on {n_exhaustive} exhaustive case(s); "
        f"recall measured on all."
    )

    # ---- Main table: all scorers at the production cutoff, ranked FP-first ----
    results = [
        evaluate(cases, labeled, scorer=s, scorer_name=n, cutoff=PRODUCTION_CUTOFF)
        for n, s in SCORERS.items()
    ]
    ranked = rank(results)

    print("\n" + "=" * 72)
    print(
        f"SCORERS @ cutoff {PRODUCTION_CUTOFF:.0f}  (ranked: fewest false positives, then recall)"
    )
    print("=" * 72)
    print(f"  {'scorer':<26}{'false pos':>10}{'recall':>14}")
    print("  " + "-" * 50)
    for r in ranked:
        flag = "  <- FP!" if r.total_fp else ""
        recall_str = f"{r.found}/{r.expected_total} = {r.recall:.0%}"
        print(f"  {r.scorer_name:<26}{r.total_fp:>10}{recall_str:>14}{flag}")

    # ---- The false positives themselves (the silent-corruption list) ----
    print("\n  False positives (wrong product confidently matched):")
    any_fp = False
    for r in ranked:
        for c in r.cases:
            for name, score, margin in c.false_positives:
                any_fp = True
                print(
                    f"    [{r.scorer_name}] {c.name[:34]:<34} -> "
                    f"'{name}' [{score:.0f}%, margin {margin:.1f}]"
                )
    if not any_fp:
        print("    none")

    # ---- Fragile correct matches (thin margin = future FP risk) ----
    best = ranked[0]
    thin = [(c.name, t) for c in best.cases for t in c.thin_matches]
    print(f"\n  Fragile matches for best scorer ({best.scorer_name}, margin < 5):")
    if thin:
        for cname, (name, score, margin) in thin:
            print(
                f"    {cname[:34]:<34} -> '{name}' [{score:.0f}%, margin {margin:.1f}]"
            )
    else:
        print("    none")

    # ---- Cutoff sweep for the top scorers (cutoff is the dominant FP dial) ----
    print("\n" + "=" * 72)
    print("CUTOFF SWEEP  (false_pos / recall per cutoff)")
    print("=" * 72)
    top_names = [r.scorer_name for r in ranked[:3]]
    header = "  {:<26}".format("scorer") + "".join(f"{c:>10}" for c in CUTOFF_SWEEP)
    print(header)
    print("  " + "-" * (24 + 10 * len(CUTOFF_SWEEP)))
    for name in top_names:
        cells = []
        for cut in CUTOFF_SWEEP:
            r = evaluate(
                cases, labeled, scorer=SCORERS[name], scorer_name=name, cutoff=cut
            )
            cells.append(f"{r.total_fp}/{r.recall:.0%}")
        print(f"  {name:<26}" + "".join(f"{c:>10}" for c in cells))

    # ---- Recommendation: lowest cutoff with zero FP and best recall ----
    print("\n" + "=" * 72)
    zero_fp = [r for r in ranked if r.total_fp == 0]
    if zero_fp:
        winner = max(zero_fp, key=lambda r: r.recall)
        print(
            f"  Best zero-FP scorer @ cutoff {PRODUCTION_CUTOFF:.0f}: "
            f"{winner.scorer_name} (recall {winner.recall:.0%})."
        )
        print(
            "  Confirm against the cutoff sweep, then set "
            f"`SCORER = fuzz.{winner.scorer_name.split()[0]}` in rekognition.py and re-baseline."
        )
    else:
        print(
            "  WARNING: every scorer produced false positives at this cutoff. Raise the cutoff."
        )
    print()


if __name__ == "__main__":
    main()
