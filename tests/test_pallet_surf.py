"""只用fake byte memory與來源幾何；不載ROM、不開PyBoy、不呼叫模型。"""
from copy import deepcopy
from importlib import reload
from types import SimpleNamespace
import re

import pytest

from laya_pokemon import pallet_surf as surf
from laya_pokemon.progress import PROFILE as PROGRESS
from laya_pokemon.observation import PROFILE as TEXT
from laya_pokemon.rocket_movement import MOVEMENT_PROFILE


def blank():
    return [[' ']*20 for _ in range(18)]


def put(r,x,y,s):
    r[y][x:x+len(s)]=list(s)
    return r


def packet(rows=None, window=True):
    r=deepcopy(rows if rows is not None else blank())
    visible=[(y,''.join(row).rstrip()) for y,row in enumerate(r)
             if re.search(r'[A-Za-z0-9]{2,}',''.join(row))][:12]
    return dict(profile=TEXT,read_valid=True,alignment_verified=True,read_error=None,
                window_visible=window,cells=r,lines=[s for _,s in visible],line_rows=[y for y,_ in visible])


def progress():
    members=[(7,'NIDOKING',[61,57,30,40]),(132,'SNORLAX',[70,133,156,34]),
             (102,'EEVEE',[33,28,98,44]),(154,'VENUSAUR',[75,15,73,22]),
             (35,'FEAROW',[64,65,19,31]),(19,'LAPRAS',[55,34,47,54])]
    party=[dict(species=s,species_name=n,level=36,exp=46656,hp=121,max_hp=121,status=0,
                moves=m,pp=[20,15,25,35]) for s,n,m in members]
    return dict(profile=PROGRESS,party_read_valid=True,initialization_candidate=True,
                party_count=6,party=party,inventory=[dict(item=3,quantity=9),dict(item=198,quantity=1)],
                money=55372,badges_raw=63,player_name_raw='KEVIN')


def start(cursor=4,marker='▶'):
    r=blank()
    for y,s in ((2,'POKÉDEX'),(4,'POKÉMON'),(6,'ITEM'),(8,'KEVIN'),(10,'SAVE'),(12,'OPTION'),(14,'EXIT')):
        put(r,12,y,s)
    return put(r,11,cursor,marker)


def party(p,cursor=0,marker='▶',field=None):
    r=blank()
    for i,m in enumerate(p['party']):
        put(r,3,2*i,m['species_name']); put(r,13,2*i,f"{m['level']:3}")
        put(r,13,2*i+1,f"{m['hp']:3}/{m['max_hp']:3}")
    put(r,0,2*cursor+1,marker); put(r,1,14,'Choose a POKéMON.')
    if field is not None:
        for y in range(8,18): r[y][11:20]=[' ']*9
        for y,s in ((10,'SURF'),(12,'STATS'),(14,'SWITCH'),(16,'CANCEL')): put(r,13,y,s)
        put(r,12,field,'▶')
    return r


def prompt(arrow=True,first='KEVIN got on',second='NIDOKING!'):
    r=put(put(blank(),1,14,first),1,16,second)
    return put(r,18,16,'▼') if arrow else r


class Run:
    def __init__(self):
        self.c=surf.PalletSurfController(); self.p=progress(); self.f=100; self.now=0
        self.loc=dict(surf.START); self.mode=0

    def call(self,rows=None,*,prev=('wait',),window=True,ready=False,frame=None,now=None,
             signal=None,movement=None,grid=None,text=None,battle=None):
        self.f=self.f+40 if frame is None else frame
        self.now=self.now+.1 if now is None else now
        g=dict(tileset_id=0,screen_cells_verified=12,observation_frame=self.f,
               verified_location=[self.loc[k] for k in ('map_id','x','y')],
               tiles=[[0x23]*20 for _ in range(18)],walkable=[[1]*20 for _ in range(18)])
        g['tiles'][14][4]=0x32; g['walkable'][14][4]=0
        s=dict(profile=surf.PROFILE,source_commit=surf.SOURCE_COMMIT,read_valid=True,read_error=None,
               observation_frame=self.f,location=deepcopy(self.loc),mode=self.mode,
               facing='down',facing_raw=0,battle_raw=0,badges_raw=self.p['badges_raw'])
        m=dict(profile=MOVEMENT_PROFILE,source_commit=surf.SOURCE_COMMIT,read_valid=True,
               read_error=None,observation_frame=self.f,simulated_remaining=0,joy_ignore=0,
               walk_counter=0,movement_flags=0,spinning=False)
        b=dict(kind='none',raw=0,active=False,observation_frame=self.f)
        if signal: s.update(signal)
        if movement: m.update(movement)
        if battle: b.update(battle)
        if grid: g.update(grid)
        return self.c.context(text if text is not None else packet(rows,window),self.p,
                              location=self.loc,battle_state=b,grid=g,signal=s,movement=m,
                              frame=self.f,previous=list(prev),now=self.now,overworld_ready=ready)

    def initialize(self):
        return self.call(window=False,ready=True)

    def to_field(self):
        assert self.initialize()['available_actions'][0]=='start'
        assert self.call(start(),prev=['start'])['available_actions'][0]=='a'
        assert self.call(party(self.p),prev=['a'])['available_actions'][0]=='a'
        return self.call(party(self.p,marker='▷',field=10),prev=['a'])

    def to_prompt(self):
        assert self.to_field()['available_actions'][0]=='a'
        self.mode=2
        return self.call(prompt(),prev=['a'])

    def to_moving(self):
        assert self.to_prompt()['available_actions'][0]=='a'
        return self.call(prev=['a'],window=False,ready=False)


def reviewed(h):
    assert h['phase']=='campaign_review'
    assert h['available_actions']==['wait']
    assert not h['surf_entry_complete']


def test_normal_native_pipeline_requires_actual_actions_prompt_and_two_closed_water_frames():
    r=Run(); original=deepcopy(r.p)
    assert r.to_moving()['available_actions']==['wait']
    assert not r.c.closed_frame
    r.loc=dict(surf.LANDING)
    h=r.call(window=False,ready=True)
    assert not h['surf_entry_complete']
    h=r.call(window=False,ready=True)
    assert h['surf_entry_complete'] and h['pallet_surf_complete']
    assert r.p==original


def test_mode_two_before_native_forward_does_not_complete():
    r=Run(); r.to_moving()
    for _ in range(3):
        h=r.call(window=False,ready=True)
        assert h['available_actions']==['wait'] and not h['surf_entry_complete']


@pytest.mark.parametrize('change',[lambda p:p['party'][0].update(hp=120),
    lambda p:p['party'][0]['pp'].__setitem__(1,14), lambda p:p['party'].reverse(),
    lambda p:p['inventory'][0].update(quantity=8), lambda p:p.update(money=55371)])
def test_baseline_party_hp_pp_bag_order_money_cannot_drift(change):
    r=Run(); r.initialize(); change(r.p)
    reviewed(r.call(start(),prev=['start']))


@pytest.mark.parametrize('mutation',[lambda p:p['party'][0]['moves'].__setitem__(1,33),
    lambda p:p.update(badges_raw=47),lambda p:p.update(party_count=5),
    lambda p:p['party'][0].update(status=8),lambda p:p.update(player_name_raw='RED')])
def test_initial_missing_move_badge_sixparty_health_name_reject(mutation):
    r=Run(); mutation(r.p); reviewed(r.initialize())


def test_candidate_is_not_action_receipt_and_same_old_page_can_retry():
    r=Run(); r.initialize()
    h=r.call(window=False,ready=True,prev=['wait'])
    assert h['available_actions'][0]=='start' and r.c.stage=='initial'
    reviewed(r.call(start(),prev=['wait']))


def test_executed_a_old_page_or_arrow_blink_is_not_resent():
    r=Run(); r.to_prompt()
    h=r.call(prompt(),prev=['a'])
    assert h['available_actions']==['wait'] and r.c.prompt_ack
    h=r.call(prompt(False),prev=['wait'])
    assert h['available_actions']==['wait'] and r.c.prompt_ack


def test_source_saved_party_underlay_is_exact_and_only_true_prompt_can_a():
    r=Run(); r.to_field(); r.mode=2
    rows=party(r.p,marker='▷')
    for y in range(12,18): rows[y]=[' ']*20
    put(rows,1,14,'KEVIN got on'); put(rows,1,16,'NIDOKING!')
    assert r.call(rows,prev=['a'])['available_actions']==['wait']
    put(rows,18,16,'▼')
    assert r.call(rows)['available_actions'][0]=='a'
    assert r.call(rows,prev=['a'])['available_actions']==['wait']
    r=Run(); r.to_field(); r.mode=2
    rows=party(r.p,marker='▷')
    for y in range(12,18): rows[y]=[' ']*20
    put(rows,1,14,'KEVIN got on'); put(rows,1,16,'NIDOKING!'); put(rows,18,16,'▼')
    put(rows,0,0,'X')
    reviewed(r.call(rows,prev=['a']))


def test_partial_and_full_without_prompt_only_wait_until_true_arrow():
    r=Run(); r.to_field(); r.mode=2
    assert r.call(prompt(False,second='NIDO'),prev=['a'])['available_actions']==['wait']
    assert r.call(prompt(False))['available_actions']==['wait']
    assert not r.c.prompt_ack
    assert r.call(prompt())['available_actions'][0]=='a'


@pytest.mark.parametrize('x,y,mark',[(0,0,'▶'),(0,1,'▷'),(17,16,'▼'),(18,14,'▼')])
def test_foreign_arrow_or_cursor_never_confirms_prompt(x,y,mark):
    r=Run(); r.to_field(); r.mode=2
    rows=put(prompt(False),x,y,mark)
    reviewed(r.call(rows,prev=['a']))


def test_wrong_native_message_rejects():
    r=Run(); r.to_field(); r.mode=2
    reviewed(r.call(prompt(second='SNORLAX!'),prev=['a']))


def test_wrong_water_tile_or_globally_land_walkable_cannot_complete():
    for tile,walk in ((0x14,0),(0x32,1)):
        r=Run(); r.to_moving(); r.loc=dict(surf.LANDING)
        ts=[[0x23]*20 for _ in range(18)]; ts[14][4]=tile
        ws=[[1]*20 for _ in range(18)]; ws[14][4]=walk
        reviewed(r.call(window=False,ready=True,grid=dict(tiles=ts,walkable=ws)))


def test_wrong_position_and_mode_unknown_do_not_complete():
    r=Run(); r.to_moving(); r.loc['x']=5
    reviewed(r.call(window=False,ready=True))
    r=Run(); r.to_moving(); r.loc=dict(surf.LANDING); r.mode=0
    reviewed(r.call(window=False,ready=True))


def test_water_position_before_real_prompt_a_cannot_complete():
    r=Run(); r.to_prompt(); r.loc=dict(surf.LANDING)
    reviewed(r.call(window=False,ready=True,prev=['wait']))


def test_busy_water_frame_resets_double_closed_requirement():
    r=Run(); r.to_moving(); r.loc=dict(surf.LANDING)
    r.call(window=False,ready=True)
    r.call(window=False,ready=False,movement=dict(walk_counter=1))
    assert not r.call(window=False,ready=True)['surf_entry_complete']
    assert r.call(window=False,ready=True)['surf_entry_complete']


def test_cursor_motion_must_be_exact_single_step_and_never_switch():
    r=Run(); r.initialize()
    assert r.call(start(8),prev=['start'])['available_actions'][0]=='up'
    reviewed(r.call(start(4),prev=['up']))
    r=Run(); r.initialize(); r.call(start(),prev=['start']); r.call(party(r.p),prev=['a'])
    assert r.call(party(r.p,marker='▷',field=14),prev=['a'])['available_actions'][0]=='up'
    assert r.call(party(r.p,marker='▷',field=12),prev=['up'])['available_actions'][0]=='up'
    assert r.call(party(r.p,marker='▷',field=10),prev=['up'])['available_actions'][0]=='a'


def test_same_frame_same_packet_waits_conflict_is_sticky():
    r=Run(); r.initialize(); f=r.f; now=r.now
    assert r.call(window=False,ready=True,frame=f,now=now)['available_actions']==['wait']
    reviewed(r.call(start(),frame=f,now=now))
    reviewed(r.call(start(),prev=['start']))


@pytest.mark.parametrize('fault',[dict(read_valid=False),dict(profile='forged'),dict(mode=None),dict(mode=True),
                                  dict(badges_raw=31),dict(facing_raw=4)])
def test_signal_faults_are_unknown_not_safe_defaults(fault):
    r=Run(); reviewed(r.call(window=False,ready=True,signal=fault))


@pytest.mark.parametrize('fault',[dict(read_valid=False),dict(alignment_verified=False),
                                  dict(window_visible=False),dict(read_error='x'),dict(profile='x')])
def test_decoder_metadata_faults_do_not_press_start_or_a(fault):
    r=Run(); r.initialize(); text=packet(start()); text.update(fault)
    reviewed(r.call(prev=['start'],text=text))


def test_budget_and_reload_preserve_existing_owner_instance():
    r=Run(); r.to_field(); r.mode=2
    r.call(prompt(False),prev=['a'])
    old=r.c; module=reload(surf)
    assert old.baseline and old.stage=='got_on'
    for _ in range(29):
        assert r.call(prompt(False))['available_actions']==['wait']
    reviewed(r.call(prompt(False)))
    assert module.MAX_WAITS==30
    r=Run(); r.initialize(); reviewed(r.call(start(),prev=['start'],now=60.10001))


CONSTANTS=dict(STATUS_FLAGS3_ADDRESS=0xD72D,EVENT_FLAGS_ADDRESS=0xD747,
               OBTAINED_BADGES_ADDRESS=0xD356,MAPS={'pallet_town':0},BADGES={'soul':4})


class Memory:
    def __init__(self, values=None, *, changed=None, error=None):
        self.values={a:0 for a in surf.ADDRESSES.values()}
        self.values.update({0xD362:4,0xD361:13,0xD356:63})
        self.values.update(values or {}); self.count={}; self.changed=changed; self.error=error
    def __getitem__(self,a):
        self.count[a]=self.count.get(a,0)+1
        if a==self.error: raise RuntimeError('fake getter error')
        if a==self.changed and self.count[a]>1: return self.values[a]+1
        return self.values[a]
    def __setitem__(self,a,v):
        raise AssertionError('reader must not write')


def read(memory=None, constants=None, frame=40, game=None):
    g=game or SimpleNamespace(memory=memory or Memory(),frame_count=frame)
    return surf.read_surf_observation(g,frame,CONSTANTS if constants is None else constants)


@pytest.mark.parametrize('mode,map_id',[(0,0),(1,32),(2,8)])
def test_readonly_source_derivation_supports_all_normal_modes_and_maps(mode,map_id):
    s=read(Memory({0xD700:mode,0xD35E:map_id}))
    assert s['read_valid'] and s['mode']==mode and s['location']['map_id']==map_id
    assert s['source_commit']==surf.SOURCE_COMMIT and s['live_calibrated'] is False


@pytest.mark.parametrize('key,bad',[('STATUS_FLAGS3_ADDRESS',True),('EVENT_FLAGS_ADDRESS',0xD748),
                                   ('OBTAINED_BADGES_ADDRESS',float(0xD356))])
def test_reader_invalid_sdk_anchor_is_unknown(key,bad):
    constants=deepcopy(CONSTANTS); constants[key]=bad
    s=read(constants=constants)
    assert not s['read_valid'] and s['mode'] is None


@pytest.mark.parametrize('value',[None,True,-1,256,2.0,3])
def test_reader_invalid_mode_never_defaults_to_walk(value):
    s=read(Memory({0xD700:value}))
    assert not s['read_valid'] and s['mode'] is None


@pytest.mark.parametrize('address',list(surf.ADDRESSES.values()))
def test_double_read_changes_and_exceptions_fail_unknown(address):
    for memory in (Memory(changed=address),Memory(error=address)):
        s=read(memory)
        assert not s['read_valid'] and s['mode'] is None


def test_reader_frame_changes_or_bad_typed_frame_fail_unknown():
    class Game:
        memory=Memory()
        calls=0
        @property
        def frame_count(self):
            self.calls+=1
            return 40 if self.calls==1 else 41
    assert read(game=Game())['read_valid'] is False
    for f in (True,-1,40.0): assert read(frame=f)['mode'] is None

