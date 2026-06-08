from pathlib import Path
from PIL import Image
import io

from app.services.image_processor import prepare_image

HEIC_PATH = Path(__file__).parent / "test_images" / "IMG_20260526_221011 (4) (1).heic"
MAX_BYTES = 5 * 1024 * 1024


def test_prepare_image_converts_heic_to_supported_format():
    """HEIC input must produce JPEG or PNG output (both Rekognition-supported)."""
    result = prepare_image(HEIC_PATH.read_bytes())
    img = Image.open(io.BytesIO(result))
    assert img.format in ("JPEG", "PNG"), f"Unexpected format: {img.format}"


def test_prepare_image_heic_output_under_5mb():
    """HEIC input must produce output within Rekognition's 5 MB limit."""
    result = prepare_image(HEIC_PATH.read_bytes())
    assert len(result) <= MAX_BYTES, f"Output too large: {len(result)} bytes"


def test_prepare_image_small_jpeg_unchanged():
    """Small JPEG under 5 MB must be returned as-is (no recompression)."""
    sample = next(
        (
            p
            for p in (Path(__file__).parent / "test_images").iterdir()
            if p.suffix.lower() == ".jpg" and p.stat().st_size <= MAX_BYTES
        ),
        None,
    )
    if sample:
        raw = sample.read_bytes()
        assert prepare_image(raw) == raw, "Small JPEG should be returned unchanged"
