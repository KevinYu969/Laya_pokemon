import json
import pytest
from laya_pokemon.campaign_plan import load_plan,validate_approved_stage


@pytest.mark.parametrize('value',[None,[],{}, {'steps':[]},{'steps':[{'id':'go','map_id':3,'target':[20,6],'kind':'shell'}]}])
def test_invalid_hot_plan_is_rejected_before_any_game_action(tmp_path,value):
    path=tmp_path/'plan.json';path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError):load_plan(path)


def test_valid_plan_and_resume_cursor_are_checked(tmp_path):
    path=tmp_path/'plan.json';value={'steps':[{'id':'go','map_id':3,'target':[20,-1],'kind':'move'}],'resume_step':'go'}
    path.write_text(json.dumps(value),encoding='utf-8');assert load_plan(path)==value
    value['resume_step']='missing';path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError):load_plan(path)


@pytest.mark.parametrize('patch', [
    {'via': None}, {'via': []}, {'via': [[14]]}, {'via': [[True, 1]]},
    {'kind': 'use_cut', 'face': 'up'},
    {'kind': 'use_cut', 'tree': [5, 8], 'face': 'north'},
])
def test_incomplete_route_extensions_stop_before_runtime_key_errors(tmp_path, patch):
    step={'id':'go','map_id':20,'target':[4,8],'kind':'move',**patch}
    path=tmp_path/'plan.json';path.write_text(json.dumps({'steps':[step]}),encoding='utf-8')
    with pytest.raises(ValueError):load_plan(path)


def test_recovery_approval_cannot_launch_unbounded_league_or_training_mode():
    for mode in ('league_campaign','balanced_training',None):
        with pytest.raises(ValueError):validate_approved_stage({'mode':mode},'battle_recovery')
    validate_approved_stage({'mode':'battle_recovery'},'battle_recovery')
