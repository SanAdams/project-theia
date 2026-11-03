from fastapi import APIRouter, UploadFile, File, HTTPException
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional

from app.services.rekognition import detect_box_labels, crop_region
from app.services.image_processor import prepare_image
from app.services.debug_annotator import annotate_scan
from app.services.storage import save_crop, barcode_url

DEBUG_DIR = Path(__file__).parent.parent.parent / "static" / "debug"
MAX_DEBUG_IMAGES = 10

router = APIRouter()


class InventoryItem(BaseModel):
    name: str
    cic_code: str
    count: int
    barcode_image_url: Optional[str] = None
    crop_image_urls: List[str] = Field(default_factory=list)


class InventoryResult(BaseModel):
    items: List[InventoryItem]
    total_boxes: int
    debug_image_url: Optional[str] = None


@router.post("/scan", response_model=InventoryResult)
async def scan_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    raw_bytes = await file.read()
    image_bytes = prepare_image(raw_bytes)

    matched_products, bboxes = detect_box_labels(image_bytes)

    known = [p for p in matched_products if p.cic_code != "--"]
    counts: Counter = Counter(p.cic_code for p in known)
    product_map = {p.cic_code: p for p in known}

    timestamp = None
    crop_urls_by_cic: dict[str, list[str]] = defaultdict(list)
    unknown_crop_urls: list[Optional[str]] = []

    if matched_products and bboxes:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        for i, (product, bb) in enumerate(zip(matched_products, bboxes)):
            crop_bytes = crop_region(image_bytes, bb)
            filename = f"crop_{timestamp}_{i:02d}_{product.cic_code}.jpg"
            url = save_crop(filename, crop_bytes)
            if product.cic_code == "--":
                # Keep the slot even if the upload failed: the box still counts.
                unknown_crop_urls.append(url)
            elif url:
                crop_urls_by_cic[product.cic_code].append(url)

    items = [
        InventoryItem(
            name=product_map[cic].name,
            cic_code=cic,
            count=count,
            barcode_image_url=barcode_url(cic),
            crop_image_urls=crop_urls_by_cic.get(cic, []),
        )
        for cic, count in sorted(counts.items())
    ]
    items += [
        InventoryItem(
            name="Unknown",
            cic_code="--",
            count=1,
            barcode_image_url=None,
            crop_image_urls=[url] if url else [],
        )
        for url in unknown_crop_urls
    ]

    debug_image_url = None
    if matched_products and bboxes:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        existing_debug = sorted(DEBUG_DIR.glob("scan_*.jpg"))
        while len(existing_debug) >= MAX_DEBUG_IMAGES:
            existing_debug.pop(0).unlink()
        annotated = annotate_scan(image_bytes, matched_products, bboxes)
        debug_path = DEBUG_DIR / f"scan_{timestamp}.jpg"
        debug_path.write_bytes(annotated)
        debug_image_url = f"/static/debug/scan_{timestamp}.jpg"

    return InventoryResult(
        items=items,
        total_boxes=len(matched_products),
        debug_image_url=debug_image_url,
    )
