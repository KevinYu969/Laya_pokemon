"""Three fixed Red natural declines. Pure hints; no dispatch, receipt authority or I/O."""
from copy import deepcopy
import re

from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .team_strategy import normalize, reference, species_key

SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
CASES={(154,43):('GROWTH',74,(75,15,73,22)),
       (35,43):('AGILITY',97,(64,65,19,31)),
       (102,45):('TAKE_DOWN',36,(44,28,98,39))}
ROSTER={154,35,102,132,7,19}
MAX_CALLS,MAX_WAITS=180,30
_SESSION=globals().get('_SESSION')


def _review(reason):
    if _SESSION is not None:
        _SESSION['error']=_SESSION.get('error') or reason;reason=_SESSION['error']
    return dict(phase='strategy_review',objective='Wait.',available_actions=['wait'],
        learning_controller='bounded_training_future_decline_v1',review_reason='future_decline_'+reason)


def _hint(action,tactic,**extra):
    data=dict(learning_controller='bounded_training_future_decline_v1',learning_tactic=tactic,
              learn_move_plan=deepcopy(_SESSION['plan']),**extra)
    if action=='wait':return dict(phase='learning_menu',objective='Wait.',available_actions=['wait'],**data)
    _SESSION['waits']=0
    return command(action,'learning_menu',data)


def _wait(reason):
    _SESSION['waits']+=1
    return _review('wait_budget_exhausted') if _SESSION['waits']>MAX_WAITS else _hint('wait',reason)


def candidate_plan(species,level,moves):
    if type(species) is not int or type(level) is not int:return None
    case=CASES.get((species,level))
    if case is None:return None
    new,new_id,before=case;ref=reference();name=species_key(species)
    if (not isinstance(moves,(list,tuple)) or len(moves)!=4 or any(type(m) is not int or m==0 for m in moves)
            or tuple(moves)!=before):return dict(decision='review',reason='exact_full_four_moves_required')
    if (ref.get('source_commit')!=SOURCE_COMMIT or name is None or ref['moves'].get(new,{}).get('id')!=new_id
            or {'level':level,'move':new} not in ref['species'][name]['level_moves']):
        return dict(decision='review',reason='fixed_natural_source_mismatch')
    return dict(decision='skip',species=species,natural_level=level,move=new,new_move_id=new_id,
                before_moves=list(before),source_commit=SOURCE_COMMIT,reason='reviewed_training_preserve_current_four_moves')


def _snapshot(progress):
    if (not isinstance(progress,dict) or progress.get('profile')!='gen1-wrapper-ram-progress-v1-unvalidated'
            or progress.get('initialization_candidate') is not True or progress.get('party_read_valid') is not True
            or type(progress.get('party_count')) is not int or progress['party_count']!=6):return None
    party=progress.get('party');ref=reference();moves={m['id']:m for m in ref['moves'].values()}
    if (not isinstance(party,list) or len(party)!=6 or any(not isinstance(m,dict) or type(m.get('species')) is not int for m in party)
            or {m['species'] for m in party}!=ROSTER):return None
    result=[]
    for mon in party:
        if (mon.get('species_name')!=species_key(mon['species'])
                or any(type(mon.get(k)) is not int for k in ('level','exp','hp','max_hp','status'))
                or not 1<=mon['level']<=100 or not 0<=mon['exp']<=0xffffff
                or not 0<mon['hp']<=mon['max_hp']<=999 or mon['status'] not in {*range(8),8,16,32,64}
                or any(not isinstance(mon.get(k),list) or len(mon[k])!=4 for k in ('moves','pp'))
                or any(type(v) is not int for v in mon['moves']+mon['pp'])
                or len(set(mon['moves']))!=4 or any(m not in moves for m in mon['moves'])):return None
        if any(not 0<=p<=255 or (p&63)>moves[m]['pp']*(5+(p>>6))//5 for m,p in zip(mon['moves'],mon['pp'])):return None
        result.append({k:deepcopy(mon[k]) for k in ('species','species_name','level','exp','hp','max_hp','status','moves','pp')})
    if (type(progress.get('money')) is not int or not 0<=progress['money']<=999999
            or type(progress.get('badges_raw')) is not int or progress['badges_raw']!=255
            or progress.get('player_name_raw')!='KEVIN' or not isinstance(progress.get('inventory'),list)
            or not isinstance(progress.get('story_event_bits'),dict)):return None
    return dict(party=result,**{k:deepcopy(progress[k]) for k in ('inventory','money','badges_raw','player_name_raw','story_event_bits')})


def _rows(text):
    if (not isinstance(text,dict) or text.get('profile')!=TEXT_PROFILE or text.get('read_valid') is not True
            or text.get('alignment_verified') is not True or text.get('read_error') is not None
            or type(text.get('window_visible')) is not bool):return None
    cells=text.get('cells')
    if (not isinstance(cells,(list,tuple)) or len(cells)!=18
            or any(not isinstance(row,(list,tuple,str)) or len(row)!=20 for row in cells)
            or any(type(c) is not str or not (len(c)==1 or y in (14,16) and c=="'t")
                   for y,row in enumerate(cells) for c in row)):return None
    raw=[''.join(row) for row in cells]
    selected=[(i,row.rstrip()) for i,row in enumerate(raw) if re.search('[A-Za-z0-9]{2,}',row)][:12]
    if text.get('lines')!=[v for _,v in selected] or text.get('line_rows')!=[i for i,_ in selected]:return None
    rows=[row.upper() for row in raw]
    if any(re.search('[A-Z0-9!?]',rows[y]) for y in (12,13,15,17)):return None
    if any(re.search('[A-Z0-9!?]',cells[y][x].upper()) for y in (14,16) for x in (0,19)):return None
    if any(c=='▼' and (x,y)!=(18,16) or c=='▷' and (x,y)!=(0,3)
           for y,row in enumerate(cells) for x,c in enumerate(row)):return None
    return rows


def _choice(rows,wanted):
    labels={word:[(m.start(),y) for y,row in enumerate(rows) for m in re.finditer(r'(?<![A-Z])'+word+r'(?![A-Z])',row)] for word in ('YES','NO')}
    if any(len(v)!=1 for v in labels.values()):return None
    yes,no=labels['YES'][0],labels['NO'][0]
    active=[(x,y) for y,row in enumerate(rows) for x,c in enumerate(row) if c=='▶']
    if yes[0] not in (15,16) or yes[1]!=8 or no!=(yes[0],10) or len(active)!=1 or active[0] not in ((yes[0]-1,8),(yes[0]-1,10)):return None
    target=labels[wanted][0]
    return 'a' if active[0][1]==target[1] else 'up' if active[0][1]>target[1] else 'down'


def _prefix(compact,pages):return bool(compact) and any(page.startswith(compact) for page in pages)


def _handoff(rows,text,current):
    """After visible DidNotLearn, permit only closed text or a verified peer EXP prompt."""
    old=_SESSION['baseline'];index=_SESSION['index'];name=species_key(_SESSION['case'][0])
    if current['party'][index]!=old['party'][index] or any(current[k]!=old[k] for k in old if k!='party'):
        return _review('post_result_learner_or_world_changed')
    gained=[]
    for i,(before,after) in enumerate(zip(old['party'],current['party'])):
        if i==index:continue
        mutable={'exp','level','hp','max_hp'}
        if {k:v for k,v in before.items() if k not in mutable}!={k:v for k,v in after.items() if k not in mutable}:
            return _review('post_result_peer_moves_pp_or_status_changed')
        exp=after['exp']-before['exp'];level=after['level']-before['level'];growth=after['max_hp']-before['max_hp']
        if not (0<=exp<=8192 and 0<=level<=1 and 0<=growth<=12 and (level or growth==0)
                and (not level or exp>0) and after['hp']==before['hp']+growth):return _review('post_result_peer_growth_unknown')
        if exp:gained.append((species_key(after['species']),exp))
    compact=normalize('\n'.join(rows[12:]));lower='\n'.join(rows[12:])
    if text['window_visible'] is False and not compact and not any(c in lower for c in ('▶','▷','▼')):return 'handoff'
    expected=gained[0][0]+'GAINED'+str(gained[0][1])+'EXPPOINTS' if len(gained)==1 else None
    if expected and expected.startswith(compact) and compact:
        return 'handoff' if compact==expected and '!' in lower else _wait('await_complete_peer_exp_handoff')
    return _review('post_result_handoff_unverified')


def context(text,party,progress=None):
    global _SESSION
    rows=_rows(text)
    if rows is None:return _review('decoder_or_geometry_unverified') if _SESSION is not None else None
    lower='\n'.join(rows[12:]);compact=normalize(lower)
    if _SESSION is None:
        if not ('TRYINGTOLEARN' in compact):return None
        if not isinstance(party,list):return _review('party_unreadable')
        matching=[(i,m) for i,m in enumerate(party) if isinstance(m,dict) and type(m.get('species')) is int
                  and type(m.get('level')) is int and (m['species'],m['level']) in CASES
                  and compact.startswith(normalize(species_key(m['species'])+'IS'))]
        if not matching:return None
        if len(matching)!=1:return _review('learner_not_unique')
        index,mon=matching[0];baseline=_snapshot(progress)
        if baseline is None or progress.get('party')!=party:return _review('full_progress_unverified')
        plan=candidate_plan(mon['species'],mon['level'],mon.get('moves'))
        if not plan or plan['decision']!='skip':return _review('exact_case_or_four_moves_unverified')
        _SESSION=dict(case=(mon['species'],mon['level']),index=index,plan=plan,baseline=baseline,stage='intro',
            seen_move=False,delete_no=False,abandon_yes=False,result_prefix=False,error=None,calls=0,waits=0)
    s=_SESSION
    if s['error']:return _review(s['error'])
    s['calls']+=1
    if s['calls']>MAX_CALLS:return _review('call_budget_exhausted')
    current=_snapshot(progress)
    if current is None or progress.get('party')!=party:return _review('current_progress_unverified')
    species,level=s['case'];new=normalize(s['plan']['move']);name=normalize(species_key(species))
    result_full=name+'DIDNOTLEARN'+new;prefix=name+'DIDNOTLEARN'
    result_tails=('DIDNOTLEARN'+new,new)
    if s['stage']=='verified' and compact not in (*result_tails,result_full):
        if _prefix(compact,(*result_tails,result_full,prefix)):return _wait('await_verified_result_close')
        handoff=_handoff(rows,text,current)
        if handoff=='handoff':_SESSION=None;return None
        return handoff
    if current!=s['baseline']:return _review('learning_resources_changed')
    if any(word in compact for word in ('WHICH','FORGOT','POOF','12AND','LEARNED')):return _review('unexpected_forget_or_learned_page')
    if not text['window_visible']:return _review('window_closed_before_verified_result')
    choices=any(re.search(r'(?<![A-Z])(?:YES|NO)(?![A-Z])',row) for row in rows)
    active=any('▶' in row for row in rows)
    if not compact and not choices and not active:return _wait('await_known_decline_transition')
    if s['stage'] in ('abandon_requested','result_prefix','verified'):
        if compact==prefix and '▼' in lower and not choices and not active:
            s['result_prefix']=True;s['stage']='result_prefix'
            return _hint('a','advance_source_did_not_learn_prefix')
        if s['result_prefix'] and compact in result_tails and '!' in lower and not choices and not active:
            if not s['seen_move'] or not s['delete_no'] or not s['abandon_yes']:return _review('result_without_decline_chain')
            s['stage']='verified'
            return _hint('a','dismiss_verified_decline',learning_declined_verified=True,learning_moves_unchanged=True,learning_result='skipped_unchanged')
        if _prefix(compact,(result_full,prefix,*result_tails)) and not choices and not active:return _wait('await_complete_did_not_learn')
    abandon='ABANDONLEARNING'+new
    if _prefix(compact,(abandon,)) and s['stage'] in ('after_delete_no','abandon','abandon_requested'):
        if not s['delete_no'] or not s['seen_move']:return _review('abandon_without_confirmed_decline')
        if compact!=abandon or '?' not in lower:
            return _review('partial_abandon_has_choices') if choices or active else _wait('await_complete_abandon')
        if choices:
            action=_choice(rows,'YES')
            if action is None:return _review('yes_no_cursor_unverified')
            if action=='a':s['abandon_yes']=True;s['stage']='abandon_requested'
            return _hint(action,'confirm_abandon_learning',menu_label='YES')
        return _wait('await_abandon_choices')
    deletes=('DELETEANOLDERMOVETOMAKEROOMFOR'+new,'MOVETOMAKEROOMFOR'+new,'FOR'+new)
    if _prefix(compact,deletes) and s['stage'] in ('intro','delete','after_delete_no'):
        if not s['seen_move']:return _review('delete_before_visual_move')
        if compact=='DELETEANOLDERMOVETOMAKEROOM' and '▼' in lower and not choices and not active:
            s['stage']='delete';return _hint('a','advance_source_delete_cont')
        if compact not in deletes or '?' not in lower:
            return _review('partial_delete_has_choices') if choices or active else _wait('await_complete_delete')
        if choices:
            action=_choice(rows,'NO')
            if action is None:return _review('yes_no_cursor_unverified')
            if action=='a':s['delete_no']=True;s['stage']='after_delete_no'
            return _hint(action,'decline_new_move',menu_label='NO')
        return _wait('await_delete_choices')
    intro=(name+'ISTRYINGTOLEARN'+new,'TRYINGTOLEARN'+new,new,'BUT'+name+'CANTLEARNMORETHAN4MOVES',
           name+'CANTLEARNMORETHAN4MOVES','CANTLEARNMORETHAN4MOVES','THAN4MOVES')
    if s['stage']=='intro' and _prefix(compact,intro) and not choices and not active:
        if compact in (name+'ISTRYINGTOLEARN','BUT'+name+'CANTLEARNMORE'):
            return _hint('a','advance_source_intro_cont') if '▼' in lower else _wait('await_intro_cont_arrow')
        if compact in intro and '!' in lower:
            if new in compact:s['seen_move']=True
            return _hint('a','advance_source_decline_intro')
        return _wait('await_complete_decline_intro')
    return _review('page_unknown_or_out_of_order')
