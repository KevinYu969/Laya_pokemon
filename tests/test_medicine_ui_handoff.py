"""真純controller/getters/native decoder的UI交接，不代替敵回合或生存驗證。"""
from copy import deepcopy
import pytest
from test_battle_medicine_bridge import env, dialog
from laya_pokemon.medicine_ui_handoff import MODE


@pytest.mark.parametrize('item',[18,52])
def test_true_medicine_done_a_and_verified_enemy_move_handoff_without_ending_turn(env,item):
    s=env.make(item);s.step['medicine_ui_handoff']=MODE;s.use();c=s.controller()
    r=s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used FIRE BLAST!'))
    assert r['medicine_ui_complete'] and r['field_move_kind']=='battle-medicine-ui-handoff'
    assert r['enemy_turn_resolved'] is False and r['survival_approved'] is False
    assert c.stage=='retaliation' and c.complete is False and c.error is None
    assert not env.b._active() and s.call() is None


def test_no_opt_in_keeps_existing_full_turn_contract(env):
    s=env.make();s.use()
    r=s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used FIRE BLAST!'))
    assert not r.get('medicine_ui_complete') and env.b._active()


@pytest.mark.parametrize('actual_a',[True,False])
def test_restored_hud_can_handoff_normal_trainer_healing_only_after_actual_a(env,actual_a):
    s=env.make();s.enemy['hp']=49;s.step['medicine_ui_handoff']=MODE;s.use();c=s.controller()
    s.enemy['hp']=149
    r=s.call(dialog(s.player,s.enemy,'BLAINE','used'),previous=['a'] if actual_a else ['wait'])
    assert bool(r.get('medicine_ui_complete')) is actual_a
    if actual_a:assert c.pending['action']=='a' and not env.b._active() and not c.complete


def test_reviewed_trainer_item_handoff_keeps_bound_state_error_and_controller(env):
    s=env.make();s.enemy['hp']=49;s.use();c=s.controller();s.enemy['hp']=149
    cells=dialog(s.player,s.enemy,'BLAINE','used')
    assert s.call(cells)['review_reason']=='battle_medicine_bound_state_changed'
    before=deepcopy(c.__dict__)
    s.step['medicine_ui_handoff']=MODE
    s.step['reviewed_medicine_ui_handoff']=dict(kind='restored_hud_after_medicine_v1',
        owner=c.owner,frame=s.game.frame_count,error='bound_state_changed')
    r=s.call(cells,same_frame=True,previous=['a'])
    assert r['medicine_ui_complete'] and c.__dict__==before
    assert r['retained_controller_error']=='bound_state_changed' and r['enemy_turn_resolved'] is False


def paused_effectiveness(env):
    s=env.make();s.use();c=s.controller()
    s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used FIRE BLAST!'))
    s.p['party'][2]['hp']=35;s.sync()
    lag=lambda state:state['progress']['party'][2].update(hp=155)
    assert s.call(dialog(s.player,s.enemy,'Critical hit!','',True),state_mutate=lag)['available_actions'][0]=='a'
    cells=dialog(s.player,s.enemy,'IT'+chr(0xE000)+' NO')
    cells[14][3]="'s"
    assert s.call(cells,state_mutate=lag)['review_reason']=='battle_medicine_native_decoder_not_verified'
    owner=c.owner
    s.step['medicine_ui_handoff']=MODE
    s.step['reviewed_medicine_ui_handoff']=dict(kind='critical_to_effectiveness_v1',owner=owner,
        frame=s.game.frame_count,error='native_decoder_not_verified')
    return s,c,cells,lag


def test_reviewed_native_effectiveness_handoff_keeps_entire_controller_error_and_budgets(env):
    s,c,cells,lag=paused_effectiveness(env);before=deepcopy(c.__dict__)
    r=s.call(cells,same_frame=True,state_mutate=lag,previous=['a'])
    assert r['reviewed_handoff'] and r['medicine_ui_complete']
    assert r['retained_controller_error']=='native_decoder_not_verified'
    assert c.__dict__==before and not env.b._active()
    assert env.b._BINDINGS[c.owner]['receipt']['enemy_turn_resolved'] is False


@pytest.mark.parametrize('bad',['frame','owner','previous','error','mode','text','inventory'])
def test_reviewed_handoff_refuses_mismatched_evidence_without_clearing_controller(env,bad):
    s,c,cells,lag=paused_effectiveness(env);previous=['a']
    if bad=='frame':s.step['reviewed_medicine_ui_handoff']['frame']-=1
    elif bad=='owner':s.step['reviewed_medicine_ui_handoff']['owner']='foreign'
    elif bad=='previous':previous=['wait']
    elif bad=='error':c.error='call_or_time_budget_exhausted'
    elif bad=='mode':s.step.pop('medicine_ui_handoff')
    elif bad=='text':cells[14][4]='X'
    else:next(i for i in s.p['inventory'] if i['item']==18)['quantity']-=1
    before=deepcopy(c.__dict__)
    r=s.call(cells,same_frame=True,state_mutate=lag,previous=previous)
    assert r['phase']=='campaign_review' and not r.get('medicine_ui_complete')
    assert c.__dict__==before and env.b._active()
