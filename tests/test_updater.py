import hashlib
from io import BytesIO
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

import updater


def info(content=b'MZfictitious-installer'):
    return dict(version='9.0.0', url=updater.BASE+'download/v9.0.0/ComparadorNotas-9.0.0-Windows-x64.exe',
                sha256=hashlib.sha256(content).hexdigest())


def test_update_is_monotonic_and_cannot_execute_other_repository():
    assert updater.validate_update(info(),'0.7.1')==info()
    assert updater.validate_update(info(),'9.0.0') is None
    assert updater.validate_update(info(),'10.0.0') is None
    bad=info();bad['url']='https://example.com/malicious.exe'
    with pytest.raises(ValueError):updater.validate_update(bad,'0.7.1')
    bad=info();bad['sha256']='not-a-checksum'
    with pytest.raises(ValueError):updater.validate_update(bad,'0.7.1')
    with pytest.raises(ValueError):updater.version_tuple('9.0.0;run')


def test_download_checks_hash_signature_and_cleans_partial_file(tmp_path,monkeypatch):
    monkeypatch.setattr(updater.urllib.request,'urlopen',lambda *a,**k:BytesIO(b'MZfictitious-installer'))
    target=updater.download_update(info(),tmp_path)
    assert target.read_bytes()==b'MZfictitious-installer'
    bad=info();bad['sha256']='0'*64
    with pytest.raises(ValueError):updater.download_update(bad,tmp_path)
    assert not list(tmp_path.glob('*.part'))
    # A failed download must not destroy a previously verified installer.
    assert target.read_bytes()==b'MZfictitious-installer'
    monkeypatch.setattr(updater.urllib.request,'urlopen',lambda *a,**k:BytesIO(b'not-an-exe'))
    with pytest.raises(ValueError):updater.download_update(info(b'not-an-exe'),tmp_path)


def test_size_limits_and_feed_validation(tmp_path,monkeypatch):
    monkeypatch.setattr(updater.urllib.request,'urlopen',lambda *a,**k:BytesIO(b'MZbig'))
    monkeypatch.setattr(updater,'MAX_INSTALLER',2)
    with pytest.raises(ValueError):updater.download_update(info(b'MZbig'),tmp_path)
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(updater.urllib.request,'urlopen',lambda *a,**k:BytesIO(json.dumps(info()).encode()))
    assert updater.check_update('0.7.1')==info()
    monkeypatch.setattr(updater.urllib.request,'urlopen',lambda *a,**k:BytesIO(b'x'*32769))
    with pytest.raises(ValueError):updater.check_update('0.7.1')


def windows(monkeypatch,tmp_path,answer=6):
    import ctypes
    message=Mock(return_value=answer)
    monkeypatch.setattr(updater,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':str(tmp_path)}))
    monkeypatch.setattr(ctypes,'windll',SimpleNamespace(user32=SimpleNamespace(MessageBoxW=message)),raising=False)
    return message


def test_installer_only_launches_after_user_accepts_and_download_is_verified(tmp_path,monkeypatch):
    message=windows(monkeypatch,tmp_path)
    monkeypatch.setattr(updater,'check_update',lambda current:info())
    verified=tmp_path/'installer.exe'
    download=Mock(return_value=verified)
    monkeypatch.setattr(updater,'download_update',download)
    launch=Mock();monkeypatch.setattr(updater.subprocess,'Popen',launch)
    assert updater.offer_update('0.7.1')
    launch.assert_called_once_with([str(verified)],close_fds=True)
    message.return_value=7
    launch.reset_mock();download.reset_mock()
    assert not updater.offer_update('0.7.1')
    download.assert_not_called();launch.assert_not_called()


def test_offline_or_corrupt_update_does_not_block_current_app(tmp_path,monkeypatch):
    windows(monkeypatch,tmp_path)
    launch=Mock();monkeypatch.setattr(updater.subprocess,'Popen',launch)
    monkeypatch.setattr(updater,'check_update',Mock(side_effect=TimeoutError('offline')))
    assert not updater.offer_update('0.7.1')
    monkeypatch.setattr(updater,'check_update',lambda current:info())
    monkeypatch.setattr(updater,'download_update',Mock(side_effect=ValueError('bad checksum')))
    assert not updater.offer_update('0.7.1')
    launch.assert_not_called()
