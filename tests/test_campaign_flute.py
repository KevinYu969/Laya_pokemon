"""Flute橋接僅從確定站位開始，真wild交棒仍不宣稱捕獲。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import campaign_transactions as tx
from laya_pokemon.poke_flute import INTENT
from tests.test_poke_flute import progress,text_at,WILD,wild_hud

class Memory:
    facing=0
    def __getitem__(self,address):
        assert address==0xC109;return self.facing
    def __setitem__(self,*args):raise AssertionError('No memory write')

@pytest.fixture(autouse=True)
def clean():
    for x in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED):x.clear()
    yield
    for x in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED):x.clear()

def setup():
    e=SimpleNamespace(memory=Memory())
    s={'phase':'unclassified','frame':1,'location':{'map_id':23,'x':10,'y':61},
       'battle_state':{'raw':0,'kind':'none','active':False},'progress':progress()}
    step={'id':'wake','kind':'interact','mechanic':'route12_poke_flute','map_id':23,
          'target':[10,61],'flute_intent':deepcopy(INTENT)}
    return e,s,{'steps':[step,{'id':'catch-review','kind':'interact','mechanic':'unsupported_capture',
                             'map_id':23,'target':[10,61]}]}

def call(a,t=None):return tx.context(*a,'wake',t if t is not None else text_at(),{})

@pytest.mark.parametrize('change',[lambda s:s['flute_intent'].update(species=143),
    lambda s:s['flute_intent'].update(item=True),lambda s:s.update(target=[10,62])])
def test_exact_wake_intent_only(change):
    a=setup();change(a[2]['steps'][0])
    assert call(a)[0]['review_reason']=='flute_explicit_wake_intent_unverified'

def test_cannot_begin_during_existing_wild_battle():
    a=setup();a[1]['battle_state']=deepcopy(WILD)
    assert call(a)[0]['review_reason']=='transaction_nonbattle_signal_conflict'

def test_verified_turn_before_opening_start():
    a=setup();a[0].memory.facing=4
    assert call(a)[0]['available_actions']==['down','wait']
    assert not tx._CONTROLLERS
    a[0].memory.facing=0
    assert call(a)[0]['available_actions']==['start','wait']


@pytest.mark.parametrize('bad',[{'cells':[[' ']*20 for _ in range(18)]},
    text_at((1,0,'YES')),text_at((1,0,'NO'))])
def test_turn_cannot_use_legacy_or_polluted_world(bad):
    a=setup();a[0].memory.facing=4
    assert call(a,bad)[0]['review_reason']=='flute_turn_requires_verified_overworld'
    assert not tx._CONTROLLERS

def test_raw_wild_signal_does_not_skip_pure_verified_use_or_complete():
    a=setup();call(a);a[1]['frame']=2;a[1]['phase']='battle_menu';a[1]['battle_state']=deepcopy(WILD)
    result,next_id=call(a,wild_hud())
    assert result['phase']=='campaign_review' and next_id=='wake'
    assert not result.get('field_move_complete')

def test_pure_handoff_is_waking_receipt_and_next_unsupported_capture_pauses(monkeypatch):
    class Fake:
        error=None
        def __init__(self,*a):pass
        def context(self,*a,**k):
            return {'phase':'poke_flute_handoff','available_actions':['wait'],
                    'poke_flute_handoff':True,'captured':False,'capture_complete':False}
    monkeypatch.setattr(tx.poke_flute,'PokeFluteController',Fake)
    a=setup();result,next_id=call(a)
    assert result['field_move_kind']=='poke_flute_woke_not_captured'
    assert result['field_move_complete'] and not result['captured'] and not result['capture_complete']
    assert next_id=='catch-review'
    result,_=tx.context(*a,next_id,text_at(),{})
    assert result['review_reason']=='unsupported_explicit_transaction'


@pytest.mark.parametrize('error',['visible_tile_alignment_incomplete','visible_display_disabled'])
def test_known_wild_visual_transition_only_waits_with_small_budget(error):
    a=setup();call(a);c=tx._CONTROLLERS['wake']
    c.used=c.played_confirmed=c.seen_rage=True
    a[1]['battle_state']=deepcopy(WILD);a[1]['phase']='battle_animation'
    t=text_at();t.update(read_valid=False,alignment_verified=False,read_error=error)
    for _ in range(25):
        result,next_id=call(a,t)
        assert result['available_actions']==['wait'] and next_id=='wake'
        assert not result.get('field_move_complete')
    assert call(a,t)[0]['review_reason']=='flute_visual_transition_wait_exhausted'


@pytest.mark.parametrize('change',[lambda c,t,b:setattr(c,'seen_rage',False),
    lambda c,t,b:t.update(read_error='visible_tile_getter_failed'),
    lambda c,t,b:b.update(opponent_species='PIDGEY')])
def test_unproven_or_getter_failure_transition_still_reviews(change):
    a=setup();call(a);c=tx._CONTROLLERS['wake'];c.used=c.played_confirmed=c.seen_rage=True
    a[1]['battle_state']=deepcopy(WILD);a[1]['phase']='battle_animation'
    t=text_at();t.update(read_valid=False,alignment_verified=False,read_error='visible_tile_alignment_incomplete')
    change(c,t,a[1]['battle_state'])
    assert call(a,t)[0]['review_reason']=='transaction_visible_text_not_verified'
