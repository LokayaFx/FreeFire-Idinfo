# Dynamic Player Media Implementation

## Data flow

1. `/player-info` retrieves the player's `basicInfo` from the existing account API.
2. `bannerId` and `headPic` are placed into a versioned local media URL.
3. `/api/banner/banner_<uid>.webp` reuses the cached account response.
4. `official_media.py` validates the numeric item IDs and constructs only
   allowlisted Free Fire CDN URLs.
5. The ASTC header is validated before native decoding.
6. Pillow composites the equipped banner, avatar, nickname, UID, region, guild,
   and level into a local WebP image.
7. The frontend fetches the local WebP, reads its media-source header, and shows
   whether official assets or a fallback were used.

## Failure behavior

- Banner texture missing: generated background + real avatar when available.
- Avatar texture missing: real banner + generated avatar when available.
- Both unavailable: fully local deterministic player card.
- Banner endpoint error: the browser's original canvas renderer is used.
- Decoder package missing: server remains available and uses local fallback.

## Security controls

- UID: 5–20 digits.
- Item ID: 6–14 digits.
- HTTPS-only asset bases.
- Fixed hostname allowlist.
- Redirects disabled.
- 8 MiB response limit.
- Maximum 4096×4096 decoded texture dimensions.
- 2D ASTC textures only.
- No arbitrary URL query parameter or remote proxy endpoint.

---

**Developer:** [refatbd](https://github.com/refatbd)
