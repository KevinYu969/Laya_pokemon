import pytest

from laya_pokemon.policy import LayaPolicy


def test_real_sdk_question_contract_without_loading_weights():
    module = pytest.importorskip("laya.agent")
    class Agent:
        def predict(self, state, questions):
            module.Agent._check_question("action", questions["action"])
            return {"answers": {"action": {"choice": "a"}}, "usage": {"truncated": False}}
    policy = object.__new__(LayaPolicy)
    policy.agent = Agent()
    assert policy.choose({"objective": "Confirm"})["action"] == "a"


def test_truncated_input_cannot_produce_button_press():
    class Agent:
        def predict(self, state, questions):
            return {"answers": {"action": {"choice": "a"}}, "usage": {"truncated": True}}
    policy = object.__new__(LayaPolicy)
    policy.agent = Agent()
    with pytest.raises(ValueError, match="截斷"):
        policy.choose({"objective": "A long state"})


def test_control_input_keeps_game_text_but_excludes_large_diagnostics():
    import json
    captured = []

    class Agent:
        def predict(self, state, questions):
            captured.append(json.loads(state))
            return {"answers": {"action": {"choice": "a"}}, "usage": {"truncated": False}}

    policy = object.__new__(LayaPolicy)
    policy.agent = Agent()
    result = policy.choose({"objective": "Advance dialogue", "phase": "unclassified",
                           "visible_text_candidates": ["Hello there!"], "previous_actions": ["start"],
                           "screen_sha256": "0" * 64, "observation_warnings": ["診斷資料" * 1000]})
    assert captured[0]["visible_text_candidates"] == ["Hello there!"]
    assert "observation_warnings" not in captured[0] and "screen_sha256" not in captured[0]
    assert "previous_actions" not in captured[0]
    assert result["model_state"] == captured[0]


def test_context_candidate_mask_still_uses_model_choice():
    class Agent:
        def predict(self, state, questions):
            assert set(questions["action"]["criteria"]) == {"up", "down", "a", "b"}
            return {"answers": {"action": {"choice": "a"}}, "usage": {"truncated": False}}
    policy = object.__new__(LayaPolicy)
    policy.agent = Agent()
    result = policy.choose({"phase": "menu", "objective": "Confirm NEW NAME", "available_actions": ["up", "down", "a", "b"]})
    assert result["action"] == "a" and result["candidate_actions"] == ["up", "down", "a", "b"]


def test_prediction_cache_reuses_only_exact_inputs_and_candidate_set():
    from collections import OrderedDict
    calls=[]
    class Agent:
        def predict(self,state,questions):
            calls.append(state)
            return {'answers':{'action':{'choice':'up'}},'usage':{'truncated':False}}
    policy=object.__new__(LayaPolicy);policy.agent=Agent();policy.cache_enabled=True;policy.prediction_cache=OrderedDict()
    state={'objective':'Move UP.','available_actions':['up','wait']}
    first=policy.choose(state)
    assert not first['prediction_cache_hit']
    first['raw']['usage']['truncated']=True
    cached=policy.choose(state)
    assert cached['prediction_cache_hit'] and not cached['raw']['usage']['truncated'] and len(calls)==1
    policy.choose({**state,'visible_text_candidates':['New text']})
    policy.choose({**state,'available_actions':['up','down','wait']})
    assert len(calls)==3


def test_fast_button_translation_keeps_full_observation_out_of_cache_input():
    from collections import OrderedDict
    calls=[]
    class Agent:
        def predict(self,state,questions):
            calls.append(state)
            return {'answers':{'action':{'choice':'up'}},'usage':{'truncated':False}}
    policy=object.__new__(LayaPolicy);policy.agent=Agent();policy.cache_enabled=True;policy.prediction_cache=OrderedDict()
    first=policy.choose({'objective':'Move UP.','phase':'overworld','world_path_hint':{'direction':'up'},'visible_text_candidates':[], 'party_summary':[{'hp':20}], 'available_actions':['up','wait']})
    second=policy.choose({'objective':'Move UP.','phase':'overworld','world_path_hint':{'direction':'up'},'visible_text_candidates':[], 'party_summary':[{'hp':19}], 'available_actions':['up','wait']})
    assert first['model_state']=={'objective':'Move UP.','phase':'overworld'}
    assert second['prediction_cache_hit'] and len(calls)==1
