"""Self-contained source fixtures, real decoders and an actually ACKed warm pure."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import importlib
tm = importlib.import_module('laya_pokemon.tm24_teaching')
h = importlib.import_module('test_tm24_teaching')
assert Path(tm.__file__).resolve() == (ROOT/'src/laya_pokemon/tm24_teaching.py').resolve()
assert Path(h.__file__).resolve() == (ROOT/'tests/test_tm24_teaching.py').resolve()
REAL_AUTHORITY = deepcopy(tm.NATIVE_RETURN_REVIEW)


class Run(h.Run):
    def __init__(self, *, old=False):
        super().__init__()
        self.controller = (h.tm if old else tm).TM24TeachingController(deepcopy(tm.INTENT))
        learned = next(i for i,e in enumerate(h.FIXTURE['schedule']) if e['view']=='learned')
        self.fake.frame_count = 19073-40*(learned+2)

    def rows(self, rows, *, previous=('wait',), consume=False, frame=None):
        self.fake.frame_count = self.fake.frame_count+40 if frame is None else frame
        self.fake.tilemap_background = h.Tilemap(tm._serial(rows))
        self.fake.tilemap_window = self.fake.tilemap_background
        if consume: self.fake.consume()
        return self.controller.context(**self.fake.packet(), previous=previous)


def warm_error(monkeypatch):
    r = Run(); r.until('learned')
    # Reproduce the former source-view omission after the genuine learned A;
    # no flags, pending, clock, resources, or error are manufactured.
    c = r.controller; views = c._views
    omitted = tm._serial(c._start(6,'▷'))
    c._views = lambda: [v for v in views() if v[2] != omitted]
    try:
        out = r.rows(c._start(6,'▷'), previous=['a'], consume=True,frame=19073)
    finally:
        del c._views
    assert out['review_reason']=='tm24_unknown_or_out_of_stage_source_page'
    assert c.stage=='native_return' and c.learned_acked and c.consumed and c.pending is None
    authority = deepcopy(REAL_AUTHORITY)
    authority['source_progress_sha256'] = tm._review_sha(c.last_packet[1])
    monkeypatch.setattr(tm,'NATIVE_RETURN_REVIEW',authority)
    return r, deepcopy(authority)


def test_native_return_waits_start_and_mixed_redraw_then_requires_real_bag_b_start_b_two_worlds():
    r=Run();r.until('learned');c=r.controller
    out=r.rows(c._start(6,'▷'),previous=['a'],consume=True)
    assert h.action(out)=='wait' and c.stage=='native_return' and c.pending is None
    drawing=c._bag(0,0,' ',post=True,arrow=len(c.inventory_after)>3)
    tm._put(drawing,12,12,'OPTION')
    assert h.action(r.rows(drawing))=='wait' and c.pending is None
    out=r.rows(c._bag(0,0,post=True,arrow=len(c.inventory_after)>3))
    assert h.action(out)=='b' and c.pending['stage']=='close_bag' and c.stage=='native_return'
    assert h.action(r.rows(c._start(6),previous=['b']))=='b' and c.stage=='close_bag'
    assert not r.call('blank',previous=['b']).get('tm24_complete')
    assert r.call('blank',previous=['wait'])['tm24_complete']


def test_named_review_changes_only_error_and_history_preserving_all_original_objects(monkeypatch):
    r,cap=warm_error(monkeypatch);c=r.controller
    original=dict(c.__dict__);packet=c.last_packet;pending=c.pending
    out=c.review_native_return_redraw(review_capsule=cap,source_evidence=deepcopy(cap['evidence']))
    assert h.action(out)=='wait' and out['tm24_native_return_reviewed'] is True
    assert c.last_packet is packet and c.pending is pending and c.error is None
    assert {k:v for k,v in c.__dict__.items() if k not in ('error','native_return_review_history')}=={
        k:v for k,v in original.items() if k!='error'}
    assert all(getattr(c,k) is v for k,v in original.items() if k!='error')
    assert c.native_return_review_history[0]['old_error']=='tm24_unknown_or_out_of_stage_source_page'
    # The review itself returns WAIT; no same-frame context/ACK is invented.
    draw=c._bag(0,0,' ',post=True,arrow=len(c.inventory_after)>3);tm._put(draw,12,12,'OPTION')
    assert h.action(r.rows(draw,previous=['wait']))=='wait'
    assert h.action(r.rows(c._bag(0,0,post=True,arrow=len(c.inventory_after)>3)))=='b'
    assert h.action(r.rows(c._start(6),previous=['b']))=='b'
    r.call('blank',previous=['b']);assert r.call('blank',previous=['wait'])['tm24_complete']


@pytest.mark.parametrize('bad',['capsule','evidence','other_error','stage','frame','pending','calls','waits',
    'clock','and_ack','learned_ack','consumed','cursor','closed','previous','location','battle','movement',
    'text','progress','history'])
def test_review_never_clears_unknown_state_or_refunds_budget(bad,monkeypatch):
    r,cap=warm_error(monkeypatch);c=r.controller;ev=deepcopy(cap['evidence'])
    if bad=='capsule':cap['plan_bytes_sha256']='a'*64
    if bad=='evidence':ev['state_sha256']='b'*64
    if bad=='other_error':c.error='tm24_actual_previous_did_not_ack_a'
    if bad=='stage':c.stage='close_bag'
    if bad=='frame':c.last_frame+=1
    if bad=='pending':c.pending=dict(action='b',frame=19073)
    if bad=='calls':c.calls=tm.MAX_CALLS+1
    if bad=='waits':c.waits=tm.MAX_WAITS+1
    if bad=='clock':c.last_now=c.started_at+61
    if bad=='and_ack':c.and_acked=False
    if bad=='learned_ack':c.learned_acked=False
    if bad=='consumed':
        c.consumed=False
        r.fake.game_wrapper.inventory_value=deepcopy(h.FIXTURE['inventory'])
    if bad=='cursor':c.cursor_expected=('bag',0)
    if bad=='closed':c.closed_frame=19073
    packet=list(c.last_packet)
    if bad=='previous':packet[-1]=['wait']
    if bad=='location':packet[2]['x']+=1
    if bad=='battle':packet[3]['raw']=1
    if bad=='movement':packet[4]['walk_counter']=1
    if bad=='text':packet[0]['cells'][0][0]='X'
    if bad=='progress':packet[1]['party'][1]['exp']+=1
    if bad=='history':c.native_return_review_history=[{'old_error':'already used'}]
    if bad=='previous':c.last_packet=tuple(packet)
    old=dict(c.__dict__);old_error=c.error
    out=c.review_native_return_redraw(review_capsule=cap,source_evidence=ev)
    assert out['phase']=='campaign_review' and c.error==old_error
    assert c.__dict__==old


@pytest.mark.parametrize('bad',['active_start','wrong_start','unknown_mixture','missing_quantity','early_world',
    'and_ack','learned_ack','consumed'])
def test_redraw_wait_is_local_to_proven_success_and_cannot_skip_true_bag_close(bad):
    r=Run();r.until('learned');c=r.controller
    assert h.action(r.rows(c._start(6,'▷'),previous=['a'],consume=True))=='wait'
    view=c._start(6,'▷')
    if bad=='active_start':view=c._start(6)
    if bad=='wrong_start':view=c._start(4,'▷')
    if bad=='unknown_mixture':view[7][2]='X'
    if bad=='missing_quantity':
        view=c._bag(0,0,post=True,arrow=len(c.inventory_after)>3);tm._clear(view,14,5,18,5)
    if bad=='early_world':view=tm._blank()
    if bad=='and_ack':c.and_acked=False
    if bad=='learned_ack':c.learned_acked=False
    if bad=='consumed':
        c.consumed=False
        r.fake.game_wrapper.inventory_value=deepcopy(h.FIXTURE['inventory'])
    out=r.rows(view)
    if bad=='missing_quantity':
        assert h.action(out)=='wait' and c.pending is None
    else:
        assert out['phase']=='campaign_review' and c.pending is None


def test_fixed_review_authority_is_independently_pinned():
    assert REAL_AUTHORITY['source_frame']==19073
    assert REAL_AUTHORITY['original_step_id']=='game29-indigo-lapras-tm24-20261028'
    assert REAL_AUTHORITY['plan_bytes_sha256']=='fe52e2c3c979c27573c365daf9eff4c730befce1742908c313c841762a828f9e'
    assert REAL_AUTHORITY['source_progress_sha256']=='7a6924ad5a0e0dd4fa82e92cf961044801ad2b84f6f95244a9c42c2c08e8341f'
