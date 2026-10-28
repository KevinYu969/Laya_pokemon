"""Typed TM peer fixtures; synthetic source replay, never a real-game claim."""
from copy import deepcopy
import importlib.util
from pathlib import Path


def _load_source_helpers():
    path=Path(__file__).with_name('test_tm24_teaching.py').resolve()
    spec=importlib.util.spec_from_file_location('_tm24_parent_fixture_source',path)
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    return helpers


# Bind real readonly readers at collection, before route's UI spies are installed.
HELPERS=_load_source_helpers()


def seed_tm24_peer(bridge, owner, *, complete=False):
    assert HELPERS.bridge is bridge
    run=HELPERS.Run()
    if complete:
        run.until('postbag')
        assert HELPERS.action(run.call('start6'))=='b'
        assert not run.call('blank').get('tm24_complete')
        result=run.call('blank')
        packet=run.fake.packet()
        state=dict(frame=packet['frame'],progress=packet['progress'],location=packet['location'],battle_state=packet['battle_state'])
        assert bridge._completion_valid(run.controller,state,packet['text'],HELPERS.grid(packet['frame']),packet['movement'],packet['frame'],None,result)
        assert run.controller.stage=='complete' and run.controller.pending is None
        assert run.fake.memory.writes==[]
    step=dict(id=owner,kind='interact',mechanic=bridge.MECHANIC,map_id=174,target=[7,7],teaching_intent=deepcopy(bridge.tm24_teaching.INTENT))
    bridge._BINDINGS[owner]=dict(step=step,job=bridge.JOB)
    bridge._CONTROLLERS[owner]=run.controller
    bridge._OWNERS[owner]=dict(pyboy=run.fake,controller=run.controller)
    if complete:bridge._COMPLETED.add(owner)
    assert bridge._registry_problem() is None
    assert bridge._active()==(set() if complete else {owner})
    return run.fake,run.controller
