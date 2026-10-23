"""四人隊已確認Cut使用者的背景▷不可被當成另一個活動游標。"""
from copy import deepcopy
import pytest
from laya_pokemon.field_moves import CutController

def selected_menu():
    c=CutController({'kind':'use_cut','species':9,'map_id':19,'tree_x':41,'tree_y':10})
    c.baseline=[(102,[33,28,0,0]),(35,[64,45,43,31]),(9,[75,15,73,22]),(7,[61,33,30,40])]
    c.target_index=2;c.field_user_confirmed=True;c.stage='choose_user'
    rows=[[' ']*20 for _ in range(18)]
    for y,name in [(0,'EEVEE'),(2,'FEAROW'),(4,'IVYSAUR'),(6,'NIDOKING')]:rows[y][3:3+len(name)]=list(name)
    for y,label in [(10,'CUT'),(12,'STATS'),(14,'SWITCH'),(16,'CANCEL')]:rows[y][13:13+len(label)]=list(label)
    rows[10][12]='▶';rows[5][0]='▷'
    return c,[''.join(r) for r in rows]

def test_actual_four_member_background_allows_only_verified_cut():
    c,rows=selected_menu();result=c._field_cut_choice(rows)
    assert result['objective']=='Confirm the current selection.' and result['menu_label']=='CUT'
    assert c.stage=='cut_selected'

@pytest.mark.parametrize('change',[
    lambda c,r:setattr(c,'field_user_confirmed',False),
    lambda c,r:setattr(c,'target_index',1),
    lambda c,r:r.__setitem__(4,r[4].replace('IVYSAUR','VENUSAR')),
    lambda c,r:r.__setitem__(3,'▷'+r[3][1:]),
    lambda c,r:r.__setitem__(12,r[12][:12]+'▶'+r[12][13:]),
])
def test_wrong_or_extra_background_marker_cannot_confirm(change):
    c,rows=selected_menu();change(c,rows)
    result=c._field_cut_choice(rows)
    assert result['phase']=='campaign_review' and result['available_actions']==['wait']
