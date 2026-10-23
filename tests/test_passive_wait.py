import pytest
from laya_pokemon.policy import LayaPolicy


def test_passive_wait_does_not_call_classification_or_press_a_button():
    policy=LayaPolicy.__new__(LayaPolicy)
    policy.choose_options=lambda *a,**k:pytest.fail('passive wait must not use inference')
    result=policy.choose({'phase':'learning_menu','objective':'Wait.','available_actions':['wait']})
    assert result['action']=='wait' and result['passive_wait'] and result['model_ms']==0
    assert not result['prediction_cache_hit']


def test_single_active_button_cannot_bypass_laya_classification():
    policy=LayaPolicy.__new__(LayaPolicy)
    with pytest.raises(ValueError):policy.choose({'available_actions':['a']})
