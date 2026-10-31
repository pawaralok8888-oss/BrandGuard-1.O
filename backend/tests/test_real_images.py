from pathlib import Path

from app.services.image_validator import measure_text_contrast

IMAGE = Path(__file__).resolve().parents[2] / "test_data" / "images" / "low_contrast_ad.png"


def test_low_contrast_ad_fails_wcag_aa():
    result = measure_text_contrast(str(IMAGE))
    assert result["status"] == "fail"
    assert result["ratio"] < 2.0