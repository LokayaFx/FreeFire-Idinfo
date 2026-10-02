import io

import pytest
from PIL import Image

import official_media


def make_astc_header(width=256, height=128, block_width=4, block_height=4):
    return (
        official_media.ASTC_MAGIC
        + bytes((block_width, block_height, 1))
        + width.to_bytes(3, "little")
        + height.to_bytes(3, "little")
        + (1).to_bytes(3, "little")
    )


def sample_player():
    return {
        "basicInfo": {
            "accountId": "4422076728",
            "nickname": "Test Player",
            "region": "BD",
            "level": 71,
            "bannerId": 901000116,
            "headPic": 902000094,
        },
        "clanBasicInfo": {"clanName": "TEST GUILD"},
    }


def test_parse_astc_header():
    data = make_astc_header() + b"compressed"
    header = official_media.parse_astc_header(data)
    assert header.width == 256
    assert header.height == 128
    assert header.block_width == 4
    assert header.block_height == 4


def test_parse_astc_rejects_invalid_magic():
    with pytest.raises(official_media.InvalidAssetError):
        official_media.parse_astc_header(b"bad!" + b"\x00" * 20)


def test_uid_and_item_validation():
    assert official_media.validate_uid("4422076728") == "4422076728"
    assert official_media.validate_item_id(902000094) == "902000094"
    with pytest.raises(ValueError):
        official_media.validate_uid("4422<script>")
    with pytest.raises(ValueError):
        official_media.validate_item_id("https://example.com/a")


def test_asset_urls_are_https_and_allowlisted():
    urls = official_media.build_official_asset_urls(902000094)
    assert urls
    assert all(url.startswith("https://") for url in urls)
    assert all("902000094_rgb.astc" in url for url in urls)
    assert all(
        official_media.urlparse(url).hostname in official_media.ALLOWED_ASSET_HOSTS
        for url in urls
    )


def test_banner_fallback_is_valid_webp(monkeypatch):
    monkeypatch.setattr(official_media, "_load_player_assets", lambda basic: (None, None))
    rendered = official_media.render_player_banner(sample_player(), width=800, height=240)
    assert rendered.source == "local-fallback"
    assert not rendered.official_banner
    assert not rendered.official_avatar
    with Image.open(io.BytesIO(rendered.data)) as image:
        assert image.format == "WEBP"
        assert image.size == (800, 240)


def test_avatar_fallback_is_valid_webp(monkeypatch):
    def unavailable(item_id):
        raise official_media.MediaError("offline")

    monkeypatch.setattr(official_media, "fetch_official_item_image", unavailable)
    rendered = official_media.render_player_avatar(sample_player(), size=256)
    assert rendered.source == "local-fallback"
    with Image.open(io.BytesIO(rendered.data)) as image:
        assert image.format == "WEBP"
        assert image.size == (256, 256)
