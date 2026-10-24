from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import campaign_route as route
from tests.test_mansion_transition_ready import env,grid,Memory


def setup_review(e):
    mod=route.mansion_transition_ready;e.loc=(216,23,22);e.now=900.
    frame=1466785
    step=dict(id='mansion-basement-stairs-ready-20261024',kind='interact',
              mechanic=mod.MECHANIC,map_id=216,target=[23,22],reviewed_standing_warp_revision=1)
    plan=dict(training_job='mansion-basement-approach-20261024')
    state=dict(frame=frame,location=dict(map_id=216,x=23,y=22),progress=e.p,
               battle_state=dict(active=False,kind='none',raw=0,observation_frame=frame))
    record=dict(baseline=deepcopy((mod._party(e.p),mod._inventory(e.p['inventory']),e.p['money'])),
                started=10.,last_now=11.5,last_frame=1466785,calls=26,waits=26,
                error=None,closed_frame=None,packet={'original':'retained'})
    mod._CONTROLLERS[step['id']]=record
    mod._BINDINGS[step['id']]=((216,23,22),165,(21,23),'"mansion-basement-approach-20261024"')
    game=SimpleNamespace(frame_count=frame,memory=Memory(e.loc,{0xD736:4}))
    return game,state,plan,step,e.text,grid(e,frame),record


def test_named_review_excludes_only_pause_and_keeps_elapsed_owner_and_counters(env):
    args=setup_review(env);r=args[-1];identity=id(r);before=deepcopy(r)
    assert route._review_mansion_standing_warp(*args[:-1]) is None
    assert id(r)==identity and r['started']==898.5 and r['last_now']==900.
    assert 900.-r['started']==before['last_now']-before['started']==1.5
    assert r['review_excluded_seconds']==888.5
    for k in ('baseline','last_frame','calls','waits','error','closed_frame','packet'):assert r[k]==before[k]
    unchanged=deepcopy(r);env.now=1200.
    assert route._review_mansion_standing_warp(*args[:-1]) is None and r==unchanged


@pytest.mark.parametrize('mutation',[
 lambda a:a[1].update(frame=1466786),lambda a:a[1]['location'].update(x=22),
 lambda a:a[2].update(training_job='other'),lambda a:a[3].update(reviewed_standing_warp_revision=True),
 lambda a:a[-1].update(error='original_error'),lambda a:a[-1].update(waits=24),
 lambda a:a[-1].update(calls=27),lambda a:a[-1].update(last_frame=1466784),
 lambda a:a[-1].update(closed_frame=1466705),lambda a:a[-1].update(last_now=71.),
 lambda a:a[1]['progress'].update(money=1),lambda a:a[0].memory.values.update({0xD736:6}),
 lambda a:a[0].memory.values.update({0xCD38:1}),lambda a:a[5]['tiles'][0].__setitem__(0,1),
 lambda a:a[4].update(read_valid=False),lambda a:a[1]['battle_state'].update(kind='wild'),
])
def test_no_other_review_or_changed_original_state_can_receive_clock_credit(env,mutation):
    args=list(setup_review(env));mutation(args);before=deepcopy(args[-1])
    assert route._review_mansion_standing_warp(*args[:-1])=='mansion_standing_warp_named_review_unverified'
    assert args[-1]==before


@pytest.mark.parametrize('other_owner',[False,True])
def test_owner_binding_drift_cannot_receive_clock_credit(env,other_owner):
    args=setup_review(env);before=deepcopy(args[-1]);mod=route.mansion_transition_ready
    if other_owner:mod._BINDINGS['another-step']=('other',)
    else:mod._BINDINGS[args[3]['id']]=('wrong-owner',)
    assert route._review_mansion_standing_warp(*args[:-1])=='mansion_standing_warp_named_review_unverified'
    assert args[-1]==before
