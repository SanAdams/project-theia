import pytest

from app.services import storage


class FakeS3:
    def __init__(self, barcode_keys=(), fail=False):
        self.barcode_keys = list(barcode_keys)
        self.fail = fail
        self.puts = []
        self.presigns = []
        self.list_calls = 0

    def put_object(self, **kwargs):
        if self.fail:
            raise RuntimeError("s3 down")
        self.puts.append(kwargs)

    def generate_presigned_url(self, op, Params, ExpiresIn):
        if self.fail:
            raise RuntimeError("s3 down")
        self.presigns.append((op, Params, ExpiresIn))
        return f"https://signed/{Params['Key']}?exp={ExpiresIn}"

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        outer = self

        class Paginator:
            def paginate(self, Bucket, Prefix):
                outer.list_calls += 1
                if outer.fail:
                    raise RuntimeError("s3 down")
                # Two pages, to prove pagination is consumed.
                keys = outer.barcode_keys
                half = len(keys) // 2
                yield {"Contents": [{"Key": k} for k in keys[:half]]}
                yield {"Contents": [{"Key": k} for k in keys[half:]]}

        return Paginator()


@pytest.fixture(autouse=True)
def reset_state(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_s3_client", None)
    monkeypatch.setattr(storage, "_barcode_cics", None)
    monkeypatch.setattr(storage, "_barcode_cics_fetched_at", 0.0)
    monkeypatch.setattr(storage, "CROPS_DIR", tmp_path / "crops")
    monkeypatch.setattr(storage, "BARCODES_DIR", tmp_path / "barcodes")
    monkeypatch.delenv("IMAGES_BUCKET", raising=False)
    monkeypatch.delenv("PRESIGNED_URL_TTL", raising=False)


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3(
        barcode_keys=[
            "barcodes/",
            "barcodes/111.png",
            "barcodes/222.png",
            "barcodes/333.png",
        ]
    )
    monkeypatch.setenv("IMAGES_BUCKET", "theia-images")
    monkeypatch.setattr(storage, "_get_s3", lambda: fake)
    return fake


# --- S3 mode ---


def test_s3_save_crop_puts_object_and_returns_presigned_url(s3):
    url = storage.save_crop("crop_1.jpg", b"jpegbytes")
    assert s3.puts == [
        {
            "Bucket": "theia-images",
            "Key": "crops/crop_1.jpg",
            "Body": b"jpegbytes",
            "ContentType": "image/jpeg",
        }
    ]
    assert url == "https://signed/crops/crop_1.jpg?exp=3600"
    assert s3.presigns[0][0] == "get_object"
    assert s3.presigns[0][1] == {"Bucket": "theia-images", "Key": "crops/crop_1.jpg"}


def test_s3_presigned_ttl_is_configurable(s3, monkeypatch):
    monkeypatch.setenv("PRESIGNED_URL_TTL", "120")
    assert storage.save_crop("c.jpg", b"x").endswith("exp=120")


def test_s3_save_crop_does_not_touch_local_disk(s3, tmp_path):
    storage.save_crop("c.jpg", b"x")
    assert not (tmp_path / "crops").exists()


def test_s3_barcode_url_only_for_cics_present(s3):
    assert storage.barcode_url("222") == "https://signed/barcodes/222.png?exp=3600"
    assert storage.barcode_url("999") is None
    # A CIC from the second page is found too (pagination consumed).
    assert storage.barcode_url("333") is not None


def test_s3_barcode_set_is_cached(s3):
    storage.barcode_url("111")
    storage.barcode_url("222")
    storage.barcode_url("999")
    assert s3.list_calls == 1


def test_s3_barcode_cache_expires(s3, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(storage.time, "monotonic", lambda: now[0])
    storage.barcode_url("111")
    now[0] += storage.BARCODE_CACHE_TTL - 1
    storage.barcode_url("111")
    assert s3.list_calls == 1
    now[0] += 2
    storage.barcode_url("111")
    assert s3.list_calls == 2


def test_s3_upload_error_returns_none_and_logs(s3, caplog):
    s3.fail = True
    assert storage.save_crop("c.jpg", b"x") is None
    assert "crop upload failed" in caplog.text


def test_s3_barcode_error_returns_none_and_is_not_cached(s3, caplog):
    s3.fail = True
    assert storage.barcode_url("111") is None
    assert "barcode lookup failed" in caplog.text
    s3.fail = False
    assert storage.barcode_url("111") is not None


def test_s3_client_uses_regional_sigv4_virtual_addressing(monkeypatch):
    captured = {}

    def fake_client(service, region_name, config):
        captured.update(service=service, region=region_name, config=config)
        return object()

    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(storage.boto3, "client", fake_client)
    storage._get_s3()
    assert captured["service"] == "s3"
    assert captured["region"] == "us-west-2"
    assert captured["config"].signature_version == "s3v4"
    assert captured["config"].s3 == {"addressing_style": "virtual"}


# --- local mode ---


def test_local_save_crop_writes_file_and_returns_static_url(tmp_path):
    url = storage.save_crop("crop_1.jpg", b"abc")
    assert url == "/static/crops/crop_1.jpg"
    assert (tmp_path / "crops" / "crop_1.jpg").read_bytes() == b"abc"


def test_local_prunes_oldest_crops(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MAX_CROP_IMAGES", 3)
    crops = tmp_path / "crops"
    crops.mkdir()
    for n in ("crop_0001.jpg", "crop_0002.jpg", "crop_0003.jpg"):
        (crops / n).write_bytes(b"old")
    storage.save_crop("crop_0004.jpg", b"new")
    assert sorted(p.name for p in crops.glob("crop_*.jpg")) == [
        "crop_0002.jpg",
        "crop_0003.jpg",
        "crop_0004.jpg",
    ]


def test_local_barcode_url_only_when_file_exists(tmp_path):
    (tmp_path / "barcodes").mkdir()
    (tmp_path / "barcodes" / "111.png").write_bytes(b"png")
    assert storage.barcode_url("111") == "/static/barcodes/111.png"
    assert storage.barcode_url("222") is None
