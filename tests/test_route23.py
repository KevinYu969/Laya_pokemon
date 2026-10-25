"""可攜合成契約測試；不讀ROM/state，不開遊戲，不呼叫任何模型。"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest
import laya_pokemon

# stage只加此精確資料夾；移入tests後只從正式src載入，沒有尋找ignored來源。
HERE=Path(__file__).resolve().parent
if HERE.name=='staged-route23-surf-20261025' and HERE.parent.name=='.local':
    laya_pokemon.__path__.insert(0,str(HERE))
elif HERE.name!='tests':raise RuntimeError('測試只能位於固定stage或正式tests')
from laya_pokemon import route23_surf as surf,route23_water as water,route23_bridge as bridge
from laya_pokemon.observation import PROFILE as TEXT
from laya_pokemon.progress import PROFILE as PROGRESS
from laya_pokemon.rocket_movement import MOVEMENT_PROFILE


def progress():
    data=[(19,'LAPRAS',39,160,[57,34,58,109],[15,15,10,10]),
          (132,'SNORLAX',41,198,[70,133,156,34],[15,20,10,15]),
          (102,'EEVEE',35,90,[33,28,98,39],[35,15,30,30]),
          (154,'VENUSAUR',35,111,[75,15,73,22],[25,30,10,10]),
          (35,'FEAROW',37,114,[64,65,19,31],[35,20,15,20]),
          (7,'NIDOKING',36,121,[61,57,30,40],[20,15,25,35])]
    return dict(profile=PROGRESS,initialization_candidate=True,party_read_valid=True,party_count=6,
        party=[dict(species=s,species_name=n,level=l,hp=h,max_hp=h,exp=80000,status=0,moves=m,pp=pp) for s,n,l,h,m,pp in data],
        inventory=[dict(item=18,quantity=10),dict(item=52,quantity=10)],money=37985,badges_raw=255,player_name_raw='KEVIN')


def text(rows=None,window=False):
    cells=[list(row) for row in (rows if rows is not None else surf._blank())]
    visible=[(y,''.join(row).rstrip()) for y,row in enumerate(cells) if re.search(r'[A-Za-z0-9]{2,}',''.join(row))][:12]
    return dict(profile=TEXT,read_valid=True,alignment_verified=True,read_error=None,window_visible=window,
                cells=cells,lines=[s for _,s in visible],line_rows=[y for y,_ in visible])


def grid(loc,frame):
    tiles=[[0x2c]*20 for _ in range(144)];walk=[[1]*20 for _ in range(144)]
    for _,x,y,mode,tile in water.PATH:
        tiles[y][x]=tile;walk[y][x]=int(mode==0)
    cells=sorted(([x,y] for y in range(144) for x in range(20)),key=lambda p:(abs(p[0]-loc['x'])+abs(p[1]-loc['y']),p[1],p[0]))[:20]
    return dict(tileset_id=23,observation_frame=frame,verified_location=[loc[k] for k in ('map_id','x','y')],
                tiles=tiles,walkable=walk,visible_verified_cells=cells,screen_cells_verified=len(cells))


def signal(loc,frame,mode,flags=7,script=0,active=False):
    return dict(profile=surf.PROFILE,source_commit=surf.SOURCE_COMMIT,read_valid=True,read_error=None,
        observation_frame=frame,location=deepcopy(loc),mode=mode,facing='up',facing_raw=4,
        battle_raw=int(active),badges_raw=255,guard_flags=flags,route23_script=script,
        npc_positions=tuple((i+1,x,y) for i,(x,y) in enumerate(surf.NPC_POSITIONS)))


def movement(frame):
    return dict(profile=MOVEMENT_PROFILE,source_commit=surf.SOURCE_COMMIT,read_valid=True,read_error=None,
        observation_frame=frame,simulated_remaining=0,joy_ignore=0,walk_counter=0,movement_flags=0,spinning=False)


class Surf:
    def __init__(self):
        self.c=surf.Route23SurfController();self.p=progress();self.f=100;self.now=0;self.loc=deepcopy(surf.START);self.mode=0
    def call(self,rows=None,prev=('wait',),ready=False,**changes):
        self.f+=40;self.now+=.1
        kwargs=dict(location=self.loc,battle_state=dict(kind='none',active=False,raw=0,observation_frame=self.f),
            grid=grid(self.loc,self.f),signal=signal(self.loc,self.f,self.mode),movement=movement(self.f),
            frame=self.f,previous=prev,now=self.now,overworld_ready=ready)
        kwargs.update(changes)
        return self.c.context(text(rows,not ready),self.p,**kwargs)
    def menu(self):
        assert self.call(ready=True)['available_actions'][0]=='start'
        assert self.call(self.c._start(4),('start',))['available_actions'][0]=='a'
        assert self.call(self.c._party(0),('a',))['available_actions'][0]=='a'
        assert self.call(self.c._field(10),('a',))['available_actions'][0]=='a'
    def ack(self):
        self.menu();self.mode=2
        assert self.call(self.c._prompt(True),('a',))['available_actions'][0]=='a'
        return self.call(prev=('a',),ready=True)


def review(result):assert result['phase']=='campaign_review' and result['available_actions']==['wait']


def test_lapras_selected_despite_two_surf_users_and_only_two_fresh_native_water_frames_complete():
    s=Surf();original=deepcopy(s.p);assert s.ack()['available_actions']==['wait']
    assert s.c.target_index==0 and s.p['party'][5]['moves'][1]==57
    s.loc=deepcopy(surf.LANDING)
    assert not s.call(ready=True)['surf_entry_complete']
    assert s.call(ready=True)['surf_entry_complete'] and s.p==original


@pytest.mark.parametrize('fault',['pallet_intent','wrong_surf_user','wrong_facing','tileset0','fake_land_water','invisible_water','badge7','wrong_roster','hp','pp','money','npc','script','guard_event'])
def test_surf_binding_and_unchanged_six_party_source_world_faults(fault):
    s=Surf()
    if fault in ('pallet_intent','wrong_surf_user'):
        intent=deepcopy(surf.ROUTE23_SURF_INTENT)
        intent['kind' if fault=='pallet_intent' else 'species']='pallet_surf' if fault=='pallet_intent' else 7
        with pytest.raises(ValueError):surf.Route23SurfController(intent)
        return
    if fault in ('hp','pp','money'):
        s.call(ready=True)
        if fault=='hp':s.p['party'][0]['hp']-=1
        elif fault=='pp':s.p['party'][0]['pp'][0]-=1
        else:s.p['money']-=1
        review(s.call(s.c._start(4),('start',)));return
    f=s.f+40;sig=signal(s.loc,f,0);g=grid(s.loc,f)
    if fault=='wrong_facing':sig.update(facing='down',facing_raw=0)
    elif fault=='tileset0':g['tileset_id']=0
    elif fault=='fake_land_water':g['walkable'][103][10]=1
    elif fault=='invisible_water':g['visible_verified_cells'].remove([10,103]);g['screen_cells_verified']-=1
    elif fault=='badge7':s.p['badges_raw']=127;sig['badges_raw']=127
    elif fault=='wrong_roster':s.p['party'].reverse()
    elif fault=='npc':sig['npc_positions']=()
    elif fault=='script':sig['route23_script']=2
    else:sig['guard_flags']=3
    review(s.call(ready=True,signal=sig,grid=g))


def test_real_prompt_a_required_and_done_arrow_old_page_is_not_resent():
    s=Surf();s.menu();s.mode=2
    rows=s.c._prompt(False)
    assert s.call(rows,('a',))['available_actions']==['wait'] and not s.c.prompt_ack
    assert s.call(s.c._prompt(True))['available_actions'][0]=='a'
    assert s.call(s.c._prompt(True),('a',))['available_actions']==['wait'] and s.c.prompt_ack
    assert s.call(rows)['available_actions']==['wait']
    s=Surf();s.menu();s.mode=2;s.call(s.c._prompt(True),('a',));s.loc=deepcopy(surf.LANDING)
    review(s.call(ready=True))


def guard_rows(badge,page,arrow=True):
    pairs=(('You can pass here','only if you have'),('only if you have','the '+badge+'!'),
           ('Oh! That is the',badge+'!'),('OK then! Please,','go right ahead!'))
    rows=[list(r) for r in surf._blank()]
    for y,line in zip((14,16),pairs[page]):surf._put(rows,1,y,line)
    if arrow:surf._put(rows,18,16,'▼')
    return rows


class Water:
    def __init__(self,flags=7):
        self.c=water.Route23WaterController();self.p=progress();self.f=0;self.now=0;self.flags=flags
    def call(self,index=0,prev=('wait',),*,active=False,rows=None,script=0,same=False,now=None,mutate=None):
        if not same:self.f+=40
        self.now=self.now+.1 if now is None else now
        node=water.PATH[index];loc=dict(zip(('map_id','x','y'),node[:3]))
        st=dict(frame=self.f,location=loc,progress=deepcopy(self.p),text=text(rows,rows is not None),
                battle_state=dict(raw=int(active),kind='wild' if active else 'none',active=active,observation_frame=self.f))
        args=dict(grid=grid(loc,self.f),signal=signal(loc,self.f,node[3],self.flags,script,active),movement=movement(self.f),previous=prev,now=self.now)
        if mutate:mutate(st,args)
        before=deepcopy((st,args));r=self.c.context(st,**args);assert (st,args)==before
        return r
    def to(self,end):
        result=self.call()
        for i in range(1,end+1):
            result=self.call(i,(result['available_actions'][0],))
            if (water.PATH[i][1],water.PATH[i][2]) in water.GUARDS and not self.flags&(1<<water.GUARDS[water.PATH[i][1:3]][0]):
                result=self.guard(i)
        return result
    def guard(self,index):
        bit,badge=water.GUARDS[water.PATH[index][1:3]]
        result=self.call(index,rows=guard_rows(badge,0));assert result['available_actions'][0]=='a'
        for page in (1,2):
            result=self.call(index,('a',),rows=guard_rows(badge,page));assert result['available_actions'][0]=='a'
        result=self.call(index,('a',),rows=guard_rows(badge,3,False));assert result['available_actions']==['wait']
        result=self.call(index,rows=guard_rows(badge,3,False));assert result['available_actions'][0]=='a'
        self.flags|=1<<bit
        assert self.call(index,('a',),script=2)['available_actions']==['wait']
        assert self.call(index)['available_actions']==['wait']
        return self.call(index)


def test_full_route_with_both_real_guard_page_transactions_and_two_native_landfall_frames():
    s=Water();original=deepcopy(s.p);r=s.to(len(water.PATH)-1)
    assert not r['route23_water_complete']
    assert s.call(len(water.PATH)-1)['route23_water_complete']
    assert s.flags==31 and s.c.flags==31 and s.p==original and s.c.pending is None and s.c.guard is None
    assert water.PATH[0]==(34,10,103,2,20) and water.PATH[-1]==(34,8,71,0,44)
    assert all(water._direction(a,b) in ('up','left','right') for a,b in zip(water.PATH,water.PATH[1:]))


def test_previously_passed_source_flags_do_not_fabricate_dialogues_or_block_plain_water():
    s=Water(flags=127);assert not s.to(len(water.PATH)-1)['route23_water_complete']
    assert s.call(len(water.PATH)-1)['route23_water_complete'] and s.c.guard is None


@pytest.mark.parametrize('fault',['candidate_only','skip_cell','tileset0','next_invisible','water_walkable','script1','npc','event','party','hp0'])
def test_water_source_real_previous_world_party_and_script_fail_closed(fault):
    s=Water(flags=127)
    def mutate(st,args):
        if fault=='candidate_only':args['previous']=('wait',)
        elif fault=='skip_cell':st['location']['y']-=1;args['signal']['location']['y']-=1
        elif fault=='tileset0':args['grid']['tileset_id']=0
        elif fault=='next_invisible':args['grid']['visible_verified_cells'].remove([10,101]);args['grid']['screen_cells_verified']-=1
        elif fault=='water_walkable':args['grid']['walkable'][102][10]=1
        elif fault=='script1':args['signal']['route23_script']=1
        elif fault=='npc':args['signal']['npc_positions']=()
        elif fault=='event':args['signal']['guard_flags']=63
        elif fault=='party':st['progress']['party'][0]['pp'][0]-=1
        else:st['progress']['party'][2]['hp']=0
    s.call();r=s.call(1,('up',),mutate=mutate)
    if fault in ('tileset0','water_walkable'):
        assert r['available_actions']==['wait']
        # 原生轉場只限原owner有限WAIT，不因錯grid完成或另送鍵。
        assert not r['route23_water_complete'];return
    review(r)


def test_pending_owner_survives_wild_and_tail_and_two_closed_return_frames_with_bounded_rebase():
    s=Water(flags=127);s.call();pending=s.c.pending
    assert s.call(1,('up',),active=True)['route23_water_battle_handoff']
    assert s.c.pending is pending and s.c.index==0 and pending['executed']
    s.p['party'][0].update(hp=140,exp=80100);s.p['party'][0]['pp'][0]-=1
    assert s.call(1,('a',),active=True)['route23_water_battle_handoff']
    assert s.call(1,('a',),rows=guard_rows('SOULBADGE',0))['route23_water_battle_handoff']
    assert s.call(1)['available_actions']==['wait'] and s.c.pending is pending
    assert s.call(1)['available_actions']==['up','wait'] and s.c.index==1
    assert s.c.fingerprint[0][0]['hp']==140


def test_later_battle_direction_cannot_backfill_unexecuted_field_key():
    s=Water(flags=127);s.call();review(s.call(1,('wait',),active=True))
    pending=s.c.pending;review(s.call(1,('up',),active=True))
    assert s.c.pending is pending and pending['executed'] is False


@pytest.mark.parametrize('fault',['unknown_page','early_event','wrong_badge','extra_arrow','candidate_only','done_arrow'])
def test_guard_never_skips_unknown_text_or_sets_event_without_true_last_done_a(fault):
    s=Water();idx=next(i for i,n in enumerate(water.PATH) if n[1:3]==(10,96));s.to(idx-1)
    rows=guard_rows('SOULBADGE',0)
    if fault=='unknown_page':surf._put(rows,1,14,'Hello stranger!')
    elif fault=='wrong_badge':rows=guard_rows('MARSHBADGE',2)
    elif fault=='extra_arrow':surf._put(rows,0,0,'▶')
    if fault=='early_event':s.flags|=8
    r=s.call(idx,('up',),rows=rows)
    if fault in ('unknown_page','wrong_badge','extra_arrow','early_event'):review(r);return
    assert r['available_actions'][0]=='a'
    if fault=='candidate_only':review(s.call(idx,('wait',),rows=guard_rows('SOULBADGE',1)));return
    s.call(idx,('a',),rows=guard_rows('SOULBADGE',1))
    s.call(idx,('a',),rows=guard_rows('SOULBADGE',2))
    review(s.call(idx,('a',),rows=guard_rows('SOULBADGE',3,True)))


def test_guard_prefix_and_old_page_only_wait_and_unexpected_native_npc_cannot_complete():
    s=Water();idx=next(i for i,n in enumerate(water.PATH) if n[1:3]==(10,96));s.to(idx-1)
    assert s.call(idx,('up',),rows=guard_rows('SOULBADGE',0))['available_actions'][0]=='a'
    assert s.call(idx,('a',),rows=guard_rows('SOULBADGE',0))['available_actions']==['wait']
    assert s.c.guard['pending']['executed']
    partial=guard_rows('SOULBADGE',1,False);partial[16][1:18]=list('the SOUL'+' '*9)
    assert s.call(idx,rows=partial)['available_actions']==['wait']
    assert s.c.guard['page']==1 and not s.c.guard['pending']


def test_timeout_and_same_frame_conflict_reload_do_not_reset_owner_budget_or_errors():
    s=Water(flags=127);s.call(now=0);old=s.c;pending=s.c.pending
    importlib.reload(water);s.c.__class__=water.Route23WaterController
    assert s.c is old and s.c.pending is pending
    review(s.call(0,now=60.01));assert s.c.pending is pending and s.c.started==0
    t=Water(flags=127);t.call();review(t.call(same=True,mutate=lambda st,args:args['signal'].update(mode=0)))


class Memory:
    def __init__(self,*,changed=None):
        self.values={a:0 for a in surf.ADDRESSES.values()};self.changed=changed;self.count={}
        self.values.update({0xD35E:34,0xD361:104,0xD362:10,0xC109:4,0xD356:255,0xD7ED:7})
        for i,(x,y) in enumerate(surf.NPC_POSITIONS,1):self.values.update({0xC100+16*i:1,0xC200+16*i+5:x+4,0xC200+16*i+4:y+4})
    def __getitem__(self,a):
        self.count[a]=self.count.get(a,0)+1
        return self.values.get(a,0)+(1 if a==self.changed and self.count[a]>1 else 0)
    def __setitem__(self,a,v):raise AssertionError('唯讀getter不可寫RAM')


def sdk():
    return dict(STATUS_FLAGS3_ADDRESS=0xD72D,EVENT_FLAGS_ADDRESS=0xD747,OBTAINED_BADGES_ADDRESS=0xD356,
                MAPS={'route_23':34},BADGES={'soul':4},EVENT_FLAGS={n:0x530+i for i,n in enumerate(surf.GUARD_EVENT_NAMES)})


def test_readonly_getter_verifies_all_source_npcs_seven_events_script_and_current_frame():
    mem=Memory();s=surf.read_surf_observation(SimpleNamespace(frame_count=40,memory=mem),40,sdk())
    assert s['read_valid'] and s['guard_flags']==7 and s['route23_script']==0 and len(s['npc_positions'])==7
    assert s['live_calibrated'] is False
    for address in list(surf.ADDRESSES.values())+[0xC110,0xC215,0xC274]:
        s=surf.read_surf_observation(SimpleNamespace(frame_count=40,memory=Memory(changed=address)),40,sdk())
        assert not s['read_valid'] and s['mode'] is None
    constants=sdk();constants['EVENT_FLAGS']['passed_soulbadge_check']=True
    assert not surf.read_surf_observation(SimpleNamespace(frame_count=40,memory=Memory()),40,constants)['read_valid']


@pytest.fixture
def env(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):monkeypatch.setattr(bridge,name,value)
    monkeypatch.setattr(bridge,'_peer_conflict',lambda:None)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx,'verified_blank_transaction_world',lambda t,g:t.get('ready') is True)
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda t,g:t.get('ready') is True)
    class FakeController:
        def __init__(self,intent):
            self.intent=intent;self.error=None;self.pending={'true':'pending'};self.started=4.;self.calls=0;self.waits=9
            self.result={'phase':'overworld','objective':'Wait.','available_actions':['wait'],'route23_water_battle_handoff':False}
        def context(self,*args,**kwargs):self.calls+=1;self.args=args;self.kwargs=kwargs;return deepcopy(self.result)
    monkeypatch.setattr(bridge.water,'Route23WaterController',FakeController)
    monkeypatch.setattr(bridge.surf,'read_surf_observation',lambda game,frame,sdk:signal(game.loc,frame,2,127))
    monkeypatch.setattr(bridge,'read_rocket_movement',lambda game,observation_frame:movement(observation_frame))
    step=dict(id='route23-water',kind='interact',mechanic='route23_water',map_id=34,target=[10,103],water_intent=deepcopy(water.INTENT))
    state=dict(frame=40,location=dict(map_id=34,x=10,y=103),progress=progress(),phase='battle_menu',objective='Attack the opponent.',available_actions=['a','wait'])
    game=SimpleNamespace(loc=state['location'])
    plan=dict(training_job='route23-source-journey',steps=[step])
    return SimpleNamespace(step=step,state=state,game=game,plan=plan)


def bcall(e,previous=None):return bridge.context(e.game,e.state,e.plan,e.step['id'],{'ready':True},{},['wait'] if previous is None else previous)


def test_bridge_preserves_truthy_actual_battle_context_owner_pending_and_budget(env):
    bcall(env);c=bridge._CONTROLLERS[env.step['id']];pending=c.pending
    c.result['route23_water_battle_handoff']=True
    result,step_id=bcall(env,['up'])
    assert result['phase']=='battle_menu' and result['objective']=='Attack the opponent.' and result['available_actions']==['a','wait']
    assert result['route23_battle_delegate']=='existing_battle' and step_id==env.step['id']
    assert c.pending is pending and c.started==4 and c.waits==9 and c.kwargs['previous']==['up']
    env.state.update(phase='overworld',objective='Move UP.',available_actions=['up','wait'])
    result,_=bcall(env)
    assert result['available_actions']==['wait'] and result['route23_battle_delegate']=='await_existing_battle_context'


@pytest.mark.parametrize('fault',['pallet_intent','wrong_user','nextmap','bad_target','job','peer','completed','missing_controller'])
def test_bridge_explicit_owner_peer_mutex_and_no_fake_completion(env,monkeypatch,fault):
    if fault in ('job','completed','missing_controller'):bcall(env)
    if fault=='pallet_intent':env.step['water_intent']['kind']='pallet_surf'
    elif fault=='wrong_user':env.step['water_intent']['surf_user']=7
    elif fault=='nextmap':env.step['nextmap']=9
    elif fault=='bad_target':env.step['target']=[10.,103]
    elif fault=='job':env.plan['training_job']='changed'
    elif fault=='peer':monkeypatch.setattr(bridge,'_peer_conflict',lambda:'trainer_medicine_ui_bridge_active')
    elif fault=='completed':bridge._COMPLETED.add(env.step['id'])
    else:bridge._CONTROLLERS.pop(env.step['id'])
    result,_=bcall(env);review(result)
    assert 'field_move_complete' not in result


def test_bridge_binding_cannot_begin_far_or_at_landfall_and_completed_flag_alone_is_not_enough(env):
    env.state['location']=dict(map_id=34,x=8,y=71)
    assert bcall(env) is None and not bridge._BINDINGS
    env.state['location']=dict(map_id=34,x=10,y=103);env.game.loc=env.state['location']
    bcall(env);bridge._CONTROLLERS[env.step['id']].result['route23_water_complete']=True
    result,_=bcall(env);review(result);assert not bridge._COMPLETED


def test_source_npc_bool_slot_does_not_equal_typed_slot_one():
    s=Surf();sig=signal(s.loc,s.f+40,0)
    sig['npc_positions']=((True,4,35),)+sig['npc_positions'][1:]
    review(s.call(ready=True,signal=sig))


def test_unknown_native_npc_dialogue_outside_source_badge_rows_stops_immediately():
    s=Water(flags=127);s.call()
    review(s.call(1,('up',),rows=guard_rows('SOULBADGE',0)))


def test_wild_capture_or_inventory_mutation_needs_review_and_keeps_pending():
    s=Water(flags=127);s.call();pending=s.c.pending
    s.call(1,('up',),active=True);s.p['inventory'][0]['quantity']-=1
    review(s.call(1));assert s.c.pending is pending


def test_portable_derived_primary_fixture_catches_source_tile_and_guard_geometry_drift():
    fixture=HERE/'route23_source.json' if HERE.name=='staged-route23-surf-20261025' else HERE/'fixtures/route23_source.json'
    proof=json.loads(fixture.read_text(encoding='utf-8'))
    assert proof['source_commit']==surf.SOURCE_COMMIT and proof['live_calibrated'] is False
    assert proof['map_dimensions_cells']==[20,144] and proof['tileset_id']==23
    assert tuple(map(tuple,proof['water_path']))==water.PATH
    assert tuple(map(tuple,proof['npc_positions']))==surf.NPC_POSITIONS
    assert proof['guard_rows_south_to_north']==list(surf.GUARD_ROWS)
    assert proof['surf_mode_address']-sum(proof['script_reverse_offset_bytes'])==surf.ADDRESSES['route23_script']==0xD667
    assert 0xD747+proof['event_id_start']//8==proof['event_byte_address']==surf.ADDRESSES['guard_flags']
    assert proof['water_wild_encounter_rate']==0
    assert {(n[1],n[2]) for n in water.PATH if n[4]==0x32}=={(10,91),(10,90)}
    assert len(proof['source_file_hashes'])==20 and all(len(h)==64 for h in proof['source_file_hashes'].values())


def test_source_coast32_is_still_surfing_and_wrong14_is_not_accepted_as_verified():
    s=Water(flags=127);idx=next(i for i,n in enumerate(water.PATH) if n[1:3]==(10,91));r=s.to(idx-1)
    assert r['available_actions']==['up','wait']
    result=s.call(idx,('up',),mutate=lambda st,args:args['grid']['tiles'][91].__setitem__(10,0x14))
    assert result['available_actions']==['wait'] and s.c.index==idx-1 and not result['route23_water_complete']
    assert s.call(idx)['available_actions']==['up','wait'] and s.c.index==idx


def test_installed_sdk_matches_route23_source_anchors_without_opening_game():
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as actual
    result=surf.read_surf_observation(SimpleNamespace(frame_count=40,memory=Memory()),40,actual)
    assert result['read_valid'] and result['route23_script']==0


@pytest.mark.parametrize('kind',['peer','safari_run','capture','registry'])
def test_real_loaded_peer_registry_mutex_is_readonly_and_includes_safari_capture(monkeypatch,kind):
    peer=SimpleNamespace(_BINDINGS={},_CONTROLLERS={},_COMPLETED=set())
    safari=SimpleNamespace(_RUN_CONTROLLER=None);capture=SimpleNamespace(_SESSIONS={})
    monkeypatch.setattr(bridge,'_PEERS',('test_route23_peer',))
    monkeypatch.setitem(sys.modules,'laya_pokemon.test_route23_peer',peer)
    monkeypatch.setitem(sys.modules,'laya_pokemon.safari_entry',safari)
    monkeypatch.setitem(sys.modules,'laya_pokemon.capture_transaction',capture)
    if kind=='peer':peer._BINDINGS['dose']={'original':'owner'}
    elif kind=='safari_run':safari._RUN_CONTROLLER=object()
    elif kind=='capture':capture._SESSIONS['catch']={'done':False}
    else:peer._COMPLETED={}
    before=(deepcopy(peer.__dict__),dict(safari.__dict__),deepcopy(capture.__dict__))
    assert bridge._peer_conflict() is not None
    assert (peer.__dict__,safari.__dict__,capture.__dict__)==before


def test_initial_wrong_mode_does_not_poison_a_new_owner_binding(env,monkeypatch):
    monkeypatch.setattr(bridge.surf,'read_surf_observation',lambda game,frame,sdk:signal(game.loc,frame,0,127))
    result,_=bcall(env);review(result)
    assert not bridge._CONTROLLERS and not bridge._BINDINGS
