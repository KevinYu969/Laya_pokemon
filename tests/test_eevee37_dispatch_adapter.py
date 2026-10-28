"""Real readonly SDK readers + actual normal dispatcher on a synthetic native."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'src/laya_pokemon/eevee37_dispatch_adapter.py'
spec=importlib.util.spec_from_file_location('laya_pokemon.eevee37_dispatch_adapter',SOURCE)
a=importlib.import_module('laya_pokemon.eevee37_dispatch_adapter')
assert Path(a.__file__).resolve()==SOURCE.resolve()
h=importlib.import_module('test_league_training_batch')
levelup=importlib.import_module('laya_pokemon.levelup_moves')
game=importlib.import_module('laya_pokemon.game')
proof=levelup.eevee37_learning_proof
assert Path(h.__file__).resolve()==(ROOT/'tests/test_league_training_batch.py').resolve()
for m,name in [(levelup,'levelup_moves.py'),(game,'game.py'),(proof,'eevee37_learning_proof.py')]:
    assert Path(m.__file__).resolve()==(ROOT/'src/laya_pokemon'/name).resolve()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    f=game.advance_action;code=f.__code__;defaults=f.__defaults__;annotations=dict(f.__annotations__)
    for name in ('_CONTEXT','_REQUEST','_HOOK','_ERROR'):monkeypatch.setattr(a,name,None)
    monkeypatch.setattr(proof,'_ACTIVE',None);monkeypatch.setattr(proof,'_DONE',{})
    monkeypatch.setattr(levelup,'_SESSION',None);monkeypatch.setattr(levelup.snorlax_harden_skip,'_SESSION',None)
    for k,v in [('_CONTROLLERS',{}),('_BINDINGS',{}),('_OWNERS',{}),('_ERRORS',{}),('_COMPLETED',set()),('_REVIEWED_ABORTS',{})]:
        monkeypatch.setattr(h.bridge,k,v)
    yield
    f.__code__=code;f.__defaults__=defaults;f.__annotations__=annotations
    game.__dict__.pop(a._ORIGINAL_NAME,None);game.__dict__.pop(a._CALLBACK_NAME,None)


class Native(h.FakePyBoy):
    def __init__(self):
        super().__init__();self.events=[];self.raise_tick=None
        self.screen.ndarray=h.np.zeros((144,160,4),dtype=h.np.uint8)
    def button_press(self,button):self.events.append(('press',button))
    def button_release(self,button):self.events.append(('release',button))
    def tick(self,*args):
        if self.raise_tick:raise self.raise_tick
        self.frame_count+=1;self.events.append(('tick',self.frame_count));return True


def setup():
    s=h.Session();s.plan['training_job']=a.JOB;s.pb=Native();address=h.sdk.PARTY_MONS_ADDRESS
    # Start real owner at36, then its wild causes the exact natural37 event.
    for index in (0,1):
        s.pb.memory.values[address+index*h.sdk.PARTY_MON_SIZE+0x21]=36;s.pb.experience(index,36**3)
    lapras=address+4*h.sdk.PARTY_MON_SIZE
    s.pb.memory.values[lapras+11]=85;s.pb.memory.values[lapras+32]=15
    s.call();s.advance(wild=True)
    s.pb.memory.values[address+0x21]=37;s.pb.experience(0,37**3);s.pb.frame_count+=40
    from laya_pokemon.owned_field_medicine import PEER_NAMES
    peers={k:({s.step_id} if k=='league_training_batch' else set()) for k in PEER_NAMES}
    return s,peers


def register(s,peers):
    return a.register_trusted_context(s.pb,s.plan,s.step_id,batch_bridge=h.bridge,
        levelup_module=levelup,peer_owners=peers)


def draw(s,*entries):
    s.pb.memory.values[0xFF40]=0xB1;s.pb.tilemap_window.cells.clear()
    reverse={v:k for k,v in h.sdk.POKEMON_TEXT_DECODING.items()}
    for x,y,value in entries:
        for i,ch in enumerate(value):s.pb.tilemap_window.cells[(x+i,y)]=reverse[ch]
    return h.read_visible_text(s.pb),h.read_progress(s.pb,h.sdk)


def trying(s):return draw(s,(1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼'))


def offered(s,peers):
    assert register(s,peers)
    text,progress=trying(s);binding=a.current_binding(text,progress);assert binding
    result=levelup.context(dict(text,observation_frame=binding['frame']),progress,learning_binding=binding)
    a.remember_learning_hint(binding,result)
    assert a.review_context() is None and result['learning_request_id']
    return text,progress,binding,result


def test_current_binding_double_real_native_getters_and_preserves_unframed_caller_text():
    s,peers=setup();assert register(s,peers);text,progress=trying(s);before=deepcopy((text,progress))
    binding=a.current_binding(text,progress)
    assert binding['native_owner'] is s.pb and binding['frame']==s.pb.frame_count
    assert binding['owner_step']==s.step_id and binding['battle_state']['raw']==1
    assert binding['controller_source_sha256']==a.CONTROLLER_SHA and (text,progress)==before
    assert 'observation_frame' not in text and a.review_context() is None


def test_first_missing_binding_same_frame_takeover_creates_one_original_proof_without_clearing_errors():
    s,peers=setup();text,progress=trying(s)
    missing=levelup.context(dict(text,observation_frame=s.pb.frame_count),progress)
    assert missing['review_reason']=='eevee37_trusted_dispatch_binding_missing' and proof._ACTIVE is None and levelup._SESSION is None
    assert register(s,peers)
    result=a.first_missing_binding_takeover(missing,text,progress)
    assert result['learning_request_id'] and proof._ACTIVE is not None and a._REQUEST['proof'] is proof._ACTIVE
    original=proof._ACTIVE;original.error='existing_error'
    assert a.first_missing_binding_takeover(missing,text,progress)['phase']=='strategy_review'
    assert proof._ACTIVE is original and original.error=='existing_error'


def test_hook_keeps_original_function_identity_signature_and_acks_only_after_success():
    s,peers=setup();text,progress,binding,result=offered(s,peers)
    function=game.advance_action;signature=str(a.inspect.signature(function));pending=proof._ACTIVE.pending
    assert a.install_actual_dispatch_hook(s.pb,function) and a.install_actual_dispatch_hook(s.pb,function)
    before=s.pb.frame_count
    assert function(s.pb,'a',2,1)==3
    assert game.advance_action is function and str(a.inspect.signature(function))==signature
    assert pending['ack']['executed_frame']==before+3 and proof._ACTIVE.acks[-1]==pending['ack']
    assert s.pb.events[0]==('press','a') and ('release','a') in s.pb.events and a._REQUEST is None


def test_wait_and_other_native_run_original_dispatch_without_any_ack():
    s,peers=setup();offered(s,peers);assert a.install_actual_dispatch_hook(s.pb,game.advance_action)
    pending=proof._ACTIVE.pending;other=Native()
    assert game.advance_action(s.pb,'wait',1,0)==1 and pending['ack'] is None
    assert game.advance_action(other,'a',1,0)==1 and pending['ack'] is None
    assert a.review_context() is None


def test_original_dispatch_exception_is_unchanged_and_never_acknowledged():
    s,peers=setup();offered(s,peers);assert a.install_actual_dispatch_hook(s.pb,game.advance_action)
    error=RuntimeError('synthetic original tick failure');s.pb.raise_tick=error
    with pytest.raises(RuntimeError) as caught:game.advance_action(s.pb,'a',1,0)
    assert caught.value is error and proof._ACTIVE.pending['ack'] is None and proof._ACTIVE.acks==[]
    assert s.pb.events[-1]==('release','a') and a.review_context() is None


def test_unoffered_or_different_action_cannot_ack_original_pending_request():
    s,peers=setup();offered(s,peers);assert a.install_actual_dispatch_hook(s.pb,game.advance_action)
    game.advance_action(s.pb,'down',1,0)
    assert proof._ACTIVE.pending['ack'] is None and a.review_context()['phase']=='strategy_review'


def test_same_frame_wait_hint_clears_dispatch_ticket_and_duplicate_callback_cannot_ack_twice():
    s,peers=setup();text,progress,binding,result=offered(s,peers)
    same=levelup.context(dict(text,observation_frame=binding['frame']),progress,learning_binding=binding)
    a.remember_learning_hint(binding,same);assert same['available_actions']==['wait'] and a._REQUEST is None
    assert a.install_actual_dispatch_hook(s.pb,game.advance_action)
    game.advance_action(s.pb,'a',1,0)
    assert proof._ACTIVE.pending['ack'] is None and proof._ACTIVE.acks==[]


def test_changed_plan_native_binding_or_peer_inventory_fails_closed_before_parser():
    s,peers=setup();assert register(s,peers);text,progress=trying(s)
    h.bridge._OWNERS[s.step_id]=Native()
    assert a.current_binding(text,progress) is None and a.review_context()['phase']=='strategy_review'
    assert proof._ACTIVE is None
    # A fresh fixture context cannot hide another peer even with identical RAM.
    a._CONTEXT=a._ERROR=None;h.bridge._OWNERS[s.step_id]=s.pb;peers['tm24_teaching']={'peer'}
    assert not register(s,peers) and proof._ACTIVE is None


def test_changed_source_unknown_preexisting_hook_or_foreign_function_is_rejected(monkeypatch):
    s,peers=setup();assert register(s,peers)
    original_sha=a.ADVANCE_SOURCE_SHA;monkeypatch.setattr(a,'ADVANCE_SOURCE_SHA','0'*64)
    assert not a.install_actual_dispatch_hook(s.pb,game.advance_action) and a._HOOK is None
    monkeypatch.setattr(a,'ADVANCE_SOURCE_SHA',original_sha);a._ERROR=None
    game.__dict__[a._CALLBACK_NAME]=object()
    assert not a.install_actual_dispatch_hook(s.pb,game.advance_action) and a._HOOK is None


def test_hook_and_registered_original_objects_survive_adapter_reload_without_reinstallation():
    s,peers=setup();offered(s,peers);assert a.install_actual_dispatch_hook(s.pb,game.advance_action)
    context=a._CONTEXT;hook=a._HOOK;request=a._REQUEST;function=game.advance_action
    spec.loader.exec_module(a)
    assert a._CONTEXT is context and a._HOOK is hook and a._REQUEST is request
    assert a.install_actual_dispatch_hook(s.pb,function)
    game.advance_action(s.pb,'a',1,0)
    assert request['pending']['ack'] and a.review_context() is None


def test_wait_then_fresh_reoffer_acks_only_the_later_actual_action():
    s,peers=setup();text,progress,binding,result=offered(s,peers)
    assert a.install_actual_dispatch_hook(s.pb,game.advance_action)
    pending=proof._ACTIVE.pending;requested=pending['frame']
    game.advance_action(s.pb,'wait',1,0)
    text,progress=trying(s);binding=a.current_binding(text,progress)
    result=levelup.context(dict(text,observation_frame=binding['frame']),progress,learning_binding=binding)
    a.remember_learning_hint(binding,result)
    assert proof._ACTIVE.pending is pending and pending['ack'] is None
    game.advance_action(s.pb,'a',1,0)
    assert pending['ack']['requested_frame']==requested and pending['ack']['executed_frame']==requested+2
    assert len(proof._ACTIVE.acks)==1 and a.review_context() is None


def test_real_observer_first_missing_review_then_trusted_parent_handoff_and_next_observe_do_not_poison():
    s,peers=setup();text,progress=trying(s)
    state=game.observe(s.pb,'Synthetic source learning.','KEVIN',(),True,'BULBASAUR','first_gym')
    assert state['review_reason']=='eevee37_trusted_dispatch_binding_missing' and proof._ACTIVE is None
    assert register(s,peers) and a.install_actual_dispatch_hook(s.pb,game.advance_action)
    hint=a.first_missing_binding_takeover(state,text,progress)
    assert hint['learning_request_id'] and proof._ACTIVE.error is None
    handed=h.bridge.context(s.pb,{**state,**hint},s.plan,s.step_id,text,None,s.previous,now=s.now+.1)
    assert handed[0]['training_batch_battle_delegate']=='existing_battle' and handed[0]['phase']=='learning_menu'
    game.advance_action(s.pb,'a',1,0)
    assert len(proof._ACTIVE.acks)==1
    next_state=game.observe(s.pb,'Synthetic source learning.','KEVIN',(),True,'BULBASAUR','first_gym')
    assert next_state['phase']=='learning_menu' and next_state['available_actions']==['wait']
    assert proof._ACTIVE.error is None and a.review_context() is None
