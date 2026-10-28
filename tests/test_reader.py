"""Reader contracts with synthetic files/transports; no emulator or network calls."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.request

import pytest


@pytest.fixture
def reader():
    path = Path(__file__).resolve().parents[1] / 'scripts/reader.py'
    spec = importlib.util.spec_from_file_location('reader_contract_test', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def config(backend='local', **changes):
    return {'backend': backend, 'base_url': 'http://127.0.0.1:11434/v1',
            'model': 'synthetic-model', 'api_key_env': '', **changes}


@pytest.mark.parametrize('total,available,model', [(32, 20, 'qwen3:8b'), (24, 16, 'qwen3:8b'),
    (32, 12, 'qwen3:4b'), (15, 10, 'qwen3:4b'), (32, 9, None), (8, 7, None)])
def test_memory_recommendations(reader, total, available, model):
    assert reader.recommendation(total, available) == model


@pytest.mark.parametrize('changes', [
    {'base_url': 'https://api.example.org/v1'}, {'model': 'qwen:cloud'},
    {'base_url': 'http://name:key@127.0.0.1/v1'},
    {'base_url': 'http://127.0.0.1/v1?api_key=secret'}, {'api_key': 'secret'},
    {'api_key_env': 'sk-plaintext-key'}, {'timeout_seconds': True},
])
def test_local_config_rejects_public_cloud_tag_and_inline_keys(reader, changes):
    with pytest.raises(reader.PlannerError):
        reader.validate_config(config(**changes), allow_cloud=True)


def test_cloud_requires_explicit_opt_in_again_when_config_reloaded(reader, tmp_path, monkeypatch):
    data = config('cloud', base_url='https://api.example.org/v1', api_key_env='SYNTHETIC_KEY')
    assert reader.validate_config(data, allow_cloud=True).backend == 'cloud'
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(reader, 'CONFIG', path)
    with pytest.raises(reader.PlannerError, match='every probe/play'):
        reader.load_planner(False)
    assert reader.load_planner(True).config.backend == 'cloud'


@pytest.mark.parametrize('changes', [{'base_url': 'http://api.example.org/v1'}, {'api_key_env': ''},
    {'base_url': 'https://127.0.0.1/v1'}, {'base_url': 'https://api.example.org/v1?key=secret'}])
def test_cloud_requires_https_key_name_and_public_host(reader, changes):
    data = config('cloud', base_url='https://api.example.org/v1', api_key_env='SYNTHETIC_KEY')
    data.update(changes)
    with pytest.raises(reader.PlannerError):
        reader.validate_config(data, allow_cloud=True)


class Transport:
    def __init__(self, decision=None):
        self.calls = []
        self.decision = decision

    def open(self, request, **kwargs):
        self.calls.append(request)
        value = {'data': [{'id': 'synthetic-model'}]} if self.decision is None else {
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(self.decision)}}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps(value).encode()
        return Response()


def test_missing_key_never_reaches_transport_and_child_does_not_inherit_key(reader, monkeypatch):
    cfg = reader.validate_config(config(api_key_env='SYNTHETIC_READER_KEY'))
    monkeypatch.delenv(cfg.api_key_env, raising=False)
    transport = Transport()
    planner = reader.ReaderPlanner(cfg, transport)
    with pytest.raises(reader.PlannerError):
        planner.verify_model()
    assert transport.calls == []
    monkeypatch.setenv(cfg.api_key_env, 'synthetic-secret')
    assert cfg.api_key_env not in reader.child_environment(cfg)
    assert reader.child_environment(cfg)['HF_HUB_OFFLINE'] == '1'


def test_redirect_handler_refuses_forwarding_authenticated_request(reader, monkeypatch):
    cfg = reader.validate_config(config(api_key_env='SYNTHETIC_READER_KEY'))
    monkeypatch.setenv(cfg.api_key_env, 'synthetic-secret')
    planner = reader.ReaderPlanner(cfg)
    handlers = [handler for handler in planner.opener.handlers if isinstance(handler, urllib.request.HTTPRedirectHandler)]
    assert len(handlers) == 1
    request = urllib.request.Request(cfg.base_url + '/models', headers={'Authorization': 'Bearer synthetic-secret'})
    with pytest.raises(reader.PlannerError):
        handlers[0].redirect_request(request, None, 302, 'redirect', {}, 'https://elsewhere.example/v1')


@pytest.mark.parametrize('decision', [{'stage': 'shell', 'reason': 'bad'},
    {'stage': 'starter', 'reason': 'not allowed here'}, {'stage': 'review', 'reason': 'ok', 'command': 'bad'}])
def test_planner_rejects_illegal_stages_and_extra_fields(reader, decision):
    planner = reader.ReaderPlanner(reader.validate_config(config()), Transport(decision))
    with pytest.raises(reader.PlannerError):
        planner.decide({}, ['review', 'stop'])


@pytest.mark.parametrize('budget,count,reason', [(1, 1, 'episode_budget'), (2, 2, 'episode_budget'), (3, 2, 'review')])
def test_play_boots_without_state_then_resumes_saved_state_and_stops_for_review(reader, tmp_path, monkeypatch, budget, count, reason):
    monkeypatch.setattr(reader, 'ROOT', tmp_path)
    monkeypatch.setattr(reader, 'load_planner', lambda _: None)
    monkeypatch.setattr(reader, 'parse_rom_header', lambda _: {'sha256': reader.RED_SHA})
    monkeypatch.setattr(reader, 'utc_now', lambda: 'synthetic-run')
    rom = tmp_path / 'synthetic.gb'
    rom.write_bytes(b'not-a-rom')
    snapshots = []
    def snapshot(rom_path, state):
        snapshots.append(state)
        return {}
    monkeypatch.setitem(sys.modules, 'strata_supervisor', SimpleNamespace(snapshot_from_state=snapshot))
    monkeypatch.setitem(sys.modules, 'serve_live_game', SimpleNamespace(handler_for=lambda path: object()))
    monkeypatch.setattr(reader, 'allowed_stages', lambda _: ['lab_rival', 'review', 'stop'] if len(snapshots) == 1 else ['review', 'stop'])
    server_events = []
    class Server:
        server_port = 12345
        def __init__(self, address, handler):
            assert address == ('127.0.0.1', 0 if not server_events else 12345)
        def serve_forever(self): pass
        def shutdown(self): server_events.append('shutdown')
        def server_close(self): server_events.append('close')
    monkeypatch.setattr(reader, 'ThreadingHTTPServer', Server)
    monkeypatch.setattr(reader.threading, 'Thread', lambda **kw: SimpleNamespace(start=lambda: None, join=lambda **kw: None))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        output = Path(command[command.index('--output') + 1])
        output.mkdir()
        (output / 'final.state').write_bytes(b'synthetic-progress')
        (output / 'summary.json').write_text(json.dumps({'stop_reason': 'action_budget'}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(reader.subprocess, 'run', run)
    args = SimpleNamespace(rom=str(rom), state=None, allow_cloud=False, episodes=budget, port=0, window=False, fast_forward=False)
    reader.play(args)
    assert len(calls) == count
    assert '--state' not in calls[0]
    if count > 1:
        assert '--state' in calls[1]
        assert Path(calls[1][calls[1].index('--state') + 1]) == snapshots[0]
        assert calls[0][calls[0].index('--output') + 1] != calls[1][calls[1].index('--output') + 1]
    assert '--live-view' in calls[0] and '--window' not in calls[0]
    report = json.loads((tmp_path / 'outputs/reader/synthetic-run/summary.json').read_text())
    assert report['status'] == 'stopped' and report['stop_reason'] == reason
    assert server_events == ['shutdown', 'close'] * count
    assert rom.read_bytes() == b'not-a-rom'
    with pytest.raises(FileExistsError):
        reader.play(args)
    assert len(calls) == count


@pytest.mark.parametrize('episodes', ['0', '21', '-1'])
def test_cli_enforces_episode_budget(reader, monkeypatch, episodes):
    monkeypatch.setattr(reader.os, 'chdir', lambda _: None)
    monkeypatch.setattr(sys, 'argv', ['reader.py', 'play', '--rom', 'synthetic.gb', '--episodes', episodes])
    with pytest.raises(SystemExit) as error:
        reader.main()
    assert error.value.code == 2
