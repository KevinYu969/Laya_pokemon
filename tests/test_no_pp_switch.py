from tests.test_battle import text_at
import laya_pokemon.battle as battle


def test_empty_attacking_pp_switches_to_distinct_healthy_attacker(monkeypatch):
    monkeypatch.setattr(battle,'_no_pp_switch',None)
    party=[{'species':9,'level':22,'hp':40,'moves':[77,45,73,22],'pp':[35,40,10,0]},
           {'species':167,'level':18,'hp':50,'moves':[43,33,30,40],'pp':[30,35,25,35]}]
    flag={'active':True,'kind':'wild','opponent_species':'ZUBAT'}
    text=text_at((1,0,'ZUBAT'),(10,7,'IVYSAUR'),(9,14,'▶FIGHT'),(10,16,'ITEM'),(16,16,'RUN'))
    result=battle.battle_context(text,flag,party)
    assert result['battle_tactic']=='switch_no_attack_pp' and result['objective']=='Move RIGHT.'
    text=text_at((3,0,'IVYSAUR'),(0,1,'▶'),(3,2,'NIDORINO'),(1,14,'Choose a POKéMON.'))
    result=battle.battle_context(text,flag,party)
    assert result['party_target_index']==1 and result['objective']=='Move DOWN.'
    text=text_at((1,0,'ZUBAT'),(10,7,'NIDORINO'),(9,14,'▶FIGHT'),(10,16,'ITEM'),(16,16,'RUN'))
    assert battle.battle_context(text,flag,party)['battle_tactic']=='damage'
    assert battle._no_pp_switch is None
