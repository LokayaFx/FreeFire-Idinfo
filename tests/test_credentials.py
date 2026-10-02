from urllib.parse import parse_qs
import pytest
import credentials
from protocol import UpstreamError

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in list(credentials.os.environ):
        if key.startswith('FREEFIRE_') and key.endswith(('_UID', '_PASSWORD')):
            monkeypatch.delenv(key)

def test_no_override():
    assert credentials.get_override('BR') is None

def test_complete_pair_and_encoding(monkeypatch):
    monkeypatch.setenv('FREEFIRE_VN_UID', '12345')
    monkeypatch.setenv('FREEFIRE_VN_PASSWORD', 'synthetic&value=+test')
    assert parse_qs(credentials.get_override('VN')) == {'uid':['12345'],'password':['synthetic&value=+test']}

def test_exact_over_group(monkeypatch):
    monkeypatch.setenv('FREEFIRE_AMERICAS_UID','111')
    monkeypatch.setenv('FREEFIRE_AMERICAS_PASSWORD','group')
    monkeypatch.setenv('FREEFIRE_BR_UID','222')
    monkeypatch.setenv('FREEFIRE_BR_PASSWORD','exact')
    assert parse_qs(credentials.get_override('BR'))['uid'] == ['222']
    assert parse_qs(credentials.get_override('EU'))['uid'] == ['111']

@pytest.mark.parametrize('uid,password', [('123',None),(None,'secret'),('', 'secret'),('abc','secret')])
def test_partial_or_invalid_override_fails_closed(monkeypatch,uid,password):
    if uid is not None:monkeypatch.setenv('FREEFIRE_BR_UID',uid)
    if password is not None:monkeypatch.setenv('FREEFIRE_BR_PASSWORD',password)
    with pytest.raises(UpstreamError) as error:
        credentials.get_override('BR')
    assert error.value.code == 'CREDENTIAL_CONFIG_ERROR'
    assert 'secret' not in str(error.value)

def test_app_uses_override(monkeypatch):
    import app
    monkeypatch.setenv('FREEFIRE_BR_UID','12345')
    monkeypatch.setenv('FREEFIRE_BR_PASSWORD','synthetic')
    assert parse_qs(app.get_account_credentials('BR'))['uid'] == ['12345']

@pytest.fixture
def account_file(tmp_path,monkeypatch):
    path=tmp_path/'accounts.txt'
    monkeypatch.setattr(credentials,'ACCOUNTS_FILE',path)
    return path


def test_scoped_file_and_group_mapping(account_file):
    account_file.write_text('123 br-test BR\n456 vn-test VN\n789 global-test GLOBAL\n')
    assert parse_qs(credentials.get_credentials('BR'))['uid']==['123']
    assert parse_qs(credentials.get_credentials('US'))['uid']==['123']
    assert parse_qs(credentials.get_credentials('VN'))['uid']==['456']
    assert parse_qs(credentials.get_credentials('BD'))['uid']==['789']


def test_environment_precedes_file(account_file,monkeypatch):
    account_file.write_text('123 bundled BR\n')
    monkeypatch.setenv('FREEFIRE_BR_UID','222')
    monkeypatch.setenv('FREEFIRE_BR_PASSWORD','override')
    assert parse_qs(credentials.get_credentials('BR'))['uid']==['222']


@pytest.mark.parametrize('content',['123 first BR\n456 second BR\n','123 secret UNKNOWN\n','123 secret extra BR\n','999 unmapped\n'])
def test_bad_or_missing_scope_fails_without_leak(account_file,content):
    account_file.write_text(content)
    with pytest.raises(UpstreamError) as error:
        credentials.get_credentials('BR')
    assert error.value.code=='CREDENTIAL_CONFIG_ERROR'
    assert 'secret' not in str(error.value)


def test_missing_account_file(account_file):
    with pytest.raises(UpstreamError):
        credentials.get_credentials('BR')
