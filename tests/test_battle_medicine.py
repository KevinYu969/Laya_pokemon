"""固定來源合成 UI＋真 pure；藥品done無箭頭，完整頁54fresh幀後一次A。"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import re

import pytest
import laya_pokemon
from laya_pokemon.player_battle import decode_player_battle
from laya_pokemon.wild_opponent import decode_enemy_mon

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-medicine-reviewed-bridge-20261025'
PURE_STAGE=ROOT/'.local/staged-medicine-hp-animation-20261025'


def source_for_test(test_path):
    p=Path(test_path).resolve()
    if p==STAGE/'test_battle_medicine.py':return PURE_STAGE/'battle_medicine.py'
    if p==ROOT/'tests/test_battle_medicine.py':return ROOT/'src/laya_pokemon/battle_medicine.py'
    raise RuntimeError('Only exact staged or formal test location is supported')


spec=importlib.util.spec_from_file_location('medicine_final_stage',source_for_test(__file__))
bm=importlib.util.module_from_spec(spec);spec.loader.exec_module(bm)

LOC={'map_id':166,'x':4,'y':3}
NAMES=[(132,'SNORLAX'),(7,'NIDOKING'),(19,'LAPRAS'),(102,'EEVEE'),(154,'VENUSAUR'),(35,'FEAROW')]


def progress(item=18,quantity=10,status=0,hp=65):
    p={'profile':'gen1-wrapper-ram-progress-v1-unvalidated','initialization_candidate':True,
       'party_read_valid':True,'party_count':6,'money':48332,
       'inventory':[{'item':4,'quantity':6},{'item':197,'quantity':1},
                    {'item':43,'quantity':1},{'item':18,'quantity':10},
                    {'item':52,'quantity':10},{'item':238,'quantity':1}],
       'party':[dict(species=s,species_name=n,level=38 if s==19 else 41,
                     exp=60000,hp=155 if s==19 else 180,max_hp=155 if s==19 else 180,
                     status=0,moves=[57,34,58,109] if s==19 else [33,0,0,0],
                     pp=[15,15,10,10] if s==19 else [35,0,0,0]) for s,n in NAMES]}
    p['party'][2]['hp']=hp;p['party'][2]['status']=status
    next(i for i in p['inventory'] if i['item']==item)['quantity']=quantity
    return p


def record(species=20,level=47,hp=149,maxhp=149,status=0,moves=None,pp=None):
    a=[0]*29;a[0]=species;a[1:3]=divmod(hp,256);a[4]=status
    a[5:7]=[20,20] if species==20 else [21,25]
    a[7]=75;a[8:12]=moves or [46,52,126,36];a[12:14]=[152,136]
    a[14]=level;a[15:17]=divmod(maxhp,256)
    for j in (17,19,21,23):a[j:j+2]=[0,90]
    a[25:29]=pp or [20,25,5,20]
    return a


def blank():return [[' ']*20 for _ in range(18)]
def at(c,x,y,s):c[y][x:x+len(s)]=list(s)
def stat(status,level=None):
    if status&7:return 'SLP'
    return {0:'' if level is None else str(level),8:'PSN',16:'BRN',32:'FRZ',64:'PAR'}[status]


def hud(player,enemy):
    c=blank();at(c,1,0,'ARCANINE');at(c,5,1,stat(enemy['status'],47))
    at(c,10,7,'LAPRAS');at(c,15,8,stat(player['status'],38))
    at(c,11,10,f"{player['hp']:3}/{player['max_hp']:3}");return c


def cmd(player,enemy,cursor=(9,16)):
    c=hud(player,enemy)
    for x,y,s in [(10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')]:at(c,x,y,s)
    c[cursor[1]][cursor[0]]='▶';return c


def dialog(player,enemy,top,bottom='',arrow=False):
    c=hud(player,enemy);at(c,1,14,top);at(c,1,16,bottom)
    if arrow:c[16][18]='▼'
    return c


def bag(player,enemy,items,offset=0,cursor=0,arrow=True):
    c=hud(player,enemy)
    for y in range(2,18):
        x=4 if y<12 else 0;c[y][x:]=[' ']*(20-x)
    labels={4:'POKé BALL',197:'HM02',43:'SECRET KEY',18:'HYPER POTION',52:'FULL HEAL',238:'TM38'}
    printed=0
    for j in range(4):
        idx=offset+j;y=4+2*j
        if idx==len(items):at(c,6,y,'CANCEL');break
        if idx>len(items):break
        i=items[idx];at(c,6,y,labels[i['item']])
        if i['item'] not in (197,43):at(c,14,y+1,f"×{i['quantity']:2}")
        printed+=1
    c[4+2*cursor][5]='▶'
    if arrow and printed==4:c[11][18]='▼'
    return c


def party(p,cursor=2,marker='▶',receipt=None,arrow=False):
    c=blank()
    for j,m in enumerate(p):
        at(c,3,2*j,m['species_name']);at(c,14,2*j,str(m['level']))
        at(c,17,2*j,stat(m['status']));at(c,13,2*j+1,f"{m['hp']:3}/{m['max_hp']:3}")
    if cursor is not None:c[2*cursor+1][0]=marker
    if receipt is None:
        at(c,1,14,'Use item on which');at(c,1,16,'POKéMON?')
    elif receipt[0]=='heal':
        at(c,1,14,'LAPRAS');at(c,1,16,f'Recovered by {receipt[1]}!')
    else:
        at(c,1,14,'LAPRAS');c[14][7]="'s";at(c,1,16,'health returned!')
    if arrow:c[16][18]='▼'
    return c


def text(c):
    lines=[(''.join(r).rstrip(),y) for y,r in enumerate(c)
           if re.search(r'[A-Za-z0-9]{2,}',''.join(r).rstrip())][:12]
    return dict(profile=bm.TEXT_PROFILE,read_valid=True,alignment_verified=True,
                read_error=None,window_visible=True,cells=deepcopy(c),
                lines=[s for s,y in lines],line_rows=[y for s,y in lines])


class Session:
    def __init__(self,item=18,quantity=10,**budget):
        self.item=item;self.intent=deepcopy(bm.HYPER_POTION_INTENT if item==18 else bm.FULL_HEAL_INTENT)
        self.c=bm.BattleMedicineController(self.intent,owner='parent-medicine-1',**budget)
        self.p=progress(item,quantity,status=16 if item==52 else 0)
        self.before=deepcopy(self.p);self.frame=1730000;self.now=0.;self.prev=[]
        self.enemy=decode_enemy_mon(record())['enemy'];self.player=self.player_now();self.kw=None
    def player_now(self):
        m=self.p['party'][2]
        return decode_player_battle(record(19,38,m['hp'],m['max_hp'],m['status'],m['moves'],m['pp']))['player']
    def call(self,cells=None,advance=40,**overrides):
        if self.kw is not None:self.frame+=advance;self.now+=.1
        raw=record(self.enemy['species'],self.enemy['level'],self.enemy['hp'],
                   self.enemy['max_hp'],self.enemy['status'],self.enemy['moves'],self.enemy['pp'])
        e=dict(profile=bm.ENEMY_PROFILE,source_commit=bm.SOURCE_COMMIT,read_valid=True,
               frame_before=self.frame,frame_after=self.frame,observation_frame=self.frame,
               location=deepcopy(LOC),battle_kind='trainer',raw=2,battle_type=0,current_opponent=247,
               raw_record=raw,enemy=deepcopy(self.enemy))
        ps=dict(profile=bm.PLAYER_PROFILE,source_commit=bm.SOURCE_COMMIT,read_valid=True,
                observation_frame=self.frame,location=deepcopy(LOC),battle_kind='trainer',
                active_party_index=2,player=deepcopy(self.player))
        kw=dict(text=text(cells if cells is not None else cmd(self.player,self.enemy)),progress=deepcopy(self.p),
                owner='parent-medicine-1',location=deepcopy(LOC),battle_state=dict(raw=2,kind='trainer',active=True,
                observation_frame=self.frame,opponent_species='ARCANINE'),player_snapshot=ps,enemy_proof=e,
                frame=self.frame,now=self.now,previous=list(self.prev))
        kw.update(overrides);self.kw=deepcopy(kw);r=self.c.context(**kw)
        self.prev=[r['available_actions'][0]];return r
    def open(self,cursor=(9,16)):
        r=self.call(cmd(self.player,self.enemy,cursor))
        while r['available_actions'][0] in ('left','down'):
            cursor=(9,cursor[1]) if r['available_actions'][0]=='left' else (9,16)
            r=self.call(cmd(self.player,self.enemy,cursor))
        assert r['available_actions'][0]=='a',r
    def select(self,first_party=2):
        self.open();off=cur=0;target=3 if self.item==18 else 4
        for j in range(target+1):
            r=self.call(bag(self.player,self.enemy,self.p['inventory'],off,cur))
            assert r['available_actions'][0]==('a' if j==target else 'down'),r
            if cur<2:cur+=1
            else:off+=1
        r=self.call(party(self.p['party'],first_party))
        while first_party!=2:
            assert r['available_actions'][0]==('down' if first_party<2 else 'up'),r
            first_party+=1 if first_party<2 else -1
            r=self.call(party(self.p['party'],first_party))
        assert r['available_actions'][0]=='a',r
    def effect(self):
        if self.item==18:self.p['party'][2]['hp']=155
        else:self.p['party'][2]['status']=0
        for j,i in enumerate(self.p['inventory']):
            if i['item']==self.item:
                i['quantity']-=1
                if i['quantity']==0:self.p['inventory'].pop(j)
                break
        self.player=self.player_now()
    def receipt(self,arrow=False):
        delta=self.c.healed[self.c.active]['hp']-self.c.baseline['party'][self.c.active]['hp']
        return party(self.p['party'],None,receipt=('heal',delta) if self.item==18 else ('cure',0),arrow=arrow)
    def use(self):
        self.select();self.effect()
        r=self.call(self.receipt());assert r['available_actions']==['wait'],r
        r=self.call(self.receipt(),advance=54);assert r['available_actions'][0]=='a',r
    def enemy_turn(self,move='EMBER',burn=False,critical=False):
        r=self.call(dialog(self.player,self.enemy,'Enemy ARCANINE','used '+move+'!'))
        assert r['available_actions']==['wait'],r
        self.player['hp']-=20;self.p['party'][2]['hp']-=20
        if critical:
            r=self.call(dialog(self.player,self.enemy,'Critical hit!','',True))
            assert r['available_actions'][0]=='a',r
        if burn:
            self.player['status']=16;self.p['party'][2]['status']=16
            r=self.call(dialog(self.player,self.enemy,'LAPRAS','was burned!',True))
            assert r['available_actions'][0]=='a',r
        r=self.call();assert r['available_actions']==['wait'] and not r.get('battle_medicine_complete'),r
        r=self.call();assert r.get('battle_medicine_complete') is True,r
        return r


@pytest.mark.parametrize('item',[18,52])
def test_complete_exact_transaction_preserves_party_money_and_uses_one(item):
    s=Session(item);s.use();r=s.enemy_turn()
    assert r['survival_approved'] is False
    assert s.c.baseline['party']==s.before['party'] and s.c.baseline['inventory']==s.before['inventory']
    assert s.p['money']==s.before['money']
    assert all(s.p['party'][j]==s.before['party'][j] for j in (0,1,3,4,5))
    assert next(i['quantity'] for i in s.p['inventory'] if i['item']==item)==9


@pytest.mark.parametrize('cursor',[(9,14),(15,14),(9,16),(15,16)])
def test_command_cursor_normal_directions_only(cursor):
    s=Session();s.open(cursor)


@pytest.mark.parametrize('first',[0,1,2,3,4,5])
def test_six_party_saved_cursor_not_assumed_zero(first):
    Session().select(first)


@pytest.mark.parametrize('item',[18,52])
def test_whole_done_receipt_settles54_fresh_frames_then_single_a(item):
    s=Session(item);s.select();s.effect()
    receipt=s.receipt();assert receipt[16][18]==' '
    assert s.call(receipt)['available_actions']==['wait']
    assert s.c.stage=='receipt'
    assert s.call(receipt,advance=53)['available_actions']==['wait']
    partial=deepcopy(receipt);partial[16][1]=' '
    assert s.call(partial,advance=1)['available_actions']==['wait']
    assert s.c.receipt_full_frame is None
    assert s.call(receipt,advance=1)['available_actions']==['wait']
    assert s.call(receipt,advance=53)['available_actions']==['wait']
    assert s.call(receipt,advance=1)['available_actions'][0]=='a'
    for _ in range(2):assert s.call(receipt)['available_actions']==['wait']
    assert s.c.stage=='retaliation'


@pytest.mark.parametrize('item',[18,52])
def test_quantity_one_removes_only_used_stack(item):
    s=Session(item,quantity=1);s.use();s.enemy_turn()
    assert all(i['item']!=item for i in s.p['inventory'])


@pytest.mark.parametrize('kind',['clock','frame','sameframe','owner','intent'])
def test_binding_clock_and_sameframe_sticky_review(kind):
    s=Session();s.call();kw=deepcopy(s.kw)
    if kind=='clock':kw['now']=-1
    elif kind=='frame':kw['frame']-=1
    elif kind=='sameframe':kw['progress']['money']+=1
    elif kind=='owner':kw['owner']='foreign'
    else:s.c.intent['quantity']=2
    r=s.c.context(**kw);assert r['phase']=='strategy_review' and r['available_actions']==['wait']
    assert s.c.context(**s.kw)['phase']=='strategy_review'


@pytest.mark.parametrize('frame',[False,0.0,-1,2**63])
def test_invalid_frame_never_starts(frame):
    s=Session();r=s.call(frame=frame);assert r['phase']=='strategy_review' and s.c.baseline is None


def test_large_native_frame_valid_and_sameframe_never_resends():
    s=Session();assert s.call()['available_actions'][0]=='a'
    assert s.c.context(**s.kw)['available_actions']==['wait']
    assert s.c.calls==2


@pytest.mark.parametrize('area',['text','enemy','player','battle','party','money','bag','location'])
def test_invalid_initial_proof_never_offers_a(area):
    s=Session();s.call();kw=deepcopy(s.kw);c=bm.BattleMedicineController(s.intent,owner=s.c.owner)
    if area=='text':kw['text']['alignment_verified']=False
    elif area=='enemy':kw['enemy_proof']['raw']=1
    elif area=='player':kw['player_snapshot']['observation_frame']+=1
    elif area=='battle':kw['battle_state']['raw']=True
    elif area=='party':kw['progress']['party_count']=True
    elif area=='money':kw['progress']['money']=False
    elif area=='bag':kw['progress']['inventory'][0]['quantity']=True
    else:kw['location']['map_id']=150
    r=c.context(**kw);assert r['available_actions']==['wait'] and r['phase']=='strategy_review'


def test_no_actual_previous_preserves_offer_and_no_duplicate_a():
    s=Session();s.call();before=s.c.pending.copy()
    for _ in range(3):
        r=s.call(bag(s.player,s.enemy,s.p['inventory']),previous=['wait'])
        assert r['available_actions']==['wait'] and s.c.pending==before


def test_old_command_across_blank_does_not_resend():
    s=Session();s.call()
    assert s.call(blank())['available_actions']==['wait']
    assert s.call()['available_actions']==['wait']


@pytest.mark.parametrize('mutation',['foreign_cursor','wrong_name','toss','offset','missing_quantity'])
def test_bag_unknown_or_wrong_semantic_position_never_a(mutation):
    s=Session();s.open();c=bag(s.player,s.enemy,s.p['inventory'])
    if mutation=='foreign_cursor':c[1][1]='▶'
    elif mutation=='wrong_name':c[4][6]='X'
    elif mutation=='toss':at(c,1,14,'TOSS')
    elif mutation=='offset':c[4][5]=' ';c[8][5]='▶'  # legitimate saved viewport; not target => down
    else:c[5][14]='X'
    r=s.call(c)
    assert r['available_actions'][0]!='a'
    if mutation!='offset':assert r['phase']=='strategy_review'


@pytest.mark.parametrize('mutation',['wrong_party_name','foreign_arrow','able','switch'])
def test_party_wrong_labels_no_apply(mutation):
    s=Session();s.open()
    for off,cur in [(0,0),(0,1),(0,2),(1,2)]:s.call(bag(s.player,s.enemy,s.p['inventory'],off,cur))
    c=party(s.p['party'])
    if mutation=='wrong_party_name':c[0][3]='X'
    elif mutation=='foreign_arrow':c[1][1]='▷'
    elif mutation=='able':at(c,12,5,'ABLE')
    else:at(c,13,12,'SWITCH')
    r=s.call(c);assert r['phase']=='strategy_review' and r['available_actions']==['wait']


@pytest.mark.parametrize('delta',['money','other_hp','pp','exp','order','extra_item','double_used','false_effect'])
def test_unrelated_or_wrong_effect_changes_review(delta):
    s=Session();s.select();s.effect()
    if delta=='money':s.p['money']-=1
    elif delta=='other_hp':s.p['party'][0]['hp']-=1
    elif delta=='pp':s.p['party'][2]['pp'][0]-=1
    elif delta=='exp':s.p['party'][2]['exp']+=1
    elif delta=='order':s.p['party'][0],s.p['party'][1]=s.p['party'][1],s.p['party'][0]
    elif delta=='extra_item':s.p['inventory'][0]['quantity']-=1
    elif delta=='double_used':s.p['inventory'][3]['quantity']-=1
    else:s.p['party'][2]['hp']-=1
    r=s.call(s.receipt());assert r['phase']=='strategy_review' and r['available_actions']==['wait']


def test_full_heal_native_contraction_only_at_source_cell():
    s=Session(52);s.select();s.effect();c=s.receipt()
    assert c[14][7]=="'s"
    c[0][0]="'s"
    r=s.call(c);assert r['phase']=='strategy_review'


@pytest.mark.parametrize('attack',['EMBER','FIRE BLAST'])
def test_critical_and_burn_are_source_prompts_not_automatic_success(attack):
    s=Session();s.use();r=s.enemy_turn(attack,burn=True,critical=True)
    assert r['battle_medicine_complete'] and s.p['party'][2]['status']==16


def test_roar_failed_native_prompt_then_command():
    s=Session();s.use()
    assert s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used ROAR!'))['available_actions']==['wait']
    assert s.call(dialog(s.player,s.enemy,'But, it failed!','',True))['available_actions'][0]=='a'
    assert not s.call().get('battle_medicine_complete')
    assert s.call().get('battle_medicine_complete')


@pytest.mark.parametrize('bad',['new_command_without_enemy','unknown_attack','recoil_ko','faint','party_unsync'])
def test_unknown_or_unresolved_enemy_turn_never_completes(bad):
    s=Session();s.use()
    if bad=='new_command_without_enemy':r=s.call()
    elif bad=='unknown_attack':r=s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used BITE!'))
    elif bad=='recoil_ko':
        s.enemy['hp']=0;r=s.call()
    elif bad=='faint':
        s.player['hp']=0;s.p['party'][2]['hp']=0;r=s.call()
    else:
        s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used EMBER!'))
        s.player['hp']-=20;r=s.call()
    assert r['available_actions']==['wait'] and r['phase']=='strategy_review'
    assert not r.get('battle_medicine_complete')


@pytest.mark.parametrize('budget', ['wait','call','time'])
def test_persistent_budget_does_not_reset_across_calls(budget):
    s=Session(max_waits=1 if budget=='wait' else 30,max_calls=1 if budget=='call' else 240)
    s.call()
    if budget=='time':r=s.call(blank(),now=61)
    elif budget=='call':r=s.call(blank())
    else:s.call(blank());r=s.call(blank())
    assert r['phase']=='strategy_review' and s.c.started==0


@pytest.mark.parametrize('item',[18,52])
def test_no_effect_or_missing_item_is_review(item):
    s=Session(item)
    if item==18:s.p['party'][2]['hp']=155
    else:s.p['party'][2]['status']=0
    s.player=s.player_now()
    assert s.call()['phase']=='strategy_review'


def test_final_same_frame_changed_packet_is_review_not_complete():
    s=Session();s.use();s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used EMBER!'))
    s.call();kw=deepcopy(s.kw);kw['progress']['money']-=1
    r=s.c.context(**kw);assert r['phase']=='strategy_review' and not s.c.complete


def test_input_snapshots_not_mutated():
    s=Session();s.call();kw=deepcopy(s.kw);before=deepcopy(kw)
    s.c.context(**kw);assert kw==before


@pytest.mark.parametrize('source_value',[False,0.0])
@pytest.mark.parametrize('field',['raw','battle_type','frame_after','current_opponent'])
def test_enemy_proof_true_integer_domain(field,source_value):
    s=Session();s.call();kw=deepcopy(s.kw)
    kw['enemy_proof'][field]=source_value
    c=bm.BattleMedicineController(s.intent,owner=s.c.owner)
    assert c.context(**kw)['phase']=='strategy_review'


def test_hp_decimal_left_alignment_not_padded():
    s=Session();s.select();s.effect();c=s.receipt()
    at(c,1,16,'Recovered by  90!')
    r=s.call(c);assert r['available_actions']==['wait'] and r['phase']=='strategy_review'


def test_burn_tick_exact_single_cell_ligature_once():
    s=Session();s.use();s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used FIRE BLAST!'))
    s.player['status']=16;s.p['party'][2]['status']=16
    assert s.call(dialog(s.player,s.enemy,'LAPRAS','was burned!',True))['available_actions'][0]=='a'
    c=dialog(s.player,s.enemy,'LAPRAS','hurt by the burn!',True);c[14][7]="'s"
    assert s.call(c)['available_actions'][0]=='a'
    assert s.call(c)['available_actions']==['wait']


@pytest.mark.parametrize('field',['level','hp','status','moves','pp','dvs'])
def test_player_packet_typed_or_identity_changes_no_a(field):
    s=Session();s.call();kw=deepcopy(s.kw)
    p=kw['player_snapshot']['player']
    if field in ('moves','pp','dvs'):p[field][0]=False
    else:p[field]=False
    c=bm.BattleMedicineController(s.intent,owner=s.c.owner)
    assert c.context(**kw)['phase']=='strategy_review'


def test_source_only_party_validation_does_not_load_reference(monkeypatch):
    import laya_pokemon.team_strategy as strategy
    def forbidden(*a,**k):raise AssertionError('controller must not load reference JSON')
    monkeypatch.setattr(strategy,'reference',forbidden)
    s=Session();s.use();s.enemy_turn()


def enemy_prompt(s,bottom,arrow=True):
    c=dialog(s.player,s.enemy,'Enemy ARCANINE',bottom,arrow)
    c[14][15]="'s"
    return c


def test_exact_source_resolution_does_not_guess_or_fallback():
    assert source_for_test(STAGE/'test_battle_medicine.py') == PURE_STAGE/'battle_medicine.py'
    assert source_for_test(ROOT/'tests/test_battle_medicine.py') == ROOT/'src/laya_pokemon/battle_medicine.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_battle_medicine.py')
    assert Path(bm.__file__).resolve() == source_for_test(__file__)


@pytest.mark.parametrize('species',[20,True,20.0,'','arcanine','ARCANINE ','NINETALES'])
def test_runtime_schema_requires_exact_species_name_string(species):
    s=Session();s.call();kw=deepcopy(s.kw)
    kw['battle_state']['opponent_species']=species
    c=bm.BattleMedicineController(s.intent,owner=s.c.owner)
    assert c.context(**kw)['phase']=='strategy_review'


@pytest.mark.parametrize('budget',['call','time'])
def test_duplicate_frame_still_consumes_clock_and_call_budgets(budget):
    s=Session(max_calls=1 if budget=='call' else 240)
    s.call();kw=deepcopy(s.kw)
    if budget=='time':kw['now']=60.0001
    r=s.c.context(**kw)
    assert r['phase']=='strategy_review' and s.c.calls==2
    assert r['review_reason']=='battle_medicine_call_or_time_budget_exhausted'
    assert not r.get('battle_medicine_complete')


def test_duplicate_frame_updates_clock_then_detects_regression():
    s=Session();s.call();kw=deepcopy(s.kw);kw['now']=30.
    assert s.c.context(**kw)['available_actions']==['wait']
    assert s.c.last_now==30.
    kw['now']=29.
    assert s.c.context(**kw)['review_reason']=='battle_medicine_clock_or_frame_regressed'


def test_sixty_second_clock_boundary_is_checked_even_without_new_frame():
    s=Session();s.call();kw=deepcopy(s.kw);kw['now']=60.
    assert s.c.context(**kw)['phase']!='strategy_review'
    kw['now']=60.01
    assert s.c.context(**kw)['phase']=='strategy_review'


@pytest.mark.parametrize('move',['EMBER','FIRE BLAST','TAKE DOWN'])
def test_native_enemy_miss_one_cell_contraction_closes_after_two_command_frames(move):
    s=Session();s.use()
    assert s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used '+move+'!'))['available_actions']==['wait']
    c=enemy_prompt(s,'attack missed!')
    assert c[14][15]=="'s" and len(c[14])==20
    assert s.call(c)['available_actions'][0]=='a'
    assert s.call(c)['available_actions']==['wait']
    assert s.call(blank())['available_actions']==['wait']
    assert s.call(c)['available_actions']==['wait']
    assert not s.call().get('battle_medicine_complete')
    assert s.call().get('battle_medicine_complete')
    assert s.enemy['hp']==149 and s.player['hp']==155


@pytest.mark.parametrize('bad',['shifted','expanded','wrong_user','foreign_cell','no_enemy_move'])
def test_miss_requires_exact_native_user_position_and_observed_move(bad):
    s=Session();s.use()
    if bad!='no_enemy_move':s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used EMBER!'))
    c=enemy_prompt(s,'attack missed!')
    if bad=='shifted':c[14][15]=' ';c[14][16]="'s"
    elif bad=='expanded':c[14][15]="'";c[14][16]='s'
    elif bad=='wrong_user':c[14][7]='X'
    elif bad=='foreign_cell':c[13][15]="'s"
    r=s.call(c)
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']


@pytest.mark.parametrize('damage',[1,3,4,23,24,60])
@pytest.mark.parametrize('item',[18,52])
def test_take_down_exact_non_ko_recoil_receipt_then_two_fresh_commands(item,damage):
    s=Session(item);s.use()
    assert s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used TAKE DOWN!'))['available_actions']==['wait']
    s.player['hp']-=damage;s.p['party'][2]['hp']-=damage
    s.enemy['hp']-=max(1,damage//4)
    c=enemy_prompt(s,'hit with recoil!')
    no_arrow=deepcopy(c);no_arrow[16][18]=' '
    assert s.call(no_arrow)['available_actions']==['wait']
    assert s.call(c)['available_actions'][0]=='a'
    assert s.call(c)['available_actions']==['wait']
    assert not s.call().get('battle_medicine_complete')
    assert s.call().get('battle_medicine_complete')
    assert s.c.recoil_hp==s.enemy['hp'] and s.c.enemy_missed is False
    assert s.p['money']==s.before['money']
    assert all(s.p['party'][j]==s.before['party'][j] for j in (0,1,3,4,5))


@pytest.mark.parametrize('bad',['zero','wrong_delta','no_player_hit','no_recoil_receipt',
                              'miss_then_recoil','status_change','enemy_heal','second_hp_loss'])
def test_take_down_recoil_must_preserve_observed_damage_and_identity(bad):
    s=Session();s.use();s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used TAKE DOWN!'))
    if bad=='miss_then_recoil':assert s.call(enemy_prompt(s,'attack missed!'))['available_actions'][0]=='a'
    if bad!='no_player_hit':s.player['hp']-=24;s.p['party'][2]['hp']-=24
    s.enemy['hp']-=6
    if bad=='zero':s.enemy['hp']=0
    elif bad=='wrong_delta':s.enemy['hp']-=1
    elif bad=='status_change':s.player['status']=16;s.p['party'][2]['status']=16
    if bad=='no_recoil_receipt':r=s.call()
    elif bad in ('enemy_heal','second_hp_loss'):
        assert s.call(enemy_prompt(s,'hit with recoil!'))['available_actions'][0]=='a'
        s.enemy['hp']+=1 if bad=='enemy_heal' else -1;r=s.call()
    else:r=s.call(enemy_prompt(s,'hit with recoil!'))
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']
    assert not r.get('battle_medicine_complete')


def test_enemy_hp_change_before_take_down_is_unknown():
    s=Session();s.use();s.enemy['hp']-=1
    assert s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used EMBER!'))['phase']=='strategy_review'


def test_take_down_miss_cannot_explain_player_damage_before_miss_receipt():
    s=Session();s.use();s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used TAKE DOWN!'))
    s.player['hp']-=24;s.p['party'][2]['hp']-=24
    assert s.call(enemy_prompt(s,'attack missed!'))['phase']=='strategy_review'


@pytest.mark.parametrize('item',[18,52])
def test_take_down_player_ko_is_review_before_recoil_prompt(item):
    s=Session(item);s.use();s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used TAKE DOWN!'))
    s.player['hp']=0;s.p['party'][2]['hp']=0;s.enemy['hp']-=6
    assert s.call(enemy_prompt(s,'hit with recoil!'))['phase']=='strategy_review'


def test_take_down_critical_hit_prompt_precedes_exact_recoil_prompt():
    s=Session();s.use();s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used TAKE DOWN!'))
    s.player['hp']-=24;s.p['party'][2]['hp']-=24
    assert s.call(dialog(s.player,s.enemy,'Critical hit!','',True))['available_actions'][0]=='a'
    s.enemy['hp']-=6
    assert s.call(enemy_prompt(s,'hit with recoil!'))['available_actions'][0]=='a'
    assert not s.call().get('battle_medicine_complete')
    assert s.call().get('battle_medicine_complete')
