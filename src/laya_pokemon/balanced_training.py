"""最低等級輪流首發／正常換人分經驗，達標後停下檢討。"""
from .party_control import lead_context
from .observation import read_visible_text
from .team_strategy import species_key,normalize
from .battle import _selection_hint,_label

_SHARED_EXPERIENCE_PENDING=globals().get('_SHARED_EXPERIENCE_PENDING')
_SHARED_EXPERIENCE_USED_REVIEWS=globals().get('_SHARED_EXPERIENCE_USED_REVIEWS',set())
_SHARED_EXPERIENCE_LAST_COMPLETION=globals().get('_SHARED_EXPERIENCE_LAST_COMPLETION')


def _shared_review(reason):
    return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
            'review_reason':'training_shared_experience_'+reason}


def _shared_closed_state(state,plan,pending):
    """共同的只讀閉合契約；不把歷史 ledger 當 decoder。"""
    from .battle import _trainer_half_party_valid
    if (not isinstance(plan,dict) or plan.get('mode')!='league_campaign'
            or plan.get('training_shared_experience') is not True
            or type(plan.get('training_direct_from_level')) is not int
            or plan['training_direct_from_level']!=25
            or plan.get('training_job')!=pending['signature'][0]
            or not isinstance(state,dict) or state.get('phase') not in ('overworld','unclassified')
            or any(k in state for k in ('review_reason','capture_tactic','snorlax_capture_tactic',
                                       'capture_completion_tactic','unsupported_reason'))):return False
    if ('capture_plan' in state and (not isinstance(state['capture_plan'],dict)
            or state['capture_plan'].get('tactic')!='not_capture')):return False
    frame=state.get('frame');battle=state.get('battle_state');p=state.get('progress');loc=state.get('location')
    if (type(frame) is not int or frame<=pending['last_frame']
            or not isinstance(battle,dict) or type(battle.get('raw')) is not int or battle['raw']!=0
            or battle.get('active') is not False or battle.get('kind')!='none'
            or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=frame
            or not isinstance(p,dict) or p.get('profile')!='gen1-wrapper-ram-progress-v1-unvalidated'
            or p.get('party_read_valid') is not True or p.get('initialization_candidate') is not True
            or type(p.get('party_count')) is not int or p['party_count']!=6
            or not _trainer_half_party_valid(p.get('party')) or len(p['party'])!=6
            or tuple(m['species'] for m in p['party'])!=pending['signature'][2]
            or any(m['hp']<=0 or type(m.get('exp')) is not int or not 0<=m['exp']<=0xFFFFFF for m in p['party'])
            or not isinstance(loc,dict) or any(type(loc.get(k)) is not int or not 0<=loc[k]<=255 for k in ('map_id','x','y'))
            or loc['map_id']!=pending['signature'][4][0]):return False
    from .team_strategy import reference,move_key
    ref=reference()
    for mon in p['party']:
        for move,pp in zip(mon['moves'],mon['pp']):
            if move and pp&63>min(63,int(ref['moves'][move_key(move)]['pp'])*(5+(pp>>6))//5):return False
    return all('observation_frame' not in part or type(part['observation_frame']) is int
               and part['observation_frame']==frame for part in (p,loc))


def _finish_shared_experience(pending,kind,**receipt):
    global _SHARED_EXPERIENCE_PENDING,_SHARED_EXPERIENCE_LAST_COMPLETION
    from copy import deepcopy
    _SHARED_EXPERIENCE_LAST_COMPLETION=deepcopy(dict(training_tactic=kind,
        pending_signature=pending['signature'],last_frame=pending['last_frame'],**receipt))
    _SHARED_EXPERIENCE_PENDING=None


def review_completed_shared_experience(closed_states,plan):
    """純父層審核 API：原始行 SHA／ledger閉合是審核聲明，非本函式讀檔驗證。"""
    import re
    pending=_SHARED_EXPERIENCE_PENDING
    capsule=plan.get('training_completed_battle_review') if isinstance(plan,dict) else None
    if capsule is None:return None
    if (not isinstance(capsule,dict) or capsule.get('schema')!='red-shared-experience-completed-review-v1'
            or not isinstance(capsule.get('nonce'),str) or not capsule['nonce'].strip()
            or len(capsule['nonce'])>128):return _shared_review('completion_review_capsule_invalid')
    if capsule['nonce'] in _SHARED_EXPERIENCE_USED_REVIEWS or pending is None:return None
    if pending.get('error'):return _shared_review(pending['error'])
    sig=pending['signature'];expected=[sig[0],sig[1],list(sig[2]),sig[3],list(sig[4])]
    binding=capsule.get('pending_signature');frames=capsule.get('closed_frames');hashes=capsule.get('closed_row_sha256')
    if (binding!=expected or not isinstance(binding,list) or len(binding)!=5
            or type(binding[1]) is not int or not isinstance(binding[2],list)
            or any(type(v) is not int for v in binding[2]) or not isinstance(binding[4],list)
            or any(type(v) is not int for v in binding[4])
            or type(capsule.get('last_frame')) is not int or capsule['last_frame']!=pending['last_frame']
            or type(capsule.get('current_frame')) is not int
            or not isinstance(frames,list) or len(frames)!=2 or any(type(f) is not int for f in frames)
            or not pending['last_frame']<frames[0]<frames[1]<capsule['current_frame']
            or capsule.get('parent_reviewed') is not True or capsule.get('ledger_closure_verified') is not True
            or not isinstance(hashes,list) or len(hashes)!=2
            or any(not isinstance(h,str) or re.fullmatch('[0-9a-f]{64}',h) is None for h in hashes)
            or not isinstance(closed_states,list) or len(closed_states)!=2):return _shared_review('completion_review_binding_invalid')
    for row,frame in zip(closed_states,frames):
        state=row.get('state') if isinstance(row,dict) else None
        if not _shared_closed_state(state,plan,pending):return _shared_review('completion_review_closed_state_invalid')
        hint=state.get('world_path_hint');loc=state['location'];direction=row.get('action')
        delta={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}.get(direction)
        if (state['frame']!=frame or state.get('visible_text_candidates')!=[]
                or state['progress']['party']!=pending['last_packet'][1]['party']
                or not isinstance(state.get('screen_sha256'),str)
                or re.fullmatch('[0-9a-f]{64}',state['screen_sha256']) is None
                or not isinstance(hint,dict) or delta is None or hint.get('direction')!=direction
                or hint.get('ledge_jump') is not False or type(hint.get('path_length')) is not int or hint['path_length']!=1
                or type(hint.get('screen_cells_verified')) is not int or hint['screen_cells_verified']<=0
                or hint.get('endpoint')!=[loc['x']+delta[0],loc['y']+delta[1]]):return _shared_review('completion_review_closed_state_invalid')
    second=closed_states[1]['state']['location']
    if [second['x'],second['y']]!=closed_states[0]['state']['world_path_hint']['endpoint']:
        return _shared_review('completion_review_movement_not_observed')
    _SHARED_EXPERIENCE_USED_REVIEWS.add(capsule['nonce'])
    _finish_shared_experience(pending,'shared_experience_reviewed_battle_completed',
        nonce=capsule['nonce'],closed_frames=frames,current_frame=capsule['current_frame'],
        source_row_sha256=hashes,parent_reviewed=True)
    return None


def shared_experience_battle_context(pyboy,state,plan):
    """只分派明示六人野戰的正常PKMN換人，不改原context或戰鬥政策。

    已知18x20 command才建立pending；六人party/SWITCH只續接該意圖。
    原最高level/hp選擇若不安全即review，絕不過濾party另選人。
    """
    global _SHARED_EXPERIENCE_PENDING
    from copy import deepcopy
    import math,time
    from .battle import (_fixed_damage_rows,_trainer_half_party_valid,
                         _trainer_half_party_view,_trainer_half_command_layout)
    from .party_control import party_choice,selection
    from .team_strategy import effective_power,reference,move_key

    # 歷史收尾只消費父層明示 capsule 一次，不偽造 decoder 或遊戲狀態。
    capsule=plan.get('training_completed_battle_review') if isinstance(plan,dict) else None
    if isinstance(capsule,dict) and capsule.get('nonce') not in _SHARED_EXPERIENCE_USED_REVIEWS:
        if (not isinstance(state,dict) or type(state.get('frame')) is not int
                or state['frame']!=capsule.get('current_frame')):
            return _shared_review('completion_review_current_frame_mismatch')
        owner=_SHARED_EXPERIENCE_PENDING
        result=review_completed_shared_experience(capsule.get('closed_states'),plan)
        if result is not None:return result
        if owner is not None and _SHARED_EXPERIENCE_PENDING is None:
            return {'phase':'battle_menu','objective':'Wait.','available_actions':['wait'],
                    **deepcopy(_SHARED_EXPERIENCE_LAST_COMPLETION)}
    pending=_SHARED_EXPERIENCE_PENDING
    if pending and not pending.get('error') and _shared_closed_state(state,plan,pending):
        try:
            frame=state['frame']
            if type(pyboy.frame_count) is int and pyboy.frame_count==frame:
                text=read_visible_text(pyboy)
                rows=_fixed_damage_rows(text)
                if (type(pyboy.frame_count) is int and pyboy.frame_count==frame and rows==[' '*20]*18
                        and text.get('window_visible') is False
                        and ('observation_frame' not in text or type(text['observation_frame']) is int and text['observation_frame']==frame)
                        and ('lines' not in text or text['lines']==[]) and ('line_rows' not in text or text['line_rows']==[])):
                    _finish_shared_experience(pending,'shared_experience_native_battle_completed',closed_frame=frame)
                    return None
        except (AttributeError,IndexError,KeyError,TypeError,ValueError,RuntimeError):pass
    if (not isinstance(plan,dict) or plan.get('mode')!='league_campaign'
            or plan.get('training_shared_experience') is not True
            or type(plan.get('training_direct_from_level')) is not int
            or plan['training_direct_from_level']!=25
            or not isinstance(plan.get('training_job'),str)
            or not plan['training_job'].strip() or len(plan['training_job'])>128
            or not isinstance(state,dict) or state.get('phase')!='battle_menu'
            or 'review_reason' in state
            or any(k in state for k in ('capture_tactic','snorlax_capture_tactic',
                                        'capture_completion_tactic','unsupported_reason'))):
        return None
    tactic=state.get('battle_tactic','')
    if (not isinstance(tactic,str) or any(word in tactic.lower()
            for word in ('capture','retreat','unsupported','review'))):return None
    if 'capture_plan' in state and (not isinstance(state['capture_plan'],dict)
            or state['capture_plan'].get('tactic')!='not_capture'):return None
    battle=state.get('battle_state');progress=state.get('progress');frame=state.get('frame')
    if (type(frame) is not int or frame<0 or not isinstance(battle,dict)
            or battle.get('kind')!='wild' or battle.get('active') is not True
            or type(battle.get('raw')) is not int or battle['raw']!=1
            or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=frame
            or not isinstance(progress,dict)
            or progress.get('profile')!='gen1-wrapper-ram-progress-v1-unvalidated'
            or progress.get('party_read_valid') is not True
            or progress.get('initialization_candidate') is not True
            or type(progress.get('party_count')) is not int or progress['party_count']!=6):return None
    party=progress.get('party')
    if (not _trainer_half_party_valid(party) or len(party)!=6
            or {m['species'] for m in party}!={19,132,7,102,154,35}
            or any(m['hp']<=0 or type(m.get('exp')) is not int or not 0<=m['exp']<=0xFFFFFF
                   for m in party)):return None
    ref=reference()
    for mon in party:
        for move,pp in zip(mon['moves'],mon['pp']):
            if move and pp&63>min(63,int(ref['moves'][move_key(move)]['pp'])*(5+(pp>>6))//5):return None
    enemy=species_key(battle.get('opponent_species'))
    if (not enemy or battle.get('wild_opponent_species') is not None
            and species_key(battle['wild_opponent_species'])!=enemy):return None
    location=state.get('location')
    if (not isinstance(location,dict) or any(type(location.get(k)) is not int
            or not 0<=location[k]<=255 for k in ('map_id','x','y'))):return None
    for p in (progress,location):
        if 'observation_frame' in p and (type(p['observation_frame']) is not int
                or p['observation_frame']!=frame):return None
    try:
        if type(pyboy.frame_count) is not int or pyboy.frame_count!=frame:return None
        text=read_visible_text(pyboy)
        if type(pyboy.frame_count) is not int or pyboy.frame_count!=frame:return None
    except (AttributeError,IndexError,KeyError,TypeError,ValueError,RuntimeError):return None
    rows=_fixed_damage_rows(text)
    if rows is None:return None
    if 'observation_frame' in text and (type(text['observation_frame']) is not int
            or text['observation_frame']!=frame):return None
    raw=[''.join(row) for row in text['cells']]
    import re
    pairs=[(i,row.rstrip()) for i,row in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',row)][:12]
    if ('lines' in text and text['lines']!=[r for _,r in pairs]
            or 'line_rows' in text and text['line_rows']!=[i for i,_ in pairs]):return None
    encounter_enemy=enemy
    visible_enemies=[species_key(row.strip()) for row in rows[:4] if species_key(row.strip())]
    if visible_enemies==['DITTO'] and enemy!='DITTO':
        from .ditto_transform import verified_effective_enemy
        if verified_effective_enemy(battle.get('ditto_transform'),visible_enemy='DITTO',
                ram_enemy=enemy,party=party,observation_frame=frame,reference_data=ref)!=enemy:
            return None
        encounter_enemy='DITTO'  # 同一已核變身遭遇；攻擊評分仍用實際複製屬性。
    signature=(plan['training_job'],25,tuple(m['species'] for m in party),encounter_enemy,
               tuple(location[k] for k in ('map_id','x','y')))
    pending=_SHARED_EXPERIENCE_PENDING
    if pending and pending['signature']!=signature:return _shared_review('owner_or_intent_changed')
    if pending:
        if pending['error']:return _shared_review(pending['error'])
        if frame<pending['last_frame']:
            pending['error']='clock_or_frame_invalid'
            return _shared_review(pending['error'])
        if frame==pending['last_frame'] and (text,progress,battle,location)!=pending['last_packet']:
            pending['error']='same_frame_packet_conflict'
            return _shared_review(pending['error'])
    command=_trainer_half_command_layout(rows)
    # 換人已完成後才遭中毒仍是正常交接，不能在招式頁再要求支援者狀態零。
    if pending and (command or state.get('battle_menu')=='moves'):
        from .battle import _trainer_half_status
        target_mon=next(m for m in party if m['species']==pending['target'])
        target_hp=[tuple(map(int,m.groups())) for row in rows[8:12]
                   if (m:=re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*',row[10:]))]
        if (visible_enemies==[encounter_enemy]
                and sum(row.strip()==species_key(target_mon['species']) for row in rows[6:10])==1
                and target_hp==[(target_mon['hp'],target_mon['max_hp'])]
                and rows[8].strip()==_trainer_half_status(target_mon)
                and not any('▼' in row or '▷' in row for row in rows)):
            _finish_shared_experience(pending,'shared_experience_target_hud_handoff',
                                     handoff_frame=frame,target_status=target_mon['status'])
            return None
    active=None
    if command:
        visible=[species_key(row.strip()) for row in rows[:4] if species_key(row.strip())]
        matches=[m for m in party for row in rows[6:10] if row.strip()==species_key(m['species'])]
        hp=[tuple(map(int,m.groups())) for row in rows[8:12]
            if (m:=re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*',row[10:]))]
        if (visible!=[encounter_enemy] or len(matches)!=1 or hp!=[(matches[0]['hp'],matches[0]['max_hp'])]
                or rows[8].strip()!=str(matches[0]['level']) or matches[0]['status']!=0):return None
        active=matches[0]
        # Preserve the original wild half-HP RUN policy, never turn it into a swap.
        if active['hp']*2<=active['max_hp']:return None
        if active['level']>=25 or pending and active['species']==pending['target']:
            _SHARED_EXPERIENCE_PENDING=None
            return None
    elif pending is None:return None
    target_index=max(range(6),key=lambda i:(party[i]['level'],party[i]['hp']))
    target=party[target_index]
    if (target['hp']*3<=target['max_hp']*2 or target['status']!=0
            or not any((pp&63)>=3 and effective_power(move,target['species'],enemy)>0
                       for move,pp in zip(target['moves'],target['pp']))):
        return _shared_review('support_not_safe')
    if pending and target['species']!=pending['target']:return _shared_review('support_changed')
    if command:
        if active['species']==target['species'] or active['level']+2>=target['level']:return None
        expected=_selection_hint(rows,(16,14),'command');page='command'
    else:
        expected=None;page=None
        for index in range(6):
            if rows==_trainer_half_party_view(party,index):
                expected=party_choice(rows,party,target_index);page='party';break
            if rows==_trainer_half_party_view(party,index,inactive=True):page='wait';break
        if page is None and rows==_trainer_half_party_view(party,target_index,True):
            expected=selection(rows,'SWITCH','battle_menu');page='switch'
        if page is None and rows==_trainer_half_party_view(party,target_index,True,inactive=True):page='wait'
        if page is None:return None
    now=time.monotonic()
    if pending is None:
        pending=dict(signature=signature,target=target['species'],lead=active['species'],
                     started=now,last_now=now,calls=0,last_frame=-1,last_packet=None,error=None)
        _SHARED_EXPERIENCE_PENDING=pending
    if pending['error']:return _shared_review(pending['error'])
    pending['calls']+=1
    if (type(now) not in (int,float) or not math.isfinite(now) or now<pending['last_now']
            or frame<pending['last_frame']):pending['error']='clock_or_frame_invalid'
    elif pending['calls']>25 or now-pending['started']>60:pending['error']='budget_exhausted'
    if pending['error']:return _shared_review(pending['error'])
    pending['last_now']=now
    packet=deepcopy((text,progress,battle,location))
    if frame==pending['last_frame']:
        if packet!=pending['last_packet']:
            pending['error']='same_frame_packet_conflict'
            return _shared_review(pending['error'])
        return {'phase':'battle_menu','objective':'Wait.','available_actions':['wait'],
                'training_tactic':'shared_experience_same_frame'}
    pending['last_frame'],pending['last_packet']=frame,packet
    if page=='wait':
        return {'phase':'battle_menu','objective':'Wait.','available_actions':['wait'],
                'training_tactic':'shared_experience_pending_menu'}
    # Existing context receives the SAME complete state/party/plan, not a mask.
    result=context(pyboy,state,plan,[])
    if (type(pyboy.frame_count) is not int or pyboy.frame_count!=frame
            or not isinstance(result,dict) or 'review_reason' in result
            or result.get('objective')!=expected['objective']
            or result.get('available_actions')!=expected['available_actions']):
        pending['error']='delegated_context_unverified'
        return _shared_review(pending['error'])
    return {**result,'training_shared_experience':True,'training_job':plan['training_job'],
            'training_support_species':target['species'],'training_shared_page':page}


def context(pyboy,state,plan,previous):
    from .campaign_route import waypoint,healthy
    party=state['progress']['party'];battle=state.get('battle_state',{})
    if not party:return {'phase':'campaign_review','review_reason':'training_party_empty'}
    text=read_visible_text(pyboy)
    if battle.get('active'):
        rows=[''.join(row).upper() for row in text.get('cells',[])]
        compact=normalize(' '.join(rows))
        if 'ALREADYOUT' in compact:
            from .party_control import command
            return command('a','battle_menu',{'training_tactic':'dismiss_already_out'})
        if 'STATS' in compact and 'SWITCH' in compact:
            from .party_control import selection
            return selection(rows,'SWITCH','battle_menu')
        from .party_control import party_choice
        healthiest=[(i,m) for i,m in enumerate(party) if m['hp']>0]
        if healthiest:
            strong_index=max(healthiest,key=lambda item:(item[1]['level'],item[1]['hp']))[0]
            party_hint=party_choice(rows,party,strong_index)
            if party_hint:return {**party_hint,'phase':'battle_menu','training_tactic':'select_training_support'}
        visible={normalize(row.strip()) for row in rows[6:10]}
        active=next((m for m in party if normalize(species_key(m['species'])) in visible),None)
        strong=max((m for m in party if m['hp']>0),key=lambda m:m['level'],default=None)
        if active and strong and active['level']<plan.get('training_direct_from_level',10) and active['level']+2<strong['level']:
            fight,item,run=(_label(rows,label) for label in ['FIGHT','ITEM','RUN'])
            # PKMN使用合成字形，字碼讀取不會還原成POKEMON。以已核對2x2選單的右上格定位。
            if fight and item and run and fight[0]==item[0] and item[1]==run[1]:
                result=_selection_hint(rows,(run[0],fight[1]),'command')
                result.update(training_tactic='switch_for_shared_experience',training_lead=active['species'])
                return result
        return None  # 原戰鬥解析器負責健康換人與實際在場者的最佳攻擊。
    target_level=plan.get('training_min_level',12)
    weakest=min(party,key=lambda m:(m['level'],m.get('exp',0)))
    if all(m['level']>=target_level for m in party):
        return {'phase':'campaign_review','review_reason':'balanced_training_checkpoint','training_min_level':target_level}
    location=state['location'];mid=location['map_id']
    # 先選最低等級隊員，不把「有隊員」當成已練等。中心內安全調整首位。
    hint=lead_context(text,party,weakest['species'],open_menu=state['phase'] in {'unclassified','overworld'})
    if hint:return {**hint,'training_target':weakest['species'],'training_min_level':target_level}
    # 非戰鬥對話先交給原解析器，例如中心回復對話。
    if state['phase'] not in {'unclassified','overworld'}:return None
    needs_heal=any(m['hp']*3<=m['max_hp']*2 or m.get('status',0) for m in party)
    if mid==68:
        step={'id':'training-center','map_id':68,'target':[3,3] if not healthy(state['progress']) else [3,8],
              'kind':'heal' if not healthy(state['progress']) else 'move','face':'up','terminal':True}
    elif mid==15:
        step={'id':'training-route4','map_id':15,'target':[11,5] if needs_heal else [10,18],'kind':'move','terminal':True}
    elif mid==14:
        from .world_map import read_world_grid
        grid=read_world_grid(pyboy,location)
        grass=[] if not grid else [(x,y) for y,row in enumerate(grid['tiles']) for x,tile in enumerate(row) if tile==grid['grass'] and (x,y)!=(location['x'],location['y'])]
        if not needs_heal and not grass:return {'phase':'campaign_review','review_reason':'training_grass_not_verified'}
        target=[60,-1] if needs_heal else list(min(grass,key=lambda p:abs(p[0]-location['x'])+abs(p[1]-location['y'])))
        step={'id':'training-grass','map_id':14,'target':target,'kind':'move','terminal':True}
    else:return {'phase':'campaign_review','review_reason':'training_map_not_implemented','map_id':mid}
    result,_=waypoint(pyboy,state,{'steps':[step],'blocked':plan.get('blocked',{}),'_detour':True},step['id'],previous)
    return {**result,'training_target':weakest['species'],'training_min_level':target_level}
