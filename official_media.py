"""Official Free Fire media retrieval and local WebP rendering.

Developer: refatbd (https://github.com/refatbd)

The module never accepts an arbitrary remote URL. It only builds numeric item
paths on an allowlisted Free Fire/Garena-related CDN and converts the official
ASTC textures to normal WebP images for browsers.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple
from urllib.parse import urlparse

import httpx
from cachetools import TTLCache
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

try:  # Optional at import time so the site still starts with a safe fallback.
    import texture2ddecoder  # type: ignore
except ImportError:  # pragma: no cover - exercised on environments without the wheel
    texture2ddecoder = None

LOGGER = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASTC_MAGIC = b"\x13\xAB\xA1\x5C"
ASTC_HEADER_SIZE = 16
MAX_ASSET_BYTES = 8 * 1024 * 1024
MAX_TEXTURE_DIMENSION = 4096
ITEM_ID_RE = re.compile(r"^[0-9]{6,14}$")
UID_RE = re.compile(r"^[0-9]{5,20}$")

# Keep the network policy intentionally narrow. Additional bases can only be
# selected from this allowlist through FF_OFFICIAL_ASSET_BASES.
KNOWN_OFFICIAL_ASSET_BASES = (
    "https://dl-tata.freefireind.in/live/ABHotUpdates/IconCDN/android",
    "https://dl.tata.freefiremobile.com/live/ABHotUpdates/IconCDN/android",
)
DEFAULT_OFFICIAL_ASSET_BASES = (KNOWN_OFFICIAL_ASSET_BASES[0],)
ALLOWED_ASSET_HOSTS = frozenset(
    urlparse(base).hostname for base in KNOWN_OFFICIAL_ASSET_BASES if urlparse(base).hostname
)

ASSET_CACHE_TTL = int(os.getenv("FF_ASSET_CACHE_TTL", "21600"))
RENDER_CACHE_TTL = int(os.getenv("FF_RENDER_CACHE_TTL", "300"))
HTTP_TIMEOUT = float(os.getenv("FF_ASSET_TIMEOUT", "5"))

_asset_cache: TTLCache = TTLCache(maxsize=512, ttl=ASSET_CACHE_TTL)
_render_cache: TTLCache = TTLCache(maxsize=256, ttl=RENDER_CACHE_TTL)
_cache_lock = threading.RLock()


class MediaError(RuntimeError):
    """Base exception for official media processing failures."""


class InvalidAssetError(MediaError):
    """Raised when an asset is malformed, oversized, or fails validation."""


@dataclass(frozen=True)
class ASTCHeader:
    block_width: int
    block_height: int
    block_depth: int
    width: int
    height: int
    depth: int


@dataclass(frozen=True)
class RenderedMedia:
    data: bytes
    source: str
    official_banner: bool = False
    official_avatar: bool = False


def validate_uid(uid: Any) -> str:
    value = str(uid or "").strip()
    if not UID_RE.fullmatch(value):
        raise ValueError("UID must contain 5 to 20 digits.")
    return value


def validate_item_id(item_id: Any) -> str:
    value = str(item_id or "").strip()
    if not ITEM_ID_RE.fullmatch(value):
        raise ValueError("Free Fire item ID must contain only digits.")
    return value


def _read_u24_le(raw: bytes) -> int:
    if len(raw) != 3:
        raise InvalidAssetError("Invalid ASTC 24-bit field.")
    return raw[0] | (raw[1] << 8) | (raw[2] << 16)


def parse_astc_header(data: bytes) -> ASTCHeader:
    if len(data) < ASTC_HEADER_SIZE:
        raise InvalidAssetError("ASTC asset is shorter than its header.")
    if data[:4] != ASTC_MAGIC:
        raise InvalidAssetError("Asset does not contain a valid ASTC header.")

    header = ASTCHeader(
        block_width=data[4],
        block_height=data[5],
        block_depth=data[6],
        width=_read_u24_le(data[7:10]),
        height=_read_u24_le(data[10:13]),
        depth=_read_u24_le(data[13:16]),
    )

    if not (1 <= header.block_width <= 12 and 1 <= header.block_height <= 12):
        raise InvalidAssetError("Unsupported ASTC block size.")
    if header.block_depth != 1 or header.depth != 1:
        raise InvalidAssetError("Only 2D ASTC textures are supported.")
    if not (1 <= header.width <= MAX_TEXTURE_DIMENSION):
        raise InvalidAssetError("ASTC texture width is outside the safety limit.")
    if not (1 <= header.height <= MAX_TEXTURE_DIMENSION):
        raise InvalidAssetError("ASTC texture height is outside the safety limit.")
    return header


def decode_astc_image(data: bytes) -> Image.Image:
    if texture2ddecoder is None:
        raise MediaError(
            "texture2ddecoder is not installed; install project requirements to decode official assets."
        )

    header = parse_astc_header(data)
    compressed = data[ASTC_HEADER_SIZE:]
    if not compressed:
        raise InvalidAssetError("ASTC texture payload is empty.")

    try:
        decoded = texture2ddecoder.decode_astc(
            compressed,
            header.width,
            header.height,
            header.block_width,
            header.block_height,
        )
        expected_length = header.width * header.height * 4
        if len(decoded) != expected_length:
            raise InvalidAssetError("Decoded ASTC output has an unexpected length.")
        img = Image.frombytes(
            "RGBA",
            (header.width, header.height),
            decoded,
            "raw",
            "BGRA",
        )
        return img.transpose(Image.ROTATE_180)
    except MediaError:
        raise
    except Exception as exc:  # Native decoder errors should not break the API.
        raise InvalidAssetError(f"Could not decode ASTC texture: {exc}") from exc


def _configured_asset_bases() -> Tuple[str, ...]:
    requested = os.getenv("FF_OFFICIAL_ASSET_BASES", "").strip()
    if not requested:
        return DEFAULT_OFFICIAL_ASSET_BASES

    accepted = []
    for raw in requested.split(","):
        candidate = raw.strip().rstrip("/")
        parsed = urlparse(candidate)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_ASSET_HOSTS:
            LOGGER.warning("Ignoring non-allowlisted Free Fire asset base: %s", candidate)
            continue
        accepted.append(candidate)
    return tuple(accepted) or DEFAULT_OFFICIAL_ASSET_BASES


def build_official_asset_urls(item_id: Any) -> Tuple[str, ...]:
    safe_id = validate_item_id(item_id)
    return tuple(f"{base}/{safe_id}_rgb.astc" for base in _configured_asset_bases())


def _download_official_asset(item_id: Any) -> Tuple[bytes, str]:
    safe_id = validate_item_id(item_id)
    with _cache_lock:
        cached = _asset_cache.get(safe_id)
    if cached is not None:
        return cached

    last_error: Optional[Exception] = None
    headers = {
        "Accept": "application/octet-stream,*/*;q=0.8",
        "User-Agent": "FreeFireInfoSite/official-media",
    }

    for url in build_official_asset_urls(safe_id):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_ASSET_HOSTS:
            continue
        try:
            chunks = []
            received = 0
            with httpx.Client(
                timeout=HTTP_TIMEOUT,
                follow_redirects=False,
                headers=headers,
            ) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    declared_size = int(response.headers.get("content-length", "0") or 0)
                    if declared_size > MAX_ASSET_BYTES:
                        raise InvalidAssetError("Official asset exceeds the configured size limit.")
                    for chunk in response.iter_bytes():
                        received += len(chunk)
                        if received > MAX_ASSET_BYTES:
                            raise InvalidAssetError("Official asset exceeds the configured size limit.")
                        chunks.append(chunk)
            raw = b"".join(chunks)
            parse_astc_header(raw)
            result = (raw, url)
            with _cache_lock:
                _asset_cache[safe_id] = result
            return result
        except (httpx.HTTPError, ValueError, MediaError) as exc:
            last_error = exc
            LOGGER.info("Official Free Fire asset %s was unavailable at %s: %s", safe_id, url, exc)

    raise MediaError(f"Official Free Fire asset {safe_id} is unavailable.") from last_error


def fetch_official_item_image(item_id: Any) -> Tuple[Image.Image, str]:
    raw, url = _download_official_asset(item_id)
    return decode_astc_image(raw), url


def _theme_colors(seed_value: Any) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    digest = hashlib.sha256(str(seed_value).encode("utf-8", "replace")).digest()
    palettes = (
        ((88, 19, 55), (30, 27, 75)),
        ((120, 53, 15), (69, 26, 3)),
        ((76, 29, 149), (46, 16, 101)),
        ((12, 74, 110), (8, 47, 73)),
        ((6, 78, 59), (2, 44, 34)),
    )
    return palettes[digest[0] % len(palettes)]


def _gradient_background(width: int, height: int, seed_value: Any) -> Image.Image:
    first, second = _theme_colors(seed_value)
    image = Image.new("RGB", (width, height), first)
    pixels = image.load()
    for y in range(height):
        y_ratio = y / max(height - 1, 1)
        for x in range(width):
            ratio = min(1.0, (x / max(width - 1, 1)) * 0.82 + y_ratio * 0.18)
            pixels[x, y] = tuple(
                int(first[channel] * (1 - ratio) + second[channel] * ratio)
                for channel in range(3)
            )
    return image.convert("RGBA")


def _cover(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGBA"), size, method=Image.Resampling.LANCZOS)


def _contain(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    result = Image.new("RGBA", size, (0, 0, 0, 0))
    copy = image.convert("RGBA")
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - copy.width) // 2
    y = (size[1] - copy.height) // 2
    result.alpha_composite(copy, (x, y))
    return result


def _font_has_glyph(f: ImageFont.ImageFont, char: str) -> bool:
    try:
        mask = f.getmask(char)
        if not mask or mask.size[0] == 0 or mask.size[1] == 0:
            return False
        missing = f.getmask("\uFFFF")
        if mask.size == missing.size and bytes(mask) == bytes(missing):
            return False
        return True
    except Exception:
        return False


def _load_font_stack(size: int) -> Tuple[ImageFont.ImageFont, ...]:
    fonts_dir = os.path.join(BASE_DIR, "fonts")
    paths = (
        os.path.join(fonts_dir, "NotoSans-Bold.ttf"),
        os.path.join(fonts_dir, "NotoSansCherokee-Bold.ttf"),
        os.path.join(fonts_dir, "NotoSansSC-Bold.ttf"),
        os.path.join(fonts_dir, "NotoSansMath-Regular.ttf"),
        os.path.join(fonts_dir, "NotoSansSymbols-Regular.ttf"),
        os.path.join(fonts_dir, "NotoSansSymbols2-Regular.ttf"),
        "C:/Windows/Fonts/himalaya.ttf",
        "C:/Windows/Fonts/seguisym.ttf",
        "C:/Windows/Fonts/seguihis.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    )
    loaded = []
    for path in paths:
        if os.path.exists(path):
            try:
                loaded.append(ImageFont.truetype(path, size=size))
            except Exception:
                continue
    if not loaded:
        try:
            loaded.append(ImageFont.load_default(size=size))
        except Exception:
            loaded.append(ImageFont.load_default())
    return tuple(loaded)


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    stack = _load_font_stack(size)
    return stack[0]


def _draw_text_safe(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: Any,
    *,
    font: Any = None,
    size: int = 36,
    fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_width: int = 2,
    stroke_fill: Tuple[int, int, int, int] = (0, 0, 0, 220),
) -> None:
    value = str(text or "")
    if not value:
        return
    
    current_size = size
    if font and hasattr(font, "size"):
        current_size = font.size
        
    font_stack = _load_font_stack(current_size)
    cur_x, cur_y = xy
    for char in value:
        best_font = font_stack[0]
        for f in font_stack:
            if _font_has_glyph(f, char):
                best_font = f
                break
        try:
            draw.text(
                (cur_x, cur_y),
                char,
                font=best_font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
            bbox = draw.textbbox((0, 0), char, font=best_font, stroke_width=stroke_width)
            w = max(bbox[2] - bbox[0], int(best_font.size * 0.38))
            cur_x += w
        except Exception:
            continue


def _player_fields(player_data: Mapping[str, Any]) -> Tuple[Mapping[str, Any], Mapping[str, Any]]:
    basic = player_data.get("basicInfo") or {}
    clan = player_data.get("clanBasicInfo") or {}
    if not isinstance(basic, Mapping):
        basic = {}
    if not isinstance(clan, Mapping):
        clan = {}
    return basic, clan


def _load_player_assets(basic: Mapping[str, Any]) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    item_jobs = {
        "banner": basic.get("bannerId"),
        "avatar": basic.get("headPic"),
    }
    loaded: dict[str, Optional[Image.Image]] = {"banner": None, "avatar": None}
    valid_jobs = {name: item_id for name, item_id in item_jobs.items() if item_id}
    if not valid_jobs:
        return None, None

    # Download the two independent textures in parallel to keep serverless
    # response time close to one CDN timeout rather than two consecutive ones.
    with ThreadPoolExecutor(max_workers=len(valid_jobs)) as executor:
        futures = {
            executor.submit(fetch_official_item_image, item_id): name
            for name, item_id in valid_jobs.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                image, _ = future.result()
                loaded[name] = image
            except (ValueError, MediaError) as exc:
                LOGGER.info("Using generated %s fallback: %s", name, exc)
            except Exception as exc:
                LOGGER.warning("Unexpected %s asset failure: %s", name, exc)

    return loaded["banner"], loaded["avatar"]


def _avatar_fallback(size: int, seed_value: Any) -> Image.Image:
    first, second = _theme_colors(seed_value)
    avatar = _gradient_background(size, size, seed_value)
    draw = ImageDraw.Draw(avatar, "RGBA")
    center_x = size // 2
    head_radius = int(size * 0.18)
    draw.ellipse(
        (center_x - head_radius, int(size * 0.19), center_x + head_radius, int(size * 0.55)),
        fill=(*second, 255),
    )
    draw.ellipse(
        (int(size * 0.21), int(size * 0.52), int(size * 0.79), int(size * 1.08)),
        fill=(*first, 255),
    )
    return avatar


def render_player_avatar(player_data: Mapping[str, Any], size: int = 512) -> RenderedMedia:
    basic, _ = _player_fields(player_data)
    size = max(128, min(int(size), 1024))
    item_id = basic.get("headPic")
    key = ("avatar", str(basic.get("accountId", "")), str(item_id), size)
    with _cache_lock:
        cached = _render_cache.get(key)
    if cached is not None:
        return cached

    official = False
    image: Optional[Image.Image] = None
    if item_id:
        try:
            image, _ = fetch_official_item_image(item_id)
            official = True
        except (ValueError, MediaError) as exc:
            LOGGER.info("Avatar item %s could not be rendered: %s", item_id, exc)

    if image is None:
        image = _avatar_fallback(size, item_id or basic.get("accountId", "0"))
    else:
        image = _cover(image, (size, size))

    canvas = Image.new("RGBA", (size, size), (15, 23, 42, 255))
    canvas.alpha_composite(image, (0, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")
    border = max(4, size // 80)
    draw.rounded_rectangle(
        (border // 2, border // 2, size - border // 2 - 1, size - border // 2 - 1),
        radius=max(12, size // 24),
        outline=(245, 158, 11, 255),
        width=border,
    )

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="WEBP", quality=92, method=6)
    result = RenderedMedia(
        data=output.getvalue(),
        source="official-free-fire-cdn" if official else "local-fallback",
        official_avatar=official,
    )
    with _cache_lock:
        _render_cache[key] = result
    return result


def render_player_banner(
    player_data: Mapping[str, Any],
    width: int = 1000,
    height: int = 250,
) -> RenderedMedia:
    basic, clan = _player_fields(player_data)
    width = max(800, min(int(width), 1600))
    height = max(200, min(int(height), 400))

    key = (
        "banner",
        str(basic.get("accountId", "")),
        str(basic.get("bannerId", "")),
        str(basic.get("headPic", "")),
        str(basic.get("nickname", "")),
        str(clan.get("clanName", "")),
        width,
        height,
    )
    with _cache_lock:
        cached = _render_cache.get(key)
    if cached is not None:
        return cached

    official_banner = False
    official_avatar = False
    banner_asset, avatar_asset = _load_player_assets(basic)

    if banner_asset is not None:
        official_banner = True
        bg = _cover(banner_asset, (width, height))
        bg = ImageEnhance.Sharpness(bg).enhance(1.8)
        bg = ImageEnhance.Contrast(bg).enhance(1.12)
        canvas = bg
    else:
        canvas = _gradient_background(width, height, basic.get("bannerId") or basic.get("accountId"))

    # Subtle contrast shadow overlay on left side for text legibility
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    for x in range(width):
        if x < int(width * 0.65):
            alpha = int(140 * (1.0 - (x / (width * 0.65))))
            overlay_draw.line([(x, 0), (x, height)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    # Avatar Square on Left (Matching Image 2)
    avatar_size = int(height * 0.72)
    avatar_x = int(height * 0.12)
    avatar_y = (height - avatar_size) // 2

    if avatar_asset is not None:
        official_avatar = True
        avatar = _cover(avatar_asset, (avatar_size, avatar_size))
    else:
        avatar = _avatar_fallback(
            avatar_size,
            basic.get("headPic") or basic.get("accountId") or "0",
        )

    # Composite avatar with solid white border (Image 2 style)
    canvas.paste(avatar, (avatar_x, avatar_y))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle(
        [avatar_x, avatar_y, avatar_x + avatar_size - 1, avatar_y + avatar_size - 1],
        outline=(255, 255, 255, 255),
        width=3,
    )

    # Typography & Text Layout (Matching Image 2)
    text_x = avatar_x + avatar_size + 28
    nickname = basic.get("nickname") or "Unknown Player"
    raw_guild = clan.get("clanName") or ""
    # Sanitize Hangul Filler space \u3164 & Braille Blank \u2800 for clean spacing
    guild_name = raw_guild.replace("\u3164", "  ").replace("\u2800", "  ") if raw_guild else ""
    level = basic.get("level") or "--"

    title_font = _load_font(max(38, int(height * 0.17)), bold=True)
    guild_font = _load_font(max(30, int(height * 0.13)), bold=True)
    level_font = _load_font(max(34, int(height * 0.15)), bold=True)

    # Top line: Nickname
    _draw_text_safe(
        draw,
        (text_x, int(height * 0.16)),
        nickname,
        font=title_font,
        fill=(255, 255, 255, 255),
        stroke_width=2,
        stroke_fill=(0, 0, 0, 220),
    )

    # Middle line: Guild Name
    if guild_name:
        _draw_text_safe(
            draw,
            (text_x, int(height * 0.52)),
            guild_name,
            font=guild_font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 220),
        )

    # Bottom Right line: Level Text (e.g. Lvl. 67)
    level_label = f"Lvl. {level}"
    _draw_text_safe(
        draw,
        (width - int(height * 0.70), int(height * 0.64)),
        level_label,
        font=level_font,
        fill=(255, 255, 255, 255),
        stroke_width=2,
        stroke_fill=(0, 0, 0, 220),
    )

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="WEBP", quality=91, method=6)
    if official_banner and official_avatar:
        source = "official-free-fire-cdn"
    elif official_banner or official_avatar:
        source = "official-free-fire-cdn+local-fallback"
    else:
        source = "local-fallback"

    result = RenderedMedia(
        data=output.getvalue(),
        source=source,
        official_banner=official_banner,
        official_avatar=official_avatar,
    )
    with _cache_lock:
        _render_cache[key] = result
    return result
