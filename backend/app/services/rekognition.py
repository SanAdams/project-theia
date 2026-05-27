import boto3
from rapidfuzz import fuzz, process
from io import BytesIO
import json
import logging
import os
from pathlib import Path
from typing import List, Optional
from PIL import Image

from app.models import Product

log = logging.getLogger(__name__)

_client = None
_products: List[Product] | None = None
_products_mtime: float = 0.0

_PRODUCTS_PATH = Path(__file__).parent.parent.parent / "products.json"
_MATCH_CUTOFF = 0.80
_SCORER = fuzz.partial_ratio

# Spatial grouping tolerances for full-image fallback (normalized 0-1 coordinates).
# Raise _X_PAD if one box's text splits across multiple groups (overcounting).
# Lower _X_PAD if adjacent boxes merge into one group (undercounting).
_X_PAD = 0.005  # ~0.5% of image width — tight to keep adjacent boxes separate
_Y_PAD = 0.04  # ~4% of image height — loose enough to span multi-line labels

# Box detection via DetectLabels
_BOX_LABEL_NAMES = {"Box", "Cardboard", "Carton", "Container", "Package", "Packaging"}
_DETECT_LABELS_MIN_CONFIDENCE = 60.0
_CROP_PADDING = (
    0.02  # extra 2% of image dimension added around each detected box region
)
_REGION_IOU_THRESHOLD = 0.5  # regions with IoU above this are considered duplicates
_MIN_MATCH_LENGTH = 3  # ignore OCR fragments shorter than this
_MIN_ALNUM_CHARS = (
    3  # ignore OCR fragments with fewer than this many alphanumeric characters
)


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "rekognition",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    return _client


def _get_products() -> List[Product]:
    global _products, _products_mtime
    mtime = _PRODUCTS_PATH.stat().st_mtime if _PRODUCTS_PATH.exists() else 0.0
    if _products is None or mtime != _products_mtime:
        _products_mtime = mtime
        data = json.loads(_PRODUCTS_PATH.read_text()) if _PRODUCTS_PATH.exists() else []
        if data and isinstance(data[0], str):
            _products = [Product(name=item, cic_code="") for item in data]
        else:
            _products = [
                Product(
                    name=p["name"],
                    cic_code=p.get("CIC Code", ""),
                    barcode=p.get("barcode", ""),
                    label=p.get("label", ""),
                    nicknames=p.get("nicknames", []),
                )
                for p in data
            ]
    return _products


def _match_product(label: str) -> Optional[tuple[Product, float]]:
    if len(label) < _MIN_MATCH_LENGTH:
        return None
    if sum(c.isalnum() for c in label) < _MIN_ALNUM_CHARS:
        return None
    products = _get_products()
    if not products:
        return None

    labeled = [p for p in products if p.label]
    if not labeled:
        return None

    match_texts = [p.label for p in labeled]
    top = process.extract(label, match_texts, scorer=_SCORER, limit=5)
    log.debug("    Top matches for %r:", label)
    for text, score, _ in top:
        log.debug("      [%.1f%%] %s", score, text)
    result = process.extractOne(
        label, match_texts, scorer=_SCORER, score_cutoff=_MATCH_CUTOFF * 100
    )
    if result:
        return next(p for p in labeled if p.label == result[0]), result[1]
    return None


# ---------------------------------------------------------------------------
# Full-image fallback: spatial grouping of DetectText results
# ---------------------------------------------------------------------------


def _overlaps_group(bb, group) -> bool:
    for member in group:
        g = member["Geometry"]["BoundingBox"]
        x_overlap = (
            bb["Left"] - _X_PAD < g["Left"] + g["Width"]
            and bb["Left"] + bb["Width"] + _X_PAD > g["Left"]
        )
        y_overlap = (
            bb["Top"] - _Y_PAD < g["Top"] + g["Height"]
            and bb["Top"] + bb["Height"] + _Y_PAD > g["Top"]
        )
        if x_overlap and y_overlap:
            return True
    return False


def _group_detections(detections) -> List[List[dict]]:
    groups: List[List[dict]] = []
    for det in detections:
        bb = det["Geometry"]["BoundingBox"]
        for group in groups:
            if _overlaps_group(bb, group):
                group.append(det)
                break
        else:
            groups.append([det])
    return groups


def _group_bbox(group) -> dict:
    """Compute the union bounding box for a spatial group of text detections."""
    left = min(d["Geometry"]["BoundingBox"]["Left"] for d in group)
    top = min(d["Geometry"]["BoundingBox"]["Top"] for d in group)
    right = max(
        d["Geometry"]["BoundingBox"]["Left"] + d["Geometry"]["BoundingBox"]["Width"]
        for d in group
    )
    bottom = max(
        d["Geometry"]["BoundingBox"]["Top"] + d["Geometry"]["BoundingBox"]["Height"]
        for d in group
    )
    return {"Left": left, "Top": top, "Width": right - left, "Height": bottom - top}


def _match_full_image(client, image_bytes: bytes) -> tuple[List[Product], List[dict]]:
    """Current approach: DetectText on the full image with spatial grouping."""
    response = client.detect_text(Image={"Bytes": image_bytes})

    all_lines = [d for d in response["TextDetections"] if d["Type"] == "LINE"]
    detections = [d for d in all_lines if d["Confidence"] >= 80.0]

    log.info(
        "Full-image DetectText: %d LINE detections, %d above 80%% confidence",
        len(all_lines),
        len(detections),
    )
    for d in all_lines:
        bb = d["Geometry"]["BoundingBox"]
        log.debug(
            "  [%.0f%%] %-40s  x=%.3f–%.3f  y=%.3f–%.3f",
            d["Confidence"],
            repr(d["DetectedText"]),
            bb["Left"],
            bb["Left"] + bb["Width"],
            bb["Top"],
            bb["Top"] + bb["Height"],
        )

    groups = _group_detections(detections)
    log.info("Grouped into %d spatial cluster(s)", len(groups))

    matched = []
    bboxes = []
    for i, group in enumerate(groups):
        texts = [d["DetectedText"] for d in group]
        log.info("  Group %d: %s", i + 1, texts)
        bboxes.append(_group_bbox(group))
        best_product, best_score = None, 0.0
        for det in group:
            result = _match_product(det["DetectedText"])
            if result and result[1] > best_score:
                best_product, best_score = result
        if best_product:
            log.info(
                "    -> matched: %s (CIC %s)", best_product.name, best_product.cic_code
            )
            matched.append(best_product)
        else:
            log.info("    -> no product match")
            matched.append(Product(name="Unknown", cic_code="--"))

    return matched, bboxes


# ---------------------------------------------------------------------------
# Two-pass approach: DetectLabels -> crop -> DetectText per box
# ---------------------------------------------------------------------------


def _iou(a: dict, b: dict) -> float:
    """Intersection over union for two normalized bounding boxes."""
    ax1, ay1 = a["Left"], a["Top"]
    ax2, ay2 = ax1 + a["Width"], ay1 + a["Height"]
    bx1, by1 = b["Left"], b["Top"]
    bx2, by2 = bx1 + b["Width"], by1 + b["Height"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    intersection = (ix2 - ix1) * (iy2 - iy1)
    union = a["Width"] * a["Height"] + b["Width"] * b["Height"] - intersection
    return intersection / union if union > 0 else 0.0


def _find_box_regions(client, image_bytes: bytes) -> List[dict]:
    """Call DetectLabels and return deduplicated bounding boxes for box-like instances."""
    response = client.detect_labels(
        Image={"Bytes": image_bytes},
        MinConfidence=_DETECT_LABELS_MIN_CONFIDENCE,
    )
    raw = []
    for label in response["Labels"]:
        if label["Name"] in _BOX_LABEL_NAMES:
            for inst in label.get("Instances", []):
                raw.append((inst["Confidence"], inst["BoundingBox"]))

    # Sort by confidence descending, deduplicate overlapping regions
    raw.sort(key=lambda x: x[0], reverse=True)
    accepted: List[dict] = []
    for _, bb in raw:
        if not any(_iou(bb, a) > _REGION_IOU_THRESHOLD for a in accepted):
            accepted.append(bb)

    return accepted


def _crop_region(image_bytes: bytes, bb: dict) -> bytes:
    """Crop a bounding box region (with padding) from image_bytes, return as JPEG bytes."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    x0 = max(0, (bb["Left"] - _CROP_PADDING) * w)
    y0 = max(0, (bb["Top"] - _CROP_PADDING) * h)
    x1 = min(w, (bb["Left"] + bb["Width"] + _CROP_PADDING) * w)
    y1 = min(h, (bb["Top"] + bb["Height"] + _CROP_PADDING) * h)
    crop = img.crop((x0, y0, x1, y1))
    buf = BytesIO()
    crop.save(buf, format="JPEG")
    return buf.getvalue()


def _match_from_crops(
    client, image_bytes: bytes, regions: List[dict]
) -> tuple[List[Product], List[dict]]:
    """Run DetectText on each cropped region and return one matched Product per box."""
    matched = []
    for i, bb in enumerate(regions):
        crop_bytes = _crop_region(image_bytes, bb)
        response = client.detect_text(Image={"Bytes": crop_bytes})
        lines = [
            d
            for d in response["TextDetections"]
            if d["Type"] == "LINE" and d["Confidence"] >= 80.0
        ]
        texts = [d["DetectedText"] for d in lines]
        log.info("  Box %d: %s", i + 1, texts)
        best_product, best_score = None, 0.0
        for det in lines:
            result = _match_product(det["DetectedText"])
            if result and result[1] > best_score:
                best_product, best_score = result
        if best_product:
            log.info(
                "    -> matched: %s (CIC %s)", best_product.name, best_product.cic_code
            )
            matched.append(best_product)
        else:
            log.info("    -> no product match")
            matched.append(Product(name="Unknown", cic_code="--"))
    return matched, regions


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def detect_box_labels(image_bytes: bytes) -> tuple[List[Product], List[dict]]:
    """
    Two-pass: DetectLabels to find box regions, then DetectText on each crop.
    Falls back to full-image DetectText with spatial grouping if no regions found.
    Returns (products, bboxes) where bboxes[i] is the normalized bounding box for products[i].
    """
    client = _get_client()

    regions = _find_box_regions(client, image_bytes)
    if regions:
        log.info(
            "DetectLabels: %d box region(s) found — running per-crop DetectText",
            len(regions),
        )
        matched, bboxes = _match_from_crops(client, image_bytes, regions)
    else:
        log.info(
            "DetectLabels: no box regions found — falling back to full-image DetectText"
        )
        matched, bboxes = _match_full_image(client, image_bytes)

    log.info("Result: %d product(s) detected", len(matched))
    return matched, bboxes


def get_ocr_lines(image_bytes: bytes) -> List[str]:
    """Return raw OCR LINE texts using the same pipeline as production, without matching.
    Intended for eval tooling — lets scripts benchmark scorer combinations without
    re-calling AWS for every run (results can be cached after the first call)."""
    client = _get_client()
    regions = _find_box_regions(client, image_bytes)
    lines: List[str] = []
    if regions:
        for bb in regions:
            crop_bytes = _crop_region(image_bytes, bb)
            response = client.detect_text(Image={"Bytes": crop_bytes})
            lines += [
                d["DetectedText"]
                for d in response["TextDetections"]
                if d["Type"] == "LINE" and d["Confidence"] >= 80.0
            ]
    else:
        response = client.detect_text(Image={"Bytes": image_bytes})
        lines = [
            d["DetectedText"]
            for d in response["TextDetections"]
            if d["Type"] == "LINE" and d["Confidence"] >= 80.0
        ]
    return lines
