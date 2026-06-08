"""
Run the Theia scan pipeline directly against one or more images.
No server required — calls AWS Rekognition directly.

Usage (from backend/):
    python scripts/scan.py path/to/image.jpg [more images or a folder]
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.image_processor import prepare_image
from app.services.rekognition import detect_box_labels

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}


def scan(path: Path) -> None:
    image_bytes = prepare_image(path.read_bytes())
    products, _ = detect_box_labels(image_bytes)

    known = [p for p in products if p.cic_code != "--"]
    unknown = sum(1 for p in products if p.cic_code == "--")

    print(f"\n{path.name}  ({len(products)} box(es))")
    seen = {}
    for p in known:
        seen[p.cic_code] = seen.get(p.cic_code, {"name": p.name, "count": 0})
        seen[p.cic_code]["count"] += 1
    for cic, info in sorted(seen.items()):
        print(f"  {info['count']:>3}×  {info['name']}  [{cic}]")
    if unknown:
        print(f"  {unknown:>3}×  Unknown")
    if not products:
        print("  (nothing matched)")


paths = []
for arg in sys.argv[1:]:
    p = Path(arg)
    if p.is_dir():
        paths.extend(f for f in sorted(p.iterdir()) if f.suffix.lower() in IMAGE_EXTS)
    else:
        paths.append(p)

if not paths:
    print("Usage: python scripts/scan.py <image> [image...] [folder]")
    sys.exit(1)

for path in paths:
    scan(path)
