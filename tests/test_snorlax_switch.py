"""純合成觀測與固定公開來源；不啟動模擬器或讀ROM／存檔。"""
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path

import pytest

from laya_pokemon.observation import PROFILE
from laya_pokemon.snorlax_switch import SnorlaxSwitchController, SOURCE_COMMIT

FIXTURE = json.loads((Path(__file__).parent / 'data/snorlax-switch-source-fixture.json').read_text(encoding='utf-8'))
NAMES = {7: 'NIDOKING', 9: 'IVYSAUR', 154: 'VENUSAUR', 35: 'FEAROW', 102: 'EEVEE'}
LOCATION = {'map_id': 23, 'x': 10, 'y': 61}
WILD = {'raw': 1, 'active': True, 'kind': 'wild', 'opponent_species': 'SNORLAX', 'wild_opponent_species': 'SNORLAX'}


def text_at(*entries, window=True):
    cells = [[' '] * 20 for _ in range(18)]
    for x, y, word in entries:
        assert len(word) + x <= 20
        cells[y][x:x + len(word)] = list(word)
    return {'profile': PROFILE, 'read_valid': True, 'alignment_verified': True,
            'window_visible': window, 'read_error': None, 'cells': cells}


def put(t, x, y, word):
    t['cells'][y][x:x + len(word)] = list(word)
    return t


def progress(roster=(154, 102, 35, 7)):
    mons = {154: (33, 45, 105), 9: (31, 35, 86), 102: (30, 77, 77), 35: (32, 99, 99), 7: (31, 105, 105)}
    return {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'party_read_valid': True,
            'initialization_candidate': True, 'player_name_raw': 'KEVIN', 'party_count': 4,
            'money': 25609, 'inventory': [{'item': 73, 'quantity': 1}, {'item': 3, 'quantity': 20}],
            'party': [{'species': s, 'species_name': NAMES[s], 'level': mons[s][0], 'hp': mons[s][1],
                       'max_hp': mons[s][2], 'exp': 20000, 'status': 0,
                       'moves': [33, 28, 0, 0], 'pp': [35, 15, 0, 0]} for s in roster]}


def enemy(frame, status=0):
    return {'profile': 'red-en-sdk-2.8.1-enemy-source-v1-unvalidated', 'source_commit': SOURCE_COMMIT,
            'live_calibrated': False, 'observation_frame': frame, 'read_valid': True, 'unknown_reason': None,
            'battle_kind': 'wild', 'location': deepcopy(LOCATION),
            'enemy': {'species': 132, 'internal_id': 132, 'species_name': 'SNORLAX', 'level': 30,
                      'hp': 140, 'max_hp': 140, 'status': status}}


def hud(p, active=0, status=0):
    m = p['party'][active]
    label = 'SLP' if status & 7 else '30'
    own = 'SLP' if m['status'] & 7 else {8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}.get(m['status'], str(m['level']))
    return text_at((1, 0, 'SNORLAX'), (5, 1, label), (10, 7, m['species_name']),
                   (15, 8, own), (11, 10, f"{m['hp']:3}/{m['max_hp']:3}"))


def command(p, active=0, cursor=(9, 14), status=0):
    t = hud(p, active, status)
    for x, y, word in ((10, 14, 'FIGHT'), (10, 16, 'ITEM'), (16, 16, 'RUN'), (*cursor, '▶')):
        put(t, x, y, word)
    return t


def party_page(p, cursor=0, *, inactive=False):
    t = text_at((1, 14, 'Choose a POKéMON.'))
    for i, m in enumerate(p['party']):
        y = i * 2
        put(t, 3, y, m['species_name'])
        put(t, 13 if m['level'] == 100 else 14, y, str(m['level']))
        if m['status']:
            put(t, 17, y, 'SLP' if m['status'] & 7 else {8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}[m['status']])
        put(t, 13, y + 1, f"{m['hp']:3}/{m['max_hp']:3}")
    return put(t, 0, cursor * 2 + 1, '▷' if inactive else '▶')


def submenu(p, cursor, *, sub_y=12, unfilled=False):
    t = party_page(p, cursor, inactive=True)
    for y in range(11, 18):
        t['cells'][y][11:20] = [' '] * 9
    for x, y, word in FIXTURE['geometry']['submenu_labels']:
        put(t, x, y, word)
    return put(t, 12, sub_y, '▷' if unfilled else '▶')


def dialogue(p, active, first, second='', prompt=False, status=0):
    t = hud(p, active, status)
    put(t, 1, 14, first); put(t, 1, 16, second)
    if prompt:
        put(t, 18, 16, '▼')
    return t


def baseline(roster=(154, 102, 35, 7), active=0, cursor=(9, 14), status=0):
    p = progress(roster)
    return {'frame': 100, 'now': 10., 'progress': p, 'location': deepcopy(LOCATION),
            'battle_state': deepcopy(WILD), 'enemy_snapshot': enemy(100, status),
            'text': command(p, active, cursor, status)}


class Session:
    def __init__(self, b=None, target=7, **limits):
        self.b = baseline() if b is None else b
        self.p = deepcopy(self.b['progress']); self.status = self.b['enemy_snapshot']['enemy']['status']
        self.c = SnorlaxSwitchController(self.b, target, **limits)
        self.frame, self.now = self.b['frame'], self.b['now']

    def call(self, t=None, **kw):
        self.frame += 16; self.now += .1
        frame = kw.pop('frame', self.frame)
        return self.c.context(text_at() if t is None else t, self.p,
            location=kw.pop('location', deepcopy(LOCATION)), battle_state=kw.pop('battle_state', deepcopy(WILD)),
            enemy_snapshot=kw.pop('enemy_snapshot', enemy(frame, self.status)), frame=frame,
            now=kw.pop('now', self.now), **kw)

    def to_party(self):
        cursor = next((x, y) for y, r in enumerate(self.b['text']['cells']) for x, c in enumerate(r) if c == '▶')
        while cursor != (15, 14):
            r = self.call(command(self.p, self.c.original_active, cursor, self.status))
            assert r['available_actions'] == ['up' if cursor[1] == 16 else 'right', 'wait']
            cursor = (cursor[0], 14) if cursor[1] == 16 else (15, 14)
        assert self.call(command(self.p, self.c.original_active, cursor, self.status))['available_actions'] == ['a', 'wait']

    def to_submenu(self, start=0):
        self.to_party(); cursor = start
        while cursor != self.c.target_index:
            delta = 1 if cursor < self.c.target_index else -1
            assert self.call(party_page(self.p, cursor))['available_actions'] == ['down' if delta == 1 else 'up', 'wait']
            cursor += delta
        assert self.call(party_page(self.p, cursor))['available_actions'] == ['a', 'wait']

    def switch(self):
        self.to_submenu()
        assert self.call(submenu(self.p, self.c.target_index))['available_actions'] == ['a', 'wait']

    def enemy_headbutt(self, hp=85):
        original, target = self.c.original_active, self.c.target_index
        old_name, name = self.p['party'][original]['species_name'], self.p['party'][target]['species_name']
        assert self.call(dialogue(self.p, original, old_name + ' enough!', 'Come back!', status=self.status))['available_actions'] == ['wait']
        assert self.call(dialogue(self.p, original, 'Go! ' + name + '!', status=self.status))['available_actions'] == ['wait']
        assert self.call(dialogue(self.p, target, 'Enemy SNORLAX', 'used HEADBUTT!', status=self.status))['available_actions'] == ['wait']
        self.p['party'][target]['hp'] = hp


@pytest.mark.parametrize('plant', [9, 154])
@pytest.mark.parametrize('permutation', list(itertools.permutations(range(4))))
def test_normal_switch_preserves_actual_order_every_roster_order(plant, permutation):
    roster = [plant, 102, 35, 7]; roster = [roster[i] for i in permutation]
    active = next(i for i, s in enumerate(roster) if s == plant)
    s = Session(baseline(roster, active)); before = deepcopy(s.p)
    s.switch(); s.enemy_headbutt()
    r = s.call(command(s.p, s.c.target_index, (9, 16)))
    assert r['snorlax_switch_complete'] and r['party_order_preserved']
    assert [m['species'] for m in s.p['party']] == roster
    assert s.p['inventory'] == before['inventory'] and s.c.target_species == 7
    for i, (a, b) in enumerate(zip(s.p['party'], before['party'])):
        assert {k:v for k,v in a.items() if k!='hp'} == {k:v for k,v in b.items() if k!='hp'}
        assert a['hp'] == (85 if i == s.c.target_index else b['hp'])
    assert r['requires_next_capture_safety_check'] and 'capture_complete' not in r


@pytest.mark.parametrize('cursor', [(9,14), (15,14), (9,16), (15,16)])
def test_only_navigates_pkmn_from_four_command_positions(cursor):
    s = Session(baseline(cursor=cursor)); s.to_party()
    assert s.c.stage == 'party' and not s.c.switch_requested


def test_semantic_pending_for_direction_and_each_a_survives_blank_and_old_ui():
    s=Session();old=command(s.p)
    assert s.call(old)['available_actions']==['right','wait']
    assert s.call()['available_actions']==['wait'];assert s.call(old)['available_actions']==['wait']
    select=command(s.p,cursor=(15,14));assert s.call(select)['available_actions']==['a','wait']
    assert s.call()['available_actions']==['wait'];assert s.call(select)['available_actions']==['wait']
    first=party_page(s.p,0);assert s.call(first)['available_actions']==['down','wait']
    assert s.call()['available_actions']==['wait'];assert s.call(first)['available_actions']==['wait']
    for i in (1,2):assert s.call(party_page(s.p,i))['available_actions']==['down','wait']
    last=party_page(s.p,3);assert s.call(last)['available_actions']==['a','wait']
    for t in [text_at(),last,party_page(s.p,3,inactive=True)]:assert s.call(t)['available_actions']==['wait']
    menu=submenu(s.p,3);assert s.call(menu)['available_actions']==['a','wait']
    for t in [text_at(),menu,submenu(s.p,3,unfilled=True),menu]:assert s.call(t)['available_actions']==['wait']


def test_critical_prompt_only_after_known_headbutt_and_never_resends_after_blank():
    s=Session();s.switch();s.enemy_headbutt()
    t=dialogue(s.p,3,'Critical hit!',prompt=True)
    assert s.call(t)['available_actions']==['a','wait']
    for page in [text_at(),t,t]:assert s.call(page)['available_actions']==['wait']
    assert s.call(command(s.p,3,(9,16)))['snorlax_switch_complete']


def test_sleep_turn_requires_source_sleep_and_target_then_single_confirm():
    s=Session(baseline(status=2));s.switch()
    assert s.call(dialogue(s.p,0,'Go! NIDOKING!',status=2))['available_actions']==['wait']
    s.status=1;t=dialogue(s.p,3,'Enemy SNORLAX','is fast asleep!',True,status=1)
    assert s.call(t)['available_actions']==['a','wait']
    assert s.call()['available_actions']==['wait'];assert s.call(t)['available_actions']==['wait']
    assert s.call(command(s.p,3,(9,16),1))['snorlax_switch_complete']


@pytest.mark.parametrize('bad', ['rest','unknown','fainted','attackmiss_contraction','wrong_prompt'])
def test_unsupported_enemy_dialogue_never_generic_confirms(bad):
    s=Session();s.switch();s.call(dialogue(s.p,0,'Go! NIDOKING!'))
    t={'rest':lambda:dialogue(s.p,3,'Enemy SNORLAX','used REST!'),
       'unknown':lambda:dialogue(s.p,3,'Delete all data?',prompt=True),
       'fainted':lambda:dialogue(s.p,3,'NIDOKING','fainted!',True),
       'attackmiss_contraction':lambda:dialogue(s.p,3,"Enemy SNORLAX's",'attack missed!',True),
       'wrong_prompt':lambda:dialogue(s.p,3,'Critical hit!',prompt=True)}[bad]()
    if bad=='attackmiss_contraction':t['cells'][14][14]="'s"
    r=s.call(t);assert r['phase']=='campaign_review' and r['available_actions']==['wait']


@pytest.mark.parametrize('stage', ['command','party','submenu','enemy'])
@pytest.mark.parametrize('pollution', ['Delete','YES','TOSS','UNKNOWN'])
def test_unknown_ui_is_never_a_or_direction(stage,pollution):
    s=Session()
    if stage=='command':t=command(s.p)
    elif stage=='party':s.to_party();t=party_page(s.p)
    elif stage=='submenu':s.to_submenu();t=submenu(s.p,3)
    else:s.switch();t=dialogue(s.p,3,'Enemy SNORLAX','used HEADBUTT!')
    put(t,0,9,pollution);r=s.call(t)
    assert r['available_actions']==['wait'] and r['phase']=='campaign_review' and not s.c.completion


@pytest.mark.parametrize('sub_y', [14,16])
def test_never_navigates_or_confirms_stats_cancel(sub_y):
    s=Session();s.to_submenu();r=s.call(submenu(s.p,3,sub_y=sub_y))
    assert r['phase']=='campaign_review' and not s.c.switch_requested


def test_partial_party_and_submenu_wait_before_any_confirm():
    s=Session();s.to_party();t=party_page(s.p);t['cells'][0][9]=' '
    assert s.call(t)['available_actions']==['wait']
    for i in range(3):assert s.call(party_page(s.p,i))['available_actions']==['down','wait']
    assert s.call(party_page(s.p,3))['available_actions']==['a','wait']
    t=submenu(s.p,3);t['cells'][12][18]=' '
    assert s.call(t)['available_actions']==['wait'] and not s.c.switch_requested
    assert s.call(submenu(s.p,3))['available_actions']==['a','wait']


@pytest.mark.parametrize('change', ['order','species','level','exp','move','pp','status','other_hp','hp_increase','faint','item','money'])
def test_party_identity_inventory_and_health_errors_before_animation_wait(change):
    s=Session();s.switch()
    if change=='order':s.p['party'].reverse()
    elif change=='species':s.p['party'][0].update(species=9,species_name='IVYSAUR')
    elif change=='level':s.p['party'][0]['level']+=1
    elif change=='exp':s.p['party'][0]['exp']+=1
    elif change=='move':s.p['party'][0]['moves'][0]=34
    elif change=='pp':s.p['party'][0]['pp'][0]-=1
    elif change=='status':s.p['party'][3]['status']=64
    elif change=='other_hp':s.p['party'][0]['hp']-=1
    elif change=='hp_increase':s.p['party'][3]['hp']+=1
    elif change=='faint':s.p['party'][3]['hp']=0
    elif change=='item':s.p['inventory'][1]['quantity']-=1
    else:s.p['money']-=1
    r=s.call();assert r['phase']=='campaign_review' and r['available_actions']==['wait']


@pytest.mark.parametrize('field,value', [('hp',139),('max_hp',141),('species',148),('status',2)])
def test_enemy_hp_identity_or_new_status_is_review_not_wait(field,value):
    s=Session();s.switch();e=enemy(s.frame+16);e['enemy'][field]=value
    r=s.call(enemy_snapshot=e);assert r['phase']=='campaign_review'


def test_new_command_alone_or_old_active_cannot_fake_switch_success():
    s=Session();s.switch()
    assert s.call(command(s.p,0))['available_actions']==['wait'] and not s.c.completion
    r=s.call(command(s.p,3));assert r['review_reason']=='snorlax_switch_sendout_or_enemy_turn_not_observed'


@pytest.mark.parametrize('field,value', [('profile',None),('read_valid',False),('alignment_verified',False),
                                      ('read_error','failed'),('window_visible',None),('observation_frame',1)])
def test_full_decoder_required_even_if_complete(field,value):
    s=Session();t=command(s.p);t[field]=value
    assert s.call(t)['review_reason']=='snorlax_switch_full_decoder_proof_required'


@pytest.mark.parametrize('field,value', [('read_valid',False),('profile','wrong'),('observation_frame',1),('enemy',None)])
def test_unknown_enemy_reader_result_is_never_synthesized(field,value):
    s=Session();e=enemy(116);e[field]=value
    assert s.call(command(s.p),enemy_snapshot=e)['phase']=='campaign_review'


def test_same_frame_pending_and_conflicts_are_not_resends():
    s=Session();t=command(s.p);s.call(t);frame=s.frame
    assert s.call(t,frame=frame)['available_actions']==['wait']
    assert s.call(command(s.p,cursor=(15,14)),frame=frame)['phase']=='campaign_review'


@pytest.mark.parametrize('bad', [True,-1,float('nan'),float('inf'),'10'])
def test_invalid_clock(bad):
    assert Session().call(now=bad)['phase']=='campaign_review'


def test_time_call_wait_budgets_locked_and_completion_is_detached_receipt():
    s=Session(max_calls=1);s.call();assert s.call()['phase']=='campaign_review'
    s=Session(max_waits=1);s.call();assert s.call()['review_reason']=='snorlax_switch_wait_budget_exhausted'
    s=Session();assert s.call(now=70.01)['review_reason']=='snorlax_switch_transaction_budget_exhausted'
    s=Session();s.switch();s.enemy_headbutt();r=s.call(command(s.p,3));r['target_hp_after_enemy_turn']=1
    done=s.c.context(None,None,location=None,battle_state=None,enemy_snapshot=None,frame=-1,now=-1)
    assert done['target_hp_after_enemy_turn']==85 and done['available_actions']==['wait']


@pytest.mark.parametrize('case', ['current','weak','fraction','bool','both_plants','faint','bad_species','bad_proof','bad_enemy'])
def test_constructor_rejects_unsafe_or_unknown_baseline(case):
    b=baseline();target=7
    if case=='current':target=154
    elif case=='weak':b['progress']['party'][3]['hp']=59
    elif case=='fraction':b['progress']['party'][3].update(hp=70,max_hp=105)
    elif case=='bool':target=True
    elif case=='both_plants':b['progress']['party'][1].update(species=9,species_name='IVYSAUR')
    elif case=='faint':b['progress']['party'][1]['hp']=0
    elif case=='bad_species':b['progress']['party'][1]['species']=[]
    elif case=='bad_proof':b['text'].pop('profile')
    else:b['enemy_snapshot']['read_valid']=False
    with pytest.raises(ValueError):SnorlaxSwitchController(b,target)


@pytest.mark.parametrize('limits', [{'max_calls':True},{'max_calls':241},{'max_waits':241},{'max_seconds':61},{'max_seconds':True}])
def test_cannot_expand_limits(limits):
    with pytest.raises(ValueError):Session(**limits)


def test_target_contract_mutation_does_not_switch_to_another_member():
    s=Session();s.c.target_species=35
    assert s.call(command(s.p))['review_reason']=='snorlax_switch_target_contract_changed'


def test_sleep_counter_cannot_increase_or_reappear_after_waking():
    s=Session(baseline(status=2));s.switch();s.call(dialogue(s.p,0,'Go! NIDOKING!',status=2))
    s.status=1;assert s.call(dialogue(s.p,3,'Enemy SNORLAX','is fast asleep!',True,status=1))['available_actions']==['a','wait']
    s.status=2;assert s.call()['review_reason']=='snorlax_switch_enemy_new_status'


@pytest.mark.parametrize('hp,maximum,valid',[(60,89,True),(60,90,False),(59,80,False)])
def test_target_hp_threshold_uses_strict_fraction(hp,maximum,valid):
    b=baseline();b['progress']['party'][3].update(hp=hp,max_hp=maximum)
    if valid:assert SnorlaxSwitchController(b,7).target_species==7
    else:
        with pytest.raises(ValueError):SnorlaxSwitchController(b,7)


def test_no_actorless_prompt_before_observed_enemy_action():
    s=Session();s.switch();s.call(dialogue(s.p,0,'Go! NIDOKING!'))
    r=s.call(dialogue(s.p,3,'But, it failed!',prompt=True))
    assert r['review_reason']=='snorlax_switch_enemy_prompt_without_known_action'


def test_known_partial_new_hud_waits_and_never_confirms_enemy_prompt():
    s=Session();s.switch();s.enemy_headbutt()
    t=dialogue(s.p,3,'Critical hit!',prompt=True);t['cells'][7][17]=' '
    assert s.call(t)['available_actions']==['wait'] and not s.c.prompt_pages
    assert s.call(dialogue(s.p,3,'Critical hit!',prompt=True))['available_actions']==['a','wait']


def test_visible_fainted_hp_reviews_even_when_party_ram_has_not_committed_damage():
    s=Session();s.switch();s.enemy_headbutt()
    t=dialogue(s.p,3,'Critical hit!',prompt=True);put(t,11,10,'  0/105')
    assert s.call(t)['review_reason']=='snorlax_switch_visible_fainted_hp'


def test_visible_damage_may_precede_party_commit_but_completion_needs_real_matching_command():
    s=Session();s.switch();s.enemy_headbutt(85)
    t=dialogue(s.p,3,'Critical hit!',prompt=True);put(t,11,10,' 70/105')
    assert s.call(t)['available_actions']==['a','wait']
    s.p['party'][3]['hp']=70
    r=s.call(command(s.p,3,(9,16)))
    assert r['snorlax_switch_complete'] and not r['target_safe_after_switch']
    assert r['requires_next_capture_safety_check']


def test_source_geometry_receipts_and_scope_are_public_not_live():
    assert FIXTURE['source_commit']==SOURCE_COMMIT and not FIXTURE['live_ui_calibrated']
    files={s['path']:s for s in FIXTURE['sources']}
    assert len(files)==12
    for s in files.values():
        assert SOURCE_COMMIT in s['url'] and len(s['git_blob_sha'])==40
        for e in s['excerpts']:assert 1<=e['start_line']<=e['end_line']<=s['line_count']
    box='\n'.join(e['text'] for e in files['data/text_boxes.asm']['excerpts'])
    assert 'SWITCH_STATS_CANCEL_MENU_TEMPLATE, 11, 11, 19, 17' in box
    assert FIXTURE['geometry']['submenu_labels']==[[13,12,'SWITCH'],[13,14,'STATS'],[13,16,'CANCEL']]
    full=files['engine/battle/used_move_text.asm'];text=full['excerpts'][0]['text'].encode()
    assert hashlib.sha1(b'blob '+str(len(text)).encode()+b'\0'+text).hexdigest()==full['git_blob_sha']


def test_no_runtime_io_buttons_ram_generic_battle_or_model_calls():
    import ast
    source=(Path(__file__).parents[1]/'src/laya_pokemon/snorlax_switch.py').read_text(encoding='utf-8')
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
            assert node.func.id not in {'open','eval','exec','__import__','battle_context'}
        if isinstance(node,ast.Attribute):assert node.attr not in {'tick','button','memory','load_state','save_state'}
    s=Session();before=deepcopy(s.b);t=command(s.p);p=deepcopy(s.p);s.call(t)
    assert s.b==before and s.p==p
