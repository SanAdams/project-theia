"""Shared evaluation harness for product-label matching.

False-positive-first by design: a false positive (matching the wrong product) silently
corrupts inventory and erodes trust, whereas a miss is a cheap human follow-up. So the
primary metric is the false-positive count; recall is secondary.

Everything here calls PRODUCTION code (`match_text`, `get_match_units` from
`app.services.rekognition`) so the eval can never diverge from what production runs.
Used by eval_matching.py, eval_heic_formats.py, capture.py, and the pytest gate.
"""

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

EVAL_DIR = Path(__file__).parent
BACKEND_DIR = EVAL_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from app.models import Product
from app.services import rekognition as rk
from app.services.image_processor import prepare_image
from app.services.rekognition import get_match_units, match_text

CACHE_DIR = EVAL_DIR / "cache"
DATASET_PATH = EVAL_DIR / "dataset.json"
PRODUCTS_PATH = BACKEND_DIR / "products.json"

# Matches flagged as "fragile" (a false positive waiting to happen as the catalog grows).
THIN_MARGIN = 5.0


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def load_catalog() -> tuple[list[Product], dict[str, str]]:
    """Return (labeled products, label->name map) from the production catalog loader."""
    labeled = [p for p in rk._get_products() if p.label]
    name_by_label = {p.label: p.name for p in labeled}
    return labeled, name_by_label


def catalog_version() -> str:
    """mtime of products.json — recorded in eval output so results are reproducible
    across catalog edits (matching depends on the catalog, not just the OCR)."""
    return str(int(PRODUCTS_PATH.stat().st_mtime))


# ---------------------------------------------------------------------------
# OCR-units cache (keyed by image bytes + OCR-pipeline version)
# ---------------------------------------------------------------------------


def pipeline_version() -> str:
    """Short hash of the OCR-pipeline constants. If any change, cached units are
    treated as stale instead of silently benchmarking phantom OCR."""
    payload = repr(
        (
            rk.MIN_TEXT_CONFIDENCE,
            rk.X_PAD,
            rk.Y_PAD,
            sorted(rk.BOX_LABEL_NAMES),
            rk.DETECT_LABELS_MIN_CONFIDENCE,
            rk.CROP_PADDING,
            rk.REGION_IOU_THRESHOLD,
        )
    )
    return hashlib.md5(payload.encode()).hexdigest()[:8]


def _cache_path(image_bytes: bytes) -> Path:
    return CACHE_DIR / f"{hashlib.md5(image_bytes).hexdigest()}.json"


def get_cached_units(image_bytes: bytes) -> Optional[list[str]]:
    path = _cache_path(image_bytes)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    # Only a dict with a matching pipeline version is valid; older raw-line-list caches
    # (a different granularity) are deliberately ignored.
    if isinstance(data, dict) and data.get("pipeline") == pipeline_version():
        return data["units"]
    return None


def save_cached_units(image_bytes: bytes, units: list[str]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(image_bytes).write_text(
        json.dumps({"pipeline": pipeline_version(), "units": units}, indent=2)
    )


def units_for_image(image_path: Path, *, allow_aws: bool) -> Optional[list[str]]:
    """Return production match-units for an image. Uses cache; only calls AWS when
    allow_aws is True (the pytest gate runs with allow_aws=False, so it never bills)."""
    image_bytes = image_path.read_bytes()
    cached = get_cached_units(image_bytes)
    if cached is not None:
        return cached
    if not allow_aws:
        return None
    units = get_match_units(prepare_image(image_bytes))
    save_cached_units(image_bytes, units)
    return units


# ---------------------------------------------------------------------------
# Dataset -> normalized cases
# ---------------------------------------------------------------------------


@dataclass
class Case:
    name: str
    units: list[str]
    expected: set[str]  # empty set = should match nothing
    exhaustive: bool  # if False, false positives are not counted (recall only)


def _short(text: str, n: int = 44) -> str:
    return text[:n]


def load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text())


def build_cases(dataset: dict, *, allow_aws: bool) -> tuple[list[Case], list[str]]:
    """Normalize all three buckets into Case objects. Returns (cases, skipped) where
    skipped lists image files with no cached units (when allow_aws is False)."""
    cases: list[Case] = []
    skipped: list[str] = []

    for tc in dataset.get("text_cases", []):
        cases.append(
            Case(
                name="text:" + _short(tc["ocr"]),
                units=[tc["ocr"]],
                expected=set(tc.get("expected", [])),
                exhaustive=True,
            )
        )

    for nc in dataset.get("negative_cases", []):
        if "ocr" in nc:
            cases.append(
                Case(
                    name="neg:" + _short(nc["ocr"]),
                    units=[nc["ocr"]],
                    expected=set(),
                    exhaustive=True,
                )
            )
            continue
        units = units_for_image(EVAL_DIR / nc["file"], allow_aws=allow_aws)
        if units is None:
            skipped.append(nc["file"])
            continue
        cases.append(
            Case(name="neg:" + nc["file"], units=units, expected=set(), exhaustive=True)
        )

    for ic in dataset.get("image_cases", []):
        units = units_for_image(EVAL_DIR / ic["file"], allow_aws=allow_aws)
        if units is None:
            skipped.append(ic["file"])
            continue
        cases.append(
            Case(
                name=ic["file"],
                units=units,
                expected={e for e in ic.get("expected", []) if e},
                exhaustive=not ic.get("partial", False),
            )
        )

    return cases, skipped


# ---------------------------------------------------------------------------
# Evaluation (FP-first)
# ---------------------------------------------------------------------------


@dataclass
class CaseResult:
    name: str
    expected: set[str]
    found: set[str]
    missed: set[str]
    false_positives: list[tuple[str, float, float]]  # (wrong_name, score, margin)
    thin_matches: list[tuple[str, float, float]]  # correct but fragile (small margin)


@dataclass
class EvalResult:
    scorer_name: str
    cutoff: float
    total_fp: int
    found: int
    expected_total: int
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.found / self.expected_total if self.expected_total else 1.0


def evaluate(
    cases: list[Case],
    labeled: list[Product],
    *,
    scorer: Callable,
    scorer_name: str,
    cutoff: float,
    thin_margin: float = THIN_MARGIN,
) -> EvalResult:
    total_fp = 0
    found_total = 0
    expected_total = 0
    case_results: list[CaseResult] = []

    for case in cases:
        # Best evidence (highest score) seen per matched product name.
        matched: dict[str, tuple[float, float]] = {}
        for unit in case.units:
            r = match_text(unit, labeled, scorer=scorer, cutoff=cutoff)
            if r.product is None:
                continue
            name = r.product.name
            if name not in matched or r.score > matched[name][0]:
                matched[name] = (r.score, r.margin)

        matched_names = set(matched)
        found = matched_names & case.expected
        missed = case.expected - matched_names
        fp_names = (matched_names - case.expected) if case.exhaustive else set()
        false_positives = [(n, matched[n][0], matched[n][1]) for n in sorted(fp_names)]
        thin = [
            (n, matched[n][0], matched[n][1])
            for n in sorted(found)
            if matched[n][1] < thin_margin
        ]

        case_results.append(
            CaseResult(case.name, case.expected, found, missed, false_positives, thin)
        )
        total_fp += len(fp_names)
        found_total += len(found)
        expected_total += len(case.expected)

    return EvalResult(
        scorer_name, cutoff, total_fp, found_total, expected_total, case_results
    )


def rank(results: list[EvalResult]) -> list[EvalResult]:
    """Lexicographic, FP-first: fewest false positives wins; recall only breaks ties.
    Deliberately NOT a summed score — summing is what produced earlier noise verdicts.
    """
    return sorted(results, key=lambda r: (r.total_fp, -r.recall))
