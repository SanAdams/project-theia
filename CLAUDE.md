# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Project Theia is an inventory scanning app that uses computer vision to count products in commercial freezers. Users photograph boxes, AWS Rekognition performs OCR on box labels, and fuzzy matching identifies products with counts.

## Last Session

**Date:** 2026-06-09  
**Note:** Added full HEIC image format support end-to-end. Backend: installed pillow-heif, fixed the early-return fast-path bug in `prepare_image` that would pass raw HEIC bytes to Rekognition, wrote an eval confirming JPEG-95 is the right strategy (PNG converts to 9 MB, over Rekognition's 5 MB limit). Mobile: `expo-image-manipulator` normalizes HEIC→JPEG before upload, using `mimeType` from the picker asset instead of fragile URI extension sniffing. Next: test on an iOS device with a real HEIC photo from the library.

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

## Architecture Reference

Detailed pipeline documentation (box cropping, nickname matching, results display — inputs, outputs, key files per stage) lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Read it before explaining pipeline stages. Regenerate it after structural changes.
