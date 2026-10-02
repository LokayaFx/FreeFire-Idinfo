import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
import app
import protocol
from proto import FreeFire_pb2


def framed(**changes):
    values = dict(token='synthetic-token', lock_region='SG',
                  server_url='https://clientbp.ppmainecoonghj.com', ttl=28800)
    values.update(changes)
    return bytes(64) + FreeFire_pb2.LoginRes(**values).SerializeToString()


@pytest.fixture(autouse=True)
def clear_caches():
    app.cached_tokens.clear()
    app.player_data_cache.clear()
    yield
    app.cached_tokens.clear()
    app.player_data_cache.clear()


def test_versioned_timestamp(monkeypatch):
    monkeypatch.setattr(protocol.time, 'time', lambda: 1800000000)
    assert protocol.binary_headers('OB55')['X-GA-SV'] == '1800000000'
    assert 'X-GA-SV' not in protocol.binary_headers('OB54')


def test_ob55_framing_and_legacy():
    body = framed()
    assert protocol.decode_login(body, 'OB55').token == 'synthetic-token'
    assert protocol.decode_login(body[64:], 'OB54').ttl == 28800


@pytest.mark.parametrize('body', [b'', bytes(64), bytes(64)+b'\xff', b'<html>503</html>'])
def test_malformed_login(body):
    with pytest.raises(protocol.UpstreamError):
        protocol.decode_login(body, 'OB55')


def test_legacy_queue_not_a_token():
    msg = FreeFire_pb2.LoginRes()
    msg.queue_info.allow = True
    with pytest.raises(protocol.UpstreamError) as error:
        protocol.decode_login(msg.SerializeToString(), 'OB54')
    assert error.value.code == 'LOGIN_QUEUE'
    assert error.value.status == 503


@pytest.mark.parametrize('url', ['http://clientbp.ppmainecoonghj.com', 'https://example.com',
    'https://clientbp.ppmainecoonghj.com@evil.example', 'https://clientbp.ppmainecoonghj.com/x',
    'https://clientbp.ppmainecoonghj.com?token=secret'])
def test_untrusted_server(url):
    with pytest.raises(protocol.UpstreamError):
        protocol.decode_login(framed(server_url=url))


def test_missing_token():
    with pytest.raises(protocol.UpstreamError) as error:
        protocol.decode_login(framed(token=''))
    assert error.value.code == 'INCOMPLETE_LOGIN'


def test_login_cache_and_upstream_status(monkeypatch):
    monkeypatch.setattr(app, 'get_access_token', AsyncMock(return_value=('fake', 'fake-open')))
    post = AsyncMock(return_value=httpx.Response(200, content=framed()))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    asyncio.run(app.create_jwt('BD'))
    assert app.cached_tokens['BD']['token'] == 'Bearer synthetic-token'
    asyncio.run(app.get_token_info('BD'))
    assert post.call_count == 1
    post.return_value = httpx.Response(503, content=b'private upstream body')
    with pytest.raises(protocol.UpstreamError) as error:
        asyncio.run(app.create_jwt('IND'))
    assert 'private' not in str(error.value)
    assert 'IND' not in app.cached_tokens


def test_success_wins_despite_failed_gateway(monkeypatch):
    async def lookup(uid, source, region, endpoint):
        if region == 'BD':
            return {'basicInfo': {'nickname': 'Synthetic', 'region': 'BD'}}
        raise protocol.UpstreamError('LOGIN_QUEUE', 'Queued', 503)
    monkeypatch.setattr(app, 'GetAccountInformation', lookup)
    assert app.get_player_data('12345')[2] == 'BD'


def test_failure_is_not_not_found(monkeypatch):
    monkeypatch.setattr(app, 'GetAccountInformation', AsyncMock(side_effect=protocol.UpstreamError('LOGIN_QUEUE', 'Queued', 503)))
    response = app.app.test_client().get('/player-info?uid=12345')
    assert response.status_code == 503
    assert response.json['code'] == 'LOOKUP_INCOMPLETE'


def test_explicit_queue_preserved(monkeypatch):
    monkeypatch.setattr(app, 'GetAccountInformation', AsyncMock(side_effect=protocol.UpstreamError('LOGIN_QUEUE', 'Queued', 503)))
    response = app.app.test_client().get('/player-info?uid=12345&region=BR')
    assert response.status_code == 503
    assert response.json['code'] == 'LOGIN_QUEUE'


def test_no_player_when_all_gateways_respond(monkeypatch):
    monkeypatch.setattr(app, 'GetAccountInformation', AsyncMock(return_value={}))
    response = app.app.test_client().get('/player-info?uid=12345')
    assert response.status_code == 400
    assert response.json['code'] == 'PLAYER_NOT_FOUND'
    assert 'not found' in response.json['error']


def test_partial_failure_is_inconclusive(monkeypatch):
    async def lookup(uid, source, region, endpoint):
        if region == 'BR':
            raise protocol.UpstreamError('LOGIN_QUEUE', 'Queued', 503)
        return {}
    monkeypatch.setattr(app, 'GetAccountInformation', lookup)
    assert app.app.test_client().get('/player-info?uid=12345').status_code == 503


def test_guest_missing_fields(monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, 'post', AsyncMock(return_value=httpx.Response(200, json={})))
    with pytest.raises(protocol.UpstreamError) as error:
        asyncio.run(app.get_access_token('synthetic'))
    assert error.value.code == 'GUEST_AUTH_FAILED'


@pytest.mark.parametrize('timestamp', [1756478597, 1766375816])
def test_ob55_field13_is_not_assumed_to_be_queue(timestamp):
    # Observed shape only; no account, token or raw upstream body in fixture.
    msg = FreeFire_pb2.LoginRes()
    msg.queue_info.allow = True
    msg.queue_info.need_wait_secs = timestamp
    with pytest.raises(protocol.UpstreamError) as error:
        protocol.decode_login(bytes(64) + msg.SerializeToString(), 'OB55')
    assert error.value.code == 'UNRECOGNIZED_LOGIN_RESPONSE'
    assert str(timestamp) not in str(error.value)


def test_unrecognized_response_not_cached(monkeypatch):
    msg = FreeFire_pb2.LoginRes()
    msg.queue_info.allow = True
    msg.queue_info.need_wait_secs = 1756478597
    monkeypatch.setattr(app, 'get_access_token', AsyncMock(return_value=('fake', 'fake-open')))
    monkeypatch.setattr(httpx.AsyncClient, 'post', AsyncMock(return_value=httpx.Response(200, content=bytes(64)+msg.SerializeToString())))
    with pytest.raises(protocol.UpstreamError):
        asyncio.run(app.create_jwt('BR'))
    assert 'BR' not in app.cached_tokens


def test_unrecognized_explicit_region_error(monkeypatch):
    monkeypatch.setattr(app, 'GetAccountInformation', AsyncMock(side_effect=protocol.UpstreamError('UNRECOGNIZED_LOGIN_RESPONSE', 'Unverified login response.')))
    response = app.app.test_client().get('/player-info?uid=12345&region=VN')
    assert response.status_code == 502
    assert response.json['code'] == 'UNRECOGNIZED_LOGIN_RESPONSE'
