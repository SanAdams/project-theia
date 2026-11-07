import io
import random

import pillow_heif
import pytest
from PIL import Image

from app.services.image_processor import prepare_image

pillow_heif.register_heif_opener()

MAX_BYTES = 5 * 1024 * 1024


def _noisy_image(width: int, height: int) -> Image.Image:
    """Random noise barely compresses, so it reliably produces large files."""
    data = random.Random(0).randbytes(width * height * 3)
    return Image.frombytes("RGB", (width, height), data)


def _encode(img: Image.Image, fmt: str, **kwargs) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


@pytest.fixture(scope="module")
def heic_bytes() -> bytes:
    # 4000x3000 noise exceeds libheif's decode limits; this size is ~10 MB.
    return _encode(_noisy_image(3000, 2250), "HEIF", quality=90)


@pytest.fixture(scope="module")
def big_jpeg_bytes() -> bytes:
    return _encode(_noisy_image(4000, 3000), "JPEG", quality=100)


def test_prepare_image_converts_heic_to_supported_format(heic_bytes):
    """HEIC input must produce JPEG or PNG output (both Rekognition-supported)."""
    result = prepare_image(heic_bytes)
    img = Image.open(io.BytesIO(result))
    assert img.format in ("JPEG", "PNG"), f"Unexpected format: {img.format}"


def test_prepare_image_heic_output_under_5mb(heic_bytes):
    """HEIC input must produce output within Rekognition's 5 MB limit."""
    assert len(heic_bytes) > MAX_BYTES, "fixture should start out over the limit"
    result = prepare_image(heic_bytes)
    assert len(result) <= MAX_BYTES, f"Output too large: {len(result)} bytes"


def test_prepare_image_compresses_oversized_jpeg(big_jpeg_bytes):
    """A JPEG over 5 MB is recompressed to fit, and stays a JPEG."""
    assert len(big_jpeg_bytes) > MAX_BYTES, "fixture should start out over the limit"
    result = prepare_image(big_jpeg_bytes)
    assert len(result) <= MAX_BYTES
    assert Image.open(io.BytesIO(result)).format == "JPEG"


def test_prepare_image_small_jpeg_unchanged():
    """Small JPEG under 5 MB must be returned as-is (no recompression)."""
    raw = _encode(_noisy_image(200, 150), "JPEG", quality=90)
    assert len(raw) <= MAX_BYTES
    assert prepare_image(raw) == raw, "Small JPEG should be returned unchanged"
