"""真呼叫waypoint的純合成路線；假PyBoy禁止RAM讀寫，不建立遊戲或模型。"""
from copy import deepcopy
import importlib
from types import SimpleNamespace

import pytest

from laya_pokemon import campaign_route as route


class ForbiddenMemory:
    def __getitem__(self,key):
        raise AssertionError('synthetic waypoint must not read game RAM')

    def __setitem__(self,key,value):
        raise AssertionError('synthetic waypoint must not write game RAM')


def plan(job='trip-a'):
    return {'mode':'league_campaign','training_job':job,'resume_revision':1,
            'steps':[{'id':'north-14-north-east-13','kind':'move','map_id':25,
                      'via':[[13,44],[13,10],[7,10],[7,8],[19,8]],
                      'target':[20,8],'next_map':24},
                     {'id':'east-13','kind':'move','map_id':24,'target':[21,8]}]}


@pytest.fixture
def walk(monkeypatch):
    emulator=SimpleNamespace(memory=ForbiddenMemory())
    grid={'walkable':[[1]*30 for _ in range(50)],'tileset_id':1,
          'screen_cells_verified':90}
    targets=[]

    def patch_readers():
        from laya_pokemon import observation
        monkeypatch.setattr(route,'read_world_grid',lambda *_:deepcopy(grid))
        monkeypatch.setattr(route.world_map,'read_npc_obstacles',lambda *a,**kw:None)
        monkeypatch.setattr(observation,'read_visible_text',lambda *_:{})
        monkeypatch.setattr(route.campaign_transactions,'ui_overworld_ready',lambda *_:True)
        real_direction=route.world_map.world_direction

        def direction(g,location,target,*args):
            targets.append((target['x'],target['y']))
            return real_direction(g,location,target,*args)
        monkeypatch.setattr(route,'world_direction',direction)

    monkeypatch.setattr(route,'_VIA_PROGRESS',{})
    monkeypatch.setattr(route,'_LEARNED_EDGES',{})
    monkeypatch.setattr(route,'_LAST_ATTEMPT',None)
    patch_readers()

    def call(p,position,step_id=None,mid=25,phase='unclassified',battle=False):
        state={'phase':phase,'location':{'map_id':mid,'x':position[0],'y':position[1]},
               'battle_state':{'active':battle,'kind':'wild' if battle else 'none'},
               'progress':{'party':[],'story_event_bits':{}}}
        return route.waypoint(emulator,state,p,step_id or p['steps'][0]['id'],[])

    return SimpleNamespace(call=call,targets=targets,repatch=patch_readers)


def test_actual_waypoint_reproduces_old_two_tile_cycle_then_keeps_progress(walk,monkeypatch):
    p=plan();positions=[(13,44),(13,43),(13,44)]

    def legacy_target(p,step,position):
        via=[tuple(v) for v in step['via']]
        following=via.index(position)+1 if position in via else 0
        return via[following] if following<len(via) else step['target']

    with monkeypatch.context() as patch:
        patch.setattr(route,'_via_target',legacy_target)
        assert [walk.call(p,pos)[0]['objective'] for pos in positions]==[
            'Move UP.','Move DOWN.','Move UP.']
    assert [walk.call(p,pos)[0]['objective'] for pos in positions]==[
        'Move UP.','Move UP.','Move UP.']
    assert walk.targets[-3:]==[(13,10)]*3


def test_visits_all_real_route14_vias_in_order_without_backtracking(walk):
    p=plan();before=deepcopy(p)
    observations=[((13,45),(13,44)),((13,44),(13,10)),((13,43),(13,10)),
                  ((13,11),(13,10)),((13,10),(7,10)),((12,10),(7,10)),
                  ((7,10),(7,8)),((7,9),(7,8)),((7,8),(19,8)),
                  ((8,8),(19,8)),((19,8),(20,8))]
    for position,expected in observations:
        result,step=walk.call(p,position)
        assert step==p['steps'][0]['id'] and result['phase']=='overworld'
        assert walk.targets[-1]==expected
    assert p==before


def test_later_via_position_cannot_skip_an_unreached_earlier_point(walk):
    p=plan()
    walk.call(p,(13,10));assert walk.targets[-1]==(13,44)
    walk.call(p,(13,44));assert walk.targets[-1]==(13,10)
    walk.call(p,(7,10));assert walk.targets[-1]==(13,10)
    walk.call(p,(13,10));assert walk.targets[-1]==(7,10)


def test_retreat_one_cell_and_revisit_earlier_via_never_reset_cursor(walk):
    p=plan()
    for pos in [(13,44),(13,10),(13,11),(13,44)]:walk.call(p,pos)
    assert walk.targets[-3:]==[(7,10)]*3


def test_resume_revision_pause_and_battle_do_not_create_a_new_journey(walk):
    p=plan();walk.call(p,(13,44));p['resume_revision']=8
    for phase,battle in [('battle_dialogue',True),('campaign_review',False),('unclassified',False)]:
        # runner在戰鬥／停檢不發導航；即使只重評同座標，key也不能被phase洗掉。
        walk.call(p,(13,43),phase=phase,battle=battle)
        assert walk.targets[-1]==(13,10)
    assert list(route._VIA_PROGRESS.values())==[1]


def test_module_reload_preserves_the_exact_active_cursor(walk):
    p=plan();walk.call(p,(13,44));saved=route._VIA_PROGRESS
    importlib.reload(route)
    assert route._VIA_PROGRESS is saved
    walk.repatch();walk.call(p,(13,43))
    assert walk.targets[-1]==(13,10) and list(saved.values())==[1]


@pytest.mark.parametrize('change',['job','step_id','via','target','map_id','new_route'])
def test_changed_job_step_or_canonical_geometry_cannot_inherit_cursor(walk,change):
    p=plan();walk.call(p,(13,44));changed=deepcopy(p);mid=25
    if change=='job':changed['training_job']='trip-b'
    elif change=='step_id':changed['steps'][0]['id']='different-step'
    elif change=='via':changed['steps'][0]['via'][1]=[12,10]
    elif change=='target':changed['steps'][0]['target']=[21,8]
    elif change=='map_id':mid=26;changed['steps'][0]['map_id']=26
    else:changed['steps'].append({'id':'new-tail','kind':'move','map_id':24,'target':[23,8]})
    walk.call(changed,(13,43),mid=mid)
    assert walk.targets[-1]==(13,44)
    assert len(route._VIA_PROGRESS)==2


def test_two_active_steps_of_same_job_have_separate_progress(walk):
    p=plan();second=deepcopy(p['steps'][0]);second['id']='same-map-return'
    p['steps'].append(second)
    walk.call(p,(13,44));walk.call(p,(13,43),step_id=second['id'])
    assert walk.targets[-1]==(13,44)
    walk.call(p,(13,43));assert walk.targets[-1]==(13,10)


def test_canonical_job_mapping_order_and_engineering_metadata_preserve_cursor(walk):
    p=plan({'run':'training','batch':2});walk.call(p,(13,44))
    changed=deepcopy(p);changed['training_job']={'batch':2,'run':'training'}
    changed['resume_revision']=12;changed['resume_step']=p['steps'][0]['id']
    changed['blocked']={'25':[[0,0]]};changed['steps'][0]['reviewed_controller_revision']=7
    walk.call(changed,(13,43));assert walk.targets[-1]==(13,10)
    assert len(route._VIA_PROGRESS)==1


@pytest.mark.parametrize('job',[None,'',{},[]])
def test_missing_job_uses_canonical_route_fallback_and_still_isolates_geometry(walk,job):
    p=plan(job);walk.call(p,(13,44));walk.call(p,(13,43))
    assert walk.targets[-1]==(13,10)
    p2=deepcopy(p);p2['steps'][0]['target']=[22,8]
    walk.call(p2,(13,43));assert walk.targets[-1]==(13,44)


def test_duplicate_coordinates_are_consumed_only_when_next_expected_point_is_reached(walk):
    p=plan();p['steps'][0]['via']=[[1,1],[2,1],[1,1],[1,1],[3,1]]
    for pos,expected in [((1,1),(2,1)),((1,1),(2,1)),((2,1),(1,1)),
                         ((1,1),(3,1)),((2,1),(3,1)),((3,1),(20,8))]:
        walk.call(p,pos);assert walk.targets[-1]==expected


def test_finished_vias_and_target_still_require_the_real_next_map_handshake(walk):
    p=plan()
    for pos in p['steps'][0]['via']:walk.call(p,pos)
    result,step=walk.call(p,(20,8))
    assert step==p['steps'][0]['id'] and result['available_actions']==['wait','b']
    assert result.get('review_reason')!='route_extension_required'
    result,step=walk.call(p,(20,8),mid=24)
    assert step=='east-13' and result['objective']=='Move RIGHT.'


def test_move_without_next_map_completes_only_after_all_vias_and_final_target(walk):
    p=plan();p['steps']=p['steps'][:1];del p['steps'][0]['next_map']
    # 初次就站在最終目標不代表走完via。
    result,step=walk.call(p,(20,8));assert step!= 'complete'
    assert walk.targets[-1]==(13,44)
    for pos in p['steps'][0]['via']:walk.call(p,pos)
    result,step=walk.call(p,(20,8))
    assert step=='complete' and result['review_reason']=='route_extension_required'


def test_no_via_has_no_cursor_and_keeps_existing_navigation(walk):
    p=plan();del p['steps'][0]['via']
    result,step=walk.call(p,(19,8))
    assert result['objective']=='Move RIGHT.' and step==p['steps'][0]['id']
    assert route._VIA_PROGRESS=={}


def test_identical_same_job_route_reuse_does_not_guess_a_new_trip_from_return_to_start(walk):
    p=plan()
    for pos in p['steps'][0]['via']:walk.call(p,pos)
    walk.call(deepcopy(p),(13,44));assert walk.targets[-1]==(20,8)
    p['training_job']='explicit-new-trip'
    walk.call(p,(13,43));assert walk.targets[-1]==(13,44)
