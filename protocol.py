"""Versioned wire behavior; see docs/OB_UPDATE_GUIDE.md before changing it."""
import os
import time
from urllib.parse import urlsplit

from google.protobuf.message import DecodeError
from proto import FreeFire_pb2

PROFILES = {
    'OB54': {'login_prefix': 0, 'timestamp_header': False},
    'OB55': {'login_prefix': 64, 'timestamp_header': True},
}
RELEASE_VERSION = os.environ.get('FREEFIRE_OB_VERSION', 'OB55').upper()
if RELEASE_VERSION not in PROFILES:
    raise RuntimeError('Unsupported FREEFIRE_OB_VERSION; supported: OB54, OB55')
LOGIN_URL = 'https://loginbp.ggblueshark.com/MajorLogin'
PLAYER_HOSTS = frozenset({
    'clientbp.ppmainecoonghj.com', 'clientbp.ggpolarbear.com',
    'client.ind.freefiremobile.com', 'client.us.freefiremobile.com',
})
USER_AGENT = 'Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)'


class UpstreamError(RuntimeError):
    """Safe public message only: never include response bodies or credentials."""
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code = code
        self.status = status


def binary_headers(version=RELEASE_VERSION):
    headers = {'User-Agent': USER_AGENT, 'Content-Type': 'application/octet-stream',
               'X-Unity-Version': '2018.4.11f1', 'X-GA': 'v1 1',
               'ReleaseVersion': version}
    if PROFILES[version]['timestamp_header']:
        headers['X-GA-SV'] = str(int(time.time()))
    return headers


def check_status(response, stage):
    if response.status_code != 200:
        raise UpstreamError('UPSTREAM_HTTP_ERROR',
                            f'{stage} returned HTTP {response.status_code}. Please try again later.')


def validate_server(url):
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == 'https' and parsed.hostname in PLAYER_HOSTS
                 and parsed.port in (None, 443) and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment
                 and parsed.path in ('', '/'))
    except ValueError:
        valid = False
    if not valid:
        raise UpstreamError('INVALID_LOGIN_SERVER', 'Login returned an unsupported player server.')
    return url.rstrip('/')


def decode_login(body, version=RELEASE_VERSION):
    # OB55 login framing only. Player responses are unprefixed Protobuf.
    offset = PROFILES[version]['login_prefix']
    if len(body) <= offset or len(body) > 4 * 1024 * 1024:
        raise UpstreamError('INVALID_LOGIN_RESPONSE', 'Login response has invalid framing.')
    result = FreeFire_pb2.LoginRes()
    try:
        result.ParseFromString(body[offset:])
    except DecodeError as exc:
        raise UpstreamError('INVALID_LOGIN_RESPONSE', 'Login protocol changed or returned malformed data.') from exc
    if not result.token or not result.lock_region or not result.server_url:
        if result.HasField('queue_info'):
            # Field 13 is only known to mean queue_info in the legacy schema.
            # OB55 BR/VN replies contain epoch-like field-3 values, not credible
            # wait durations. Do not infer queue/ban semantics from this parser.
            if version == 'OB54':
                raise UpstreamError('LOGIN_QUEUE', 'Login gateway returned a queue response. Please try again later.', 503)
            raise UpstreamError('UNRECOGNIZED_LOGIN_RESPONSE',
                                'Login returned no usable token. The response meaning is unverified; the service account or protocol needs investigation.', 502)
        raise UpstreamError('INCOMPLETE_LOGIN', 'Login did not return a usable token and server.')
    validate_server(result.server_url)
    return result
