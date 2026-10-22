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
