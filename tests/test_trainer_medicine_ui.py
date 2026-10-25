"""Real pure controller/decoders; literal source-layout UI and packet fixtures."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import laya_pokemon
from laya_pokemon.player_battle import decode_player_battle
from laya_pokemon.wild_opponent import decode_enemy_mon
from laya_pokemon.observation import read_visible_text
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-trainer-medicine-postreview-20261025'


def source_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_trainer_medicine_ui.py':return STAGE/'trainer_medicine_ui.py'
    if p==ROOT/'tests/test_trainer_medicine_ui.py':return ROOT/'src/laya_pokemon/trainer_medicine_ui.py'
    raise RuntimeError('Exact stage/formal test path required')


spec=importlib.util.spec_from_file_location('trainer_medicine_ui_candidate',source_for_test(__file__))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NAMES=[(19,'LAPRAS'),(132,'SNORLAX'),(102,'EEVEE'),(154,'VENUSAUR'),(35,'FEAROW'),(7,'NIDOKING')]


def record(species,level,hp,maxhp,status,moves,pp):
    raw=[species,*divmod(hp,256),0,status,21,25,75,*moves,152,136,level,*divmod(maxhp,256)]
    for value in (90,85,80,88):raw.extend(divmod(value,256))
    raw.extend(pp);return raw


def canvas():return [[' ']*20 for _ in range(18)]
def put(c,x,y,s):c[y][x:x+len(s)]=list(s)
def status(s):return 'SLP' if s&7 else {0:'',8:'PSN',16:'BRN',32:'FRZ',64:'PAR'}[s]


def hud(player,enemy):
    c=canvas();put(c,1,0,'RHYDON');put(c,10,7,player['species_name'])
    for x,y,p in ((4,1,enemy),(14,8,player)):
        put(c,x+1 if p['status'] or p['level']<100 else x,y,status(p['status']) or str(p['level']))
    put(c,11,10,f"{player['hp']:3}/{player['max_hp']:3}");return c


def command(player,enemy,cursor=(9,16)):
    c=hud(player,enemy)
    for x,y,s in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')):put(c,x,y,s)
    c[cursor[1]][cursor[0]]='▶';return c


def party(rows,cursor=None,dim=False,receipt=None):
    c=canvas()
    for i,p in enumerate(rows):
        put(c,3,2*i,p['species_name']);put(c,13 if p['level']==100 else 14,2*i,str(p['level']))
        put(c,17,2*i,status(p['status']));put(c,13,2*i+1,f"{p['hp']:3}/{p['max_hp']:3}")
    if cursor is not None:c[2*cursor+1][0]='▷' if dim else '▶'
    if receipt is None:put(c,1,14,'Use item on which');put(c,1,16,'POKéMON?')
    else:
        active,item,delta=receipt;name=rows[active]['species_name'];put(c,1,14,name)
        if item==18:put(c,1,16,f'Recovered by {delta}!')
        else:c[14][1+len(name)]="'s";put(c,1,16,'health returned!')
    return c


def bag(player,enemy,items,off,cur):
    c=hud(player,enemy);labels={4:'POKé BALL',197:'HM02',43:'SECRET KEY',18:'HYPER POTION',52:'FULL HEAL',238:'TM38'}
    for y in range(2,18):c[y][4 if y<12 else 0:]=[' ']*(16 if y<12 else 20)
    printed=0
    for i in range(4):
        n=off+i;y=4+2*i
        if n==len(items):put(c,6,y,'CANCEL');break
        if n>len(items):break
        item=items[n];put(c,6,y,labels[item['item']])
        if item['item'] not in (197,43):put(c,14,y+1,f"×{item['quantity']:2}")
        printed+=1
    c[4+2*cur][5]='▶'
    if printed==4:c[11][18]='▼'
    return c


def text(cells):
    chars=sorted({c for row in cells for c in row});enc={c:i for i,c in enumerate(chars)}
    class Tiles:
        def __getitem__(self,xy):x,y=xy;return enc[cells[y][x]]
    game=SimpleNamespace(memory={0xFF40:0xB1},screen=SimpleNamespace(tilemap_position_list=[(0,0,0,0)]*144),
                         tilemap_background=Tiles(),tilemap_window=Tiles())
    t=read_visible_text(game,{i:c for c,i in enc.items()});assert t['read_valid'];return t


class Session:
    def __init__(self,active=0,item=18,quantity=10,map_id=45,level=None,**caps):
        self.active,self.item=active,item;self.loc=dict(map_id=map_id,x=5,y=3)
        self.p=dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
            party_read_valid=True,party_count=6,money=48332,
            inventory=[dict(item=i,quantity=quantity if i==item else q) for i,q in ((4,6),(197,1),(43,1),(18,10),(52,10),(238,1))],
            party=[dict(species=s,species_name=n,level=48+i,exp=100000,hp=200,max_hp=250,status=0,
                moves=[33,34,58,109],pp=[20,15,10,10]) for i,(s,n) in enumerate(NAMES)])
        self.p['party'][active].update(hp=65,status=16 if item==52 else 0)
        if level is not None:self.p['party'][active]['level']=level
        self.player=self.player_now();self.enemy=decode_enemy_mon(record(1,55,190,190,0,[23,39,30,32],[20,30,25,5]))['enemy']
        self.intent=deepcopy(m.HYPER_POTION_INTENT if item==18 else m.FULL_HEAL_INTENT)
        self.c=m.TrainerMedicineUIController(self.intent,owner='parent-owned-ui',**caps)
        self.before=deepcopy(self.p);self.frame=100000;self.now=0.;self.prev=[];self.kw=None
    def player_now(self):
        p=self.p['party'][self.active]
        return decode_player_battle(record(p['species'],p['level'],p['hp'],p['max_hp'],p['status'],p['moves'],p['pp']))['player']
    def call(self,cells=None,advance=40,**overrides):
        if self.kw is not None:self.frame+=advance;self.now+=.1
        enemyraw=record(self.enemy['species'],self.enemy['level'],self.enemy['hp'],self.enemy['max_hp'],self.enemy['status'],self.enemy['moves'],self.enemy['pp'])
        ps=dict(profile=m.ui.PLAYER_PROFILE,source_commit=m.SOURCE_COMMIT,read_valid=True,
            observation_frame=self.frame,battle_kind='trainer',location=deepcopy(self.loc),active_party_index=self.active,player=deepcopy(self.player))
        es=dict(profile=m.ui.ENEMY_PROFILE,source_commit=m.SOURCE_COMMIT,read_valid=True,
            observation_frame=self.frame,frame_before=self.frame,frame_after=self.frame,battle_kind='trainer',raw=2,
            battle_type=0,current_opponent=201,location=deepcopy(self.loc),raw_record=enemyraw,enemy=deepcopy(self.enemy))
        kw=dict(text=text(cells if cells is not None else command(self.player,self.enemy)),progress=deepcopy(self.p),
            player_snapshot=ps,enemy_proof=es,frame=self.frame,now=self.now,owner=self.c.owner,previous=list(self.prev),
            location=deepcopy(self.loc),battle_state=dict(raw=2,kind='trainer',active=True,observation_frame=self.frame,opponent_species='RHYDON'))
        kw.update(overrides);self.kw=deepcopy(kw);before=deepcopy(kw);r=self.c.context(**kw)
        assert kw==before;self.prev=[r['available_actions'][0]];return r
    def select(self):
        cursor=(15,14);r=self.call(command(self.player,self.enemy,cursor))
        while r['available_actions'][0] in ('left','down'):
            cursor=(9,cursor[1]) if r['available_actions'][0]=='left' else (9,16)
            r=self.call(command(self.player,self.enemy,cursor))
        assert r['available_actions'][0]=='a';off=cur=0;target=3 if self.item==18 else 4
        for index in range(target+1):
            r=self.call(bag(self.player,self.enemy,self.p['inventory'],off,cur))
            assert r['available_actions'][0]==('a' if index==target else 'down')
            if cur<2:cur+=1
            else:off+=1
        current=5;r=self.call(party(self.p['party'],current))
        while current!=self.active:
            assert r['available_actions'][0]=='up';current-=1;r=self.call(party(self.p['party'],current))
        assert r['available_actions'][0]=='a'
    def effect(self):
        p=self.p['party'][self.active]
        if self.item==18:p['hp']=min(p['max_hp'],p['hp']+200)
        else:p['status']=0
        for index,item in enumerate(self.p['inventory']):
            if item['item']==self.item:
                item['quantity']-=1
                if item['quantity']==0:self.p['inventory'].pop(index)
                break
        self.player=self.player_now()
    def receipt(self):
        delta=self.p['party'][self.active]['hp']-self.before['party'][self.active]['hp']
        return party(self.p['party'],receipt=(self.active,self.item,delta))
    def ack_offer(self):
        self.select();self.effect()
        assert self.call(self.receipt())['available_actions']==['wait']
        assert self.call(self.receipt(),advance=53)['available_actions']==['wait']
        assert self.call(self.receipt(),advance=1)['available_actions'][0]=='a'


@pytest.mark.parametrize('active',range(6))
@pytest.mark.parametrize('item',[18,52])
def test_all_six_dynamic_active_species_levels_and_both_medicines_handoff_ui_only(active,item):
    s=Session(active,item);s.ack_offer();r=s.call(hud(s.player,s.enemy))
    assert r['available_actions']==['wait'] and r['medicine_ui_complete'] is True
    assert r['medicine_handoff']=='existing_battle' and r['enemy_turn_resolved'] is False and r['survival_approved'] is False
    assert not r.get('field_move_complete') and s.c.receipt_acknowledged
    assert s.p['money']==s.before['money']
    assert all(s.p['party'][i]==s.before['party'][i] for i in range(6) if i!=active)
    assert next(i['quantity'] for i in s.p['inventory'] if i['item']==item)==9


@pytest.mark.parametrize('item',[18,52])
def test_level100_hud_party_position_and_quantity_one_stack_removal(item):
    s=Session(5,item,quantity=1,level=100);s.ack_offer()
    view=hud(s.player,s.enemy);assert ''.join(view[8][14:17])=='100'
    assert s.call(view)['medicine_ui_complete'] and not any(i['item']==item for i in s.p['inventory'])


@pytest.mark.parametrize('map_id',[45,245,246,247,113,120])
def test_exact_map_whitelist_accepts_real_typed_initial_command(map_id):
    assert Session(map_id=map_id).call()['available_actions'][0]=='a'


def test_receipt_a_needs_actual_previous_and_fresh_frame_before_handoff():
    s=Session();s.ack_offer();kw=deepcopy(s.kw)
    assert s.c.context(**kw)['available_actions']==['wait'] and not s.c.receipt_acknowledged
    assert not s.call(hud(s.player,s.enemy),previous=['wait']).get('medicine_ui_complete')
    assert not s.c.receipt_acknowledged
    assert s.call(hud(s.player,s.enemy),previous=['a'])['medicine_ui_complete']


def test_enemy_used_page_is_never_acknowledged_or_claimed_resolved():
    s=Session();s.ack_offer();s.player['hp']=25
    view=hud(s.player,s.enemy);put(view,1,14,'Enemy RHYDON');put(view,1,16,'used STOMP!')
    r=s.call(view)
    assert r['medicine_ui_complete'] and r['available_actions']==['wait'] and r['enemy_turn_resolved'] is False
    assert s.kw['player_snapshot']['player']['hp']==25 and s.kw['progress']['party'][0]['hp']==250


@pytest.mark.parametrize('bad',['map166','faint','bench_faint','reader','frame','species','inventory','noeffect'])
def test_unknown_faint_bad_reader_or_unowned_scope_never_starts(bad):
    s=Session(map_id=166 if bad=='map166' else 45)
    if bad=='faint':s.player['hp']=0;s.p['party'][0]['hp']=0
    elif bad=='bench_faint':s.p['party'][1]['hp']=0
    elif bad=='inventory':s.p['inventory'][3]['quantity']=False
    elif bad=='noeffect':s.player['hp']=250;s.p['party'][0]['hp']=250
    s.call();kw=deepcopy(s.kw)
    if bad=='reader':kw['enemy_proof']['read_valid']=False
    elif bad=='frame':kw['player_snapshot']['observation_frame']=False
    elif bad=='species':kw['player_snapshot']['player']['species']=False
    c=m.TrainerMedicineUIController(s.intent,owner=s.c.owner)
    r=c.context(**kw);assert r['phase']=='strategy_review' and r['available_actions']==['wait']
    assert not r.get('medicine_ui_complete')


@pytest.mark.parametrize('bad',['double_used','other_party','money','false_effect'])
def test_effect_and_complete_original_inventory_party_money_are_conserved(bad):
    s=Session();s.select();s.effect()
    if bad=='double_used':s.p['inventory'][3]['quantity']-=1
    elif bad=='other_party':s.p['party'][1]['hp']-=1
    elif bad=='money':s.p['money']-=1
    else:s.p['party'][0]['hp']-=1;s.player=s.player_now()
    r=s.call(s.receipt());assert r['phase']=='strategy_review' and not r.get('medicine_ui_complete')


@pytest.mark.parametrize('bad',['party','hybrid_receipt','wrong_hud','faint_text','art_pollution'])
def test_false_restored_pages_never_handoff(bad):
    s=Session();s.ack_offer();view=party(s.p['party']) if bad=='party' else hud(s.player,s.enemy)
    if bad=='hybrid_receipt':put(view,1,14,'LAPRAS');put(view,1,16,'Recovered by 185!')
    elif bad=='wrong_hud':view[0][1]='X'
    elif bad=='faint_text':put(view,1,14,'RHYDON fainted!')
    elif bad=='art_pollution':view[5][1]='#'
    r=s.call(view);assert r['available_actions']==['wait'] and not r.get('medicine_ui_complete')


@pytest.mark.parametrize('budget',['call','time','wait'])
def test_instance_budgets_do_not_reset_at_receipt_or_handoff(budget):
    s=Session();s.ack_offer();started=s.c.started
    if budget=='call':s.c.max_calls=s.c.calls
    elif budget=='wait':s.c.max_waits=s.c.waits
    r=s.call(s.receipt(),now=started+61 if budget=='time' else s.now+.1)
    assert r['phase']=='strategy_review' and s.c.started==started
    assert s.c.error is not None and not r.get('medicine_ui_complete')


def test_constructor_intents_and_exact_source_path_are_bounded():
    intent=deepcopy(m.HYPER_POTION_INTENT);intent['item']=4
    with pytest.raises(ValueError):m.TrainerMedicineUIController(intent,owner='x')
    assert Path(m.__file__).resolve()==source_for_test(__file__)
    assert source_for_test(ROOT/'tests/test_trainer_medicine_ui.py')==ROOT/'src/laya_pokemon/trainer_medicine_ui.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_trainer_medicine_ui.py')


def test_full_heal_source_stat_recalculation_does_not_change_identity_or_pp():
    s=Session(1,52);s.select();s.effect();s.player['attack']+=30;s.player['speed']+=40
    assert s.call(s.receipt())['available_actions']==['wait']
    assert s.call(s.receipt(),advance=54)['available_actions'][0]=='a'
    assert s.call(hud(s.player,s.enemy))['medicine_ui_complete']


def test_enemy_level100_uses_source_hud_position_without_lv_tile():
    s=Session();s.enemy['level']=100
    view=command(s.player,s.enemy);assert ''.join(view[1][4:7])=='100'
    assert s.call(view)['available_actions'][0]=='a'


def test_dynamic_active_hp_animation_is_wait_only_after_one_observed_consumption():
    s=Session(4);s.select();s.effect();view=party(s.p['party'],4,dim=True)
    put(view,13,9,'100/250');r=s.call(view)
    assert r['medicine_ui_tactic']=='known_active_hp_animation' and r['available_actions']==['wait']
    assert s.kw['player_snapshot']['player']['hp']==250 and s.kw['progress']['party'][4]['hp']==250
    assert not r.get('medicine_ui_complete') and s.p['inventory'][3]['quantity']==9


def test_battle_bag_never_accepts_overworld_use_toss_overlay():
    s=Session();assert s.call()['available_actions'][0]=='a'
    view=bag(s.player,s.enemy,s.p['inventory'],0,0);put(view,1,14,'USE');put(view,1,16,'TOSS')
    r=s.call(view)
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']


def test_hyper_potion_cannot_explain_unrelated_pre_ack_battle_stat_change():
    s=Session();s.select();s.effect();s.player['attack']+=1
    assert s.call(s.receipt())['review_reason']=='trainer_medicine_ui_hyper_potion_unrelated_battle_change'


def test_one_hyper_potion_adds200_without_automatically_filling_or_using_another():
    s=Session(1);s.p['party'][1].update(hp=50,max_hp=500)
    s.player=s.player_now();s.before=deepcopy(s.p);s.ack_offer()
    assert s.player['hp']==250 and s.player['max_hp']==500
    assert s.call(hud(s.player,s.enemy))['medicine_ui_complete']
    assert s.p['inventory'][3]['quantity']==9


def test_full_hp_dim_cursor_and_native_recovered_message_redraw_only_wait():
    s=Session(5);s.select();s.effect();view=party(s.p['party'],5,dim=True)
    for y in range(12,18):view[y]=[' ']*20
    put(view,1,14,'NIDOKING');put(view,1,16,'Recovered by 185')
    r=s.call(view)
    assert r['available_actions']==['wait'] and r['medicine_ui_tactic']=='known_active_hp_animation'
    assert s.c.stage=='receipt' and s.c.error is None and s.c.receipt_full_frame is None
    assert not r.get('medicine_ui_complete') and s.p['inventory'][3]['quantity']==9
    assert s.call(s.receipt())['available_actions']==['wait']
    assert s.call(s.receipt(),advance=53)['available_actions']==['wait']
    assert s.call(s.receipt(),advance=1)['available_actions'][0]=='a'


def test_full_heal_cleared_status_dim_cursor_and_native_done_redraw_only_wait():
    s=Session(1,52);s.select();s.effect();view=party(s.p['party'],1,dim=True)
    for y in range(12,18):view[y]=[' ']*20
    put(view,1,14,'SNORLAX');view[14][8]="'s";put(view,1,16,'health returned')
    r=s.call(view)
    assert r['available_actions']==['wait'] and s.c.error is None and not r.get('medicine_ui_complete')
    assert s.kw['player_snapshot']['player']['status']==0 and s.kw['progress']['party'][1]['status']==0
    assert s.p['inventory'][4]['quantity']==9 and s.c.receipt_full_frame is None
    assert s.call(s.receipt())['available_actions']==['wait']
    assert s.call(s.receipt(),advance=54)['available_actions'][0]=='a'
