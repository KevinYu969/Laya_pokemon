"""地端橋接的權限／解析／停止條件；全部使用合成資料，不連網或啟動遊戲。"""
import json
from types import SimpleNamespace

import pytest

from laya_pokemon.local_planner import PlannerConfig, PlannerError, StrataPlanner, strict_object, allowed_stages, NoRedirect
from laya_pokemon.capture_route import team_waypoint


def config_file(tmp_path, **changes):
    path = tmp_path / 'planner.json'
    path.write_text(json.dumps({'device_lane': 'private_personal_confirmed', 'base_url': 'http://127.0.0.1:8080',
                               'model': 'synthetic-local-model', 'api_key_env': '', **changes}), encoding='utf-8')
    return path


@pytest.mark.parametrize('changes', [
    {'device_lane': 'unconfirmed'}, {'base_url': 'https://api.openai.com/v1'},
    {'base_url': 'http://username:secret@127.0.0.1:8080'}, {'base_url': 'http://127.0.0.1:8080/?key=secret'},
    {'base_url': 'file:///private'}, {'timeout_seconds': 600}, {'timeout_seconds': True}, {'api_key': 'inline-secret'},
])
def test_unconfirmed_public_or_embedded_credential_config_is_rejected(tmp_path, changes):
    with pytest.raises(PlannerError):
        PlannerConfig.load(config_file(tmp_path, **changes))


def test_private_config_normalizes_v1_and_does_not_follow_redirects(tmp_path):
    cfg = PlannerConfig.load(config_file(tmp_path))
    assert cfg.base_url == 'http://127.0.0.1:8080/v1'
    with pytest.raises(PlannerError):
        NoRedirect().redirect_request(None, None, 302, None, None, 'https://example.org')


@pytest.mark.parametrize('value', ['{"stage":"stop","stage":"team_training"}', '["stop"]', '{"x":NaN}', '```json\n{}\n```'])
def test_json_duplicate_keys_or_free_text_is_not_executed(value):
    with pytest.raises(PlannerError):
        strict_object(value)


class Response:
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return json.dumps(self.value).encode('utf-8')


class Transport:
    def __init__(self, decision=None, finish='stop'):
        self.calls = []
        self.decision = decision or {'stage': 'team_training', 'reason': 'Train the current lead.'}
        self.finish = finish
    def open(self, request, **kwargs):
        self.calls.append(request)
        if request.full_url.endswith('/models'):
            return Response({'data': [{'id': 'synthetic-local-model'}]})
        return Response({'choices': [{'finish_reason': self.finish, 'message': {'content': json.dumps(self.decision)}}],
                         'usage': {'prompt_tokens': 100, 'completion_tokens': 12, 'total_tokens': 112}})


def test_catalog_and_typed_stage_preserve_reported_token_usage(tmp_path):
    transport = Transport()
    planner = StrataPlanner(PlannerConfig.load(config_file(tmp_path)), transport)
    assert planner.verify_model()['catalog_verified']
    result = planner.decide({'party': []}, ['team_training', 'review', 'stop'])
    assert result['usage']['total_tokens'] == 112 and result['stage'] == 'team_training'
    request = json.loads(transport.calls[-1].data)
    assert request['reasoning_effort'] == 'none' and request['response_format']['type'] == 'json_schema'
    assert 'tools' not in request and 'image_url' not in json.dumps(request)


@pytest.mark.parametrize('decision,finish', [
    ({'stage': 'shell', 'reason': 'run this'}, 'stop'),
    ({'stage': 'team_training', 'reason': 'ok', 'command': 'bad'}, 'stop'),
    ({'stage': 'team_training', 'reason': 'ok'}, 'length'),
])
def test_model_cannot_expand_stages_commands_or_use_truncated_output(tmp_path, decision, finish):
    planner = StrataPlanner(PlannerConfig.load(config_file(tmp_path)), Transport(decision, finish))
    with pytest.raises(PlannerError):
        planner.decide({}, ['team_training', 'review', 'stop'])


def test_missing_api_key_stops_before_any_network_access(tmp_path):
    planner = StrataPlanner(PlannerConfig.load(config_file(tmp_path, api_key_env='SYNTHETIC_UNSET_LAYA_KEY')), Transport())
    with pytest.raises(PlannerError):
        planner.verify_model()
    assert planner.opener.calls == []


def snapshot():
    return {'party_valid': True, 'battle': 'none', 'location': {'map_id': 33},
            'party': [{'species': 153, 'level': 7}, {'species': 3, 'level': 3}],
            'story': {k: True for k in ('got_starter', 'battled_rival_in_oaks_lab', 'got_oaks_parcel', 'oak_got_parcel', 'got_pokedex')}}


def test_current_team_can_train_but_unknown_flags_or_completed_level_require_review():
    state = snapshot()
    assert allowed_stages(state) == ['team_training', 'review', 'stop']
    state['party'][0]['level'] = 13
    assert allowed_stages(state) == ['review', 'stop']
    state['party'][0]['level'] = 7
    state['story']['got_pokedex'] = None
    assert allowed_stages(state) == ['review', 'stop']


def test_training_does_not_stop_just_because_nidoran_was_caught():
    party = [{'species': 153, 'level': 7, 'hp': 23, 'max_hp': 23}, {'species': 3, 'level': 3, 'hp': 16, 'max_hp': 16}]
    args = ({'map_id': 33, 'x': 30, 'y': 8}, {'got_pokedex': True}, party, 7)
    assert team_waypoint(*args)['goal'] == 'first_team_capture_complete'
    assert team_waypoint(*args, training=True)['goal'] == 'patrol_route22_east_grass'
    party[0]['level'] = 13
    assert team_waypoint(*args, training=True)['goal'] == 'lead_training_complete'


def test_supervisor_never_restarts_a_window_closed_game(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('strata_supervisor', Path(__file__).resolve().parents[1]/'scripts/strata_supervisor.py')
    supervisor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(supervisor)
    monkeypatch.setattr(supervisor, 'ROOT', tmp_path)
    (tmp_path/'.local').mkdir()
    cfg = tmp_path/'.local/planner.json'
    cfg.write_text(config_file(tmp_path).read_text(), encoding='utf-8')
    (tmp_path/'rom.gb').write_bytes(b'synthetic')
    (tmp_path/'source.state').write_bytes(b'synthetic-state')
    monkeypatch.setattr(supervisor, 'parse_rom_header', lambda _: {'sha256': '5ca7ba01642a3b27b0cc0b5349b52792795b62d3ed977e98a09390659af96b7b'})
    monkeypatch.setattr(supervisor, 'snapshot_from_state', lambda *args: snapshot())
    class Planner:
        def __init__(self, config): pass
        def verify_model(self): return {'catalog_verified': True}
        def decide(self, state, choices): return {'stage': 'team_training', 'reason': 'train'}
    monkeypatch.setattr(supervisor, 'StrataPlanner', Planner)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert '--offline' in command and command[command.index('--policy')+1] == 'laya'
        target = Path(command[command.index('--output')+1]);target.mkdir()
        (target/'summary.json').write_text(json.dumps({'stop_reason': 'window_closed'}))
        (target/'final.state').write_bytes(b'preserved')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(supervisor.subprocess, 'run', run)
    output = tmp_path/'outputs/session'
    monkeypatch.setattr(supervisor.sys, 'argv', ['supervisor', '--config', str(cfg), '--rom', str(tmp_path/'rom.gb'),
                                              '--state', str(tmp_path/'source.state'), '--output', str(output), '--episodes', '3'])
    supervisor.main()
    result = json.loads((output/'summary.json').read_text())
    assert len(calls) == 1 and result['stop_reason'] == 'window_closed'
    assert (tmp_path/'source.state').read_bytes() == b'synthetic-state'
