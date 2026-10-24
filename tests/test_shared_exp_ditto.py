"""變身改屬性但不換遭遇；沿既有同幀證明交回一般戰鬥。"""
from test_shared_experience_training import Harness,command,packet
from laya_pokemon import balanced_training as training
from laya_pokemon import ditto_transform as dt
from laya_pokemon.team_strategy import reference


def ditto_text(party,active):
    rows=[''.join(row) for row in command(party,active=active)['cells']]
    rows[0]=' DITTO'+' '*14
    return packet(rows)


def setup(monkeypatch,valid=True):
    env=Harness(monkeypatch)
    env.state['battle_state'].update(opponent_species='DITTO',wild_opponent_species='DITTO')
    env.call(ditto_text(env.party,0));owner=training._SHARED_EXPERIENCE_PENDING
    signal=dt._certificate(dict(wild=1,battle_type=0,status3=8,original=76,effective=132,
        cur_opponent=0,nick=list(dt._DITTO_NICK),types=[0,0],party=[m['species'] for m in env.party]),
        reference(),env.frame+4)
    if not valid:signal['read_valid']=False
    env.state['battle_state'].update(opponent_species='SNORLAX',wild_opponent_species='SNORLAX',ditto_transform=signal)
    return env,owner


def test_verified_transform_preserves_encounter_and_completes_target_handoff(monkeypatch):
    env,owner=setup(monkeypatch)
    assert owner['signature'][3]=='DITTO'
    assert env.call(ditto_text(env.party,-1)) is None
    assert training._SHARED_EXPERIENCE_PENDING is None
    assert training._SHARED_EXPERIENCE_LAST_COMPLETION['training_tactic']=='shared_experience_target_hud_handoff'


def test_unknown_transform_cannot_complete_pending(monkeypatch):
    env,owner=setup(monkeypatch,valid=False)
    assert env.call(ditto_text(env.party,-1)) is None
    assert training._SHARED_EXPERIENCE_PENDING is owner
