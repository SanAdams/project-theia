# Architecture — Project Theia Recognition Pipeline

## Overview

A photo of a commercial freezer enters the system as raw image bytes. The pipeline returns a list of matched products with counts. There are four stages: image preparation, box region detection, OCR per region, and product matching.

---

## Stage 1: Image Preparation

**File:** `backend/app/services/image_processor.py`

**Input:** Raw image bytes from the multipart upload.

**Output:** Compressed JPEG bytes, guaranteed under 5 MB.

**What it does:** AWS Rekognition rejects inline images over 5 MB. `prepare_image` passes images that are already small through unchanged. For larger images, it re-encodes as JPEG starting at quality 85 and steps down by 10 until under the limit (minimum quality 20).

---

## Stage 2: Box Region Detection (DetectLabels)

**File:** `backend/app/services/rekognition.py` — `_find_box_regions`

**Input:** Compressed image bytes.

**Output:** A list of deduplicated bounding boxes (normalized 0–1 coordinates) for detected box-like regions. Empty list if none found.

**What it does:**

- Calls `rekognition.detect_labels` with `MinConfidence=60`.
- Collects bounding boxes from labels whose names are in `_BOX_LABEL_NAMES`: `{Box, Cardboard, Carton, Container, Package, Packaging}`.
- Sorts candidates by confidence descending, then deduplicates: any box whose IoU with an already-accepted box exceeds `_REGION_IOU_THRESHOLD` (0.5) is dropped.

**Key constants:**
| Constant | Value | Effect |
|---|---|---|
| `_DETECT_LABELS_MIN_CONFIDENCE` | 60.0 | Lower = more regions found, more noise |
| `_REGION_IOU_THRESHOLD` | 0.5 | Lower = stricter deduplication |
| `_CROP_PADDING` | 0.02 | Extra 2% image dimension added around each crop |

---

## Stage 3: OCR per Region (DetectText)

**File:** `backend/app/services/rekognition.py` — `_match_from_crops` / `_match_full_image`

**Input:** Image bytes + list of bounding boxes from Stage 2.

**Output:** List of matched `Product` objects (one attempt per region, first match wins).

### Primary path — per-crop DetectText

When Stage 2 returns regions, each box is cropped from the full image (with 2% padding via `_crop_region`) and sent to `rekognition.detect_text` as a separate call. This makes small label text fill more of the frame, improving OCR accuracy.

Only `LINE` type detections with `Confidence >= 80.0` are kept. Each line is passed to Stage 4 (product matching); if a match is found, that box is done and the loop moves to the next region.

### Fallback path — full-image DetectText

When Stage 2 returns no regions, `_match_full_image` calls `detect_text` on the full image and spatially groups the results using `_group_detections`.

**Spatial grouping:** Two detections are in the same group if their bounding boxes overlap when each is expanded by `_X_PAD` (0.5% of width) and `_Y_PAD` (4% of height). This keeps multi-line label text together as one unit while separating adjacent boxes.

**Tuning guidance:**

- Overcounting (one box splits into multiple groups): raise `_X_PAD`.
- Undercounting (adjacent boxes merge): lower `_X_PAD`.

---

## Stage 4: Product Matching

**File:** `backend/app/services/rekognition.py` — `_match_product`

**Input:** A single detected text string.

**Output:** A `Product` object, or `None`.

**What it does:**

1. **Primary pass** — rapidfuzz `extractOne` against each product's `match_text` (the `label` field if set, otherwise `name`). Cutoff: 75%.
2. **Fallback pass** — if primary fails, rapidfuzz `extractOne` against every `nickname` across all products. Same 75% cutoff.

Logs the top-5 fuzzy scores for every lookup at INFO level — useful for diagnosing why a product did or didn't match.

**Product catalog:** `backend/products.json` — loaded on first call, then hot-reloaded whenever the file's mtime changes (no server restart needed).

---

## Data Model

**File:** `backend/app/models.py`

```
Product
  name        str   — canonical Pascal-case name ("Ring Donut")
  cic_code    str   — 8-digit inventory system identifier
  barcode     str   — optional; if set, used as scan_code
  label       str   — exact box label text; used for OCR matching instead of name
  nicknames   list  — fallback aliases matched only if label/name fails
  match_text  prop  — returns label if set, else name
  scan_code   prop  — returns barcode if set, else cic_code
```

---

## API Layer

**File:** `backend/app/routers/inventory.py`

`POST /api/v1/scan` — multipart/form-data, field `file`.

Aggregates matched products by `cic_code` (Counter), returns:

```json
{
  "items": [{ "name": "...", "cic_code": "...", "count": 1 }],
  "total_boxes": 1
}
```

---

## Mobile Client

**Files:** `mobile/src/screens/CameraScreen.tsx`, `mobile/src/services/api.ts`

- Android: reads `EXPO_PUBLIC_API_URL` from `.env`, sends multipart POST via axios.
- Web: uses native `fetch`, derives API base URL from `window.location.hostname:8000` (axios has adapter issues with FormData in Metro bundle).

Results are displayed in `mobile/src/screens/ResultsScreen.tsx` with product name and CIC code.

---

## Call Graph (happy path)

```
CameraScreen → api.ts → POST /api/v1/scan
  → prepare_image          (compress if > 5 MB)
  → detect_box_labels
      → _find_box_regions  (DetectLabels → deduplicated BBs)
      → _match_from_crops  (DetectText per crop → _match_product per line)
          → _match_product (rapidfuzz primary → nicknames fallback)
  → aggregate by cic_code
  → InventoryResult
ResultsScreen ← items[]
```
