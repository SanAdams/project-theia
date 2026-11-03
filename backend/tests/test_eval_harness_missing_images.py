"""The eval photos are gitignored, so a fresh clone doesn't have them. The harness
must treat a missing photo as "skipped", not crash, so the text-only cases still run."""

from eval import harness as h


def test_missing_image_is_skipped_not_fatal():
    dataset = {
        "text_cases": [{"ocr": "SOME LABEL TEXT", "expected": []}],
        "negative_cases": [{"file": "images/does-not-exist-neg.jpg"}],
        "image_cases": [{"file": "images/does-not-exist.jpg", "expected": []}],
    }
    cases, skipped = h.build_cases(dataset, allow_aws=False)
    assert sorted(skipped) == [
        "images/does-not-exist-neg.jpg",
        "images/does-not-exist.jpg",
    ]
    assert [c.name for c in cases] == ["text:SOME LABEL TEXT"]
