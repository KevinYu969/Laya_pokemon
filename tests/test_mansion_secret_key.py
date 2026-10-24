"""固定公開source＋fake getter；不讀遊戲檔、不建立模擬器、不送按鍵。"""
import base64
from copy import deepcopy
from types import SimpleNamespace
import zlib

import pytest

from laya_pokemon import mansion_secret_key as key
from tests.test_fly_pallet import progress
from tests.test_mansion_transition_ready import MATRICES


CONSTANTS=SimpleNamespace(EVENT_FLAGS_ADDRESS=0xD747,STATUS_FLAGS3_ADDRESS=0xD72D,
    OBTAINED_BADGES_ADDRESS=0xD356,BAG_ITEM_COUNT_ADDRESS=0xD31D,
    BAG_ITEMS_ADDRESS=0xD31E,BAG_ITEM_CAPACITY=20,MAPS={'pokemon_mansion_b1f':216},
    ITEMS={'SECRET_KEY':43},EVENT_FLAGS={'mansion_switch_on':0x278})


class Memory:
    def __init__(self):
        self.values={a:0 for a in key.ADDRESSES.values()}
        self.values.update({0xD35E:216,0xD361:12,0xD362:5,0xC109:0,
            0xD4E1:8,0xC180:61,0xC284:17,0xC285:9,0xD512:43,0xD513:0,0xD796:1})
        self.values.update({key.FLAG_ADDRESS+i:0 for i in range(32)})
        self.values.update({key.TABLE_ADDRESS+i:0 for i in range(33)})
        for i,v in enumerate([3,190,4,191,5,192,6,193,8,194,255]):self.values[key.TABLE_ADDRESS+i]=v
        self.reads=[];self.hook=None
    def __getitem__(self,a):
        self.reads.append(a);return self.hook(a,self.values[a]) if self.hook else self.values[a]
    def __setitem__(self,*args):raise AssertionError('getter only')


class Fake:
    def __init__(self):self.memory=Memory();self.frame_count=0
    def tick(self,*a):raise AssertionError('no tick')
    def load_state(self,*a):raise AssertionError('no state')
    def button(self,*a):raise AssertionError('no button')


def blank():return [[' ']*20 for _ in range(18)]


def receipt():
    r=blank();r[14][1:12]=list('KEVIN found');r[16][1:12]=list('SECRET KEY!');return r


def packet(rows,window=True):
    import re
    pairs=[(y,''.join(r).rstrip()) for y,r in enumerate(rows) if re.search(r'[A-Za-z0-9]{2,}',''.join(r))][:12]
    return dict(profile=key.TEXT_PROFILE,read_valid=True,read_error=None,alignment_verified=True,
        cells=deepcopy(rows),window_visible=window,lines=[s for _,s in pairs],line_rows=[y for y,_ in pairs])


def grid(frame):
    raw=zlib.decompress(base64.b64decode(MATRICES[216]));assert len(raw)==840
    tiles=[list(raw[i*30:(i+1)*30]) for i in range(28)]
    coll={1,16,17,19,27,32,33,34,48,49,50,66,67,72,82,85,88,94}
    cells=[[x,y] for y in range(10,15) for x in range(3,8)]
    return dict(source=key.GRID_SOURCE,observation_frame=frame,verified_location=[216,5,12],
        tileset_id=22,tiles=tiles,walkable=[[int(t in coll) for t in row] for row in tiles],
        visible_verified_cells=cells,screen_cells_verified=len(cells))


class Session:
    def __init__(self):
        self.c=key.MansionSecretKeyController();self.pb=Fake();self.p=progress()
        assert len(self.p['inventory'])==19
        self.now=0.;self.previous=[]
    def call(self,rows=None,*,ready=False,window=True,same=False,previous=None,
             text_change=None,signal_change=None,grid_change=None,now=None):
        if not same:self.pb.frame_count+=1;self.now+=.1
        if now is not None:self.now=now
        t=packet(blank() if rows is None else rows,window)
        if text_change:text_change(t)
        s=key.read_mansion_secret_key(self.pb,self.pb.frame_count,CONSTANTS)
        if signal_change:signal_change(s)
        g=grid(self.pb.frame_count)
        if grid_change:grid_change(g)
        return self.c.context(t,self.p,location=deepcopy(key.LOCATION),
            battle_state=dict(kind='none',active=False,raw=0,observation_frame=self.pb.frame_count),
            grid=g,signal=s,frame=self.pb.frame_count,previous=self.previous if previous is None else previous,
            now=self.now,overworld_ready=ready)
    def offer(self,action='a'):
        out=self.call(ready=True,window=False);assert out['available_actions']==[action,'wait'],out
        self.previous=[action];return out
    def acquired(self):
        self.p['inventory'].append(dict(item=43,quantity=1));self.pb.memory.values[0xD5BE]|=4
    def full_receipt(self):
        self.acquired();out=self.call(receipt())
        assert out['available_actions']==['wait'] and self.c.seen_receipt and not out['mansion_secret_key_complete']
        self.previous=['wait'];return out
    def finish(self):
        out=self.call(ready=True,window=False);assert not out['mansion_secret_key_complete']
        out=self.call(ready=True,window=False);assert out['mansion_secret_key_complete']
        return out


def review(out):
    assert out['available_actions']==['wait'] and 'review_reason' in out
    assert not out.get('mansion_secret_key_complete')


def test_normal_one_inspect_a_source_done_receipt_never_a_then_two_closed():
    s=Session();original=deepcopy(s.p);s.offer();s.full_receipt();s.finish()
    expected=deepcopy(original);expected['inventory'].append(dict(item=43,quantity=1))
    assert s.p==expected and s.c.baseline['inventory']==original['inventory']
    assert s.call(ready=True,window=False)['mansion_secret_key_complete']


def test_normal_turn_down_requires_actual_new_frame_before_inspect():
    s=Session();s.pb.memory.values[0xC109]=4;s.offer('down')
    assert s.call(ready=True,window=False)['available_actions']==['wait']
    s.pb.memory.values[0xC109]=0;s.offer();s.full_receipt();s.finish()


def test_after_give_before_hide_only_waits_no_new_a():
    s=Session();s.offer();s.p['inventory'].append(dict(item=43,quantity=1))
    partial=receipt();partial[16]=[' ']*20
    assert s.call(partial)['available_actions']==['wait'] and not s.c.seen_receipt
    s.pb.memory.values[0xD5BE]|=4
    assert s.call(receipt())['available_actions']==['wait'] and s.c.seen_receipt
    s.finish()


def test_repeated_receipt_or_blank_before_receipt_never_rechecks_ball():
    s=Session();s.offer()
    for _ in range(3):assert s.call(ready=True,window=False)['available_actions']==['wait']
    s.full_receipt()
    for _ in range(3):assert s.call(receipt())['available_actions']==['wait']
    s.finish()


def test_source_has_no_prompt_arrow_unknown_not_confirmed():
    s=Session();s.offer();s.acquired();r=receipt();r[16][18]='▼';review(s.call(r))
    assert s.c.seen_receipt is False


def test_acquired_bag_and_hidden_without_seen_full_native_receipt_not_complete():
    s=Session();s.offer();s.acquired();review(s.call(ready=True,window=False))
    assert s.c.error.endswith('native_receipt_not_observed')


def test_full_receipt_without_bag_or_hidden_is_rejected():
    s=Session();s.offer();review(s.call(receipt()))
    s=Session();s.offer();s.p['inventory'].append(dict(item=43,quantity=1));review(s.call(receipt()))
    s=Session();s.offer();s.pb.memory.values[0xD5BE]|=4;review(s.call(receipt()))


@pytest.mark.parametrize('where,char',[(0,'X'),(18,'▶'),(19,'!')])
def test_unknown_foreground_never_a_or_complete(where,char):
    s=Session();s.offer();s.acquired();r=receipt();r[0][where]=char;review(s.call(r))


@pytest.mark.parametrize('fault',[lambda p:p['inventory'].append(dict(item=29,quantity=1)),
    lambda p:p['inventory'].append(dict(item=43,quantity=1)),lambda p:p.update(party_read_valid=False),
    lambda p:p['party'][0].update(hp=0),lambda p:p['party'][1].update(status=8)])
def test_invalid_initial_bag_space_or_party(fault):
    s=Session();fault(s.p);review(s.call(ready=True,window=False))


@pytest.mark.parametrize('fault',[lambda p:p['inventory'].reverse(),lambda p:p.update(money=p['money']+1),
    lambda p:p['party'].reverse(),lambda p:p['party'][0]['pp'].__setitem__(0,1),
    lambda p:p['party'][0].update(exp=p['party'][0]['exp']+1)])
def test_no_rebase_of_other_inventory_party_money(fault):
    s=Session();s.offer();baseline=deepcopy(s.c.baseline);fault(s.p)
    review(s.call(receipt()));assert s.c.baseline==baseline


def test_key_quantity_or_append_order_must_be_exact():
    s=Session();s.offer();s.acquired();s.p['inventory'][-1]['quantity']=2;review(s.call(receipt()))
    s=Session();s.offer();s.acquired();s.p['inventory'][0],s.p['inventory'][-1]=s.p['inventory'][-1],s.p['inventory'][0]
    review(s.call(receipt()))


def test_other_hidden_flags_and_mansion_switch_unchanged():
    s=Session();s.offer();s.pb.memory.values[0xD5BE]|=1;review(s.call())
    s=Session();s.offer();s.pb.memory.values[0xD796]|=2;review(s.call())


def test_true_previous_and_frame_required_no_early_consumption():
    s=Session();s.offer();s.acquired();review(s.call(receipt(),previous=[]))
    s=Session();s.offer()
    assert s.call(ready=True,window=False,same=True,previous=[])['available_actions']==['wait']
    s.acquired();review(s.call(receipt(),same=True,previous=[]))


def test_partial_and_known_decoder_transition_only_bounded_wait():
    s=Session();s.offer();s.acquired();r=receipt();r[16][5:]=[' ']*15
    assert s.call(r)['available_actions']==['wait'] and not s.c.seen_receipt
    def native(t):t.update(read_valid=False,alignment_verified=False,read_error='visible_tile_alignment_incomplete')
    assert s.call(r,text_change=native)['available_actions']==['wait'] and not s.c.seen_receipt
    s.call(receipt());assert s.c.seen_receipt;s.finish()


@pytest.mark.parametrize('fault',[lambda t:t.update(profile='legacy'),lambda t:t.update(read_valid=False),
    lambda t:t.update(alignment_verified=False),lambda t:t.pop('lines'),lambda t:t.pop('line_rows'),
    lambda t:t.pop('read_error')])
def test_complete_native_decoder_proof_required(fault):
    s=Session();review(s.call(ready=True,window=False,text_change=fault))


@pytest.mark.parametrize('fault',[lambda g:g.update(tileset_id=19),lambda g:g.update(observation_frame=0),
    lambda g:g['tiles'][0].__setitem__(0,1),lambda g:g['walkable'][12].__setitem__(5,0),
    lambda g:g.update(visible_verified_cells=[[5,12]]*25)])
def test_source_grid_or_visible_object_front_conflict(fault):
    s=Session();review(s.call(ready=True,window=False,grid_change=fault))


def test_budget_sticky_error_and_reload_instance_identity():
    s=Session();s.offer();base=s.c.baseline;s.c.__class__=key.MansionSecretKeyController
    review(s.call(now=61));assert s.c.baseline is base;review(s.call())
    s=Session();s.offer();review(s.call(now=-1))
    s=Session();s.offer()
    for _ in range(key.MAX_WAITS):assert s.call()['available_actions']==['wait']
    review(s.call());assert s.c.error.endswith('wait_budget_exhausted')


@pytest.mark.parametrize('mutation',[lambda i:i.update(object_index=192),lambda i:i.update(object_slot=True),
    lambda i:i.update(map_id=215),lambda i:i.update(player_y=13),lambda i:i.update(quantity=2)])
def test_fixed_intent_only(mutation):
    i=deepcopy(key.SECRET_KEY_INTENT);mutation(i)
    with pytest.raises(ValueError):key.MansionSecretKeyController(i)


def test_reader_all_bytes_double_read_only_source_identity():
    pb=Fake();before=deepcopy(pb.memory.values);out=key.read_mansion_secret_key(pb,0,CONSTANTS)
    assert out['read_valid'] and out['item_hidden'] is False and out['location']==key.LOCATION
    addresses=list(key.ADDRESSES.values())+list(range(key.FLAG_ADDRESS,key.FLAG_ADDRESS+32))+list(range(key.TABLE_ADDRESS,key.TABLE_ADDRESS+33))
    assert pb.memory.reads==addresses*2 and pb.memory.values==before
    assert 0xC182 not in pb.memory.reads  # ImageIndex=FF亦可只是offscreen。


@pytest.mark.parametrize('address',list(key.ADDRESSES.values())+[0xD5BE,0xD5CE])
def test_reader_unknown_or_bad_typed_byte_never_visible_default(address):
    for bad in (None,True,-1,256):
        pb=Fake();pb.memory.values[address]=bad;out=key.read_mansion_secret_key(pb,0,CONSTANTS)
        assert out['read_valid'] is False and out['item_hidden'] is None


@pytest.mark.parametrize('a,v',[(0xD35E,165),(0xD362,6),(0xD4E1,7),(0xC180,0),
    (0xC284,16),(0xC285,8),(0xD512,29),(0xD513,1),(0xD5CE,8),(0xD5D7,192),
    (0xD5D8,0),(0xD700,2),(0xD796,0),(0xC109,3),(0xCD6B,128),(0xD736,128)])
def test_reader_source_pairs_slot_object_identity_must_match(a,v):
    pb=Fake();pb.memory.values[a]=v;assert key.read_mansion_secret_key(pb,0,CONSTANTS)['read_valid'] is False


@pytest.mark.parametrize('mutation',[lambda c:setattr(c,'BAG_ITEM_CAPACITY',19),
    lambda c:setattr(c,'EVENT_FLAGS_ADDRESS',True),lambda c:c.ITEMS.update(SECRET_KEY=42),
    lambda c:c.MAPS.update(pokemon_mansion_b1f=215),lambda c:c.EVENT_FLAGS.update(mansion_switch_on=True)])
def test_reader_sdk_anchors_required_before_any_memory_read(mutation):
    pb=Fake();c=deepcopy(CONSTANTS);mutation(c)
    assert key.read_mansion_secret_key(pb,0,c)['read_valid'] is False and pb.memory.reads==[]


def test_reader_torn_snapshot_frame_and_getter_exception_unknown():
    pb=Fake();n=len(key.ADDRESSES)+32+33
    pb.memory.hook=lambda a,v:v^2 if a==0xD5BE and len(pb.memory.reads)>n else v
    assert key.read_mansion_secret_key(pb,0,CONSTANTS)['read_valid'] is False


def test_primary_zero_based_c2_index_and_bit2_not_old_bit1():
    assert key.SECRET_KEY_INTENT['object_index']==0xC2==194
    assert key.OBJECT_PAIRS==((3,0xBE),(4,0xBF),(5,0xC0),(6,0xC1),(8,0xC2))
    pb=Fake();pb.memory.values[0xD5BE]=2
    assert key.read_mansion_secret_key(pb,0,CONSTANTS)['item_hidden'] is False
    pb.memory.values[0xD5BE]=4
    assert key.read_mansion_secret_key(pb,0,CONSTANTS)['item_hidden'] is True
    for i,v in enumerate([3,189,4,190,5,191,6,192,8,193,255]):pb.memory.values[key.TABLE_ADDRESS+i]=v
    assert key.read_mansion_secret_key(pb,0,CONSTANTS)['read_valid'] is False
    with pytest.raises(ValueError):key.MansionSecretKeyController({**key.SECRET_KEY_INTENT,'object_index':193})


def test_bound_owner_and_explicit_packet_frame_cannot_change():
    s=Session();s.offer();s.c.intent['object_index']=193
    review(s.call());assert s.c.error.endswith('intent_changed')
    s=Session();review(s.call(ready=True,window=False,text_change=lambda t:t.update(observation_frame=0)))
    s=Session();s.p['observation_frame']=0;review(s.call(ready=True,window=False))


def test_old_bit1_with_added_key_is_never_a_success_receipt():
    s=Session();s.offer();s.p['inventory'].append(dict(item=43,quantity=1));s.pb.memory.values[0xD5BE]=2
    review(s.call(receipt()));assert not s.c.seen_receipt


@pytest.mark.parametrize('address',[0xD513,0xD5A6,0xD5D9])
@pytest.mark.parametrize('bad',[False,0.0])
def test_second_sample_scalar_flags_and_table_require_real_byte(address,bad):
    pb=Fake();sample_size=len(key.ADDRESSES)+32+33
    assert pb.memory.values[address]==0 and 0==bad
    pb.memory.hook=lambda a,v:bad if a==address and len(pb.memory.reads)>sample_size else v
    out=key.read_mansion_secret_key(pb,0,CONSTANTS)
    assert out['read_valid'] is False and out['item_hidden'] is None
    pb=Fake()
    def advancing(a,v):pb.frame_count+=1;return v
    pb.memory.hook=advancing;assert key.read_mansion_secret_key(pb,0,CONSTANTS)['read_valid'] is False
    pb=Fake();pb.memory.hook=lambda a,v:(_ for _ in ()).throw(OSError('unreadable'))
    assert key.read_mansion_secret_key(pb,0,CONSTANTS)['read_valid'] is False
