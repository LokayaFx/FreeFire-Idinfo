"""
Free Fire Info Site & API — Official Media Edition
Developer: refatbd (https://github.com/refatbd)
"""

import asyncio
import time
import httpx
import json
from collections import defaultdict
from flask import Flask, request, jsonify, render_template, Response, url_for
from flask_cors import CORS
from cachetools import TTLCache
from typing import Tuple
from proto import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
from google.protobuf import json_format, message
from google.protobuf.message import Message
from Crypto.Cipher import AES
import base64
import threading

from official_media import render_player_avatar, render_player_banner, validate_uid

# === Settings ===
MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
from protocol import (RELEASE_VERSION, LOGIN_URL, UpstreamError, binary_headers,
                      check_status, decode_login, validate_server)
RELEASEVERSION = RELEASE_VERSION
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
SUPPORTED_REGIONS = {"IND", "BR", "US", "SAC", "NA", "SG", "RU", "ID", "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EUROPE"}
REGION_ALIASES = {"EU": "EUROPE"}

import os

# === Flask App Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'), static_folder=os.path.join(BASE_DIR, 'static'))
CORS(app)
player_data_cache = TTLCache(maxsize=256, ttl=300)
player_data_cache_lock = threading.RLock()
cached_tokens = defaultdict(dict)

# === Helper Functions ===
def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(plaintext))

def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    instance = message_type()
    instance.ParseFromString(encoded_data)
    return instance

async def json_to_proto(json_data: str, proto_message: Message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

def get_account_credentials(region: str) -> str:
    from credentials import get_credentials
    return get_credentials(region)

# === Token Generation ===
async def get_access_token(account: str):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = account + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {'User-Agent': USERAGENT, 'Connection': "Keep-Alive", 'Accept-Encoding': "gzip", 'Content-Type': "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, data=payload, headers=headers)
        check_status(resp, "Guest authentication")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError('INVALID_GUEST_RESPONSE', 'Guest authentication returned invalid data.') from exc
        if not isinstance(data, dict) or not data.get('access_token') or not data.get('open_id'):
            raise UpstreamError('GUEST_AUTH_FAILED', 'Guest authentication did not return required credentials.')
        return data['access_token'], data['open_id']

async def create_jwt(region: str):
    account = get_account_credentials(region)
    token_val, open_id = await get_access_token(account)
    body = json.dumps({"open_id": open_id, "open_id_type": "4", "login_token": token_val, "orign_platform_type": "4"})
    proto_bytes = await json_to_proto(body, FreeFire_pb2.LoginReq())
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, proto_bytes)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(LOGIN_URL, content=payload, headers=binary_headers())
    check_status(resp, 'MajorLogin')
    msg = decode_login(resp.content)
    ttl = min(msg.ttl or 25200, 25200)
    cached_tokens[region] = {
        'token': f'Bearer {msg.token}', 'region': msg.lock_region,
        'server_url': validate_server(msg.server_url),
        'expires_at': time.time() + ttl,
    }

async def initialize_tokens():
    tasks = [create_jwt(r) for r in SUPPORTED_REGIONS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failed = sum(isinstance(result, Exception) for result in results)
    if failed:
        raise UpstreamError('TOKEN_REFRESH_INCOMPLETE', f'{failed} regional token refreshes failed; successful tokens remain available.', 503)

def start_token_refresher():
    def _loop():
        while True:
            time.sleep(25200)
            try:
                asyncio.run(initialize_tokens())
                print("[INFO] Regional tokens refreshed periodically.")
            except Exception as e:
                print(f"[WARN] Periodic token refresh error: {e}")

    refresher_thread = threading.Thread(target=_loop, daemon=True)
    refresher_thread.start()

async def get_token_info(region: str) -> Tuple[str,str,str]:
    info = cached_tokens.get(region)
    if info and time.time() < info['expires_at']:
        return info['token'], info['region'], info['server_url']
    await create_jwt(region)
    info = cached_tokens[region]
    if not info:
        raise RuntimeError(f"Failed to acquire token for region {region}")
    return info['token'], info['region'], info['server_url']

async def GetAccountInformation(uid, unk, region, endpoint):
    region = region.upper()
    if region not in SUPPORTED_REGIONS:
        raise ValueError(f"Unsupported region: {region}")
    payload = await json_to_proto(json.dumps({'a': uid, 'b': unk}), main_pb2.GetPlayerPersonalShow())
    data_enc = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, payload)
    token, lock, server = await get_token_info(region)
    server = validate_server(server)
    headers = {**binary_headers(), 'Authorization': token}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(server+endpoint, content=data_enc, headers=headers)
    check_status(resp, 'Player lookup')
    try:
        return json.loads(json_format.MessageToJson(decode_protobuf(resp.content, AccountPersonalShow_pb2.AccountPersonalShowInfo)))
    except message.DecodeError as exc:
        raise UpstreamError('INVALID_PLAYER_RESPONSE', 'Player response could not be decoded.') from exc



GATEWAY_REGIONS = ["BD", "SG", "IND", "BR", "VN", "ID", "TH", "TW"]

def normalize_region(region: str) -> str:
    value = str(region or "").strip().upper()
    value = REGION_ALIASES.get(value, value)
    if value not in SUPPORTED_REGIONS:
        raise ValueError(f"Unsupported region: {value or 'missing'}")
    return value


def get_player_data(uid: str, region: str = None):
    safe_uid = validate_uid(uid)

    if region:
        safe_region = normalize_region(region)
        cache_key = (safe_region, safe_uid)
        with player_data_cache_lock:
            cached_player = player_data_cache.get(cache_key)
        if cached_player is not None:
            return cached_player, safe_uid, safe_region

        player_data = asyncio.run(
            GetAccountInformation(safe_uid, "7", safe_region, "/GetPlayerPersonalShow")
        )
        basic = player_data.get("basicInfo") or {}
        if not basic.get("nickname"):
            raise ValueError(f"No player found for UID '{safe_uid}' in region {safe_region}.")
        with player_data_cache_lock:
            player_data_cache[cache_key] = player_data
        return player_data, safe_uid, safe_region
    else:
        # Check cache for any cached region entry matching safe_uid
        with player_data_cache_lock:
            for (cached_reg, cached_u), data in player_data_cache.items():
                if cached_u == safe_uid:
                    return data, safe_uid, cached_reg

        # Auto-detect region across gateway clusters concurrently
        async def _find_auto():
            async def _try_reg(reg):
                try:
                    res = await GetAccountInformation(safe_uid, "7", reg, "/GetPlayerPersonalShow")
                    basic = res.get("basicInfo") or {}
                    if basic and basic.get("nickname"):
                        det_reg = basic.get("region") or reg
                        return res, det_reg
                except Exception as exc:
                    return exc
                return None

            tasks = [_try_reg(r) for r in GATEWAY_REGIONS]
            results = await asyncio.gather(*tasks)
            for res in results:
                if isinstance(res, tuple):
                    return res
            if any(isinstance(res, Exception) for res in results):
                raise UpstreamError('LOOKUP_INCOMPLETE', 'Some login gateways are unavailable. Player lookup could not be completed; try again later or specify a region.', 503)
            return None

        result = asyncio.run(_find_auto())
        if not result:
            raise ValueError(f"Player account not found for UID '{safe_uid}'.")

        player_data, safe_region = result
        cache_key = (safe_region, safe_uid)
        with player_data_cache_lock:
            player_data_cache[cache_key] = player_data
        return player_data, safe_uid, safe_region


def media_response(rendered):
    response = Response(rendered.data, mimetype="image/webp")
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Free-Fire-Media-Source"] = rendered.source
    response.headers["X-Free-Fire-Official-Banner"] = "1" if rendered.official_banner else "0"
    response.headers["X-Free-Fire-Official-Avatar"] = "1" if rendered.official_avatar else "0"
    return response

# === Flask Routes ===
@app.route('/')
def index():
    return render_template('index.html', release_version=RELEASEVERSION)

@app.route('/player-info')
def get_account_info():
    region = request.args.get('region')
    uid = request.args.get('uid')

    if not uid:
        return jsonify({"error": "Please provide UID."}), 400

    try:
        return_data, safe_uid, safe_region = get_player_data(uid, region)
        basic = return_data.get("basicInfo") or {}
        version = f"v7-{basic.get('bannerId', '0')}-{basic.get('headPic', '0')}-{int(time.time())}"
        return_data["mediaInfo"] = {
            "bannerUrl": url_for(
                "get_player_banner", uid=safe_uid, region=safe_region, v=version
            ),
            "avatarUrl": url_for(
                "get_player_avatar", uid=safe_uid, region=safe_region, v=version
            ),
            "policy": "official-free-fire-cdn-only-with-local-fallback",
        }
        return jsonify(return_data), 200
    except UpstreamError as e:
        return jsonify({'error': str(e), 'code': e.code}), e.status
    except httpx.HTTPError:
        return jsonify({'error': 'Upstream connection failed. Please try again later.', 'code': 'UPSTREAM_CONNECTION_ERROR'}), 502
    except ValueError as e:
        return jsonify({"error": str(e), "code": "PLAYER_NOT_FOUND" if "not found" in str(e).lower() else "INVALID_INPUT"}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


@app.route('/api/banner/banner_<uid>.webp')
def get_player_banner(uid):
    region = request.args.get('region')
    try:
        player_data, _, _ = get_player_data(uid, region)
        return media_response(render_player_banner(player_data))
    except UpstreamError as e:
        return jsonify({'error': str(e), 'code': e.code}), e.status
    except httpx.HTTPError:
        return jsonify({'error': 'Upstream connection failed. Please try again later.', 'code': 'UPSTREAM_CONNECTION_ERROR'}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Banner generation failed: {str(e)}"}), 502


@app.route('/api/avatar/avatar_<uid>.webp')
def get_player_avatar(uid):
    region = request.args.get('region')
    try:
        player_data, _, _ = get_player_data(uid, region)
        return media_response(render_player_avatar(player_data))
    except UpstreamError as e:
        return jsonify({'error': str(e), 'code': e.code}), e.status
    except httpx.HTTPError:
        return jsonify({'error': 'Upstream connection failed. Please try again later.', 'code': 'UPSTREAM_CONNECTION_ERROR'}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Avatar generation failed: {str(e)}"}), 502


@app.route('/refresh', methods=['GET','POST'])
def refresh_tokens_endpoint():
    try:
        asyncio.run(initialize_tokens())
        return jsonify({'message':'Tokens refreshed for all regions.'}),200
    except UpstreamError as e:
        return jsonify({'error': str(e), 'code': e.code}), e.status
    except Exception:
        return jsonify({'error': 'Token refresh failed.', 'code': 'TOKEN_REFRESH_FAILED'}), 502

if __name__ == '__main__':
    print("[*] Pre-warming regional tokens across all Free Fire gateways...")
    try:
        asyncio.run(initialize_tokens())
        print(f"[✓] Tokens successfully initialized for {len(cached_tokens)} regions.")
    except Exception as e:
        print(f"[!] Warning during initial token warmup: {e}")

    start_token_refresher()
    print("[*] Free Fire Info Site server starting on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)


