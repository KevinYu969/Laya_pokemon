from tests.test_battle import text_at
from laya_pokemon.party_control import lead_context,party_choice

PARTY=[{'species':9},{'species':3},{'species':5}]


def test_normal_start_menu_selects_pokemon_instead_of_items():
    text=text_at((12,2,'▷POKéDEX'),(13,4,'POKéMON'),(13,6,'ITEM'))
    assert lead_context(text,PARTY,5)['objective']=='Move DOWN.'


def test_low_member_is_selected_then_switch_submenu_then_destination():
    text=text_at((3,0,'IVYSAUR'),(0,1,'▷'),(3,2,'NIDORAN♂'),(3,4,'SPEAROW'))
    assert lead_context(text,PARTY,5)['party_target_index']==2
    text=text_at((10,12,'▷STATS'),(11,14,'SWITCH'),(11,16,'CANCEL'))
    assert lead_context(text,PARTY,5)['menu_label']=='SWITCH'
    text=text_at((3,0,'IVYSAUR'),(3,2,'NIDORAN♂'),(3,4,'SPEAROW'),(0,5,'▷'),(1,14,'Move POKéMON'),(1,16,'where?'))
    assert lead_context(text,PARTY,5)['party_target_index']==0


def test_order_change_is_verified_and_menu_closed_before_travel():
    text=text_at((3,0,'SPEAROW'),(0,1,'▷'),(3,2,'NIDORAN♂'),(3,4,'IVYSAUR'))
    result=lead_context(text,list(reversed(PARTY)),5)
    assert result['party_order_verified'] and result['available_actions']==['b','wait']


def test_does_not_open_start_over_a_nurse_dialogue():
    text=text_at((1,14,'We hope to see'),(1,16,'you again!'))
    assert lead_context(text,PARTY,5,open_menu=False) is None


def test_verified_lead_does_not_cancel_nurses_heal_menu():
    text=text_at((12,10,'▶HEAL'),(13,12,'CANCEL'),(1,16,'perfect health!'))
    assert lead_context(text,PARTY,9,open_menu=False) is None


def test_swap_destination_ignores_static_source_marker():
    text=text_at((3,0,'IVYSAUR'),(0,1,'▶'),(3,2,'NIDORAN♂'),(3,4,'SPEAROW'),(0,5,'▷'),(1,14,'Move POKéMON'),(1,16,'where?'))
    assert lead_context(text,PARTY,5)['objective']=='Confirm the current selection.'


def test_switch_training_uses_verified_upper_right_cell_when_pkmn_glyph_is_not_decoded(monkeypatch):
    import laya_pokemon.balanced_training as training
    text=text_at((1,0,'SPEAROW'),(10,7,'SPEAROW'),(9,14,'▶FIGHT'),(10,16,'ITEM'),(16,16,'RUN'))
    monkeypatch.setattr(training,'read_visible_text',lambda _:text)
    state={'battle_state':{'active':True},'progress':{'party':[{'species':5,'level':3,'hp':16},{'species':9,'level':18,'hp':52}]}}
    result=training.context(None,state,{},[])
    assert result['objective']=='Move RIGHT.' and result['training_tactic']=='switch_for_shared_experience'


def test_training_support_uses_highest_level_even_if_lower_member_has_stronger_move(monkeypatch):
    import laya_pokemon.balanced_training as training
    text=text_at((3,0,'SPEAROW'),(3,2,'NIDORAN♂'),(0,3,'▶'),(3,4,'IVYSAUR'),(1,14,'Choose a POKéMON.'))
    monkeypatch.setattr(training,'read_visible_text',lambda _:text)
    state={'battle_state':{'active':True},'progress':{'party':[{'species':5,'level':10,'hp':31},{'species':3,'level':11,'hp':29},{'species':9,'level':20,'hp':56}]}}
    result=training.context(None,state,{},[])
    assert result['party_target_index']==2 and result['objective']=='Move DOWN.'
