"""以真實可見選單正常調整首位；不寫入隊伍記憶體。"""
from .team_strategy import family,normalize,species_key


def selection(rows,label,kind='party_menu'):
    matches=[(x,y) for y,row in enumerate(rows) for x in range(len(row))
             if row[x:].startswith(label)]
    if len(matches)!=1:return None
    tx,ty=matches[0]
    cursors=[(x,y) for y,row in enumerate(rows) for x,char in enumerate(row)
             if char in {'▶','▷'} and abs(x-tx)<=2]
    if len(cursors)!=1:return None
    x,y=cursors[0]
    action='a' if y==ty else 'up' if y>ty else 'down'
    return command(action,kind,{'menu_label':label})


def command(action,kind='party_menu',extra=None):
    objectives={'a':'Confirm the current selection.','b':'Cancel the current menu.',
                'start':'Open the game menu with START.','up':'Move UP.','down':'Move DOWN.'}
    return {'phase':kind,'objective':objectives[action],'available_actions':[action,'wait'],
            'controller_menu_verified':True,
            'phase_source':'local verified visible party/menu controller; Laya button classification',**(extra or {})}


def party_choice(rows,party,index):
    names=[(i,y) for i,mon in enumerate(party) for y,row in enumerate(rows[:12])
           if normalize(species_key(mon['species'])) in normalize(row)]
    cursors=[(x,y) for y,row in enumerate(rows[:12]) for x,c in enumerate(row[:2]) if c=='▶']
    if not cursors:cursors=[(x,y) for y,row in enumerate(rows[:12]) for x,c in enumerate(row[:2]) if c=='▷']
    if len(names)!=len(party) or len(cursors)!=1:return None
    current=next((i for i,y in names if y<=cursors[0][1]<=y+1),None)
    if current is None:return None
    return command('a' if current==index else 'up' if current>index else 'down',extra={'party_target_index':index})


def lead_context(text,party,target_species,*,open_menu=True):
    cells=text.get('cells',[])
    if len(cells)!=18:return None
    rows=[''.join(row).upper() for row in cells];joined=normalize(' '.join(rows))
    target=next((i for i,m in enumerate(party) if m['species']==target_species),None)
    if target is None:
        target_family=family(target_species)
        matches=[i for i,m in enumerate(party) if target_family is not None and family(m['species'])==target_family]
        if not matches:return {'phase':'campaign_review','review_reason':'training_member_missing'}
        if len(matches)!=1:return {'phase':'campaign_review','review_reason':'training_member_ambiguous'}
        target=matches[0]
    # 切換完成後先關閉所有選單，隊伍順序以唯讀實際資料核對。
    party_visible=all(any(normalize(species_key(m['species'])) in normalize(row) for row in rows[:12]) for m in party)
    if target==0 and (party_visible or any(token in joined for token in ['CHOOSEAPOKEMON','MOVEPOKEMON'])):
        return command('b',extra={'party_order_verified':True})
    if 'STATS' in joined and 'SWITCH' in joined and 'CANCEL' in joined:
        return selection(rows,'SWITCH') or {'phase':'campaign_review','review_reason':'switch_submenu_cursor_unreadable'}
    if 'MOVEPOKEMON' in joined or ('WHERE' in joined and 'POKEMON' in joined):
        return party_choice(rows,party,0) or {'phase':'campaign_review','review_reason':'swap_destination_unreadable'}
    if 'POKEDEX' in joined and 'POKEMON' in joined and 'ITEM' in joined:
        if target==0:return command('b',extra={'party_order_verified':True})
        for label in ['POKÉMON','POKEMON']:
            hint=selection(rows,label)
            if hint:return hint
        return {'phase':'campaign_review','review_reason':'start_menu_cursor_unreadable'}
    hint=party_choice(rows,party,target)
    if hint:
        return command('b',extra={'party_order_verified':True}) if target==0 else hint
    if target!=0 and open_menu:return command('start')
    return None
