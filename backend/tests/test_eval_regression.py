"""False-positive-first regression gate for product-label matching.

Runs the PRODUCTION scorer/cutoff over the eval dataset using ONLY cached OCR and text/
negative cases — never calls AWS, so it is safe in CI. Guards the property that matters
most: false positives must not grow. A miss is a cheap human follow-up; a wrong-product
match silently corrupts inventory and erodes trust.

Re-baseline scripts/eval/baseline.json after a deliberate scorer/cutoff change.
"""

import json
import warnings

import pytest

from eval import harness as h

from app.services.rekognition import MATCH_CUTOFF, SCORER

BASELINE = json.loads((h.EVAL_DIR / "baseline.json").read_text())


@pytest.fixture(scope="module")
def production_result():
    labeled, _ = h.load_catalog()
    cases, _ = h.build_cases(h.load_dataset(), allow_aws=False)
    return h.evaluate(
        cases, labeled, scorer=SCORER, scorer_name="production", cutoff=MATCH_CUTOFF
    )


def test_no_new_false_positives(production_result):
    """HARD GATE: false positives may only stay flat or shrink versus the baseline."""
    offenders = [
        f"  {c.name}: {[(n, round(s), round(m, 1)) for n, s, m in c.false_positives]}"
        for c in production_result.cases
        if c.false_positives
    ]
    assert production_result.total_fp <= BASELINE["fp"], (
        f"False positives rose to {production_result.total_fp} "
        f"(baseline {BASELINE['fp']}). A wrong-product match is worse than a miss — "
        "investigate before changing the baseline:\n" + "\n".join(offenders)
    )


def test_recall_not_silently_regressed(production_result):
    """ADVISORY: a recall drop only warns — becoming more conservative is acceptable."""
    base = (
        BASELINE["recall_found"] / BASELINE["recall_total"]
        if BASELINE["recall_total"]
        else 1.0
    )
    if production_result.recall < base - 1e-9:
        warnings.warn(
            f"Recall dropped to {production_result.recall:.0%} (baseline {base:.0%}). "
            "Not a failure, but confirm it is intentional.",
            stacklevel=2,
        )


# Note: there is deliberately no test singling out one product (e.g. Lemon Snack Pie).
# Such cases live in dataset.json as exemplars of a failure CLASS (here: a code/number
# inserted mid-label splitting a contiguous phrase). The general gate above already fails
# if any of them produces a false positive — a per-product test would only be redundant.
