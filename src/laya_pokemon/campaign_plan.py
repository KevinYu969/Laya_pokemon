"""熱更新路線最小格式驗證；不接受 null 或不支援的操作。"""
import json


def validate_approved_stage(plan,stage):
    if stage not in {'league_campaign','battle_recovery','balanced_training'} or plan.get('mode')!=stage:
        raise ValueError('Strata核准階段與本機路線mode不符；不得擴張執行範圍')


def load_plan(path):
    plan=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(plan,dict) or not isinstance(plan.get('steps'),list) or not plan['steps']:
        raise ValueError('路線須為含非空steps的JSON物件')
    ids=set()
    for step in plan['steps']:
        if not isinstance(step,dict) or not isinstance(step.get('id'),str) or not step['id'] or step['id'] in ids:
            raise ValueError('路線ID缺少或重複')
        ids.add(step['id'])
        if step.get('kind') not in {'move','interact','heal','teach_cut','use_cut','gym_switches'}:
            raise ValueError('不支援的路線操作')
        if type(step.get('map_id')) is not int or not 0<=step['map_id']<=255:
            raise ValueError('地圖ID不符')
        target=step.get('target')
        if not isinstance(target,list) or len(target)!=2 or any(type(v) is not int for v in target):
            raise ValueError('目標須為兩個整數座標')
        if 'via' in step and (not isinstance(step['via'],list) or not step['via'] or any(
                not isinstance(point,list) or len(point)!=2 or any(type(v) is not int for v in point)
                for point in step['via'])):
            raise ValueError('via須為非空的整數座標清單')
        if step['kind']=='use_cut':
            tree=step.get('tree')
            if (not isinstance(tree,list) or len(tree)!=2 or any(type(v) is not int or v<0 for v in tree)
                    or step.get('face') not in {'up','down','left','right'}):
                raise ValueError('居合斬須指定樹木整數座標與朝向')
    if plan.get('resume_step') is not None and plan['resume_step'] not in ids:
        raise ValueError('resume_step不存在於路線')
    return plan
