"""最低等級輪流首發／正常換人分經驗，達標後停下檢討。"""
from .party_control import lead_context
from .observation import read_visible_text
from .team_strategy import species_key,normalize
from .battle import _selection_hint,_label


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
        if active and strong and active['level']+2<strong['level']:
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
