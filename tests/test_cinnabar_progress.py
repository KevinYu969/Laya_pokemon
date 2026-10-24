"""固定a536711的夏伯新8欄；純fake getter，不讀遊戲或第二大腦。"""
from copy import deepcopy
from pathlib import Path
import builtins

import pytest

from laya_pokemon import progress as p
from tests.test_progress import fuchsia_constants,fuchsia_game


EXPECTED={'got_tm38':0x298,'beat_blaine':0x299,
    'beat_cinnabar_gym_trainer_0':0x29A,'beat_cinnabar_gym_trainer_1':0x29B,
    'beat_cinnabar_gym_trainer_2':0x29C,'beat_cinnabar_gym_trainer_3':0x29D,
    'beat_cinnabar_gym_trainer_4':0x29E,'beat_cinnabar_gym_trainer_5':0x29F,
    'beat_cinnabar_gym_trainer_6':0x2A0}
ADDED=set(EXPECTED)-{'beat_blaine'}


def setup(first=0,second=0):
    c=fuchsia_constants();c.EVENT_FLAGS=dict(c.EVENT_FLAGS)
    g=fuchsia_game(c,0);g.memory.data.update({0xD79A:first,0xD79B:second})
    return g,c


def test_primary_enum_and_sdk_all_nine_exact_ints():
    _,c=setup()
    assert c.EVENT_FLAGS_ADDRESS==0xD747 and type(c.EVENT_FLAGS_ADDRESS) is int
    assert {n:c.EVENT_FLAGS[n] for n in EXPECTED}==EXPECTED
    assert all(type(c.EVENT_FLAGS[n]) is int for n in EXPECTED)
    assert ADDED<=set(p.STORY_EVENT_NAMES) and len(ADDED)==8
    assert {0xD747+v//8 for v in EXPECTED.values()}=={0xD79A,0xD79B}


@pytest.mark.parametrize('name',EXPECTED)
def test_each_independent_real_source_bit_and_cross_byte(name):
    eid=EXPECTED[name];g,c=setup(1<<(eid%8) if eid//8==0x298//8 else 0,1 if name.endswith('_6') else 0)
    before=deepcopy(g.memory.data);r=p.read_progress(g,c)
    assert {n:r['story_event_bits'][n] for n in EXPECTED}=={n:n==name for n in EXPECTED}
    assert g.memory.reads[0xD79A]==g.memory.reads[0xD79B]==1 and g.memory.data==before
    assert r['badges_raw']==15 and r['champion_observed'] is False and r['hall_of_fame_confirmed'] is None


@pytest.mark.parametrize('name',EXPECTED)
def test_missing_any_group_anchor_only_disables_new_fields(name):
    g,c=setup(255,1);c.EVENT_FLAGS.pop(name);r=p.read_progress(g,c)
    assert all(r['story_event_bits'][n] is None for n in ADDED)
    assert r['story_event_bits']['beat_blaine'] is (None if name=='beat_blaine' else True)
    assert g.memory.reads[0xD79B]==0


@pytest.mark.parametrize('name',EXPECTED)
@pytest.mark.parametrize('bad',[True,False,1.0,-1,None])
def test_every_sdk_type_value_mismatch_disables_new_contract(name,bad):
    _,c=setup();c.EVENT_FLAGS[name]=bad
    assert p._cinnabar_events_supported(c) is False
    # Boss invalid float/None retains legacy generic behavior; do not alter it.
    if name!='beat_blaine':
        g,_=setup(255,1);r=p.read_progress(g,c)
        assert all(r['story_event_bits'][n] is None for n in ADDED)
        assert r['story_event_bits']['beat_blaine'] is True


@pytest.mark.parametrize('base',[True,0xD746,0xD748])
def test_base_mismatch_never_reinterprets_eight_new_bits(base):
    g,c=setup(255,1);c.EVENT_FLAGS_ADDRESS=base;r=p.read_progress(g,c)
    assert all(r['story_event_bits'][n] is None for n in ADDED)
    # base+1時原generic Blaine本身會讀D79B；本輪刻意保留legacy行為。
    legacy_boss_address=base+c.EVENT_FLAGS['beat_blaine']//8
    assert g.memory.reads[0xD79B]==int(legacy_boss_address==0xD79B)


@pytest.mark.parametrize('address',[0xD79A,0xD79B])
@pytest.mark.parametrize('unknown',[None,True,False,-1,256,1.0,ValueError('unknown'),KeyError('unknown')])
def test_unknown_byte_only_affects_its_own_cached_address(address,unknown):
    g,c=setup(255,1);g.memory.data[address]=unknown;r=p.read_progress(g,c)
    assert {n:r['story_event_bits'][n] for n in ADDED}=={
        n:None if 0xD747+EXPECTED[n]//8==address else True for n in ADDED}
    assert g.memory.reads[0xD79A]==g.memory.reads[0xD79B]==1


@pytest.mark.parametrize('error',[RuntimeError('unreadable'),OSError('unreadable')])
def test_new_cross_byte_getter_exception_does_not_change_legacy_boss(error):
    g,c=setup(2,error);r=p.read_progress(g,c)
    assert r['story_event_bits']['beat_blaine'] is True
    assert r['story_event_bits']['beat_cinnabar_gym_trainer_6'] is None
    assert all(r['story_event_bits'][n] is False for n in ADDED if not n.endswith('_6'))


def test_new_anchor_mapping_getter_exception_leaves_legacy_boss_alone():
    class Events(dict):
        def get(self,name,*args):
            if name=='got_tm38':raise RuntimeError('new anchor unreadable')
            return super().get(name,*args)
    g,c=setup(2,1);c.EVENT_FLAGS=Events(c.EVENT_FLAGS);r=p.read_progress(g,c)
    assert r['story_event_bits']['beat_blaine'] is True
    assert all(r['story_event_bits'][n] is None for n in ADDED)


def test_legacy_blaine_shared_address_exception_remains_original_behavior():
    g,c=setup(RuntimeError('legacy failed'),1)
    with pytest.raises(RuntimeError,match='legacy failed'):p.read_progress(g,c)


def test_reader_uses_no_files_or_second_brain(monkeypatch):
    g,c=setup(255,1);p.read_progress(g,c)  # 載入既有公開adapter，再禁止任何檔案IO。
    def forbidden(*args,**kwargs):raise AssertionError('no filesystem access during read_progress')
    monkeypatch.setattr(builtins,'open',forbidden)
    monkeypatch.setattr(Path,'read_text',forbidden);monkeypatch.setattr(Path,'read_bytes',forbidden)
    assert all(p.read_progress(g,c)['story_event_bits'][n] is True for n in ADDED)
