"""已檢討的單一倒下隊員：只走完必要解謎到石英中心，不核准繼續挑戰。"""
from hashlib import sha256
import json
import re

JOB='league28-reviewed-fnt-indigo-center-20261028'
KIND='reviewed_nidoking_fnt_to_indigo_v1'
SOURCE_REVIEW_SHA256='81e66c2c3f90a388c91e1f53b13c3525bb5d936dca22cd4cd17f97730d230313'
SOURCE_STATE_SHA256='f744bf950f91d0d7063208fd3eba2f5757d12e9a93f309f4a1f6bd6a2390ed61'
ROSTER=frozenset((7,132,102,154,35,19))
ROUTE=(('move',198,(21,15),None),('interact',198,(21,15),'3f_hole'),
       ('move',198,(23,15),None),('move',194,(22,16),None),
       ('interact',194,(22,16),'strength'),('interact',194,(22,16),'2f_switch2'),
       ('move',194,(25,14),None),('move',198,(27,15),None),
       ('move',198,(26,8),None),('move',194,(27,7),None),
       ('move',194,(30,7),None),('move',34,(14,32),None),
       ('move',34,(9,-1),None),('move',9,(9,17),None),
       ('move',9,(9,5),None),('move',174,(7,7),None),('heal',174,(7,7),None),
       ('move',174,(7,8),None),('move',174,(7,7),None))


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _walk(start,segments):
    x,y=start;out=[]
    for direction,count in segments:
        dx,dy={'r':(1,0),'l':(-1,0),'u':(0,-1),'d':(0,1)}[direction]
        for _ in range(count):x+=dx;y+=dy;out.append([x,y])
    return out


def expected_steps():
    """公開主來源的有限行程；SHA不能藉重新計算放寬via/warp/終點。"""
    steps=[]
    for i,(kind,mid,target,mechanic) in enumerate(ROUTE):
        step=dict(id=f'league28-fnt-recovery-{i:02d}',kind=kind,map_id=mid,target=list(target),recovery_route=True)
        if mechanic=='strength':step.update(mechanic='victory_strength',strength_intent=dict(kind='victory_strength',map_id=194,player_x=22,player_y=16,species=132,move=70))
        elif mechanic:step.update(mechanic='victory_later_boulder',boulder_case=mechanic)
        steps.append(step)
    for i,destination in ((2,194),(6,198),(8,194),(10,34),(12,9),(14,174)):
        steps[i].update(next_map=destination,terminal=True)
    steps[6]['via']=_walk((10,16),(('r',5),('u',2),('r',10)))
    steps[8]['via']=_walk((27,15),(('u',7),('l',1)))
    steps[10]['via']=[[28,7],[29,7]]
    steps[12]['via']=_walk((14,32),(('r',4),('u',12),('l',4),('u',10),('l',1),('u',4),('l',3),('u',6),('l',1)))
    steps[14]['via']=_walk((9,17),(('u',12),))
    steps[15]['via']=_walk((7,11),(('u',4),))
    steps[16].update(face='up',require_full_pp=True)
    return steps


def valid_plan(plan):
    if type(plan) is not dict:return False
    try:
        capsule=plan.get('reviewed_fnt_recovery')
        if (type(plan) is not dict or plan.get('mode')!='league_campaign' or plan.get('training_job')!=JOB
                or type(capsule) is not dict or set(capsule)!={'kind','source_frame','source_location','fainted_species','steps_sha256','review_sha256','state_sha256'}
                or capsule['kind']!=KIND or type(capsule['source_frame']) is not int or capsule['source_frame']!=32809
                or capsule['review_sha256']!=SOURCE_REVIEW_SHA256 or capsule['state_sha256']!=SOURCE_STATE_SHA256
                or capsule['source_location']!={'map_id':198,'x':6,'y':1}
                or digest(capsule['source_location'])!=digest({'map_id':198,'x':6,'y':1})
                or type(capsule['fainted_species']) is not int or capsule['fainted_species']!=7
                or any(type(capsule[k]) is not str or re.fullmatch('[0-9a-f]{64}',capsule[k]) is None
                       for k in ('steps_sha256','review_sha256','state_sha256'))
                or type(plan.get('lead_species')) is not int or plan['lead_species']!=35
                or type(plan.get('steps')) is not list or len(plan['steps'])!=len(ROUTE)
                or digest(plan['steps'])!=digest(expected_steps())
                or capsule['steps_sha256']!=digest(plan['steps'])):return False
        ids=[]
        for step,(kind,mid,target,mechanic) in zip(plan['steps'],ROUTE):
            if (type(step) is not dict or type(step.get('id')) is not str or not step['id']
                    or step.get('kind')!=kind or type(step.get('map_id')) is not int or step['map_id']!=mid
                    or type(step.get('target')) is not list or any(type(x) is not int for x in step['target'])
                    or step['target']!=list(target) or step.get('recovery_route') is not True
                    or set(step)-{'id','kind','map_id','target','via','next_map','terminal','recovery_route','face','require_full_pp','mechanic','boulder_case','strength_intent'}):return False
            ids.append(step['id'])
            if mechanic=='strength':
                if step.get('mechanic')!='victory_strength' or step.get('strength_intent')!={'kind':'victory_strength','map_id':194,'player_x':22,'player_y':16,'species':132,'move':70}:return False
            elif mechanic is not None:
                if step.get('mechanic')!='victory_later_boulder' or step.get('boulder_case')!=mechanic:return False
            elif 'mechanic' in step:return False
        return len(ids)==len(set(ids))
    except (TypeError,KeyError,ValueError,RecursionError):return False


def _known_party(progress):
    if (type(progress) is not dict or progress.get('party_read_valid') is not True
            or type(progress.get('party_count')) is not int or progress['party_count']!=6
            or progress.get('player_name_raw')!='KEVIN'
            or type(progress.get('badges_raw')) is not int or progress['badges_raw']!=255):return None
    party=progress.get('party')
    if (type(party) is not list or len(party)!=6 or any(type(m) is not dict for m in party)
            or any(type(m.get('species')) is not int for m in party)
            or {m.get('species') for m in party}!=ROSTER):return None
    for m in party:
        hp,maximum=m.get('hp'),m.get('max_hp')
        if (type(hp) is not int or type(maximum) is not int or not 0<=hp<=maximum or maximum<=0
                or type(m.get('status')) is not int or m['status']!=0):return None
    return party


def admitted(plan,step_id,progress):
    """救援每一步均核五員存活與同一Nido FNT，不能落回legacy豁免。"""
    if not valid_plan(plan) or not any(s['id']==step_id for s in plan['steps']):return ()
    party=_known_party(progress)
    if party is None or any((m['species']==7 and m['hp']!=0) or (m['species']!=7 and m['hp']<=0) for m in party):return ()
    return (7,)


def allowance(plan,step_id,progress):
    return (7,) if admitted(plan,step_id,progress)==(7,) and next(s for s in plan['steps'] if s['id']==step_id)['kind']=='interact' else ()


def healed_terminal(plan,step_id,state,*,full_party_healed):
    """正常護士全恢復後才允診間兩個普通步驟，產生兩fresh真世界收據。"""
    if not valid_plan(plan) or full_party_healed is not True or type(state) is not dict:return False
    party=_known_party(state.get('progress'))
    if party is None or any(m['hp']!=m['max_hp'] for m in party):return False
    index=next((i for i,s in enumerate(plan['steps']) if s['id']==step_id),-1)
    loc=state.get('location',{})
    return (index>=16 and type(loc) is dict and set(loc)=={'map_id','x','y'}
        and all(type(v) is int for v in loc.values())
        and loc in ({'map_id':174,'x':7,'y':7},{'map_id':174,'x':7,'y':8}))
