"""Crop and barcode image storage.

With IMAGES_BUCKET unset, images live on local disk under static/ and are served
by the app's /static mount (local dev). With IMAGES_BUCKET set, they live in a
private S3 bucket (crops/<filename>, barcodes/<cic>.png) and the API hands out
presigned GET URLs.

Presigned URLs stop working when the credentials that signed them expire, which
with task-role credentials can be sooner than PRESIGNED_URL_TTL. That's acceptable:
every scan issues fresh URLs.
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional, Set

import boto3
from botocore.config import Config

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent.parent / "static"
BARCODES_DIR = STATIC_DIR / "barcodes"
CROPS_DIR = STATIC_DIR / "crops"
MAX_CROP_IMAGES = 500

BARCODE_CACHE_TTL = 300  # seconds
DEFAULT_PRESIGNED_URL_TTL = 3600

_s3_client = None
_barcode_cics: Optional[Set[str]] = None
_barcode_cics_fetched_at = 0.0


def _bucket() -> Optional[str]:
    return os.getenv("IMAGES_BUCKET") or None


def _presigned_ttl() -> int:
    try:
        return int(os.getenv("PRESIGNED_URL_TTL", DEFAULT_PRESIGNED_URL_TTL))
    except ValueError:
        log.warning("Invalid PRESIGNED_URL_TTL; using %d", DEFAULT_PRESIGNED_URL_TTL)
        return DEFAULT_PRESIGNED_URL_TTL


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
    return _s3_client


def _presign(bucket: str, key: str) -> str:
    return _get_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=_presigned_ttl(),
    )


def save_crop(filename: str, data: bytes) -> Optional[str]:
    """Store a crop and return a URL for it, or None if S3 storage failed."""
    bucket = _bucket()
    if bucket is None:
        return _save_crop_local(filename, data)
    key = f"crops/{filename}"
    try:
        _get_s3().put_object(
            Bucket=bucket, Key=key, Body=data, ContentType="image/jpeg"
        )
        return _presign(bucket, key)
    except Exception as e:
        log.warning("S3 crop upload failed for %s: %s", key, e)
        return None


def _save_crop_local(filename: str, data: bytes) -> str:
    CROPS_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(CROPS_DIR.glob("crop_*.jpg"))
    # Make room for the file about to be written. Filenames sort by timestamp, so
    # the oldest go first and a request's own earlier crops are the newest.
    while len(existing) >= MAX_CROP_IMAGES and existing:
        existing.pop(0).unlink()
    (CROPS_DIR / filename).write_bytes(data)
    return f"/static/crops/{filename}"


def _list_barcode_cics(bucket: str) -> Set[str]:
    cics: Set[str] = set()
    paginator = _get_s3().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="barcodes/"):
        for obj in page.get("Contents", []):
            name = obj["Key"][len("barcodes/") :]
            if name.endswith(".png"):
                cics.add(name[: -len(".png")])
    return cics


def _barcode_cic_set(bucket: str) -> Set[str]:
    global _barcode_cics, _barcode_cics_fetched_at
    now = time.monotonic()
    if _barcode_cics is None or now - _barcode_cics_fetched_at >= BARCODE_CACHE_TTL:
        _barcode_cics = _list_barcode_cics(bucket)
        _barcode_cics_fetched_at = now
    return _barcode_cics


def barcode_url(cic: str) -> Optional[str]:
    """URL for a product's barcode image, or None if there isn't one."""
    bucket = _bucket()
    if bucket is None:
        if (BARCODES_DIR / f"{cic}.png").exists():
            return f"/static/barcodes/{cic}.png"
        return None
    try:
        if cic not in _barcode_cic_set(bucket):
            return None
        return _presign(bucket, f"barcodes/{cic}.png")
    except Exception as e:
        log.warning("S3 barcode lookup failed for %s: %s", cic, e)
        return None
