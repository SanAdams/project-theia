from PIL import Image
import io

MAX_BYTES = 5 * 1024 * 1024  # Rekognition inline limit: 5 MB


def prepare_image(image_bytes: bytes) -> bytes:
    """Compress the image down to under 5 MB if needed, preserving quality."""
    if len(image_bytes) <= MAX_BYTES:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    output = io.BytesIO()
    quality = 85

    while quality > 20:
        output.seek(0)
        output.truncate()
        img.save(output, format="JPEG", quality=quality)
        if output.tell() <= MAX_BYTES:
            break
        quality -= 10

    return output.getvalue()
