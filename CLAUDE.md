# Project Theia - Inventory Scanning System

## Overview
Project Theia is an inventory scanning app that uses computer vision to automatically count products in freezers. Users photograph boxes, AWS Rekognition performs OCR on text labels, and fuzzy matching identifies products with counts.

## Architecture
- **Mobile**: React Native/Expo app (Android-first) with camera functionality
- **Backend**: Python FastAPI server with AWS Rekognition integration
- **Infrastructure**: AWS setup for Rekognition access

## Tech Stack
- **Mobile**: React Native 0.81.5, Expo 54, TypeScript, React Navigation
- **Backend**: FastAPI, boto3, rapidfuzz, Pillow, Uvicorn
- **AWS**: Rekognition for text detection

## Key Features
- Camera-based photo capture
- OCR text extraction from images
- Fuzzy string matching against product catalog
- Inventory count reporting

## Recent Development
- Fixed Expo dependencies (react-native-web, react-dom)
- Set up Python virtual environment
- Rebuilt PDF parser using pdfplumber (column-aware) — extracts 441 products from order guide
- Field name changed from `barcode` to `CIC Code` everywhere
- products.json needs manual name corrections for some entries (see "Product Catalog" below)

## Setup Commands
```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Add AWS credentials
uvicorn main:app --reload

# Mobile
cd mobile
npm install
npx expo start --tunnel
```

## API Endpoints
- `POST /api/v1/scan`: Upload image, returns inventory counts

## Product Catalog
Stored in `backend/products.json` as array of objects:
```json
{
  "name": "Product Name",
  "CIC Code": "94981327",
  "page": 1
}
```
- 441 products extracted from `Order Inventory Guides Jan 2026.pdf` (19 pages, two-column layout)
- Parser: `backend/scripts/parse_products.py` uses pdfplumber — re-run it to regenerate from the PDF
- pdfplumber must be installed: `pip install pdfplumber` (already in venv, not yet in requirements.txt)
- **Manual edits in progress**: products.json is open for corrections. Known issues:
  - Page 5 entries `94983232/34/39/42/43` (Banana/Butter/Blueberry/Cinnamon/Lemon) are sliced pound cake loaves, names need context added
  - Some very short single-word names (Cherry, Apple, Oatmeal, etc.) lack category context due to PDF layout
  - `rekognition.py` reads `p["name"]` for fuzzy matching — names just need to be recognizable from box label OCR

## Current Status
- Backend running on localhost:8000
- Mobile app bundling with tunnel mode
- Product catalog at 441 entries, manual name cleanup in progress
- Next: finish manual edits to products.json, then test with real freezer images

## Future Enhancements
- Barcode scanning integration
- Improved OCR for handwritten labels
- Spatial grouping for multi-line product names
- Inventory management integration using CIC codes