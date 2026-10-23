from tests.test_battle import text_at
import laya_pokemon.battle as battle


def test_live_calibrated_ivysaur22_skip_requires_visible_move_then_no_then_yes(monkeypatch):
    monkeypatch.setattr(battle,'_skip_poison_session',None)
    party=[{'species':5,'level':12,'moves':[64,45,43,0]}, {'species':9,'level':22,'moves':[33,45,73,22]}]
    result=battle.learning_context(text_at((10,4,'IVYSAUR'),(1,14,'IVYSAUR is'),(1,16,'trying to learn')),party)
    assert result['learning_tactic']=='advance_poisonpowder_intro'
    result=battle.learning_context(text_at((1,14,'POISONPOWDER!')),party)
    assert result['learning_tactic']=='advance_poisonpowder_intro'
    result=battle.learning_context(text_at((1,14,'Delete an older'),(1,16,'move to make room▼')),party)
    assert result['learning_tactic']=='advance_wrapped_learning_question'
    text=text_at((14,7,'▶YES'),(15,9,'NO'),(1,14,'Delete an older'),(1,16,'move?'))
    result=battle.learning_context(text,party)
    assert result['menu_label']=='NO' and result['objective']=='Move DOWN.'
    text=text_at((14,7,'▶YES'),(15,9,'NO'),(1,14,'move to make room'),(1,16,'for POISONPOWDER?'))
    assert battle.learning_context(text,party)['menu_label']=='NO'
    text=text_at((14,7,'▶YES'),(15,9,'NO'),(1,14,'Stop learning'),(1,16,'POISONPOWDER?'))
    assert battle.learning_context(text,party)['menu_label']=='YES'
    result=battle.learning_context(text_at((1,14,'IVYSAUR did not'),(1,16,'learn POISONPOWDER!')),party)
    assert result['learning_tactic']=='skip_confirmed' and battle._skip_poison_session is None


def test_skip_flow_cannot_confirm_an_unexpected_forget_move_menu(monkeypatch):
    monkeypatch.setattr(battle,'_skip_poison_session',{'phase':'delete_decision','confirmed_move':True,'plan':{'decision':'skip'}})
    party=[{'species':9,'level':22,'moves':[33,45,73,22]}]
    result=battle.learning_context(text_at((5,12,'▶TACKLE'),(1,14,'Which move should'),(1,16,'be forgotten?')),party)
    assert result['phase']=='strategy_review'


def test_unknown_four_move_replacement_still_requires_review(monkeypatch):
    monkeypatch.setattr(battle,'_skip_poison_session',None)
    party=[{'species':9,'level':30,'moves':[33,45,73,22]}]
    result=battle.learning_context(text_at((1,14,'IVYSAUR is trying'),(1,16,'to learn RAZOR LEAF')),party)
    assert result['phase']=='strategy_review'
