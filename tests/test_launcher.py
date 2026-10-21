import json
import os
import socket
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock
from app import app, APP_VERSION
import iniciar


def test_version_and_no_cache_are_visible():
    client=app.test_client()
    response=client.get('/')
    assert f'Versão {APP_VERSION}' in response.text
    assert f'app.js?v={APP_VERSION}' in response.text
    assert response.headers['Cache-Control']=='no-store'
    assert client.get('/versao').json['versao']==APP_VERSION


def test_occupied_port_selects_another_port():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0));occupied.listen()
        initial=occupied.getsockname()[1]
        alternate=iniciar.choose_port(initial)
        assert alternate!=initial
        with socket.socket() as available:
            available.bind(('127.0.0.1',alternate))


def test_does_not_open_a_different_copy(monkeypatch):
    class OldCopy(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers()
            self.wfile.write(b'{"instancia":"older-copy"}')
        def log_message(self,*args): pass
    server=HTTPServer(('127.0.0.1',0),OldCopy)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    opened=Mock();monkeypatch.setattr(iniciar.webbrowser,'open',opened)
    monkeypatch.setattr('time.sleep',lambda _:None)
    process=Mock();process.poll.return_value=None
    try:
        assert iniciar.open_when_ready(process,f'http://127.0.0.1:{server.server_port}','new-copy') is False
        opened.assert_not_called()
    finally:
        server.shutdown();thread.join();server.server_close()


def test_new_application_opens_separately_from_an_old_listener(monkeypatch):
    # A real child server must identify itself before its browser is opened.
    opened=threading.Event();addresses=[]
    def capture(address):
        addresses.append(address);opened.set()
    monkeypatch.setattr(iniciar.webbrowser,'open',capture)
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0));occupied.listen()
        occupied_port=occupied.getsockname()[1]
        choose_port=iniciar.choose_port
        monkeypatch.setattr(iniciar,'choose_port',lambda:choose_port(occupied_port))
        process=iniciar.start_application(sys.executable)
        try:
            assert opened.wait(15), 'O novo processo não ficou pronto.'
            address=addresses[0]
            assert address!=f'http://127.0.0.1:{occupied_port}'
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(address+'/versao',timeout=3) as response:
                version=json.load(response)
            assert version['versao']==APP_VERSION and version['instancia']
            with opener.open(address,timeout=3) as response:
                assert f'Versão {APP_VERSION}' in response.read().decode()
        finally:
            process.terminate();process.wait(timeout=5)
