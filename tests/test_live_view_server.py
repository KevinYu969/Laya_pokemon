"""本機即時顯示器只可讀兩份指定輸出，不可瀏覽遊戲檔案。"""
from http.client import HTTPResponse
from io import BytesIO
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('serve_live_game', Path(__file__).parents[1] / 'scripts/serve_live_game.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


@pytest.fixture
def live_server(tmp_path):
    return tmp_path, viewer.handler_for(tmp_path)


def request(handler, path, method='GET'):
    # 以真HTTP parser/handler處理BytesIO，驗路由邊界且不依賴沙盒網路權限。
    output = BytesIO()
    class InMemoryHandler(handler):
        def setup(self):
            self.rfile = BytesIO(f'{method} {path} HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n'.encode())
            self.wfile = output
        def finish(self): pass
    InMemoryHandler(None, ('127.0.0.1', 1), None)
    response = HTTPResponse(SimpleNamespace(makefile=lambda *_:BytesIO(output.getvalue())))
    response.begin()
    return response.status, dict(response.getheaders()), response.read()


def test_viewer_serves_only_current_frame_and_valid_metadata(live_server):
    run, port = live_server
    (run/'live-frame.json').write_text('{"frame":123,"status":"running"}', encoding='utf-8')
    (run/'live-frame.png').write_bytes(b'only-published-png')
    code, headers, body = request(port, '/api/status?ignore=cache')
    assert code == 200 and b'123' in body and headers['Cache-Control'] == 'no-store'
    assert request(port, '/live-frame.png?frame=123')[2] == b'only-published-png'
    assert 'PyBoy'.encode() in request(port, '/')[2]


@pytest.mark.parametrize('route', ['/checkpoint.state', '/../secret', '/live-frame.json', '/roms/pokemon_red.gb', '/%2e%2e/secret'])
def test_viewer_does_not_expose_other_files_or_directories(live_server, route):
    run, port = live_server
    (run/'checkpoint.state').write_bytes(b'private-fixture')
    assert request(port, route)[0] == 404


def test_viewer_reports_not_ready_instead_of_inventing_game_state(live_server):
    run, port = live_server
    assert request(port, '/api/status')[0] == 503
    (run/'live-frame.json').write_text('{partial', encoding='utf-8')
    assert request(port, '/api/status')[0] == 503
    assert request(port, '/', method='POST')[0] == 501


def test_locked_frame_publish_still_shows_real_campaign_pause_without_changing_pixels_or_party(live_server):
    run,handler=live_server
    old=dict(frame=98194,status='running',phase='battle_dialogue',party=[{'hp':90}],at='2026-10-28T03:14:29+00:00')
    (run/'live-frame.json').write_text(json.dumps(old),encoding='utf-8')
    (run/'live-frame.png').write_bytes(b'actual-stale-pixels')
    (run/'summary.json').write_text(json.dumps(dict(status='paused_for_review',review_reason='party_attrition_requires_center',private='never expose')),encoding='utf-8')
    body=json.loads(request(handler,'/api/status')[2])
    assert body=={**old,'status':'paused_for_review','review_reason':'party_attrition_requires_center'}
    assert request(handler,'/live-frame.png')[2]==b'actual-stale-pixels'
    assert request(handler,'/summary.json')[0]==404


@pytest.mark.parametrize('status,expected',[('running','running'),('failed','stopped'),('stopped','stopped')])
def test_campaign_status_does_not_copy_stale_reason_or_exception_details(live_server,status,expected):
    run,handler=live_server
    (run/'live-frame.json').write_text('{"frame":9,"status":"paused_for_review"}',encoding='utf-8')
    (run/'summary.json').write_text(json.dumps(dict(status=status,review_reason='old_reason',exception='private')),encoding='utf-8')
    assert json.loads(request(handler,'/api/status')[2])==dict(frame=9,status=expected,review_reason=None)
