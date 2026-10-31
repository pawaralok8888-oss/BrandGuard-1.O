import random

from PIL import Image

from app.services.image_validator import ImageValidator, contrast_ratio


# ---------- Contrast ----------

def test_black_on_white_is_maximum_contrast():
    assert round(contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0


def test_light_grey_on_white_fails_wcag_aa():
    result = ImageValidator().check_text_contrast("#CCCCCC", "#FFFFFF")
    assert result[0]["status"] == "fail"
    assert result[0]["severity"] == "critical"


def test_brand_green_on_white_passes_wcag_aa():
    result = ImageValidator().check_text_contrast("#2D5F3F", "#FFFFFF")
    assert result[0]["status"] == "pass"


# ---------- Alt text ----------

def test_missing_alt_text_is_detected():
    findings = ImageValidator().check_alt_text_missing('<img src="test.png">')
    assert findings[0]["type"] == "missing_alt_text"


def test_image_with_alt_text_passes():
    findings = ImageValidator().check_alt_text_missing('<img src="a.png" alt="Product bottle">')
    assert findings == []


# ---------- Logo match ----------

def test_same_logo_is_approved(tmp_path):
    logo = tmp_path / "logo.png"
    Image.new("RGB", (120, 120), (45, 95, 63)).save(logo)
    validator = ImageValidator(approved_logo_path=str(logo))
    assert validator.check_logo_match(str(logo))[0]["status"] == "approved"


def _noise_image(path, seed):
    rng = random.Random(seed)  # same seed always gives the same image
    img = Image.new("RGB", (160, 160))
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                 for _ in range(160 * 160)])
    img.save(path)


def test_different_logo_is_flagged(tmp_path):
    approved = tmp_path / "approved.png"
    other = tmp_path / "other.png"
    _noise_image(approved, seed=1)
    _noise_image(other, seed=2)

    validator = ImageValidator(approved_logo_path=str(approved))
    assert validator.check_logo_match(str(other))[0]["status"] == "mismatch"


# ---------- Brand colours ----------

def test_brand_coloured_image_passes(tmp_path):
    path = tmp_path / "brand.png"
    Image.new("RGB", (100, 100), (45, 95, 63)).save(path)
    result = ImageValidator().check_brand_colours(str(path))
    assert result[0]["status"] == "pass"


def test_off_brand_colour_is_flagged(tmp_path):
    path = tmp_path / "magenta.png"
    Image.new("RGB", (100, 100), (255, 0, 255)).save(path)
    result = ImageValidator().check_brand_colours(str(path))
    assert result[0]["status"] == "fail"
    assert result[0]["off_brand_colours"]