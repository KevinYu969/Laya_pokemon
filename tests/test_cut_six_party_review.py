"""具名恢復保留原Cut實例／基線／等待計數，不能清除其他錯誤。"""
from types import SimpleNamespace
from copy import deepcopy
import pytest
from laya_pokemon.campaign_route import _review_cut_six_party


def case():
    party=[dict(species=species,moves=moves) for species,moves in
           [(7,[61,57,30,40]),(132,[70,133,156,34]),(102,[33,28,98,39]),
            (154,[75,15,73,22]),(35,[64,65,43,31]),(19,[55,34,47,54])]]
    c=SimpleNamespace(error='cut_field_submenu_cursor_unverified',stage='choose_user',
        field_user_confirmed=True,target_index=3,baseline=[(m['species'],m['moves'][:]) for m in party],
        start_location=dict(map_id=27,x=34,y=10,facing='up'),safe_wait_count=8,safe_wait_stage='choose_user')
    step=dict(id='route16-native-cut',kind='use_cut',map_id=27,tree=[34,9],reviewed_cut_six_party_revision=1)
    state=dict(frame=1436457,location=dict(map_id=27,x=34,y=10),progress=dict(party=party))
    return c,step,state


def test_real_named_review_clears_only_error_and_retains_original_baseline_and_waits():
    c,step,state=case();base=c.baseline;before=deepcopy(state)
    assert _review_cut_six_party(c,step,state) is None and c.error is None
    assert c.baseline is base and c.safe_wait_count==8 and c.safe_wait_stage=='choose_user'
    assert c.field_user_confirmed and state==before
    assert _review_cut_six_party(c,step,state) is None and c.safe_wait_count==8


@pytest.mark.parametrize('field,value',[('error','cut_other_error'),('stage','initial'),
                                      ('field_user_confirmed',False),('target_index',4),('baseline',[])])
def test_wrong_controller_can_never_be_reset(field,value):
    c,step,state=case();setattr(c,field,value)
    assert _review_cut_six_party(c,step,state)=='cut_six_party_named_review_unverified'
    assert c.safe_wait_count==8


@pytest.mark.parametrize('frame',[1436456,1436458,True])
def test_named_frame_cannot_be_reused_elsewhere(frame):
    c,step,state=case();state['frame']=frame
    assert _review_cut_six_party(c,step,state)=='cut_six_party_named_review_unverified'
