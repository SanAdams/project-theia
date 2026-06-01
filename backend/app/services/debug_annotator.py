import logging
from io import BytesIO
from typing import List

from PIL import Image, ImageDraw, ImageFont

from app.models import Product

log = logging.getLogger(__name__)

_PALETTE = [
    "#FF3B30",
    "#FF9500",
    "#34C759",
    "#007AFF",
    "#AF52DE",
    "#FF2D55",
    "#5AC8FA",
    "#FFCC00",
]
_BOX_WIDTH = 3
_FONT_SIZE = 20


def _load_font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    log.warning(
        "No TrueType font found; falling back to bitmap default — debug text may look small"
    )
    return ImageFont.load_default()


def annotate_scan(
    image_bytes: bytes, products: List[Product], bboxes: List[dict]
) -> bytes:
    """Draw numbered, labeled bounding boxes on image_bytes. Returns JPEG bytes."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font = _load_font(_FONT_SIZE)

    for i, (product, bb) in enumerate(zip(products, bboxes)):
        color = _PALETTE[i % len(_PALETTE)]
        x0 = bb["Left"] * w
        y0 = bb["Top"] * h
        x1 = (bb["Left"] + bb["Width"]) * w
        y1 = (bb["Top"] + bb["Height"]) * h

        draw.rectangle([x0, y0, x1, y1], outline=color, width=_BOX_WIDTH)

        label = f"{i + 1}. {product.name}"
        try:
            bbox = font.getbbox(label)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            text_w, text_h = _FONT_SIZE * len(label) // 2, _FONT_SIZE

        pad = 3
        tx = max(0, x0)
        ty = max(0, y0 - text_h - pad * 2)

        draw.rectangle(
            [tx, ty, min(w, tx + text_w + pad * 2), ty + text_h + pad * 2],
            fill=color,
        )
        draw.text((tx + pad, ty + pad), label, fill="white", font=font)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
