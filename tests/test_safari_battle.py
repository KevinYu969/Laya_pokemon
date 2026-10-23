"""Safari RUN候選的純fake memory／文字測試，不載ROM、模型或模擬器。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon import safari_battle as sb
from tests.test_battle import text_at


LOCATION = {'map_id': 220, 'x': 18, 'y': 22}


def sdk():
    return SimpleNamespace(**sb.SDK_ANCHORS, EVENT_FLAGS={'in_safari_zone': 591, 'safari_game_over': 590})


def memory():
    return {0xD057:1,0xD05A:2,0xD790:128,0xDA47:30,0xD70D:1,0xD70E:144,
            0xD35E:220,0xD362:18,0xD361:22,0xCFE5:18,0xCFF3:25}


def read(data=None, frame=10, **kwargs):
    return sb.read_safari_battle_signal(SimpleNamespace(memory=memory() if data is None else data,frame_count=frame),
        observation_frame=kwargs.get('observation_frame',frame),expected_location=kwargs.get('location',LOCATION),
        constants=kwargs.get('constants',sdk()))


def text(*entries, hud=True):
    result = text_at(*([(1,0,'RHYHORN'),(5,1,'25')] if hud else []),*entries)
    result.update(profile=sb.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,window_visible=True)
    return result


def menu(cursor=(1,14), marker='▶', count='30'):
    return text((2,14,'BALL×'),(7,14,count),(14,14,'BAIT'),(2,16,'THROW ROCK'),(14,16,'RUN'),
                (cursor[0],cursor[1],marker))


def args(frame=10, now=1., raw=1):
    data=memory();data[0xD057]=raw
    signal=read(data,frame)
    return {'location':deepcopy(LOCATION),'battle_state':{'raw':raw,'active':raw==1,
                'kind':'wild' if raw==1 else 'none','observation_frame':frame,'opponent_species':'RHYHORN' if raw==1 else None},
            'safari':{'profile':sb.SAFARI_PROFILE,'read_valid':True,'observation_frame':frame,
                       'in_safari':True,'game_over':False,'balls':30,'steps':400},
            'battle_signal':signal,'frame':frame,'now':now}


def controller():
    return sb.SafariRunController(deepcopy(sb.INTENT))


def test_reader_source_values_and_no_writes():
    class ReadOnly(dict):
        def __setitem__(self,*args):
            raise AssertionError('No RAM writes allowed')
    data=ReadOnly(memory());before=deepcopy(dict(data))
    packet=read(data)
    assert packet['read_valid'] and packet['raw']==1 and packet['battle_type']==2
    assert packet['in_safari'] and not packet['game_over'] and packet['balls']==30 and packet['steps']==400
    assert packet['enemy_species']==18 and packet['enemy_level']==25 and dict(data)==before


@pytest.mark.parametrize('cursor,actions', [((1,14),['right','down','a']),((13,14),['down','a']),
                                         ((1,16),['right','a']),((13,16),['a'])])
def test_all_four_source_cursors_only_navigate_to_run(cursor,actions):
    c=controller();frame=10
    for wanted in actions:
        result=c.context(menu(cursor),**args(frame))
        assert result['available_actions']==[wanted,'wait'] and result['controller_menu_verified']
        if wanted=='right':cursor=(13,cursor[1])
        elif wanted=='down':cursor=(13,16)
        frame+=1
    assert c.run_sent and c.stage=='running'


def test_old_cursor_blank_old_cursor_does_not_resend_direction():
    c=controller()
    assert c.context(menu(),**args())['available_actions']==['right','wait']
    for frame,t in [(11,text()),(12,menu()),(13,menu())]:
        assert c.context(t,**args(frame))['available_actions']==['wait']
    assert c.context(menu((13,14)),**args(14))['available_actions']==['down','wait']


def test_complete_wild_intro_once_partial_and_old_page_only_wait():
    c=controller()
    assert c.context(text((1,14,'Wild RHYHORN'),(1,16,'appea')),**args())['available_actions']==['wait']
    complete=text((1,14,'Wild RHYHORN'),(1,16,'appeared!'),(18,16,'▼'))
    assert c.context(complete,**args(11))['available_actions']==['a','wait']
    assert c.context(complete,**args(12))['available_actions']==['wait']
    assert c.context(menu((13,16)),**args(13))['available_actions']==['a','wait']


def test_run_confirmation_receipt_and_two_new_closed_frames():
    c=controller()
    assert c.context(menu((13,16)),**args())['available_actions']==['a','wait']
    assert c.context(menu((13,16)),**args(11))['available_actions']==['wait']
    assert c.context(menu((13,16),'▷'),**args(12))['available_actions']==['wait']
    assert c.context(text((1,14,'Got away safe')),**args(13))['available_actions']==['wait']
    full=text((1,14,'Got away safely!'),(18,16,'▼'))
    assert c.context(full,**args(14))['available_actions']==['a','wait']
    assert c.context(full,**args(15))['available_actions']==['wait']
    closed=text(hud=False);closed['window_visible']=False
    a=args(16,raw=0);a['overworld_ready']=True
    assert c.context(closed,**a)['available_actions']==['wait']
    a=args(17,raw=0);a['overworld_ready']=True
    result=c.context(closed,**a)
    assert result['safari_run_complete'] and result['safari_run_message_seen'] and result['available_actions']==['wait']


@pytest.mark.parametrize('change', ['profile','alignment','read_error','partial_menu','duplicate_label',
                                   'duplicate_cursor','wrong_ball_text','unknown_dialogue','upper_pollution'])
def test_unknown_or_unverified_ui_never_selects_ball_bait_rock(change):
    c=controller();t=menu((13,16))
    if change=='profile':t.pop('profile')
    elif change=='alignment':t['alignment_verified']=False
    elif change=='read_error':t['read_error']='unknown'
    elif change=='partial_menu':t['cells'][16][14:17]=list('RU ')
    elif change=='duplicate_label':t['cells'][13][2:5]=list('RUN')
    elif change=='duplicate_cursor':t['cells'][14][1]='▶'
    elif change=='wrong_ball_text':t=menu((13,16),count='29')
    elif change=='unknown_dialogue':t=text((1,14,'Throw a rock?'))
    else:t['cells'][3][:3]=list('YES')
    result=c.context(t,**args())
    assert result['phase']=='campaign_review' and result['available_actions']==['wait'] and not c.run_sent


@pytest.mark.parametrize('change', ['type','raw','active','frame','safari_unknown','safari_false','game_over',
                                   'balls','cross_packet_balls','steps','map','enemy','enemy_name','intent'])
def test_inconsistent_safari_battle_or_accounting_stops(change):
    c=controller();a=args()
    if change=='type':a['battle_signal']['battle_type']=0
    elif change=='raw':a['battle_signal']['raw']=2
    elif change=='active':a['battle_state']['active']=None
    elif change=='frame':a['battle_signal']['observation_frame']=True
    elif change=='safari_unknown':a['safari']['read_valid']=False
    elif change=='safari_false':a['safari']['in_safari']=False
    elif change=='game_over':a['battle_signal']['game_over']=True
    elif change=='balls':a['battle_signal']['balls']=a['safari']['balls']=29
    elif change=='cross_packet_balls':a['safari']['balls']=29
    elif change=='steps':a['safari']['steps']=399
    elif change=='map':a['location']['map_id']=222
    elif change=='enemy':a['battle_signal']['enemy_species']=76
    elif change=='enemy_name':a['battle_state']['opponent_species']='TAUROS'
    else:c.intent={'kind':'throw_safari_ball'}
    result=c.context(menu((13,16)),**a)
    assert result['available_actions']==['wait'] and result['phase']=='campaign_review' and not c.run_sent


def test_no_control_of_ordinary_wild_or_trainer_outside_safari():
    for raw in (1,2):
        c=controller();a=args();a['location']['map_id']=23
        a['battle_signal'].update(location=deepcopy(a['location']),raw=raw,battle_type=0,flags_raw=0,in_safari=False)
        assert c.context(menu(),**a) is None and not c.run_sent


def test_pending_run_only_waits_unreadable_transition_and_does_not_fake_closed_proof():
    c=controller();c.context(menu((13,16)),**args())
    bad=text();bad.update(read_valid=False,alignment_verified=False,read_error='visible_display_disabled')
    a=args(11,raw=0);a['overworld_ready']=True
    result=c.context(bad,**a)
    assert result['available_actions']==['wait'] and 'safari_run_complete' not in result
    assert c.context(None,**args(12))['available_actions']==['wait']


def test_cannot_complete_on_unclosed_or_single_frame_and_never_invents_receipt():
    c=controller();c.context(menu((13,16)),**args())
    closed=text(hud=False);closed['window_visible']=False
    assert 'safari_run_complete' not in c.context(closed,**args(11,raw=0))
    a=args(12,raw=0);a['overworld_ready']=True
    assert 'safari_run_complete' not in c.context(closed,**a)
    a=args(13,raw=0);a['overworld_ready']=True
    result=c.context(closed,**a)
    assert result['safari_run_complete'] and result['safari_run_message_seen'] is False


def test_calls_time_and_waits_are_bounded():
    c=controller();c.context(menu(),**args(now=0.))
    assert c.context(menu(),**args(11,now=60.001))['review_reason']=='safari_run_budget_exhausted'
    c=controller();c.context(menu(),**args())
    for n in range(1,27):result=c.context(menu(),**args(10+n))
    assert result['review_reason']=='safari_run_wait_budget_exhausted'
    c=controller();c.calls=150
    assert c.context(menu(),**args())['review_reason']=='safari_run_budget_exhausted'


def test_same_frame_or_changed_source_cannot_resend_or_mutate_inputs():
    c=controller();a=args();t=menu();snapshot=deepcopy((a,t))
    c.context(t,**a)
    assert (a,t)==snapshot
    assert c.context(t,**a)['available_actions']==['wait']
    changed=deepcopy(a);changed['safari']['gate_script']=1
    assert c.context(t,**changed)['phase']=='campaign_review'


@pytest.mark.parametrize('change', ['missing','boolbyte','torn','wrong_frame','sdk','event','location'])
def test_reader_unknowns_fail_closed_without_partial_valid_data(change):
    data=memory();kw={}
    if change=='missing':del data[0xDA47]
    elif change=='boolbyte':data[0xD05A]=True
    elif change=='torn':
        class Torn(dict):
            calls=0
            def __getitem__(self,k):
                if k==0xD05A:
                    self.calls+=1
                    return 2 if self.calls==1 else 0
                return super().__getitem__(k)
        data=Torn(data)
    elif change=='wrong_frame':kw['observation_frame']=11
    elif change=='sdk':kw['constants']=SimpleNamespace()
    elif change=='event':
        c=sdk();c.EVENT_FLAGS={'in_safari_zone':590,'safari_game_over':591};kw['constants']=c
    else:kw['location']={'map_id':220,'x':17,'y':22}
    result=read(data,**kw)
    assert result['read_valid'] is False and 'balls' not in result


def test_negative_monotonic_clock_never_requests_a_button():
    result=controller().context(menu(),**args(now=-1.))
    assert result['phase']=='campaign_review' and result['available_actions']==['wait']


def test_unreadable_packet_between_closed_frames_restarts_closure_proof():
    c=controller();c.context(menu((13,16)),**args())
    closed=text(hud=False);closed['window_visible']=False
    a=args(11,raw=0);a['overworld_ready']=True
    assert not c.context(closed,**a).get('safari_run_complete')
    invalid=text(hud=False);invalid.update(read_valid=False,read_error='visible_display_disabled')
    assert c.context(invalid,**args(12,raw=0))['available_actions']==['wait']
    a=args(13,raw=0);a['overworld_ready']=True
    assert not c.context(closed,**a).get('safari_run_complete')
    a=args(14,raw=0);a['overworld_ready']=True
    assert c.context(closed,**a)['safari_run_complete']


def test_sdk_anchors_and_all_safari_maps_match_installed_official_constants():
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as c
    from laya_pokemon.safari_entry import SAFARI_MAPS
    assert {k:getattr(c,k) for k in sb.SDK_ANCHORS}==sb.SDK_ANCHORS
    assert SAFARI_MAPS=={v for k,v in c.MAPS.items() if k.startswith('safari_zone_') and k!='safari_zone_gate'}


# 2026-10-24首遇EXEGGCUTE開場wipe：合成原場契約，不讀實況或存檔。
def exeggcute_args(frame=10,now=1.,raw=1):
    a=args(frame,now,raw)
    a['location']={'map_id':220,'x':22,'y':13}
    a['battle_signal'].update(location=deepcopy(a['location']),steps=479,
                              enemy_species=12 if raw==1 else None,
                              enemy_level=24 if raw==1 else None)
    a['safari']['steps']=479
    a['battle_state']['opponent_species']='EXEGGCUTE' if raw==1 else None
    return a


def exeggcute_text(*entries,hud=True):
    return text(*([(1,0,'EXEGGCUTE'),(5,1,'24')] if hud else []),*entries,hud=False)


def exeggcute_menu(cursor=(1,14)):
    return exeggcute_text((2,14,'BALL×'),(7,14,'30'),(14,14,'BAIT'),(2,16,'THROW ROCK'),
                          (14,16,'RUN'),(cursor[0],cursor[1],'▶'))


def native_wipe(placement='full'):
    t=exeggcute_text(hud=False)
    for y in (range(18) if placement=='full' else [3 if placement=='upper' else 15]):
        t['cells'][y]=['9']*20
    return t


def run_review(result):
    assert result['phase']=='campaign_review' and result['available_actions']==['wait']
    assert not result.get('safari_run_complete')
    return result['review_reason']


def test_exeggcute_native_wipe_blank_alignment_typing_intro_then_exact_run_and_close():
    c=controller()
    first=exeggcute_args();snapshot=deepcopy(first)
    assert c.context(native_wipe(),**first)['available_actions']==['wait']
    assert first==snapshot and not c.intro_sent and not c.run_sent
    assert c.context(exeggcute_text(hud=False),**exeggcute_args(11))['available_actions']==['wait']
    fault=exeggcute_text(hud=False);fault.update(read_valid=False,alignment_verified=False,
                                               read_error='visible_tile_alignment_incomplete')
    assert c.context(fault,**exeggcute_args(12))['available_actions']==['wait']
    partial=exeggcute_text((1,14,'Wild EXEGGCUTE'),(1,16,'appea'))
    assert c.context(partial,**exeggcute_args(13))['available_actions']==['wait']
    full=exeggcute_text((1,14,'Wild EXEGGCUTE'),(1,16,'appeared!'),(18,16,'▼'))
    assert c.context(full,**exeggcute_args(14))['available_actions']==['a','wait']
    assert c.intro_sent and not c.run_sent
    assert c.context(exeggcute_menu(),**exeggcute_args(15))['available_actions']==['right','wait']
    assert c.context(exeggcute_menu(),**exeggcute_args(16))['available_actions']==['wait']
    assert c.context(exeggcute_menu((13,14)),**exeggcute_args(17))['available_actions']==['down','wait']
    assert c.context(exeggcute_menu((13,16)),**exeggcute_args(18))['available_actions']==['a','wait']
    assert c.run_sent
    receipt=exeggcute_text((1,14,'Got away safely!'),(18,16,'▼'))
    assert c.context(receipt,**exeggcute_args(19))['available_actions']==['a','wait']
    closed=exeggcute_text(hud=False);closed['window_visible']=False
    a=exeggcute_args(20,raw=0);a['overworld_ready']=True
    assert not c.context(closed,**a).get('safari_run_complete')
    a=exeggcute_args(21,raw=0);a['overworld_ready']=True
    result=c.context(closed,**a)
    assert result['safari_run_complete'] and result['safari_run_message_seen']
    assert result['available_actions']==['wait']


@pytest.mark.parametrize('placement',['full','upper','lower'])
def test_opening_only_nines_and_spaces_waits_regardless_of_wipe_row(placement):
    c=controller();result=c.context(native_wipe(placement),**exeggcute_args())
    assert result['phase']=='safari_battle' and result['available_actions']==['wait']
    assert c.stage=='start' and not c.intro_sent and not c.run_sent


@pytest.mark.parametrize('error',['visible_display_disabled','visible_tile_alignment_incomplete'])
def test_initial_known_decoder_transition_is_wait_only(error):
    c=controller();t=exeggcute_text(hud=False)
    t.update(read_valid=False,alignment_verified=False,read_error=error)
    result=c.context(t,**exeggcute_args())
    assert result['available_actions']==['wait'] and result['phase']=='safari_battle'
    assert not c.intro_sent and not c.run_sent


@pytest.mark.parametrize('change',['source_profile','balls','flags','cross_steps','frame','enemy_changed'])
def test_wipe_wait_cannot_bypass_same_encounter_source_contract(change):
    c=controller();c.context(native_wipe(),**exeggcute_args())
    a=exeggcute_args(11)
    if change=='source_profile':a['battle_signal']['profile']='unknown'
    elif change=='balls':a['battle_signal']['balls']=a['safari']['balls']=29
    elif change=='flags':
        a['battle_signal'].update(flags_raw=0,in_safari=False);a['safari']['in_safari']=False
    elif change=='cross_steps':a['safari']['steps']=478
    elif change=='frame':a['battle_signal']['observation_frame']=10
    else:
        a['battle_signal']['enemy_species']=18;a['battle_signal']['enemy_level']=25
        a['battle_state']['opponent_species']='RHYHORN'
    run_review(c.context(native_wipe(),**a));assert not c.intro_sent and not c.run_sent


@pytest.mark.parametrize('where,char',[(3,'X'),(15,'0'),(15,'▶')])
def test_valid_wipe_with_any_foreign_character_is_review(where,char):
    c=controller();t=native_wipe();t['cells'][where][5]=char
    run_review(c.context(t,**exeggcute_args()))


@pytest.mark.parametrize('stage',['intro','menu','run'])
def test_nines_after_intro_menu_or_run_cannot_reenter_initial_wipe_exception(stage):
    c=controller()
    if stage=='intro':
        t=exeggcute_text((1,14,'Wild EXEGGCUTE'),(1,16,'appeared!'))
        c.context(t,**exeggcute_args())
    elif stage=='menu':c.context(exeggcute_menu(),**exeggcute_args())
    else:c.context(exeggcute_menu((13,16)),**exeggcute_args())
    run_review(c.context(native_wipe(),**exeggcute_args(11)))


def test_initial_native_wipe_twenty_five_waits_then_sticky_review():
    c=controller()
    for i in range(25):
        result=c.context(native_wipe(),**exeggcute_args(10+i))
        assert result['phase']=='safari_battle' and result['available_actions']==['wait']
    reason=run_review(c.context(native_wipe(),**exeggcute_args(35)))
    assert reason=='safari_run_wait_budget_exhausted'
    assert run_review(c.context(exeggcute_menu((13,16)),**exeggcute_args(36)))==reason
    assert not c.intro_sent and not c.run_sent


def test_initial_wipe_same_frame_never_resends_and_conflicting_packet_is_review():
    c=controller();t=native_wipe();a=exeggcute_args()
    assert c.context(t,**a)['available_actions']==['wait']
    assert c.context(t,**a)['available_actions']==['wait']
    changed=deepcopy(t);changed['cells'][3][3]=' '
    run_review(c.context(changed,**a))


def test_initial_wipe_cannot_bypass_wall_or_total_call_budget():
    c=controller();c.context(native_wipe(),**exeggcute_args())
    assert run_review(c.context(native_wipe(),**exeggcute_args(11,now=61.001)))=='safari_run_budget_exhausted'
    c=controller();c.calls=150
    assert run_review(c.context(native_wipe(),**exeggcute_args()))=='safari_run_budget_exhausted'
