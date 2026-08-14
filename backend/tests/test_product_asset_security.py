import io
import re

import pytest
from PIL import Image, PngImagePlugin

from app.services import catalog_service, product_asset_service


def _png_bytes(*, size: tuple[int, int] = (32, 24), metadata: bool = False) -> bytes:
    image = Image.new("RGBA", size, (20, 40, 60, 180))
    output = io.BytesIO()
    pnginfo = None
    if metadata:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("private-note", "must-not-survive")
    image.save(output, format="PNG", pnginfo=pnginfo)
    return output.getvalue()


def test_uploaded_image_is_decoded_reencoded_and_metadata_free():
    encoded = product_asset_service.sanitize_product_image(
        _png_bytes(metadata=True)
    )

    assert b"must-not-survive" not in encoded
    with Image.open(io.BytesIO(encoded)) as image:
        assert image.format == "WEBP"
        assert image.size == (32, 24)
        assert "private-note" not in image.info


@pytest.mark.parametrize("payload", [b"", b"not-an-image", b"\x89PNG\r\n\x1a\n"])
def test_invalid_image_payload_is_rejected(payload):
    with pytest.raises(product_asset_service.ProductAssetError):
        product_asset_service.sanitize_product_image(payload)


def test_decoded_dimension_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(product_asset_service, "MAX_IMAGE_WIDTH", 16)
    with pytest.raises(product_asset_service.ProductAssetError, match="image_dimensions"):
        product_asset_service.sanitize_product_image(_png_bytes(size=(17, 1)))


def test_store_uses_stable_content_hash_and_never_product_name(monkeypatch, tmp_path):
    monkeypatch.setattr(product_asset_service.settings, "ASSET_ROOT", str(tmp_path))
    first = product_asset_service.store_product_image(_png_bytes())
    second = product_asset_service.store_product_image(_png_bytes())

    assert first.created is True
    assert second.created is False
    assert first.url == second.url
    assert first.path == second.path
    assert re.fullmatch(r"[0-9a-f]{64}\.webp", first.path.name)
    assert first.path.read_bytes()


def test_public_catalog_omits_legacy_external_asset_urls():
    assert catalog_service.public_asset_url("https://tracker.invalid/logo.png") is None
    assert catalog_service.public_asset_url("/static/product-assets/test.webp") == (
        "/static/product-assets/test.webp"
    )


def test_owned_asset_path_rejects_traversal_and_legacy_names(monkeypatch, tmp_path):
    monkeypatch.setattr(product_asset_service.settings, "ASSET_ROOT", str(tmp_path))
    assert product_asset_service.owned_product_asset_path(
        "/static/product-assets/../../private.key"
    ) is None
    assert product_asset_service.owned_product_asset_path(
        "/static/product-assets/product-name.png"
    ) is None
