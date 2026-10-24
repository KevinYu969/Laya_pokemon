"""固定公開來源的純物理格／fake getter；不建立模擬器或操作遊戲。"""
from copy import deepcopy
from types import SimpleNamespace
import re

import pytest

from laya_pokemon import mansion_statue as m
from tests.test_fly_pallet import progress


CONSTANTS=SimpleNamespace(EVENT_FLAGS_ADDRESS=0xD747,OBTAINED_BADGES_ADDRESS=0xD356,
    STATUS_FLAGS3_ADDRESS=0xD72D,EVENT_FLAGS={'mansion_switch_on':0x278},
    MAPS={'pokemon_mansion_3f':215,'pokemon_mansion_b1f':216})


def intent(mid=215,x=10,y=6,before=False):
    return dict(kind='mansion_statue',map_id=mid,player_x=x,player_y=y,
                source_before=before,source_after=not before)


class Memory:
    def __init__(self,i):
        self.values={0xD35E:i['map_id'],0xD361:i['player_y'],0xD362:i['player_x'],
                     0xC109:4,0xD796:int(i['source_before']),0xCD6B:0,0xCD38:0,
                     0xCFC5:0,0xD736:0,0xD700:0}
        self.reads=[];self.hook=None

    def __getitem__(self,a):
        self.reads.append(a)
        return self.hook(a,self.values[a]) if self.hook else self.values[a]

    def __setitem__(self,*args):raise AssertionError('getter only')


class Fake:
    def __init__(self,i):self.frame_count=0;self.memory=Memory(i)
    def tick(self,*args):raise AssertionError('no tick')
    def load_state(self,*args):raise AssertionError('no state')


def blank():return [[' ']*20 for _ in range(18)]


def page(label='',arrow=False):
    r=blank();r[14][1:1+len(label)]=list(label)
    if arrow:r[16][18]='▼'
    return r


def first(arrow=True):return page('A secret switch!',arrow)


def menu(y=8,marker='▶'):
    r=page('Press it?');r[8][16:19]=list('YES');r[10][16:18]=list('NO');r[y][15]=marker
    return r


def pressed(arrow=True):
    r=page();r[14][1:11]=list('Who wouldn');r[14][11]="'t";r[14][12]='?'
    if arrow:r[16][18]='▼'
    return r


def packet(rows,window=True):
    pairs=[(y,''.join(row).rstrip()) for y,row in enumerate(rows)
           if re.search(r'[A-Za-z0-9]{2,}',''.join(row))][:12]
    return dict(profile=m.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
                cells=deepcopy(rows),window_visible=window,lines=[s for _,s in pairs],line_rows=[y for y,_ in pairs])


def grid(i,frame,state):
    h=18 if i['map_id']==215 else 28;x,y=i['player_x'],i['player_y']
    tiles=[[1]*30 for _ in range(h)];walk=[[1]*30 for _ in range(h)]
    # 固定source block腳下四格，與控制器常數獨立列值。
    if i['map_id']==215:
        points=([(15,4,36),(15,5,36)] if state else [(15,10,36),(15,11,36)])
    elif state:points=[(26,17,24),(27,17,24),(13,22,36),(13,23,36)]
    else:points=[(9,6,36),(9,7,36),(16,16,24),(17,16,24)]
    for a,b,t in points:tiles[b][a]=t;walk[b][a]=0
    tiles[y-1][x]=61;walk[y-1][x]=0
    visible=[[x+dx,y+dy] for dy in (-2,-1,0) for dx in (-1,0,1,2)]
    return dict(source=m.GRID_SOURCE,observation_frame=frame,verified_location=[i['map_id'],x,y],
                tileset_id=22,tiles=tiles,walkable=walk,visible_verified_cells=visible,screen_cells_verified=12)


class Session:
    def __init__(self,i=None):
        self.i=deepcopy(i or intent());self.c=m.MansionStatueController(self.i)
        self.pb=Fake(self.i);self.p=progress();self.previous=[];self.now=0.;self.last=None

    def call(self,rows=None,ready=False,window=True,same=False,signal_change=None,grid_change=None,
             text_change=None,progress_change=None,previous=None,now=None):
        if not same:self.pb.frame_count+=1;self.now+=.1
        if now is not None:self.now=now
        signal=m.read_mansion_statue(self.pb,self.pb.frame_count,CONSTANTS)
        if signal_change:signal_change(signal)
        g=grid(self.i,self.pb.frame_count,bool(self.pb.memory.values[0xD796]&1))
        if grid_change:grid_change(g)
        text=packet(blank() if rows is None else rows,window)
        if text_change:text_change(text)
        if progress_change:progress_change(self.p)
        out=self.c.context(text,self.p,location=signal.get('location'),
            battle_state=dict(kind='none',active=False,raw=0,observation_frame=self.pb.frame_count),
            grid=g,signal=signal,frame=self.pb.frame_count,previous=self.previous if previous is None else previous,
            now=self.now,overworld_ready=ready)
        self.last=out;return out

    def send(self,rows,action='a',**kw):
        o=self.call(rows,**kw);assert o['available_actions']==[action,'wait'],o
        self.previous=[action];return o

    def to_pressed(self):
        self.send(None,ready=True,window=False)
        self.send(first())
        self.send(menu())

    def finish(self):
        self.send(pressed())
        self.pb.memory.values[0xD796]=int(self.i['source_after'])
        o=self.call(ready=True,window=False);assert o['available_actions']==['wait'] and not o['mansion_statue_complete']
        self.previous=['wait']
        o=self.call(ready=True,window=False);assert o['mansion_statue_complete'] is True
        return o


@pytest.mark.parametrize('i',[intent(),intent(216,18,26,True),intent(216,20,4,False),intent(216,20,4,True),intent(216,18,26,False)])
def test_five_normal_independent_transactions(i):
    s=Session(i);before=deepcopy(s.p);s.to_pressed();s.finish()
    assert s.p==before and s.c.stage=='complete' and s.c.final_executed
    assert s.call(ready=True,window=False)['mansion_statue_complete']


def test_face_up_is_normal_offer_and_requires_new_frame_actual_previous():
    s=Session();s.pb.memory.values[0xC109]=8
    s.send(None,'up',ready=True,window=False)
    assert s.call(ready=True,window=False)['available_actions']==['wait']
    s.pb.memory.values[0xC109]=4
    s.send(None,ready=True,window=False)


@pytest.mark.parametrize('bad',[{},intent(165,2,6),{**intent(),'source_before':0},
    {**intent(),'source_after':False},{**intent(),'extra':1},{**intent(),'player_x':True}])
def test_only_exact_registry_intents(bad):
    with pytest.raises(ValueError):m.MansionStatueController(bad)


def test_first_full_before_true_prompt_only_waits():
    s=Session();s.send(None,ready=True,window=False)
    assert s.call(first(False))['available_actions']==['wait']
    s.send(first())


def test_pressed_full_before_true_prompt_only_waits():
    s=Session();s.to_pressed();assert s.call(pressed(False))['available_actions']==['wait']
    assert s.pb.memory.values[0xD796]==0;s.finish()


def test_no_cursor_moves_up_once_across_blank_and_stale_page():
    s=Session();s.send(None,ready=True,window=False);s.send(first());s.send(menu(10),'up')
    for r in (blank(),menu(10),blank(),menu(10)):
        assert s.call(r)['available_actions']==['wait']
        s.previous=['wait']
    s.send(menu());s.finish()


def test_every_confirm_stale_page_or_blank_never_resends():
    s=Session();s.send(None,ready=True,window=False)
    assert s.call(ready=True,window=False)['available_actions']==['wait']
    s.send(first());assert s.call(first())['available_actions']==['wait']
    s.send(menu());assert s.call(menu())['available_actions']==['wait']
    s.send(pressed());assert s.call(pressed())['available_actions']==['wait']
    assert s.c.final_executed is True and s.c.stage=='closing'


def test_no_actual_previous_changed_page_fails_without_a():
    s=Session();s.send(None,ready=True,window=False)
    assert s.call(first(),previous=[])['review_reason'].endswith('without_actual_previous')


@pytest.mark.parametrize('stage,fn',[('first',first),('question',menu),('pressed',pressed)])
@pytest.mark.parametrize('xy',[(0,0),(0,14),(19,17),(15,9)])
def test_foreign_readable_or_cursor_anywhere_stops(stage,fn,xy):
    s=Session();s.send(None,ready=True,window=False)
    if stage in ('question','pressed'):s.send(first())
    if stage=='pressed':s.send(menu())
    r=fn();r[xy[1]][xy[0]]='X'
    o=s.call(r);assert o['available_actions']==['wait'] and 'review_reason' in o


@pytest.mark.parametrize('change',[lambda t:t.update(profile='legacy'),lambda t:t.update(read_valid=False),
    lambda t:t.update(alignment_verified=False),lambda t:t.update(read_error='unknown'),
    lambda t:t.pop('lines'),lambda t:t.pop('line_rows'),lambda t:t.pop('read_error')])
def test_complete_decoder_proof_required(change):
    s=Session();o=s.call(ready=True,window=False,text_change=change)
    assert o['available_actions']==['wait'] and 'review_reason' in o


@pytest.mark.parametrize('change',[lambda p:p['party'][0].update(hp=0),lambda p:p['party'][0].update(status=8),
    lambda p:p.update(party_read_valid=False),lambda p:p.update(party_count=5),
    lambda p:p['party'][1].update(species=7),lambda p:p.update(money=True)])
def test_unhealthy_invalid_initial_party_stops(change):
    s=Session();o=s.call(ready=True,window=False,progress_change=change)
    assert 'review_reason' in o


@pytest.mark.parametrize('change',[lambda p:p['party'][0]['pp'].__setitem__(0,1),
    lambda p:p['inventory'].reverse(),lambda p:p.update(money=p['money']+1),
    lambda p:p['party'].reverse(),lambda p:p['party'][0].update(exp=p['party'][0]['exp']+1)])
def test_bound_party_bag_money_never_rebased(change):
    s=Session();s.send(None,ready=True,window=False);base=deepcopy(s.c.baseline)
    assert s.call(first(),progress_change=change)['review_reason'].endswith('baseline_changed')
    assert s.c.baseline==base


def test_flag_after_not_required_until_final_previous_confirm_and_grid_redraw():
    s=Session();s.to_pressed();s.send(pressed());assert s.pb.memory.values[0xD796]==0
    assert s.call()['available_actions']==['wait']
    s.pb.memory.values[0xD796]=1
    assert not s.call(ready=True,window=False,grid_change=lambda g:g.update(grid(s.i,s.pb.frame_count,False)))['mansion_statue_complete']
    assert not s.call(ready=True,window=False)['mansion_statue_complete']
    assert s.call(ready=True,window=False)['mansion_statue_complete']


def test_premature_event_or_other_bits_cannot_be_treated_as_success():
    s=Session();s.send(None,ready=True,window=False);s.pb.memory.values[0xD796]=1
    assert 'review_reason' in s.call(first())
    s=Session();s.to_pressed();s.pb.memory.values[0xD796]=2
    assert s.call(pressed())['review_reason'].endswith('other_event_bits_changed')


@pytest.mark.parametrize('x,y,char',[(10,14,"'t"),(11,13,"'t"),(11,14,"'l"),(5,14,"'t")])
def test_ligature_is_local_and_exact(x,y,char):
    s=Session();s.to_pressed();r=pressed();r[y][x]=char
    assert 'review_reason' in s.call(r)


@pytest.mark.parametrize('mutate',[lambda g:g.update(tileset_id=19),lambda g:g.update(observation_frame=0),
    lambda g:g.update(screen_cells_verified=1),lambda g:g['tiles'][5].__setitem__(10,1),
    lambda g:g['walkable'][5].__setitem__(10,1),lambda g:g['tiles'][10].__setitem__(15,1)])
def test_source_grid_stance_front_and_door_state_required(mutate):
    s=Session();assert 'review_reason' in s.call(ready=True,window=False,grid_change=mutate)


def test_same_frame_exact_is_wait_conflict_and_reverse_are_sticky_review():
    s=Session();s.send(None,ready=True,window=False)
    # The packet must retain exactly the previous actual-action ledger too.
    assert s.call(ready=True,window=False,same=True,previous=[])['available_actions']==['wait']
    assert 'review_reason' in s.call(first(),same=True,previous=[])
    assert 'review_reason' in s.call(ready=True,window=False)
    s=Session();s.send(None,ready=True,window=False);s.pb.frame_count=-1
    assert 'review_reason' in s.call(same=True)


def test_budget_negative_clock_wait_and_reload_state_preserved():
    s=Session();s.send(None,ready=True,window=False);s.c.__class__=m.MansionStatueController
    assert s.call(first(False),now=61)['review_reason'].endswith('budget_exhausted')
    s=Session();s.send(None,ready=True,window=False)
    assert s.call(first(False),now=-1)['review_reason'].endswith('clock_or_frame_invalid')
    s=Session();s.send(None,ready=True,window=False)
    for _ in range(m.MAX_WAITS):assert s.call(first(False))['available_actions']==['wait']
    assert s.call(first(False))['review_reason'].endswith('wait_budget_exhausted')


def test_reader_double_getter_only_with_exact_source_contract():
    pb=Fake(intent());o=m.read_mansion_statue(pb,0,CONSTANTS)
    assert o['read_valid'] and o['switch_on'] is False
    assert pb.memory.reads==list(m.ADDRESSES.values())*2
    assert set(o['location'])=={'map_id','x','y'}


@pytest.mark.parametrize('address',list(m.ADDRESSES.values()))
@pytest.mark.parametrize('bad',[None,True,-1,256])
def test_reader_unknown_byte_never_fills_defaults(address,bad):
    pb=Fake(intent());pb.memory.values[address]=bad;o=m.read_mansion_statue(pb,0,CONSTANTS)
    assert o['read_valid'] is False and o['switch_on'] is None


@pytest.mark.parametrize('key,value',[('EVENT_FLAGS_ADDRESS',0xD748),('OBTAINED_BADGES_ADDRESS',True),
    ('STATUS_FLAGS3_ADDRESS',0),('EVENT_FLAGS',{'mansion_switch_on':True}),
    ('MAPS',{'pokemon_mansion_3f':215,'pokemon_mansion_b1f':215})])
def test_reader_sdk_mismatch_no_reads(key,value):
    pb=Fake(intent());c=deepcopy(CONSTANTS);setattr(c,key,value)
    assert m.read_mansion_statue(pb,0,c)['read_valid'] is False and pb.memory.reads==[]


def test_reader_torn_memory_frame_and_getter_failures_unknown():
    pb=Fake(intent())
    pb.memory.hook=lambda a,v: (1-v if a==0xD796 and len(pb.memory.reads)>10 else v)
    assert m.read_mansion_statue(pb,0,CONSTANTS)['read_valid'] is False
    pb=Fake(intent())
    def advance(a,v):pb.frame_count+=1;return v
    pb.memory.hook=advance
    assert m.read_mansion_statue(pb,0,CONSTANTS)['read_valid'] is False
    pb=Fake(intent());pb.memory.hook=lambda a,v: (_ for _ in ()).throw(RuntimeError('unreadable'))
    assert m.read_mansion_statue(pb,0,CONSTANTS)['read_valid'] is False


@pytest.mark.parametrize('a,v',[(0xD35E,165),(0xD362,9),(0xD700,2),(0xC109,3),(0xCD6B,128),(0xD736,128)])
def test_reader_known_domain_rejects_unrelated_movement(a,v):
    pb=Fake(intent());pb.memory.values[a]=v
    assert m.read_mansion_statue(pb,0,CONSTANTS)['read_valid'] is False


@pytest.mark.parametrize('mask',[0,0xFC,0xFF])
def test_reader_only_known_joy_masks(mask):
    pb=Fake(intent());pb.memory.values[0xCD6B]=mask
    assert m.read_mansion_statue(pb,0,CONSTANTS)['read_valid'] is True


def test_intent_mutation_and_explicit_source_signal_proof_missing_fail_closed():
    s=Session();s.send(None,ready=True,window=False);s.c.intent['source_before']=True
    assert s.call(first())['review_reason'].endswith('intent_changed')
    s=Session()
    assert s.call(ready=True,window=False,signal_change=lambda d:d.pop('read_error'))['review_reason'].endswith('source_signal_unverified')
