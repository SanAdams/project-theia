import io
import logging

import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024  # Rekognition inline limit: 5 MB
_REKOGNITION_UNSUPPORTED = {"HEIF"}  # Rekognition only accepts JPEG and PNG


def prepare_image(image_bytes: bytes) -> bytes:
    """Compress the image to under 5 MB if needed, preserving quality.

    Always converts HEIC/HEIF to JPEG — Rekognition rejects those formats and
    HEIC photos typically exceed 5 MB as PNG (making lossless conversion
    impractical). JPEG quality starts at 95 and steps down only if needed.
    """
    img = Image.open(io.BytesIO(image_bytes))
    is_heic = img.format in _REKOGNITION_UNSUPPORTED

    if not is_heic and len(image_bytes) <= MAX_BYTES:
        return image_bytes  # Fast path: small, already-supported format

    img = img.convert("RGB")
    output = io.BytesIO()
    quality = 95

    while quality > 20:
        output.seek(0)
        output.truncate()
        img.save(output, format="JPEG", quality=quality)
        if output.tell() <= MAX_BYTES:
            break
        quality -= 10

    result = output.getvalue()
    if len(result) > MAX_BYTES:
        log.warning(
            "prepare_image: could not compress image below 5 MB (final size: %d bytes) — Rekognition may reject it",
            len(result),
        )
    return result
