"""洋館開關的固定來源只讀bit；fake getter禁止寫入，無ROM/模型/UI。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon.progress import (
    STORY_EVENT_NAMES, _mansion_switch_event_supported, read_progress,
)
from tests.test_progress import fuchsia_constants, fuchsia_game


# pret/pokered a536711 constants/event_constants.asm164–165:
# const_next $278 / const EVENT_MANSION_SWITCH_ON。
# D747 + 0x278 // 8 = D796；bit0。不能改用legacy任意SDK映射。
def inputs(value=0):
    constants=fuchsia_constants()
    constants.EVENT_FLAGS=deepcopy(constants.EVENT_FLAGS)
    game=fuchsia_game(constants,0)
    game.memory.data[0xD796]=value
    return game,constants


def test_fixed_public_source_agrees_with_sdk_exact_event_and_address():
    _,c=inputs()
    assert type(c.EVENT_FLAGS_ADDRESS) is int and c.EVENT_FLAGS_ADDRESS==0xD747
    assert type(c.EVENT_FLAGS['mansion_switch_on']) is int and c.EVENT_FLAGS['mansion_switch_on']==0x278
    assert c.EVENT_FLAGS_ADDRESS+c.EVENT_FLAGS['mansion_switch_on']//8==0xD796
    assert c.EVENT_FLAGS['mansion_switch_on']%8==0
    assert STORY_EVENT_NAMES.count('mansion_switch_on')==1


@pytest.mark.parametrize('value,expected',[(0,False),(1,True),(2,False),(128,False),(254,False),(255,True)])
def test_only_bit_zero_controls_switch_and_read_is_cached_once(value,expected):
    game,c=inputs(value);before=deepcopy(game.memory.data)
    out=read_progress(game,c)
    assert out['story_event_bits']['mansion_switch_on'] is expected
    assert game.memory.reads[0xD796]==1 and game.memory.data==before
    assert out['badges_raw']==15 and out['badge_count']==4
    assert out['champion_observed'] is False and out['hall_of_fame_confirmed'] is None


@pytest.mark.parametrize('invalid',[None,False,True,-1,256,1.0,'1',
    KeyError('unreadable'),RuntimeError('getter'),OSError('getter')])
def test_unknown_byte_and_getter_errors_remain_none_not_false(invalid):
    game,c=inputs(invalid)
    out=read_progress(game,c)
    assert out['story_event_bits']['mansion_switch_on'] is None
    assert game.memory.reads[0xD796]==1
    assert out['story_event_bits']['beat_koga'] is False


@pytest.mark.parametrize('invalid',[None,True,False,-1,0x279,float(0x278),'0x278'])
def test_wrong_event_id_is_unknown_and_never_uses_generic_mapping(invalid):
    game,c=inputs(255);c.EVENT_FLAGS['mansion_switch_on']=invalid
    out=read_progress(game,c)
    assert out['story_event_bits']['mansion_switch_on'] is None
    assert game.memory.reads[0xD796]==0
    assert out['story_event_bits']['beat_koga'] is False


def test_missing_new_event_anchor_is_unknown_without_changing_legacy_results():
    game,c=inputs(255);c.EVENT_FLAGS.pop('mansion_switch_on')
    out=read_progress(game,c)
    assert out['story_event_bits']['mansion_switch_on'] is None
    assert game.memory.reads[0xD796]==0
    game2,c2=inputs(0);out2=read_progress(game2,c2)
    assert {k:v for k,v in out['story_event_bits'].items() if k!='mansion_switch_on'}=={
        k:v for k,v in out2['story_event_bits'].items() if k!='mansion_switch_on'}
    assert out['party']==out2['party'] and out['badges_raw']==out2['badges_raw']


@pytest.mark.parametrize('base',[True,False,0xD746,0xD748])
def test_wrong_integer_or_bool_base_cannot_turn_mansion_bit_into_false(base):
    game,c=inputs(255);c.EVENT_FLAGS_ADDRESS=base
    out=read_progress(game,c)
    assert out['story_event_bits']['mansion_switch_on'] is None
    assert game.memory.reads[0xD796]==0


@pytest.mark.parametrize('base',[None,True,False,0xD746,float(0xD747),'0xD747'])
def test_isolated_new_field_guard_rejects_missing_or_bad_base_without_changing_legacy_contract(base):
    # legacy read_progress仍要求SDK整體有EVENT_FLAGS_ADDRESS；本輪父層明定
    # 不藉新欄修所有舊generic的缺base例外，所以整體缺失只測新guard。
    c=SimpleNamespace(EVENT_FLAGS_ADDRESS=base,EVENT_FLAGS={'mansion_switch_on':0x278})
    assert _mansion_switch_event_supported(c) is False
    assert _mansion_switch_event_supported(SimpleNamespace(EVENT_FLAGS={'mansion_switch_on':0x278})) is False


def test_new_guard_rejects_missing_nonmapping_or_throwing_anchor():
    for events in (None,[],{}, {'mansion_switch_on':True}):
        assert _mansion_switch_event_supported(SimpleNamespace(EVENT_FLAGS_ADDRESS=0xD747,EVENT_FLAGS=events)) is False
    class BadAnchor:
        @property
        def EVENT_FLAGS_ADDRESS(self):
            raise RuntimeError('unavailable source anchor')
    assert _mansion_switch_event_supported(BadAnchor()) is False


def test_switch_on_off_does_not_rewrite_other_story_flags_roster_or_map_contracts():
    game,c=inputs(0);before=read_progress(game,c)
    flags=deepcopy(c.EVENT_FLAGS)
    game.memory.data[0xD796]=1
    after=read_progress(game,c)
    a=before.pop('story_event_bits');b=after.pop('story_event_bits')
    assert a.pop('mansion_switch_on') is False and b.pop('mansion_switch_on') is True
    assert a==b and before==after and c.EVENT_FLAGS==flags
