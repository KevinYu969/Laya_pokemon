"""只測橋接的fake controller/decoder/SDK；不宣稱真購物controller通過。"""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType,SimpleNamespace

import pytest
import laya_pokemon

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-cinnabar-purchase-bridge-20261024'


def source_path(test_path):
    p=Path(test_path).resolve()
    if p==STAGE/'test_cinnabar_purchase_bridge.py':return STAGE/'cinnabar_purchase_bridge.py'
    if p==ROOT/'tests/test_cinnabar_purchase_bridge.py':return ROOT/'src/laya_pokemon/cinnabar_purchase_bridge.py'
    raise RuntimeError('只允許本專案指定staged或正式tests位置')


BRIDGE_PATH=source_path(__file__)


def load(fake,existing=None):
    had=hasattr(laya_pokemon,'cinnabar_purchase');prior=getattr(laya_pokemon,'cinnabar_purchase',None)
    real_reload=importlib.reload
    try:
        laya_pokemon.cinnabar_purchase=fake
        importlib.reload=lambda m:m if m is fake else real_reload(m)
        name='laya_pokemon._isolated_cinnabar_purchase_bridge'
        spec=importlib.util.spec_from_file_location(name,BRIDGE_PATH)
        m=existing or importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
        return m
    finally:
        importlib.reload=real_reload
        if had:laya_pokemon.cinnabar_purchase=prior
        else:del laya_pokemon.cinnabar_purchase


class Memory:
    def __init__(self):
        self.values={0xD35E:172,0xC109:8,0xD361:5,0xD362:2};self.reads=[];self.hook=None
    def __getitem__(self,address):
        self.reads.append(address);v=self.values[address]
        return self.hook(address,v)if self.hook else v
    def __setitem__(self,*a):raise AssertionError('memory writes forbidden')


@pytest.fixture
def env(monkeypatch):
    fake=ModuleType('laya_pokemon.cinnabar_purchase')
    # 只是假API常數，不是橋接另寫價格或從真遊戲取得的資料。
    common=dict(map_id=172,player_x=2,player_y=5,facing='left',quantity=10)
    fake.HYPER_POTION_INTENT=dict(common,kind='buy_hyper_potion',item=18,unit_price=1500,total_price=15000)
    fake.FULL_HEAL_INTENT=dict(common,kind='buy_full_heal',item=52,unit_price=600,total_price=6000)
    class Controller:
        instances=[]
        def __init__(self,intent,**caps):
            self.intent=deepcopy(intent);self.caps=caps;self.baseline={'original':True}
            self.started=3.;self.calls=0;self.waits=7;self.error=None;self.pending={'retained':True}
            self.result=dict(phase='mart_menu',objective='Wait.',available_actions=['wait'],original_receipt='kept')
            self.args=None;Controller.instances.append(self)
        def context(self,text,progress,**kwargs):
            self.calls+=1;self.args=(text,progress,kwargs)
            return deepcopy(self.result)
    fake.CinnabarPurchaseController=Controller
    b=load(fake)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx,'verified_blank_transaction_world',lambda t,g:isinstance(t,dict)and t.get('closed')is True and g.get('verified')is True)
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda t,g:t.get('ready',False)if isinstance(t,dict)else False)
    monkeypatch.setattr(b,'_sdk_constants',lambda:SimpleNamespace(MAPS={'cinnabar_mart':172}))
    monkeypatch.setattr(b.time,'monotonic',lambda:20.)
    m=Memory();game=SimpleNamespace(memory=m,frame_count=10)
    step=dict(id='buy',kind='interact',mechanic=b.MECHANIC,map_id=172,target=[2,5],face='left',purchase_intent=deepcopy(fake.HYPER_POTION_INTENT))
    state=dict(frame=10,location=dict(map_id=172,x=2,y=5),progress={'test_progress':'original'},
        battle_state=dict(kind='none',active=False,raw=0,observation_frame=10))
    return SimpleNamespace(b=b,fake=fake,game=game,m=m,step=step,plan=dict(steps=[step,dict(id='after',kind='move')]),state=state,
        text=dict(ready=True,closed=True,observation_frame=10),grid=dict(verified=True),previous=['left','wait'])


def call(e,step_id='buy'):
    before=deepcopy((e.state,e.plan,e.text,e.grid,e.previous,e.m.values))
    out=e.b.context(e.game,e.state,e.plan,step_id,e.text,e.grid,e.previous)
    assert (e.state,e.plan,e.text,e.grid,e.previous,e.m.values)==before
    return out


@pytest.mark.parametrize('kind',['HYPER_POTION_INTENT','FULL_HEAL_INTENT'])
def test_exact_api_caps_true_previous_location_copy_and_full_context_passthrough(env,kind):
    e=env;e.step['purchase_intent']=deepcopy(getattr(e.fake,kind));out,sid=call(e)
    assert sid=='buy'and out['original_receipt']=='kept'
    c=e.b._CONTROLLER['buy'];t,p,args=c.args
    assert t is e.text and p is e.state['progress']and args['battle_state']is e.state['battle_state']
    assert args['previous']is e.previous and args['frame']==10 and args['now']==20.
    assert args['location']==dict(map_id=172,x=2,y=5,facing='left',facing_raw=8)
    assert args['location']is not e.state['location']and args['overworld_ready']is True
    assert args['intent']==getattr(e.fake,kind)and c.caps==dict(max_calls=240,max_seconds=60,max_waits=30)
    assert e.m.reads==[0xD35E,0xC109,0xD361,0xD362]*2


@pytest.mark.parametrize('key,value',[('kind','move'),('map_id',True),('map_id',171),('target',[2.,5]),
    ('target',[2,4]),('target',(2,5)),('face','up'),('event','done'),('item',18),
    ('next_map',172),('terminal',True),('badge',64),('await_script_event',True)])
def test_wrong_step_or_generic_shortcut_cannot_create_controller(env,key,value):
    e=env;e.step[key]=value;out,_=call(e)
    assert out['available_actions']==['wait']and out['phase']=='campaign_review'
    assert not e.b._CONTROLLER and not e.b._BINDINGS and not e.fake.CinnabarPurchaseController.instances


@pytest.mark.parametrize('key,value',[('quantity',True),('quantity',1),('quantity',10.),('item',True),
    ('item',[]),('total_price',0),('unit_price',600),('unknown','extra')])
def test_intent_all_keys_types_and_values_must_match_imported_constant(env,key,value):
    e=env;e.step['purchase_intent'][key]=value
    assert call(e)[0]['review_reason'].endswith('explicit_intent_unverified')and not e.b._BINDINGS


@pytest.mark.parametrize('fault',['overlay','not_ready','nonbool_ready','wrong_location','float_location','bad_battle','bad_frame','bad_previous','packet_frame'])
def test_initial_unknowns_never_bind_or_emit_field_action(env,fault):
    e=env
    if fault=='overlay':e.text['closed']=False
    elif fault=='not_ready':e.text['ready']=False
    elif fault=='nonbool_ready':e.text['ready']=1
    elif fault=='wrong_location':e.state['location']['y']=4
    elif fault=='float_location':e.state['location']['x']=2.
    elif fault=='bad_battle':e.state['battle_state']['raw']=True
    elif fault=='bad_frame':e.state['frame']=True
    elif fault=='bad_previous':e.previous=['A']
    else:e.text['observation_frame']=999
    out,_=call(e);assert out['phase']=='campaign_review'and out['available_actions']==['wait']
    assert not e.b._CONTROLLER and not e.b._BINDINGS


@pytest.mark.parametrize('address',[0xD35E,0xC109,0xD361,0xD362])
@pytest.mark.parametrize('bad',[False,0.0])
def test_second_sample_false_or_float_always_unknown(env,address,bad):
    e=env;e.m.hook=lambda a,v:bad if a==address and len(e.m.reads)>4 else v
    assert call(e)[0]['phase']=='campaign_review'and not e.b._BINDINGS


@pytest.mark.parametrize('fault',['sdk_missing','sdk_bool','sdk_wrong','sdk_throw','getter_throw','frame_change','wrong_facing'])
def test_getter_sdk_stance_and_frame_fail_closed(env,monkeypatch,fault):
    e=env
    if fault.startswith('sdk_'):
        class Broken:
            @property
            def MAPS(self):raise OSError('test')
        sdk={'sdk_missing':SimpleNamespace(MAPS={}), 'sdk_bool':SimpleNamespace(MAPS={'cinnabar_mart':True}),
             'sdk_wrong':SimpleNamespace(MAPS={'cinnabar_mart':171}),'sdk_throw':Broken()}[fault]
        monkeypatch.setattr(e.b,'_sdk_constants',lambda:sdk)
    elif fault=='getter_throw':
        def broken(*a):raise RuntimeError('test')
        e.m.hook=broken
    elif fault=='frame_change':
        def changing(a,v):
            if len(e.m.reads)==8:e.game.frame_count=11
            return v
        e.m.hook=changing
    else:e.m.values[0xC109]=4
    assert call(e)[0]['phase']=='campaign_review'and not e.b._BINDINGS


def test_active_and_completed_owner_cannot_change_intent_or_reset_original_controller(env):
    e=env;call(e);c=e.b._CONTROLLER['buy'];base=c.baseline;pending=c.pending
    assert call(e,'after')[0]['review_reason'].endswith('owner_changed')
    e.b._COMPLETED.add('buy');e.step['purchase_intent']=deepcopy(e.fake.FULL_HEAL_INTENT)
    assert call(e)[0]['review_reason'].endswith('intent_changed')
    assert e.b._CONTROLLER['buy']is c and c.baseline is base and c.pending is pending
    assert (c.started,c.calls,c.waits)==(3.,1,7)


@pytest.mark.parametrize('lost',['controller','binding'])
def test_existing_transaction_state_loss_never_constructs_fresh_baseline(env,lost):
    e=env;call(e)
    (e.b._CONTROLLER if lost=='controller'else e.b._BINDINGS).clear()
    assert call(e)[0]['review_reason'].endswith('controller_or_binding_lost')
    assert len(e.fake.CinnabarPurchaseController.instances)==1


def test_reload_keeps_instance_error_pending_baseline_and_budget(env,monkeypatch):
    e=env;call(e);c=e.b._CONTROLLER['buy'];base=c.baseline;pending=c.pending
    c.error='sticky';c.calls=29;c.waits=17;e.b=load(e.fake,e.b)
    monkeypatch.setattr(e.b,'_sdk_constants',lambda:SimpleNamespace(MAPS={'cinnabar_mart':172}))
    assert e.b._CONTROLLER['buy']is c and c.baseline is base and c.pending is pending
    assert (c.started,c.calls,c.waits,c.error)==(3.,29,17,'sticky')
    c.result=dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],review_reason='pure_sticky')
    assert call(e)[0]['review_reason']=='pure_sticky'
    assert (c.started,c.calls,c.waits,c.error)==(3.,30,17,'sticky')


@pytest.mark.parametrize('flag',[True,False,1])
def test_only_exact_pure_complete_receipt_advances_and_preserves_full_result(env,flag):
    e=env;call(e);c=e.b._CONTROLLER['buy'];c.result['cinnabar_purchase_complete']=flag
    out,sid=call(e);assert out['original_receipt']=='kept'
    if flag is True:
        assert sid=='after'and out['field_move_complete']is True and out['field_move_kind']=='cinnabar-purchase'
        assert 'buy'in e.b._COMPLETED
    else:assert sid=='buy'and not e.b._COMPLETED and 'field_move_complete'not in out


@pytest.mark.parametrize('where',['stage','formal','unknown'])
def test_only_designated_stage_or_formal_source_path_is_loadable(where):
    if where=='stage':assert source_path(STAGE/'test_cinnabar_purchase_bridge.py')==STAGE/'cinnabar_purchase_bridge.py'
    elif where=='formal':assert source_path(ROOT/'tests/test_cinnabar_purchase_bridge.py')==ROOT/'src/laya_pokemon/cinnabar_purchase_bridge.py'
    else:
        with pytest.raises(RuntimeError):source_path(ROOT/'tests/cinnabar_purchase_bridge.py')
