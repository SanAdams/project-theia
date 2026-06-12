# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Project Theia is an inventory scanning app that uses computer vision to count products in commercial freezers. Users photograph boxes, AWS Rekognition performs OCR on box labels, and fuzzy matching identifies products with counts.

## Last Session

**Date:** 2026-06-12  
**Note:** Fixed web layout bug in ResultsScreen where pagination controls rendered below the viewport fold. Root cause: `flex:1` maps to `flex-basis:0%` in CSS, overriding an explicit `height` — Yoga (native) treats height as authoritative but browsers don't. Fix: `flexBasis:"auto"` + `maxHeight` + `overflow:"hidden"` on the container, and `minHeight:0` on the list. Pagination (10 items/page, Prev/Next) now works on web and native.

## Setup Commands

```bash
# Backend (run from backend/)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
uvicorn main:app --reload --host 0.0.0.0

# Mobile (run from mobile/)
npm install
npx expo start
```

The VS Code task **Ctrl+Shift+B** (Start Theia) launches both services sequentially, stopping any existing processes first. `backend/scripts/stop.ps1` handles the teardown.

## Architecture

### Recognition Pipeline (`backend/app/services/rekognition.py`)

Two-pass approach:

1. **DetectLabels** — finds box-like regions in the image (Box, Cardboard, Carton, etc.), deduplicates overlapping bounding boxes via IoU
2. **DetectText per crop** — each region is cropped from the image (with 2% padding) and sent to Rekognition separately, so small labels fill more of the frame
3. **Fallback** — if DetectLabels finds no regions, falls back to full-image DetectText with spatial grouping (`X_PAD`/`Y_PAD` tolerances)

Matching is done by `_match_product`:

- **Primary**: fuzzy match (rapidfuzz, 80% cutoff) against `product.label`

`_products` is cached in memory but re-read automatically when `products.json`'s mtime changes — no restart needed after catalog edits.

### Product Catalog (`backend/products.json`)

Array of objects:

```json
{
  "name": "Ring Donut",
  "CIC Code": "94981327",
  "label": "READY TO FINISH RING YEAST-RAISED DONUT"
}
```

- `name` — canonical product name (Pascal case)
- `CIC Code` — 8-digit identifier used in inventory systems
- `label` — exact text printed on the box label; used for OCR matching instead of `name` when set

Parser: `backend/scripts/parse_products.py` regenerates from `Order Inventory Guides Jan 2026.pdf` using pdfplumber.

### API (`backend/app/routers/inventory.py`)

`POST /api/v1/scan` — accepts `multipart/form-data` with a `file` field, returns:

```json
{
  "items": [{ "name": "...", "cic_code": "...", "count": 1 }],
  "total_boxes": 1
}
```

Images are compressed to under 5 MB before being sent to Rekognition (`image_processor.py`).

### Mobile (`mobile/`)

React Native/Expo app (Android-first, web also works). Key files:

- `App.tsx` — navigation setup and `InventoryItem` type
- `src/screens/CameraScreen.tsx` — image picker, triggers scan
- `src/screens/ResultsScreen.tsx` — displays matched products with CIC codes
- `src/services/api.ts` — scan API call; web path uses native `fetch` directly (axios has adapter issues with FormData in the Metro bundle); API base URL on web is derived from `window.location.hostname:8000`

Mobile `.env`:

```
EXPO_PUBLIC_API_URL=http://<machine-ip>:8000
```

Used by the native (Android) path only. The web client always connects to port 8000 on whatever host served the app.

## Debugging

When debugging upload or connectivity failures, **validate `.env` first**: ping or curl every configured host and IP before looking at any code. A stale IP is a common silent failure mode.

Backend logs are verbose by design: every DetectText detection, spatial group, top-5 fuzzy match scores, and final result are logged to INFO. Watch the Backend terminal during scans to diagnose matching issues.

## React Native Web layout gotchas (this app runs on web AND native)

Yoga (native) and CSS (web) resolve flexbox differently. Code that is
correct on iOS/Android can silently break in the browser:

- `flex: 1` maps to CSS `flex: 1 1 0%`. flex-basis:0% **overrides
  `height`** on the main axis in CSS (Yoga honors height). If an element
  needs an explicit height on web, also set `flexBasis: "auto"`.
- CSS flex children default to `min-height: auto` and won't shrink below
  content size. Yoga defaults to 0. Scrollable flex children need
  `minHeight: 0` to scroll internally on web.
- Expo's web template sets `body { overflow: hidden }`. Overflowing
  content is CLIPPED with no scrollbar — invisible elements may be
  rendering fine, just below the fold.
- Prefer `maxHeight` as a hard cap when bounding screens on web;
  flex-grow cannot exceed it regardless of the ancestor chain.

## Debugging protocol for layout/visibility bugs

Do NOT propose a fix until you have measurements. In order:

1. Prove the running bundle is the edited file: add a visible version
   tag to on-screen text + a module-level console.log. If it doesn't
   appear, stop — fix the build/import, not the layout.
2. Log the inputs (dimensions, item counts, computed values) and add
   `onLayout` probes to each structural element. Compare INTENDED size
   vs RESOLVED size — the first mismatch names the culprit.
3. On web, check the DOM: clientHeight vs scrollHeight and computed
   overflow on html/body/#root.
4. Only then propose a fix, and state which measurement it explains.

If two consecutive fixes produce zero visual change, assume the wrong
code is being served (cache, duplicate file, stale export) until proven
otherwise.

## Architecture Reference

Detailed pipeline documentation (box cropping, nickname matching, results display — inputs, outputs, key files per stage) lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Read it before explaining pipeline stages. Regenerate it after structural changes.
