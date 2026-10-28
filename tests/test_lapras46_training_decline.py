"""Canonical-import, synthetic UI tests. No private logs, state or live game."""
from copy import deepcopy
from pathlib import Path
import re

import pytest
from laya_pokemon import training_future_decline as c

assert Path(c.__file__).resolve()==Path(__file__).resolve().parent.parent/'src/laya_pokemon/training_future_decline.py'


@pytest.fixture(autouse=True)
def isolate_session(monkeypatch):
    monkeypatch.setattr(c,'_SESSION',None)


def progress():
    rows=[(154,'VENUSAUR',[75,15,73,22],[25,30,10,10]),
        (35,'FEAROW',[64,65,19,31],[35,20,15,20]),
        (102,'EEVEE',[44,28,98,39],[25,15,30,30]),
        (132,'SNORLAX',[70,133,156,34],[15,20,10,15]),
        (7,'NIDOKING',[61,57,30,40],[20,15,25,35]),
        (19,'LAPRAS',[57,34,58,85],[15,15,10,15])]
    return dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
        party_read_valid=True,party_count=6,player_name_raw='KEVIN',badges_raw=255,
        money=1000,inventory=[],story_event_bits={},party=[
            dict(species=s,species_name=n,level=46 if s==19 else 45,exp=100000,
                hp=100,max_hp=100,status=0,moves=m,pp=p) for s,n,m,p in rows])


def text(*items,window=True):
    cells=[[' ']*20 for _ in range(18)]
    for x,y,value in items:
        assert x+len(value)<=20
        cells[y][x:x+len(value)]=list(value)
    rows=[''.join(row) for row in cells]
    selected=[(i,row.rstrip()) for i,row in enumerate(rows) if re.search('[A-Za-z0-9]{2,}',row)][:12]
    return dict(profile=c.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
        window_visible=window,cells=cells,lines=[v for _,v in selected],line_rows=[i for i,_ in selected])


def call(p,page):
    before=deepcopy((p,page));out=c.context(page,p['party'],p)
    assert before==(p,page)
    return out


def question(kind,selected):
    lines=((1,14,'for HYDRO PUMP?'),) if kind=='delete' else ((1,14,'Abandon learning'),(1,16,'HYDRO PUMP?'))
    return text((15,8,'YES'),(15,10,'NO'),(14,8 if selected=='YES' else 10,'▶'),*lines)


def to_delete(p):
    pages=[text((1,14,'LAPRAS is'),(1,16,'trying to learn'),(18,16,'▼')),
        text((1,14,'trying to learn'),(1,16,'HYDRO PUMP!')),
        text((1,14,'But, LAPRAS'),(1,16,'cant learn more'),(18,16,'▼')),
        text((1,14,'than 4 moves!')),
        text((1,14,'Delete an older'),(1,16,'move to make room'),(18,16,'▼'))]
    for page in pages:assert call(p,page)['phase']=='learning_menu'


def test_lapras46_hydro_pump_normal_decline_preserves_surf_and_all_resources():
    p=progress();before=deepcopy(p)
    plan=c.candidate_plan(19,46,[57,34,58,85])
    assert plan['decision']=='skip' and plan['new_move_id']==56 and plan['move']=='HYDRO_PUMP'
    to_delete(p)
    assert call(p,question('delete','YES'))['available_actions'][0]=='down'
    assert call(p,question('delete','NO'))['menu_label']=='NO'
    assert call(p,question('abandon','NO'))['available_actions'][0]=='up'
    assert call(p,question('abandon','YES'))['menu_label']=='YES'
    assert not call(p,text((1,14,'did not learn'),(1,16,'HYDRO PUMP!'))).get('learning_declined_verified')
    call(p,text((1,14,'LAPRAS'),(1,16,'did not learn'),(18,16,'▼')))
    out=call(p,text((1,14,'did not learn'),(1,16,'HYDRO PUMP!')))
    assert out['learning_declined_verified'] and out['learning_moves_unchanged']
    assert out['learning_result']=='skipped_unchanged' and 'learning_receipt' not in out
    assert p==before
    assert call(p,text(window=False)) is None and c._SESSION is None


def test_lapras46_wrong_roster_moves_unknown_result_or_pp_change_never_approve(monkeypatch):
    assert c.candidate_plan(19,45,[57,34,58,85]) is None
    assert c.candidate_plan(102,37,[33,28,98,39]) is None
    for moves in ([0,34,58,85],[56,34,58,85],[57,34,58,84]):
        monkeypatch.setattr(c,'_SESSION',None);p=progress();p['party'][5]['moves']=moves
        assert c.candidate_plan(19,46,moves)['decision']=='review'
        out=call(p,text((1,14,'LAPRAS is'),(1,16,'trying to learn'),(18,16,'▼')))
        assert out['phase']=='strategy_review' and out['available_actions']==['wait']
    for bad in ('pp','learned','wrong_move'):
        monkeypatch.setattr(c,'_SESSION',None);p=progress();to_delete(p)
        if bad=='pp':p['party'][5]['pp'][0]-=1;page=question('delete','NO')
        elif bad=='learned':page=text((1,14,'LAPRAS learned'),(1,16,'HYDRO PUMP!'))
        else:page=text((1,14,'for ICE BEAM?'),(15,8,'YES'),(15,10,'NO'),(14,10,'▶'))
        out=call(p,page)
        assert out['phase']=='strategy_review' and out['available_actions']==['wait']
        assert not out.get('learning_declined_verified')
