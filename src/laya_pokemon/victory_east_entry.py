"""Only Route23's east training entry: bounded readonly WAIT, no completion."""
JOB='league-six-party45-game29-20261028'
SUPERVISOR='vr2-east-balanced45-v1'
COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE=dict(map_id=194,x=14,y=31)  # New map byte, source coordinates/header.
LANDING=dict(map_id=194,x=29,y=7)
OLD_HEADER=(23,72,10,7)
NEW_HEADER=(17,9,15,13)
MAX_FRAMES,MAX_WAITS=240,8
_WAITS=globals().get('_WAITS',{})
_ERROR=globals().get('_ERROR',None)
_ADDR=(0xD35E,0xD362,0xD361,0xD367,0xD368,0xD369,0xD4E1,
       0xCD38,0xCD6B,0xCFC5,0xD736,0xD730,0xD733,0xD72D,0xD057)
_LOAD_ERRORS=frozenset(('frame_or_grid_unverified','closed_world_required','native_header_or_objects_unverified'))


def _active():
    if (type(_WAITS) is not dict or any(type(k) is not str or not k or type(v) is not dict
            or type(v.get('done')) is not bool or type(v.get('owner')) is not str or not v['owner']
            for k,v in _WAITS.items()) or _ERROR is not None and (type(_ERROR) is not str or not _ERROR)):
        return None
    return {'east-entry-error'} if _ERROR else {v['owner'] for v in _WAITS.values() if not v['done']}


def _pair(plan,step_id):
    """Only exact adjacent move semantics; IDs may change for each outing."""
    try:
        if (type(plan) is not dict or plan.get('mode')!='league_campaign'
                or plan.get('training_job')!=JOB or plan.get('training_supervisor')!=SUPERVISOR
                or plan.get('source_commit')!=COMMIT or type(step_id) is not str
                or type(plan.get('steps')) is not list or any(type(s) is not dict
                    or type(s.get('id')) is not str or not s['id'] for s in plan['steps'])):
            return None
        steps=plan['steps'];ids=[s['id'] for s in steps]
        if len(ids)!=len(set(ids)) or step_id not in ids:return None
        for a,b in zip(steps,steps[1:]):
            if step_id not in (a['id'],b['id']):continue
            av={k:v for k,v in a.items() if k!='id'};bv={k:v for k,v in b.items() if k!='id'}
            if (av!=dict(kind='move',map_id=34,target=[14,31],next_map=194,terminal=True)
                    or bv!=dict(kind='move',map_id=194,target=[29,7])
                    or type(a['map_id']) is not int or type(a['next_map']) is not int
                    or type(b['map_id']) is not int or type(a['target']) is not list
                    or a.get('terminal') is not True
                    or type(b['target']) is not list
                    or any(type(n) is not int for n in a['target']+b['target'])):continue
            return a['id'],b['id']
    except (KeyError,TypeError,ValueError):pass
    return None


def applies(plan,step_id,location):
    active=_active()
    if active is None or active:return True
    pair=_pair(plan,step_id)
    return pair is not None and pair[1] not in _WAITS and location==SOURCE


def _fail(reason,step_id):
    global _ERROR
    if _ERROR is not None and (type(_ERROR) is not str or not _ERROR):_ERROR='registry_unverified'
    elif _ERROR is None:_ERROR=reason if type(reason) is str and reason else 'registry_unverified'
    owners={v['owner'] for v in _WAITS.values() if type(v) is dict and v.get('done') is False
            and type(v.get('owner')) is str} if type(_WAITS) is dict else set()
    owner=next(iter(owners)) if len(owners)==1 else step_id
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='victory_east_entry_'+_ERROR),owner


def _wait(owner):
    return dict(phase='overworld',objective='Wait.',available_actions=['wait'],
        victory_east_entry=owner,suppress_navigation_stall=True,suppress_blocked_edge_learning=True),owner


def preflight(pyboy,state,plan,step_id,*,shared,native_owner,game_id,peer_owners):
    """Read owner/plan/state only, before UI or native memory getters."""
    try:
        active=_active()
        if active is None or _ERROR:return _fail(_ERROR or 'registry_unverified',step_id)
        if not applies(plan,step_id,state.get('location') if type(state) is dict else None):return None
        pair=_pair(plan,step_id)
        if (pair is None or len(active)>1 or type(game_id) is not str or game_id!='game29'
                or pyboy is None or native_owner is not pyboy or type(state) is not dict
                or type(state.get('frame')) is not int or state['frame']<0
                or type(pyboy.frame_count) is not int or pyboy.frame_count!=state['frame']):
            return _fail('original_scope_step_or_native_changed',step_id)
        if (type(peer_owners) is not dict or set(peer_owners)!=shared.PEER_NAMES
                or any(type(v) is not set or v for v in peer_owners.values()) or shared._active()!=set()):
            return _fail('complete_peer_mutex_required',step_id)
        r=_WAITS.get(pair[1])
        if active and (r is None or r['owner'] not in active):return _fail('active_owner_changed',step_id)
        loc=state.get('location');battle=state.get('battle_state');reason=state.get('review_reason')
        if (type(loc) is not dict or set(loc)!={'map_id','x','y'} or any(type(v) is not int for v in loc.values())
                or loc not in (SOURCE,LANDING) or r is None and loc!=SOURCE
                or r is not None and r['landed'] and loc!=LANDING
                or type(battle) is not dict or type(battle.get('raw')) is not int or battle['raw']!=0
                or battle.get('active') is not False or battle.get('kind')!='none'
                or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=state['frame']
                or state.get('phase') not in ('overworld','unclassified','campaign_review')
                or reason is not None and not (state.get('phase')=='campaign_review'
                    and reason in {'victory_navigation_'+e for e in _LOAD_ERRORS}
                    and (r is None or state['frame']==r['start_frame']))
                or state.get('phase')=='campaign_review' and reason is None):
            return _fail('fixed_transfer_or_nonbattle_unverified',step_id)
        from laya_pokemon.league_training_supervisor import validate_party
        party=validate_party(state.get('progress'))
        if any(m['status']!=0 for m in party):return _fail('healthy_known_party_required',step_id)
        if r is not None and (r['native_owner'] is not pyboy or r['pair']!=pair
                or r['plan']!=shared.canonical(plan) or r['progress']!=shared.canonical(state['progress'])
                or state['frame']<r['last_frame'] or state['frame']-r['start_frame']>MAX_FRAMES):
            return _fail('baseline_or_actual_frame_budget_changed',step_id)
        return None
    except Exception:return _fail('preflight_unverified',step_id)


def context(pyboy,state,plan,step_id,text,grid,npcs,*,shared,native_owner,game_id,peer_owners):
    gate=preflight(pyboy,state,plan,step_id,shared=shared,native_owner=native_owner,
                   game_id=game_id,peer_owners=peer_owners)
    if gate is not None:return gate
    if not applies(plan,step_id,state.get('location')):return None
    try:
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        from laya_pokemon.progress import read_progress
        from laya_pokemon.hm_teaching import _rows
        from laya_pokemon.campaign_transactions import verified_blank_transaction_world
        from laya_pokemon import victory_road_navigation as nav,world_map,victory_later_boulders_bridge as later
        if (type(sdk.STATUS_FLAGS3_ADDRESS) is not int or sdk.STATUS_FLAGS3_ADDRESS!=0xD72D
                or any(type(sdk.MAPS.get(k)) is not int or sdk.MAPS[k]!=v
                       for k,v in (('route_23',34),('victory_road_2f',194)))):
            return _fail('sdk_source_anchors_unverified',step_id)
        first=tuple(pyboy.memory[a] for a in _ADDR);second=tuple(pyboy.memory[a] for a in _ADDR)
        if (first!=second or pyboy.frame_count!=state['frame']
                or any(type(v) is not int or not 0<=v<=255 for v in first)
                or shared.canonical(read_progress(pyboy,sdk))!=shared.canonical(state['progress'])):
            return _fail('fresh_native_or_full_progress_unverified',step_id)
        ready=verified_blank_transaction_world(text,grid)
        actual=nav.read_victory_road_npcs(pyboy,grid,state['location'],world_map_module=world_map,
                                       boulder_module=later.boulder,overworld_ready=ready)
        if shared.canonical(actual)!=shared.canonical(npcs):return _fail('fresh_original_npc_receipt_required',step_id)
        mid,x,y,tileset,height,width,count,sim,joy,walk,motion,flags5,flags7,flags3,battle=first
        if (dict(map_id=mid,x=x,y=y)!=state['location'] or (tileset,height,width,count) not in (OLD_HEADER,NEW_HEADER)
                or battle!=0 or flags3!=0 or flags7!=0 or sim!=0 or walk!=0 or joy not in (0,255)
                or motion not in (0,1,4,5) or flags5 not in (0,0x24,0x26)
                or _rows(text)!=(' '*20,)*18 or text['window_visible'] is not False):
            return _fail('only_source_native_entry_allowed',step_id)
        pair=_pair(plan,step_id);r=_WAITS.get(pair[1])
        if r is None:
            if ((tileset,height,width,count)!=OLD_HEADER or state['location']!=SOURCE or not ready
                    or type(npcs) is not dict or npcs.get('read_valid') is not False
                    or npcs.get('read_error')!='frame_or_grid_unverified'):
                return _fail('original_route23_header_required',step_id)
            r=dict(done=False,owner=step_id,pair=pair,native_owner=pyboy,plan=shared.canonical(plan),
                progress=shared.canonical(state['progress']),start_frame=state['frame'],last_frame=state['frame'],
                last_packet=None,waits=0,landed=False,history=[])
            _WAITS[pair[1]]=r
        packet=shared.canonical((state,first,text,grid,npcs))
        if state['frame']==r['last_frame'] and r['last_packet'] is not None:
            return _wait(r['owner']) if packet==r['last_packet'] else _fail('same_frame_packet_changed',r['owner'])
        r['landed']=r['landed'] or state['location']==LANDING
        r['last_frame'],r['last_packet']=state['frame'],packet
        if (state['location']==LANDING and (tileset,height,width,count)==NEW_HEADER
                and (sim,joy,walk,flags5)==(0,0,0,0) and motion in (0,4) and ready
                and type(npcs) is dict and npcs.get('read_valid') is True
                and type(npcs.get('observation_frame')) is int and npcs['observation_frame']==state['frame']
                and npcs.get('fixed_floor')==194):
            r.update(done=True,settled_frame=state['frame']);r['history'].append(dict(frame=state['frame'],raw=first,settled=True))
            return None
        if r['waits']>=MAX_WAITS:return _fail('fresh_wait_budget_exceeded',r['owner'])
        r['waits']+=1;r['history'].append(dict(frame=state['frame'],raw=first,settled=False))
        return _wait(r['owner'])
    except Exception:return _fail('readonly_settle_getter_failed',step_id)
