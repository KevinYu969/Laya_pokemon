"""可核對的正常遊戲行程；路線資料可熱更新，不寫遊戲記憶體。"""
import importlib
from . import party_control,balanced_training
if 'waypoint' in globals():
    importlib.reload(party_control)
    importlib.reload(balanced_training)
from . import world_map
importlib.reload(world_map)
read_world_grid,world_direction=world_map.read_world_grid,world_map.world_direction
_LEARNED_EDGES=globals().get('_LEARNED_EDGES',{})
_LAST_ATTEMPT=globals().get('_LAST_ATTEMPT')


def satisfied(step,progress):
    if 'event' in step:return progress['story_event_bits'].get(step['event']) is True
    if 'item' in step:return any(i['item']==step['item'] for i in progress.get('inventory') or [])
    if 'badge' in step:return bool((progress.get('badges_raw') or 0)&step['badge'])
    return False


def healthy(progress):
    party=progress['party']
    return bool(party) and all(m['hp']==m['max_hp'] and not m.get('status',0) for m in party) and all((pp&63)>=3 for move,pp in zip(party[0].get('moves',[]),party[0].get('pp',[])) if move in {22,33})


def waypoint(pyboy,state,plan,step_id,previous):
    global _LAST_ATTEMPT
    steps=plan['steps'];ids=[s['id'] for s in steps]
    if len(ids)!=len(set(ids)):raise ValueError('路線ID重複')
    index=ids.index(step_id) if step_id in ids else 0
    loc=state['location'];progress=state['progress'];mid=loc['map_id'];x,y=loc['x'],loc['y']
    # 先承認已完成的轉場，再判斷補血繞路，避免「進中心→繞路出門→再進中心」循環。
    while index<len(steps) and (satisfied(steps[index],progress) or steps[index].get('next_map')==mid):index+=1
    current=steps[index] if index<len(steps) else {}
    if pyboy is not None and _LAST_ATTEMPT:
        old=_LAST_ATTEMPT
        if (mid,x,y,current.get('id'))==old['key'] and previous and previous[-1]==old['direction']:
            old['misses']+=1
            if old['misses']>=3:
                dx,dy={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}[old['direction']]
                _LEARNED_EDGES.setdefault(mid,set()).add(((x,y),(x+dx,y+dy)))
                _LAST_ATTEMPT=None
        else:_LAST_ATTEMPT=None
    lead=progress['party'][0] if progress.get('party') else None
    needs_heal=lead is not None and (lead['hp']*3<=lead['max_hp']*2 or lead.get('status',0) or sum(pp&63 for move,pp in zip(lead.get('moves',[]),lead.get('pp',[])) if move in {22,33})<3)
    detour=None
    if not plan.get('_detour'):
        if mid in {58,68,64} and current.get('map_id')!=mid:
            detour={'id':'detour-center','map_id':mid,'target':[3,3] if not healthy(progress) else [3,8],'kind':'heal' if not healthy(progress) else 'move','face':'up','terminal':True}
        elif mid==14 and needs_heal:detour={'id':'detour-return-pewter','map_id':14,'target':[-1,9],'kind':'move','terminal':True}
        elif mid==2 and current.get('map_id')==14:detour={'id':'detour-city','map_id':2,'target':[13,25] if not healthy(progress) else [40,17],'kind':'move','terminal':True}
    if detour:
        context,_=waypoint(pyboy,state,{'steps':[detour],'blocked':plan.get('blocked',{}),'_detour':True},detour['id'],previous)
        return context,current.get('id',step_id)
    while index<len(steps):
        step=steps[index]
        if satisfied(step,progress) or ('next_map' in step and mid==step['next_map']):index+=1;continue
        if mid!=step['map_id']:
            return {'phase':'campaign_review','review_reason':'unexpected_map','expected_map':step['map_id'],'route_step':step['id']},step['id']
        target=step.get('target',[x,y]);target={'x':target[0],'y':target[1]}
        if step['kind']=='heal' and healthy(progress):index+=1;continue
        if step['kind']=='move' and [x,y]==list(target.values()) and 'next_map' not in step:index+=1;continue
        if [x,y]==list(target.values()) and step['kind'] in {'interact','heal'}:
            direction=step.get('face','up')
            return {'phase':'overworld','objective':'Confirm the current selection.' if previous and previous[-1]==direction else f'Move {direction.upper()}.',
                    'available_actions':['a','b'] if previous and previous[-1]==direction else ['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'controller_interaction':True},step['id']
        grid=read_world_grid(pyboy,loc)
        blocked=[tuple(p) for p in plan.get('blocked',{}).get(str(mid),[])]
        npcs=world_map.read_npc_obstacles(pyboy,grid,blocked) if grid else None
        if npcs:blocked=list(set(blocked)|set(npcs['positions']))
        cleared=[]
        if mid==61:
            if progress['story_event_bits'].get('got_helix_fossil'):cleared.append((13,6))
            if progress['story_event_bits'].get('got_dome_fossil'):cleared.append((12,6))
            blocked=[p for p in blocked if p not in cleared]
        learned=_LEARNED_EDGES.get(mid,set())
        hint=world_direction(grid,loc,target,blocked,learned) if grid else None
        if not hint and abs(target['x']-x)+abs(target['y']-y)==1 and step.get('terminal') and ((x,y),(target['x'],target['y'])) not in learned:
            direction='up' if target['y']<y else 'down' if target['y']>y else 'left' if target['x']<x else 'right'
            hint={'direction':direction,'kind':'source_verified_terminal_step','path_length':1}
        if hint:
            if npcs:hint['npc_obstacles']=npcs
            if cleared:hint['cleared_story_objects']=cleared
            if learned:hint['observed_blocked_edges']=[list(edge) for edge in sorted(learned)]
            key=(mid,x,y,step['id'])
            if pyboy is not None and (_LAST_ATTEMPT is None or _LAST_ATTEMPT['key']!=key or _LAST_ATTEMPT['direction']!=hint['direction']):
                _LAST_ATTEMPT={'key':key,'direction':hint['direction'],'misses':0}
            return {'phase':'overworld','objective':f"Move {hint['direction'].upper()}.",'available_actions':['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'world_path_hint':hint},step['id']
        return {'phase':'overworld','objective':'Wait.','available_actions':['wait','b'],'navigation_warning':'no_verified_path',
                'goal':step['id'],'route_step':step['id']},step['id']
    return {'phase':'campaign_review','review_reason':'route_extension_required','route_step':'complete'},'complete'
