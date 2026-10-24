"""Sabrina真ledger的數值/文字，搭配來源座標重建的合成cells；不讀遊戲。

原152行SHA b4e5a1d33659e25d8426b14edd604a0f6f30b48db19d8cafd25bf9e21fa658f0。
23798/23799/23800真state/文字列如下；ledger沒有完整cells/decoder metadata，
所以本檔的cells與read_valid是明示合成fixture，不能冒稱實機原packet。
"""
from copy import deepcopy
import re

import pytest

from laya_pokemon.battle_shift_review import BattleShiftReview, shift_plan
from laya_pokemon.observation import PROFILE


PARTY = [
    dict(species=132, species_name='SNORLAX', level=41, hp=111, max_hp=198,
         exp=91196, status=8, moves=[70,133,156,34], pp=[15,20,10,11]),
    dict(species=7, species_name='NIDOKING', level=36, hp=121, max_hp=121,
         exp=42254, status=0, moves=[61,57,30,40], pp=[20,15,25,35]),
    dict(species=102, species_name='EEVEE', level=35, hp=90, max_hp=90,
         exp=43317, status=0, moves=[33,28,98,39], pp=[35,15,30,30]),
    dict(species=154, species_name='VENUSAUR', level=35, hp=111, max_hp=111,
         exp=36804, status=0, moves=[75,15,73,22], pp=[25,30,10,10]),
    dict(species=35, species_name='FEAROW', level=36, hp=111, max_hp=111,
         exp=50081, status=0, moves=[64,65,43,31], pp=[35,20,30,20]),
    dict(species=19, species_name='LAPRAS', level=30, hp=124, max_hp=124,
         exp=33943, status=0, moves=[55,34,47,54], pp=[25,15,15,30]),
]
NATIVE_TEXT = {
    23798: ['          SNORLAX','               PSN','           111/198',
            ' SABRINA is',' about to use     ▼'],
    23799: ['          SNORLAX','               PSN','           111/198',
            ' about to use',' ALAKAZAM!        ▼'],
    23800: ['          SNORLAX',' ▶YES          PSN','  NO       111/198',
            ' Will KEVIN',' change POKéMON?'],
}
ROW_SHA_23800 = '7ea57bcdb47ce16ba781bc6d477a6500d8c65321667e3b90511308124b5d0c8f'


def packet(entries):
    cells = [[' '] * 20 for _ in range(18)]
    for x,y,value in entries:
        assert x + len(value) <= 20
        cells[y][x:x+len(value)] = list(value)
    return refresh({'cells':cells,'profile':PROFILE,'read_valid':True,
                    'alignment_verified':True,'read_error':None,'window_visible':False})


def refresh(text):
    selected = [(y,''.join(row).rstrip()) for y,row in enumerate(text['cells'])
                if re.search(r'[A-Za-z0-9]{2,}',''.join(row))][:12]
    text.update(lines=[row for _,row in selected],line_rows=[y for y,_ in selected])
    return text


def hud(party=PARTY, active=0):
    mon=party[active]
    status='PSN' if mon['status']==8 else f"{mon['level']:3}"
    return [(10,7,mon['species_name']),(15,8,status),
            (11,10,f"{mon['hp']:3}/{mon['max_hp']:3}")]


def page(kind, party=PARTY):
    entries=hud(party)
    if kind=='preface':entries += [(1,14,'SABRINA is'),(1,16,'about to use'),(18,16,'▼')]
    elif kind=='species':entries += [(1,14,'about to use'),(1,16,'ALAKAZAM!'),(18,16,'▼')]
    elif kind=='question':entries += [(2,8,'YES'),(2,10,'NO'),(1,8,'▶'),(1,14,'Will KEVIN'),(1,16,'change POKéMON?')]
    return packet(entries)


def party_page(party=PARTY, cursor=0, *, inactive=False, wrong_footer=False):
    entries=[]
    for i,mon in enumerate(party):
        entries += [(3,i*2,mon['species_name']),(14,i*2,str(mon['level'])),
                    (13,i*2+1,f"{mon['hp']:3}/{mon['max_hp']:3}")]
        if mon['status']==8:entries += [(17,i*2,'PSN')]
    entries += [(0,cursor*2+1,'▷' if inactive else '▶'),
                (1,14,'Choose a POKéMON.' if wrong_footer else 'Bring out which')]
    if not wrong_footer:entries += [(1,16,'POKéMON?')]
    return packet(entries)


def command_page(party=PARTY, active=4):
    return packet(hud(party,active)+[(1,0,'ALAKAZAM'),(5,1,' 43'),
                  (10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'),(9,14,'▶')])


class Harness:
    def __init__(self, party=None):
        self.controller=BattleShiftReview()
        self.party=deepcopy(PARTY if party is None else party)
        self.frame=1411025
        self.now=0
        self.previous=[]

    def feed(self,text,*,actual=None,frame=None,now=None,previous=None,enemy='ALAKAZAM',progress_change=None):
        self.frame=self.frame+40 if frame is None else frame
        self.now=self.now+.1 if now is None else now
        progress={'profile':'gen1-wrapper-ram-progress-v1-unvalidated',
                  'initialization_candidate':True,'party_read_valid':True,
                  'party_count':len(self.party),'party':deepcopy(self.party)}
        if progress_change:progress.update(progress_change)
        state={'raw':2,'active':True,'kind':'trainer','opponent_species':enemy,'observation_frame':self.frame}
        out=self.controller.context(text,state,progress,frame=self.frame,now=self.now,
                                    previous=self.previous if previous is None else previous)
        if out is not None:
            self.previous=[{'frame':self.frame,'action':out['available_actions'][0] if actual is None else actual}]
        return out

    def offer(self):
        assert self.feed(page('preface',self.party))['available_actions']==['a','wait']
        assert self.feed(page('species',self.party))['available_actions']==['a','wait']
        return self.feed(page('question',self.party))


def review(out):
    assert out['phase']=='strategy_review' and out['available_actions']==['wait']


def test_sabrina_true_ledger_text_and_values_select_fearow_instead_of_unconditional_b():
    for step,kind in [(23798,'preface'),(23799,'species'),(23800,'question')]:
        assert page(kind)['lines']==NATIVE_TEXT[step]
    original=deepcopy(PARTY)
    assert PARTY[0]['hp']/PARTY[0]['max_hp']>.5 and PARTY[0]['status']==8
    plan=shift_plan(PARTY,0,'ALAKAZAM')
    assert plan['decision']=='switch' and plan['target_index']==4 and plan['target_species']==35
    h=Harness();out=h.offer()
    assert out['available_actions']==['a','wait'] and h.controller.target==4
    assert PARTY==original


def test_normal_six_slot_free_shift_has_no_switch_submenu_and_requires_real_target_command():
    h=Harness();h.offer();original=deepcopy(h.party)
    for cursor in range(4):
        out=h.feed(party_page(h.party,cursor));assert out['objective']=='Move DOWN.'
    out=h.feed(party_page(h.party,4));assert out['available_actions']==['a','wait']
    sendout=packet(hud(h.party)+[(1,14,'SABRINA sent'),(1,16,'out ALAKAZAM!')])
    assert h.feed(sendout)['available_actions']==['wait']
    assert h.controller.last_completed is None
    assert h.feed(command_page(h.party)) is None
    assert h.controller.last_completed['target_species']==35
    assert h.party==original
    # 下一次EXP自然變動不沿用已完成流程的指紋。
    h.party[4]['exp']+=1
    assert h.feed(page('preface',h.party))['available_actions']==['a','wait']


def test_healthy_active_keeps_without_forcing_switch_even_if_next_enemy_unknown():
    party=deepcopy(PARTY);party[0].update(hp=198,status=0)
    assert shift_plan(party,0,None)['decision']=='keep'
    h=Harness(party);assert h.feed(page('question',party))['available_actions']==['b','wait']
    assert h.feed(packet([])) is None
    h.party[0]['exp']+=1
    assert h.feed(page('question',h.party))['available_actions']==['b','wait']


def test_risky_active_missing_visible_next_species_reviews_instead_of_fallthrough_b_or_a():
    h=Harness();review(h.feed(page('question')))
    assert h.controller.target is None


@pytest.mark.parametrize('change',[
    lambda p:p[4].update(status=8),
    lambda p:p[4].update(hp=74),
    lambda p:p[4].update(pp=[0,2,0,0]),
    lambda p:p[4].update(moves=[45,43,0,0],pp=[40,30,0,0]),
    lambda p:p[4].update(level=10),
])
def test_cannot_replace_with_poisoned_low_hp_low_pp_nonattacking_or_underlevel_support(change):
    party=deepcopy(PARTY);change(party)
    assert shift_plan(party,0,'ALAKAZAM')['decision']=='review'


def test_poison_grass_psychic_weakness_and_much_lower_offense_are_not_better_support():
    party=deepcopy(PARTY);party[4]['hp']=0
    # 健康尼多王/妙蛙花仍有超能力弱點；伊布/拉普拉斯的攻擊分數也不足。
    assert shift_plan(party,0,'ALAKAZAM')['decision']=='review'


@pytest.mark.parametrize('change',[
    lambda t:t.update(read_valid=False),lambda t:t.update(window_visible=True),
    lambda t:t.update(profile='unknown'),lambda t:t.update(line_rows=[0]),
    lambda t:t['cells'][0].__setitem__(0,'▷'),
    lambda t:t['cells'][10].__setitem__(3,'T'),
])
def test_question_unknown_decoder_foreign_mark_or_pollution_never_confirms(change):
    h=Harness();h.feed(page('preface'));h.feed(page('species'))
    text=page('question');change(text);review(h.feed(text))


@pytest.mark.parametrize('which',['text','progress'])
def test_peer_reproduced_explicit_observation_frame_conflict_cannot_a(which):
    h=Harness();h.feed(page('preface'));h.feed(page('species'));text=page('question')
    if which=='text':text['observation_frame']=999
    out=h.feed(text,progress_change={'observation_frame':999} if which=='progress' else None)
    review(out)


def test_only_ledger_text_without_native_cells_cannot_be_promoted_to_decoder_proof():
    h=Harness();review(h.feed({'profile':PROFILE,'lines':NATIVE_TEXT[23800]}))


def test_candidate_is_not_actual_a_when_laya_selected_wait():
    h=Harness();out=h.feed(page('preface'),actual='wait')
    assert out['available_actions']==['a','wait']
    assert h.controller.stage=='idle'
    out=h.feed(page('preface'))
    assert out['available_actions']==['a','wait'] and h.controller.stage=='idle'


def test_false_previous_or_same_frame_conflict_is_sticky_review():
    h=Harness();h.feed(page('preface'))
    review(h.feed(page('species'),previous=[{'frame':0,'action':'a'}]))
    review(h.feed(page('species')))
    h=Harness();h.offer();frame=h.frame
    text=page('question');text['window_visible']=True
    review(h.feed(text,frame=frame))


def test_blink_and_partial_species_only_wait_and_do_not_choose_a_new_enemy():
    h=Harness();h.feed(page('preface'))
    text=packet(hud()+[(1,14,'about to use'),(1,16,'ALA')])
    assert h.feed(text)['available_actions']==['wait'] and h.controller.enemy is None
    text=page('species');text['cells'][16][18]=' ';refresh(text)
    assert h.feed(text)['available_actions']==['wait'] and h.controller.enemy is None


def test_native_species_and_ram_disagreement_reviews():
    h=Harness();h.feed(page('preface'));review(h.feed(page('species'),enemy='GENGAR'))


def test_actual_up_on_no_cursor_old_page_waits_instead_of_repeating_up():
    h=Harness();h.feed(page('preface'));h.feed(page('species'))
    t=page('question');t['cells'][8][1]=' ';t['cells'][10][1]='▶';refresh(t)
    assert h.feed(t)['objective']=='Move UP.'
    assert h.feed(t)['available_actions']==['wait']
    assert h.feed(page('question'))['available_actions']==['a','wait']


def test_inactive_party_and_unknown_normal_switch_submenu_do_not_choose_member():
    h=Harness();h.offer()
    assert h.feed(party_page(inactive=True))['available_actions']==['wait']
    review(h.feed(party_page(wrong_footer=True)))


def test_same_frame_identical_packet_waits_and_changed_party_never_rebinds():
    h=Harness();h.offer();frame=h.frame
    assert h.feed(page('question'),frame=frame)['available_actions']==['wait']
    h.party[4]['hp']-=1
    review(h.feed(party_page(h.party)))


def test_wait_and_clock_budgets_are_bounded_and_do_not_a():
    h=Harness();h.offer()
    for _ in range(26):out=h.feed(packet([]))
    review(out)
    h=Harness();h.feed(page('preface'));review(h.feed(page('species'),now=61))


def test_nontrainer_outside_scope_does_not_override_wild_capture_or_loss_handling():
    c=BattleShiftReview()
    for kind,raw,active in [('wild',1,True),('lost_transition',255,False),('none',0,False)]:
        assert c.context(page('question'),{'kind':kind,'raw':raw,'active':active},{},frame=1,now=1) is None


def test_reference_pp_and_type_input_invalid_do_not_create_switch():
    for change in [lambda p:p[0].update(hp=True),lambda p:p[4].update(pp=[0,True,0,0]),
                   lambda p:p.append(deepcopy(p[4]))]:
        party=deepcopy(PARTY);change(party)
        assert shift_plan(party,0,'ALAKAZAM')['decision']=='review'


def test_healthy_but_all_attacks_immune_does_not_blindly_keep():
    party=deepcopy(PARTY);party[0].update(hp=198,status=0)
    assert shift_plan(party,0,'GENGAR')['decision']!='keep'


def test_bound_upcoming_ram_identity_change_cannot_confirm_yes():
    h=Harness();h.feed(page('preface'));h.feed(page('species'))
    review(h.feed(page('question'),enemy='GENGAR'))
