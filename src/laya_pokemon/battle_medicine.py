"""紅蓮戰鬥用藥的私人純候選；不讀 RAM、不發按鍵、不決定用藥安全。

固定 pret/pokered a536711：core 2225–2286 在戰鬥袋直接 UseItem；
item_effects 805–841/861–913/1075–1195/1226–1237；party_menu
14–105/174–225；text_2 1365–1391/1423–1427。藥品回執是 done，
不初始化 ▼；完整且實際效果/扣量一致的原生頁穩定至少54幀
（RedrawPartyMenu Delay3 + 外層Delay50 + 一個fresh frame）才一次 A。
所有版面為 source-only 候選，尚未實機校準；未知保守停檢。
"""
from copy import deepcopy
import math
import re

from laya_pokemon.observation import PROFILE as TEXT_PROFILE
from laya_pokemon.party_control import command
from laya_pokemon.mart_purchase import _inventory
from laya_pokemon.player_pc_deposit import _name, _KEY_ITEMS
from laya_pokemon.player_battle import PROFILE as PLAYER_PROFILE
from laya_pokemon.wild_opponent import decode_enemy_mon, _STATUS, _SPECIES

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE = 'red-en-active-lapras38-battle-medicine-source-v1-candidate'
ENEMY_PROFILE = 'red-en-sdk-2.8.1-trainer-enemy-source-v1-unvalidated'
_COMMON = dict(map_id=166, target_species=19, target_level=38, quantity=1,
               required_moves=[57, 34, 58, 109])
HYPER_POTION_INTENT = dict(_COMMON, kind='battle_hyper_potion_active_lapras38', item=18)
FULL_HEAL_INTENT = dict(_COMMON, kind='battle_full_heal_active_lapras38', item=52)
ROSTER = {19, 132, 7, 102, 154, 35}
_ACTIONS = {'a', 'b', 'up', 'down', 'left', 'right', 'start', 'wait'}
_COMMAND = {(9, 14), (15, 14), (9, 16), (15, 16)}
_S = '\ue000'  # private one-cell representation, never accepted from caller


def _int(v, lo=0, hi=2**63-1):
    return type(v) is int and lo <= v <= hi


def _clock(v):
    return type(v) in (int, float) and math.isfinite(v) and v >= 0


def _exact(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_exact(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_exact(x, y) for x, y in zip(a, b))
    return a == b


def _intent(v):
    return any(_exact(v, x) for x in (HYPER_POTION_INTENT, FULL_HEAL_INTENT))


def _party(p):
    # Fixed public enum in memory; no reference-JSON load or filtered party copy.
    if (not isinstance(p,dict) or p.get('profile') != 'gen1-wrapper-ram-progress-v1-unvalidated'
            or p.get('initialization_candidate') is not True or p.get('party_read_valid') is not True
            or not _int(p.get('party_count'),6,6) or not isinstance(p.get('party'),list)
            or len(p['party']) != 6):
        return None
    for m in p['party']:
        if (not isinstance(m,dict) or not _int(m.get('species'),1,190)
                or m.get('species') not in _SPECIES or m.get('species_name') != _SPECIES[m['species']]
                or not _int(m.get('level'),1,100) or not _int(m.get('exp'),0,0xFFFFFF)
                or not _int(m.get('hp'),1,999) or not _int(m.get('max_hp'),m['hp'],999)
                or type(m.get('status')) is not int or m['status'] not in _STATUS
                or not isinstance(m.get('moves'),list) or len(m['moves']) != 4
                or not isinstance(m.get('pp'),list) or len(m['pp']) != 4
                or any(not _int(v,0,165) for v in m['moves'])
                or any(not _int(v,0,255) for v in m['pp'])
                or m['moves'][0] == 0
                or any(move == 0 and (pp != 0 or any(m['moves'][j+1:]))
                       for j,(move,pp) in enumerate(zip(m['moves'],m['pp'])))):
            return None
    return p['party']


def _rows(t):
    if (not isinstance(t, dict) or t.get('profile') != TEXT_PROFILE
            or t.get('read_valid') is not True or t.get('alignment_verified') is not True
            or t.get('read_error') is not None or type(t.get('window_visible')) is not bool):
        return None
    c = t.get('cells')
    if not isinstance(c, (list, tuple)) or len(c) != 18:
        return None
    out = []
    for y, row in enumerate(c):
        if not isinstance(row, (list, tuple)) or len(row) != 20:
            return None
        r = []
        for x, v in enumerate(row):
            # SDK $BD is one physical cell. Only the two native USER anchors:
            # LAPRAS's and Enemy ARCANINE's; exact full-row templates below
            # still reject another name, shifted contraction, or wrong text.
            if v == "'s" and y == 14 and (
                    x == 7 and ''.join(row[1:7]).upper() == 'LAPRAS'
                    or x == 15 and ''.join(row[1:15]).upper() == 'ENEMY ARCANINE'):
                r.append(_S)
            elif not isinstance(v, str) or len(v) != 1 or v == _S:
                return None
            else:
                r.append(v.upper())
        out.append(''.join(r))
    # Existing decoder keeps at most twelve letter-bearing lines. Preserve physical
    # contraction when checking summaries; do not shift arrows by expanding it.
    expected = [(''.join(row).rstrip(), y) for y, row in enumerate(c)
                if re.search(r'[A-Za-z0-9]{2,}', ''.join(row).rstrip())][:12]
    if (t.get('lines') != [s for s, _ in expected]
            or t.get('line_rows') != [y for _, y in expected]):
        return None
    return tuple(out)


def _canvas():
    return [[' '] * 20 for _ in range(18)]


def _put(c, x, y, s):
    c[y][x:x+len(s)] = list(s)


def _freeze(c):
    return tuple(''.join(r).upper() for r in c)


def _status(status, level=None):
    if status & 7:
        return 'SLP'
    return {0: '' if level is None else str(level), 8: 'PSN', 16: 'BRN',
            32: 'FRZ', 64: 'PAR'}.get(status)


def _hud(player, enemy):
    c = _canvas()
    # core CenterMonName: start+2, subtract once per pair for the first 4 chars.
    for x, y, name in ((1, 0, enemy['species_name']), (10, 7, 'LAPRAS')):
        _put(c, x + max(0, 2 - (len(name)-1)//2), y, name)
    _put(c, 5, 1, _status(enemy['status'], enemy['level']))
    _put(c, 15, 8, _status(player['status'], player['level']))
    _put(c, 11, 10, f"{player['hp']:3}/{player['max_hp']:3}")
    return c


def _command_view(player, enemy, cursor):
    c = _hud(player, enemy)
    for x, y, s in ((10, 14, 'FIGHT'), (10, 16, 'ITEM'), (16, 16, 'RUN')):
        _put(c, x, y, s)
    c[cursor[1]][cursor[0]] = '▶'
    return _freeze(c)


def _dialog(player, enemy, top, bottom='', arrow=False):
    c = _hud(player, enemy)
    _put(c, 1, 14, top); _put(c, 1, 16, bottom)
    if arrow:
        c[16][18] = '▼'
    return _freeze(c)


def _party_view(party, cursor=None, marker='▶', receipt=None, arrow=False):
    c = _canvas()
    for i, m in enumerate(party):
        y = 2*i
        _put(c, 3, y, m['species_name'])
        _put(c, 13 if m['level'] == 100 else 14, y, str(m['level']))
        _put(c, 17, y, _status(m['status']))
        _put(c, 13, y+1, f"{m['hp']:3}/{m['max_hp']:3}")
    if cursor is not None:
        c[2*cursor+1][0] = marker
    top, bottom = ('USE ITEM ON WHICH', 'POKÉMON?') if receipt is None else receipt
    _put(c, 1, 14, top); _put(c, 1, 16, bottom)
    if arrow:
        c[16][18] = '▼'
    return _freeze(c)


def _bag_view(player, enemy, items, offset, cursor, arrow):
    c = _hud(player, enemy)
    # LIST_MENU_BOX (4,2)..(19,12), battle core clears lower text box.
    for y in range(2, 18):
        a = 4 if y < 12 else 0
        c[y][a:20] = [' '] * (20-a)
    printed = 0
    for n in range(4):
        j, y = offset+n, 4+2*n
        if j == len(items):
            _put(c, 6, y, 'CANCEL'); break
        if j > len(items):
            break
        item = items[j]
        _put(c, 6, y, _name(item['item']))
        if item['item'] not in _KEY_ITEMS:
            _put(c, 14, y+1, f"×{item['quantity']:2}")
        printed += 1
    c[4+2*cursor][5] = '▶'
    if arrow and printed == 4:
        c[11][18] = '▼'
    return _freeze(c)


def _clean_art(rows):
    # Same narrowly situated decoder '#' artifacts as existing native switch UI;
    # all other font cells (including unused corners) are fully checked.
    return tuple(''.join(' ' if ch == '#' and
                        (x < 8 and 5 <= y < 12 or 12 <= x < 19 and y < 7)
                        else ch for x, ch in enumerate(row))
                 for y, row in enumerate(rows))


def _partial(rows, expected):
    return all(ch in (' ', expected[y][x])
               for y, row in enumerate(rows) for x, ch in enumerate(row))


def _player(s, frame, loc):
    if (not isinstance(s, dict) or s.get('profile') != PLAYER_PROFILE
            or s.get('source_commit') != SOURCE_COMMIT or s.get('read_valid') is not True
            or not _int(s.get('observation_frame')) or s['observation_frame'] != frame
            or s.get('battle_kind') != 'trainer' or not _exact(s.get('location'), loc)
            or not _int(s.get('active_party_index'), 0, 5)):
        return None
    p = s.get('player')
    if (not isinstance(p, dict) or p.get('species_name') != 'LAPRAS'
            or not _int(p.get('species'), 19, 19) or not _int(p.get('level'), 38, 38)
            or not _int(p.get('hp'), 1, 999) or not _int(p.get('max_hp'), p['hp'], 999)
            or type(p.get('status')) is not int or p['status'] not in _STATUS
            or not _exact(p.get('moves'), [57, 34, 58, 109])
            or not isinstance(p.get('pp'), list) or len(p['pp']) != 4
            or any(not _int(v, 0, 255) for v in p['pp'])
            or not _int(p.get('internal_id'),19,19)
            or not isinstance(p.get('dvs'),list) or len(p['dvs']) != 2
            or any(not _int(v,0,255) for v in p['dvs'])
            or not isinstance(p.get('types'),list) or len(p['types']) != 2
            or any(not _int(v,0,26) for v in p['types'])
            or any(not _int(p.get(k), 1, 999) for k in ('attack','defense','speed','special'))):
        return None
    return p


def _enemy(s, frame, loc):
    if (not isinstance(s, dict) or s.get('profile') != ENEMY_PROFILE
            or s.get('source_commit') != SOURCE_COMMIT or s.get('read_valid') is not True
            or any(not _int(s.get(k)) or s[k] != frame for k in
                   ('observation_frame', 'frame_before', 'frame_after'))
            or type(s.get('raw')) is not int or s['raw'] != 2
            or type(s.get('battle_type')) is not int or s['battle_type'] != 0
            or s.get('battle_kind') != 'trainer'
            or not _int(s.get('current_opponent'),0,255)
            or not _exact(s.get('location'), loc)):
        return None
    d = decode_enemy_mon(s.get('raw_record'))
    return d['enemy'] if d['read_valid'] and _exact(d['enemy'], s.get('enemy')) else None


class BattleMedicineController:
    """Only explicit parent-owned intent; caller serializes real reader snapshots.

    context(text, progress, *, owner, location, battle_state, player_snapshot,
            enemy_proof, frame, previous, now). Completion is ONLY
    battle_medicine_complete=True on two fresh full post-enemy command frames.
    It is not a damage/survival approval. Reuse this instance after a review.
    """
    def __init__(self, intent, *, owner, max_calls=240, max_seconds=60, max_waits=30):
        if (not _intent(intent) or not isinstance(owner, str) or not 1 <= len(owner) <= 128
                or not _int(max_calls, 1, 240) or not _int(max_waits, 1, 30)
                or not _clock(max_seconds) or not 0 < max_seconds <= 60):
            raise ValueError('Only fixed parent-owned Lapras38 medicine intent and bounded budget')
        self.intent, self.contract, self.owner = deepcopy(intent), deepcopy(intent), owner
        self.max_calls, self.max_seconds, self.max_waits = max_calls, max_seconds, max_waits
        self.stage, self.error, self.complete = 'command', None, False
        self.calls = self.waits = 0
        self.started = self.last_now = self.last_frame = self.last_packet = None
        self.baseline = self.healed = self.after_items = self.active = None
        self.pending = self.sent_rows = self.expected_cursor = self.expected_bag = None
        self.enemy_action = None
        self.enemy_hp = self.recoil_hp = None
        self.enemy_missed = False
        self.take_down_pre_hp = self.take_down_pre_status = None
        self.prompt_pages = set()
        self.last_prompt = None
        self.final_frame = self.final_packet = None
        self.receipt_full_frame = self.receipt_full_rows = None

    def _hint(self, action, tactic, **extra):
        info = dict(battle_medicine_profile=PROFILE, source_commit=SOURCE_COMMIT,
                    battle_medicine_stage=self.stage, battle_medicine_tactic=tactic,
                    candidate_only=True, **extra)
        if action == 'wait':
            # Main default 32 settle frames: sample native done pages every40, not128.
            return dict(phase='battle_medicine_wait', objective='Wait.', available_actions=['wait'], **info)
        if action in ('left','right'):
            return dict(phase='battle_menu',objective='Move '+action.upper()+'.',
                        available_actions=[action,'wait'],controller_menu_verified=True,**info)
        return command(action, 'battle_menu' if self.stage == 'command' else 'item_menu', info)

    def _fail(self, reason):
        if self.error is None:
            self.error = reason
        return dict(self._hint('wait', 'review'), phase='strategy_review',
                    review_reason='battle_medicine_' + self.error)

    def _wait(self, reason):
        self.waits += 1
        if self.waits > self.max_waits:
            return self._fail('wait_budget_exhausted')
        return self._hint('wait', reason)

    def _offer(self, action, rows, stage, tactic):
        self.pending = dict(action=action, frame=self.last_frame)
        self.sent_rows, self.stage = rows, stage
        return self._hint(action, tactic)

    def _unchanged_player(self, player):
        # Full Heal legally recalculates battle stats; persistent identity/PP do not change.
        return all(_exact(player.get(k), self.baseline['player'].get(k)) for k in
                   ('species','internal_id','species_name','level','max_hp','moves','pp','dvs','types'))

    def _party_allowed(self, party):
        if len(party) != 6:
            return False
        for i, m in enumerate(party):
            b = self.baseline['party'][i]
            if i != self.active:
                if not _exact(m, b):
                    return False
            elif not _exact({k:v for k,v in m.items() if k not in ('hp','status')},
                            {k:v for k,v in b.items() if k not in ('hp','status')}):
                return False
        return True

    def _known_hyper_hp_animation(self, text, progress, *, player_snapshot,
                                  enemy_proof, frame, owner):
        """Exact native dim-cursor party page; displayed HP alone may lag RAM.

        No counters, proof packets, timers or action state are modified here.
        Both actual RAM representations must already equal the healed result,
        and the entire inventory must already show exactly one consumption.
        """
        if (owner != self.owner or not _exact(self.intent,self.contract)
                or not _exact(self.contract,HYPER_POTION_INTENT)
                or self.stage != 'receipt' or self.complete
                or self.enemy_action is not None or not _int(frame)
                or not _int(self.last_frame) or frame < self.last_frame
                or not _int(self.active,0,5) or not isinstance(self.baseline,dict)
                or not isinstance(self.healed,list) or len(self.healed) != 6
                or not isinstance(progress,dict)):
            return False
        for packet in (text,progress):
            if (not isinstance(packet,dict) or 'observation_frame' in packet
                    and (not _int(packet['observation_frame']) or packet['observation_frame'] != frame)):
                return False
        b = self.baseline
        loc = b['location']
        party,items = _party(progress),_inventory(progress.get('inventory'))
        player,enemy = _player(player_snapshot,frame,loc),_enemy(enemy_proof,frame,loc)
        if (party is None or player is None or enemy is None or items is None
                or player_snapshot['active_party_index'] != self.active
                or not _exact(party,self.healed) or not _exact(items,self.after_items)
                or not _int(progress.get('money'),0,999999) or progress['money'] != b['money']
                or not _exact(enemy,b['enemy'])):
            return False
        expected_player = deepcopy(b['player'])
        expected_player['hp'] = self.healed[self.active]['hp']
        if not _exact(player,expected_player):
            return False
        # A duplicate physical frame must retain the original four supplied
        # packets; repair cannot bypass the controller's changed-frame guard.
        if frame == self.last_frame and (not isinstance(self.last_packet,tuple)
                or len(self.last_packet) != 6 or not _exact(
                    (text,progress,player_snapshot,enemy_proof),
                    (self.last_packet[0],self.last_packet[1],self.last_packet[4],self.last_packet[5]))):
            return False
        rows = _rows(text)  # no art/partial cleanup: every other cell is exact
        if rows is None:
            return False
        hp_row = 2*self.active+1
        token = rows[hp_row][13:16]
        if not re.fullmatch(r' {0,2}[0-9]{1,3}',token):
            return False
        visible_hp = int(token)
        before,after = b['party'][self.active]['hp'],self.healed[self.active]['hp']
        if token != f'{visible_hp:3}' or not before <= visible_hp <= after or before >= after:
            return False
        expected = list(_party_view(self.healed,self.active,'▷'))
        expected[hp_row] = expected[hp_row][:13] + f'{visible_hp:3}' + expected[hp_row][16:]
        if rows[:12]!=tuple(expected[:12]):
            return False
        # RedrawPartyMenu may retain the dim cursor while the item message
        # replaces its old prompt. This is still autonomous UI, never an A.
        delta=after-before
        receipt=_party_view(self.healed,receipt=('LAPRAS',f'RECOVERED BY {delta}!'))
        return (_partial(rows[12:],tuple(expected[12:]))
                or _partial(rows[12:],receipt[12:]))

    def reviewed_hp_animation_repair(self, text, progress, *, player_snapshot,
                                     enemy_proof, frame, owner):
        """Explicit parent-reviewed repair of this single known false error.

        Caller must gate invocation with its reviewed plan marker. This method
        is never called automatically. It clears only the named error; all
        baseline/pending/proof/counter/clock state remains byte-for-byte equal.
        A later context call still enforces the original clock/call budgets.
        """
        if self.error != 'medicine_receipt_unknown' or self.stage != 'receipt':
            return False
        if not self._known_hyper_hp_animation(text,progress,
                player_snapshot=player_snapshot,enemy_proof=enemy_proof,
                frame=frame,owner=owner):
            return False
        self.error = None
        return True

    def _fire_blast_animation_bound(self, text, progress, *, player_snapshot,
                                    enemy_proof, frame, owner):
        """Read-only conservation proof for an already observed FIRE BLAST."""
        if (owner != self.owner or not _exact(self.intent,self.contract) or not _intent(self.contract)
                or self.stage != 'retaliation' or self.enemy_action != 'FIRE BLAST' or self.complete
                or self.pending is not None or self.prompt_pages
                or not _int(frame) or not _int(self.last_frame) or frame < self.last_frame
                or not _int(self.active,0,5) or not isinstance(self.baseline,dict)
                or not isinstance(self.healed,list) or len(self.healed)!=6
                or not isinstance(progress,dict)):
            return None
        for packet in (text,progress):
            if (not isinstance(packet,dict) or 'observation_frame' in packet
                    and (not _int(packet['observation_frame']) or packet['observation_frame']!=frame)):
                return None
        b=self.baseline;h=self.healed[self.active];loc=b['location']
        party,items=_party(progress),_inventory(progress.get('inventory'))
        player,enemy=_player(player_snapshot,frame,loc),_enemy(enemy_proof,frame,loc)
        if (party is None or player is None or enemy is None or items is None
                or player_snapshot['active_party_index']!=self.active
                or not _exact(items,self.after_items) or not _int(progress.get('money'),0,999999)
                or progress['money']!=b['money'] or not self._party_allowed(party)
                or not self._unchanged_player(player) or not _exact(enemy,b['enemy'])
                or enemy['species_name']!='ARCANINE' or 126 not in enemy['moves']
                or not 1 <= player['hp'] <= h['hp'] or player['status']!=h['status']
                or party[self.active]['hp'] not in (h['hp'],player['hp'])):
            return None
        expected_party=deepcopy(self.healed)
        expected_party[self.active]['hp']=party[self.active]['hp']
        if not _exact(party,expected_party):
            return None
        if frame==self.last_frame and (not isinstance(self.last_packet,tuple)
                or len(self.last_packet)!=6 or not _exact(
                    (text,progress,player_snapshot,enemy_proof),
                    (self.last_packet[0],self.last_packet[1],self.last_packet[4],self.last_packet[5]))):
            return None
        return player,party,enemy

    def _known_fire_blast_alignment(self, text, progress, **proof):
        bound=self._fire_blast_animation_bound(text,progress,**proof)
        if bound is None:
            return False
        player,party,enemy=bound
        if (not _exact(party,self.healed) or player['hp']!=self.healed[self.active]['hp']
                or text.get('profile')!=TEXT_PROFILE or text.get('read_valid') is not False
                or text.get('alignment_verified') is not False or text.get('window_visible') is not True
                or text.get('read_error')!='visible_tile_alignment_incomplete'):
            return False
        cells=text.get('cells')
        if (not isinstance(cells,(list,tuple)) or len(cells)!=18
                or any(not isinstance(row,(list,tuple)) or len(row)!=20
                       or any(not isinstance(ch,str) or len(ch)!=1 or ch==_S for ch in row)
                       for row in cells)):
            return False
        expected=[(''.join(row).rstrip(),y) for y,row in enumerate(cells)
                  if re.search(r'[A-Za-z0-9]{2,}',''.join(row).rstrip())][:12]
        if text.get('lines')!=[s for s,y in expected] or text.get('line_rows')!=[y for s,y in expected]:
            return False
        rows=tuple(''.join(row).upper() for row in cells)
        return _partial(rows,_dialog(player,enemy,'ENEMY ARCANINE','USED FIRE BLAST!'))

    def _known_fire_blast_hp_bar(self, text, progress, **proof):
        bound=self._fire_blast_animation_bound(text,progress,**proof)
        if bound is None:
            return False
        player,party,enemy=bound;rows=_rows(text)
        if rows is None:
            return False
        token=rows[10][11:14]
        if not re.fullmatch(r' {0,2}[0-9]{1,3}',token):
            return False
        visible_hp=int(token)
        if (token!=f'{visible_hp:3}' or visible_hp==player['hp']
                or not player['hp'] <= visible_hp <= self.healed[self.active]['hp']):
            return False
        # Render-only copy: the true BattleMon/party packets are never altered.
        rendered={**player,'hp':visible_hp}
        return rows==_dialog(rendered,enemy,'ENEMY ARCANINE','USED FIRE BLAST!')

    def reviewed_retaliation_animation_repair(self, text, progress, *, player_snapshot,
                                               enemy_proof, frame, owner):
        """Explicit reviewed marker only; preserve every field except this error."""
        if self.error!='native_decoder_not_verified' or self.stage!='retaliation':
            return False
        if not self._known_fire_blast_alignment(text,progress,player_snapshot=player_snapshot,
                enemy_proof=enemy_proof,frame=frame,owner=owner):
            return False
        self.error=None
        return True

    def context(self, text, progress, *, owner, location, battle_state,
                player_snapshot, enemy_proof, frame, previous, now):
        if self.error:
            return self._fail(self.error)
        if (owner != self.owner or not _exact(self.intent, self.contract)
                or not _int(frame) or not _clock(now)
                or not isinstance(previous, (list, tuple))
                or any(type(a) is not str or a not in _ACTIONS for a in previous)):
            return self._fail('owner_intent_frame_clock_or_previous_invalid')
        if self.last_now is not None and (now < self.last_now or frame < self.last_frame):
            return self._fail('clock_or_frame_regressed')
        if self.started is None:
            self.started = now
        self.calls += 1
        # Every invocation consumes budget, even duplicates of one video frame.
        # Advance last_now before the duplicate return to detect time regression.
        if self.calls > self.max_calls or now - self.started > self.max_seconds:
            return self._fail('call_or_time_budget_exhausted')
        self.last_now = now
        packet = deepcopy((text, progress, location, battle_state, player_snapshot, enemy_proof))
        if self.last_frame == frame:
            if not _exact(packet, self.last_packet):
                return self._fail('same_frame_observation_changed')
            return self._wait('same_frame_no_resend')
        self.last_frame, self.last_packet = frame, packet
        loc = {k: location.get(k) for k in ('map_id', 'x', 'y')} if isinstance(location, dict) else None
        if (loc is None or not _int(loc['map_id'],166,166) or not _int(loc['x'],0,19)
                or not _int(loc['y'],0,17) or not isinstance(battle_state, dict)
                or type(battle_state.get('raw')) is not int or battle_state['raw'] != 2
                or battle_state.get('active') is not True or battle_state.get('kind') != 'trainer'
                or not _int(battle_state.get('observation_frame'))
                or battle_state['observation_frame'] != frame):
            return self._fail('location_or_verified_trainer_required')
        rows = _rows(text)
        if rows is None:
            if self._known_fire_blast_alignment(text,progress,player_snapshot=player_snapshot,
                    enemy_proof=enemy_proof,frame=frame,owner=owner):
                self.final_frame=self.final_packet=None
                return self._wait('known_fire_blast_alignment_animation')
            return self._fail('native_decoder_not_verified')
        rows = _clean_art(rows)
        for p in (text, progress):
            if 'observation_frame' in p and (not _int(p['observation_frame']) or p['observation_frame'] != frame):
                return self._fail('packet_frame_mismatch')
        party, items = _party(progress), _inventory(progress.get('inventory'))
        player, enemy = _player(player_snapshot,frame,loc), _enemy(enemy_proof,frame,loc)
        if (party is None or len(party) != 6 or {m['species'] for m in party} != ROSTER
                or any(m['hp'] <= 0 or m['status'] not in _STATUS for m in party)
                or items is None or any(_name(i['item']) in (None,'?????') for i in items)
                or not _int(progress.get('money'),0,999999) or player is None or enemy is None
                or enemy['hp'] <= 0
                or type(battle_state.get('opponent_species')) is not str
                or battle_state['opponent_species'] != enemy['species_name']):
            return self._fail('party_inventory_player_or_enemy_unverified')
        active = player_snapshot['active_party_index']
        if party[active]['species'] != 19 or party[active]['level'] != 38:
            return self._fail('active_lapras_required')
        if self.baseline is None:
            if not any(rows == _command_view(player,enemy,c) for c in _COMMAND):
                return self._fail('initial_full_command_required')
            if (any(party[active][k] != player[k] for k in ('hp','max_hp','status','moves','pp'))
                    or any(m['status'] != 0 for i,m in enumerate(party) if i != active)):
                return self._fail('initial_party_and_battle_must_match')
            item = next((i for i in items if i['item'] == self.contract['item']), None)
            if item is None:
                return self._fail('medicine_not_owned')
            if (self.contract['item'] == 18 and player['hp'] == player['max_hp']
                    or self.contract['item'] == 52 and player['status'] == 0):
                return self._fail('medicine_would_have_no_effect')
            self.active = active
            self.baseline = dict(party=deepcopy(party), inventory=deepcopy(items),
                                 player=deepcopy(player), enemy=deepcopy(enemy),
                                 money=progress['money'], location=deepcopy(loc))
            self.enemy_hp = enemy['hp']
            self.healed = deepcopy(party)
            if self.contract['item'] == 18:
                self.healed[active]['hp'] = min(player['max_hp'], player['hp'] + 200)
            else:
                self.healed[active]['status'] = 0
            self.after_items = deepcopy(items)
            for j, i in enumerate(self.after_items):
                if i['item'] == self.contract['item']:
                    i['quantity'] -= 1
                    if i['quantity'] == 0:
                        self.after_items.pop(j)
                    break
        b = self.baseline
        # TAKE DOWN is the sole newly supported recoil action, and only the
        # fixed Arcanine move. Its source effect subtracts HP from the USER
        # before the exact recoil prompt; identity/stats/status still bind.
        take_down = (self.stage in ('retaliation', 'complete')
                     and enemy['species_name'] == 'ARCANINE' and 36 in enemy['moves']
                     and (self.enemy_action == 'TAKE DOWN' or rows ==
                          _dialog(player,enemy,'ENEMY ARCANINE','USED TAKE DOWN!')))
        enemy_vary = ('pp','pp_remaining','hp') if take_down else ('pp','pp_remaining')
        if (active != self.active or not _exact(loc,b['location']) or progress['money'] != b['money']
                or not self._party_allowed(party) or not self._unchanged_player(player)
                or not _exact({k:v for k,v in enemy.items() if k not in enemy_vary},
                              {k:v for k,v in b['enemy'].items() if k not in enemy_vary})
                or not 1 <= enemy['hp'] <= self.enemy_hp
                or self.recoil_hp is not None and enemy['hp'] != self.recoil_hp
                or self.enemy_missed and enemy['hp'] != b['enemy']['hp']):
            return self._fail('bound_state_changed')
        self.enemy_hp = enemy['hp']
        if self.stage in ('command','bag','party'):
            if not _exact(party,b['party']) or not _exact(items,b['inventory']) or not _exact(player,b['player']):
                return self._fail('premature_effect_or_unrelated_change')
        elif self.stage == 'receipt':
            # source applies effect first, removes item next, redraws only afterwards.
            if (not (_exact(party,b['party']) or _exact(party,self.healed))
                    or not (_exact(items,b['inventory']) or _exact(items,self.after_items))
                    or _exact(items,self.after_items) and not _exact(party,self.healed)):
                return self._fail('medicine_effect_order_or_delta_invalid')
        else:
            h = self.healed[active]
            if (not _exact(items,self.after_items) or not 1 <= player['hp'] <= h['hp']
                    or not 1 <= party[active]['hp'] <= h['hp']
                    or player['status'] not in (h['status'],16)
                    or party[active]['status'] not in (h['status'],16)):
                return self._fail('post_item_or_retaliation_invalid')
            if (self.enemy_action == 'TAKE DOWN' and self.take_down_pre_status is not None
                    and player['status'] != self.take_down_pre_status):
                return self._fail('take_down_unrelated_status_change')
        if self.pending is not None:
            if not previous or previous[-1] != self.pending['action']:
                if previous and previous[-1] != 'wait':
                    return self._fail('actual_previous_does_not_match_offer')
                return self._wait('await_actual_previous')
            self.pending = None
        # A prior old page, including prompt blink/blank, cannot repeat an offer.
        if self.sent_rows is not None and rows == self.sent_rows:
            return self._wait('old_page_no_resend')
        if self.complete:
            if not any(rows == _command_view(player,enemy,c) for c in _COMMAND):
                return self._fail('completed_command_changed')
            return self._hint('wait','complete',battle_medicine_complete=True,
                              enemy_turn_resolved=True, survival_approved=False)
        if self.stage == 'command':
            found = next((c for c in _COMMAND if rows == _command_view(player,enemy,c)),None)
            if found is None:
                return self._fail('full_command_cursor_unverified')
            if self.expected_cursor is not None and found != self.expected_cursor:
                return self._fail('command_cursor_did_not_follow_offer')
            if found != (9,16):
                action = 'left' if found[0] == 15 else 'down'
                self.expected_cursor = (9,found[1]) if action == 'left' else (9,16)
                return self._offer(action,rows,'command','navigate_item')
            return self._offer('a',rows,'bag','open_battle_item_direct')
        if self.stage == 'bag':
            candidates = [(off,cur) for off in range(max(1,len(items))) for cur in range(3)
                          if off+cur <= len(items) and any(rows == _bag_view(player,enemy,items,off,cur,arrow)
                                                        for arrow in (False,True))]
            if len(candidates) != 1:
                templates = [_bag_view(player,enemy,items,off,cur,arrow)
                             for off in range(max(1,len(items))) for cur in range(3)
                             if off+cur <= len(items) for arrow in (False,True)]
                return self._wait('known_bag_partial') if any(_partial(rows,t) for t in templates) else self._fail('bag_viewport_unverified')
            off,cur = candidates[0]
            if self.expected_bag is not None and (off,cur) != self.expected_bag:
                return self._fail('bag_cursor_did_not_follow_offer')
            target = next(j for j,i in enumerate(items) if i['item'] == self.contract['item'])
            if off+cur == target:
                self.expected_bag = None
                return self._offer('a',rows,'party','use_selected_medicine_no_toss')
            action = 'down' if off+cur < target else 'up'
            self.expected_bag = ((off,cur+1) if cur < 2 else (off+1,2)) if action == 'down' else ((off,cur-1) if cur > 0 else (max(0,off-1),0))
            return self._offer(action,rows,'bag','navigate_actual_bag')
        if self.stage == 'party':
            found = next((j for j in range(6) if rows == _party_view(party,j)),None)
            if found is None:
                return self._wait('known_party_partial') if any(_partial(rows,_party_view(party,j)) for j in range(6)) else self._fail('use_item_party_unverified')
            if self.expected_cursor is not None and isinstance(self.expected_cursor,int) and found != self.expected_cursor:
                return self._fail('party_cursor_did_not_follow_offer')
            if found != self.active:
                action = 'down' if found < self.active else 'up'
                self.expected_cursor = found + (1 if action == 'down' else -1)
                return self._offer(action,rows,'party','select_active_lapras_only')
            self.expected_cursor = None
            return self._offer('a',rows,'receipt','apply_one_medicine')
        if self.stage == 'receipt':
            delta = self.healed[active]['hp'] - b['party'][active]['hp']
            # home/text.asm467–486 sets LEFT_ALIGN for text_decimal; width3 is
            # maximum digits, not three padded physical cells.
            receipt = ('LAPRAS',f'RECOVERED BY {delta}!') if self.contract['item'] == 18 else ('LAPRAS'+_S,'HEALTH RETURNED!')
            templates = [_party_view(self.healed,receipt=receipt,arrow=False)]
            if _rows(text) == templates[0]:
                if (not _exact(items,self.after_items) or not _exact(party,self.healed)
                        or any(player[k] != self.healed[active][k] for k in ('hp','status'))):
                    return self._fail('receipt_without_observed_effect_and_consumption')
                first = getattr(self,'receipt_full_frame',None)
                if first is None or getattr(self,'receipt_full_rows',None) != rows:
                    self.receipt_full_frame,self.receipt_full_rows = frame,rows
                    return self._wait('known_medicine_done_receipt_settling')
                if not _int(first) or first > frame:
                    return self._fail('receipt_settle_frame_invalid')
                if frame-first < 54:
                    return self._wait('known_medicine_done_receipt_settling')
                self.expected_cursor = None
                return self._offer('a',rows,'retaliation','ack_stable_medicine_done_receipt_once')
            self.receipt_full_frame = self.receipt_full_rows = None
            if self._known_hyper_hp_animation(text,progress,
                    player_snapshot=player_snapshot,enemy_proof=enemy_proof,
                    frame=frame,owner=owner):
                return self._wait('known_hyper_potion_hp_animation')
            if any(_partial(rows,t) for t in templates) or _partial(rows,_party_view(b['party'],active,'▷')):
                return self._wait('known_effect_or_receipt_before_prompt')
            return self._fail('medicine_receipt_unknown')
        if self._known_fire_blast_hp_bar(text,progress,player_snapshot=player_snapshot,
                enemy_proof=enemy_proof,frame=frame,owner=owner):
            self.final_frame=self.final_packet=None
            return self._wait('known_fire_blast_damage_hp_bar')
        # Source used-move page is autonomous done; never A to attack.
        used = {name:_dialog(player,enemy,'ENEMY '+enemy['species_name'],'USED '+name+'!')
                for name in ('EMBER','FIRE BLAST','ROAR')}
        if enemy['species_name'] == 'ARCANINE' and 36 in enemy['moves']:
            used['TAKE DOWN'] = _dialog(player,enemy,'ENEMY ARCANINE','USED TAKE DOWN!')
        for name, view in used.items():
            if rows == view:
                if self.enemy_action not in (None,name):
                    return self._fail('multiple_enemy_actions')
                if name == 'TAKE DOWN' and self.enemy_action is None:
                    self.take_down_pre_hp = player['hp']
                    self.take_down_pre_status = player['status']
                self.enemy_action = name
                self.final_frame = self.final_packet = None
                return self._wait('observed_enemy_'+name.lower().replace(' ','_'))
        prompts = {'critical':('CRITICAL HIT!',''), 'burned':('LAPRAS','WAS BURNED!'),
                   'burn_tick':('LAPRAS'+_S,'HURT BY THE BURN!'),
                   'miss':('ENEMY '+enemy['species_name']+_S,'ATTACK MISSED!'),
                   'recoil':('ENEMY ARCANINE'+_S,'HIT WITH RECOIL!'),
                   'roar_failed':('BUT, IT FAILED!','')}
        def prompt_allowed(key):
            if key == 'recoil':
                return self.enemy_action == 'TAKE DOWN'
            if key == 'roar_failed':
                return self.enemy_action == 'ROAR'
            if key == 'burned':
                return self.enemy_action in ('EMBER','FIRE BLAST')
            return not (key in ('burn_tick','critical') and self.enemy_action == 'ROAR')
        if self.enemy_action is not None:
            for key,(top,bot) in prompts.items():
                if not prompt_allowed(key):
                    continue
                view = _dialog(player,enemy,top,bot,True)
                if rows == view:
                    if key in self.prompt_pages:
                        return self._wait('old_enemy_prompt_no_resend')
                    if key == 'miss':
                        if (self.recoil_hp is not None or enemy['hp'] != b['enemy']['hp']
                                or self.enemy_action == 'TAKE DOWN'
                                and player['hp'] != self.take_down_pre_hp):
                            return self._fail('miss_with_enemy_hp_loss')
                        self.enemy_missed = True
                    elif key == 'recoil':
                        damage = (self.take_down_pre_hp - player['hp']
                                  if self.take_down_pre_hp is not None else 0)
                        if (self.enemy_missed or enemy['hp'] >= b['enemy']['hp']
                                or damage <= 0 or b['enemy']['hp'] - enemy['hp'] != max(1,damage // 4)):
                            return self._fail('recoil_without_observed_non_ko_hit')
                        self.recoil_hp = enemy['hp']
                    self.prompt_pages.add(key)
                    return self._offer('a',rows,'retaliation','ack_known_'+key+'_prompt')
        command_cursor = next((c for c in _COMMAND if rows == _command_view(player,enemy,c)),None)
        if command_cursor is not None:
            if self.enemy_action is None:
                return self._fail('new_command_without_observed_enemy_turn')
            if self.enemy_action == 'TAKE DOWN' and not (self.enemy_missed or self.recoil_hp is not None):
                return self._fail('take_down_requires_miss_or_non_ko_recoil_receipt')
            if any(player[k] != party[active][k] for k in ('hp','status','max_hp','moves','pp')):
                return self._fail('new_command_party_not_synchronized')
            final = deepcopy((player,party,items,rows,enemy))
            if self.final_frame is None or not _exact(final,self.final_packet):
                self.final_frame,self.final_packet = frame,final
                return self._wait('first_post_enemy_full_command')
            if frame <= self.final_frame:
                return self._wait('await_new_command_frame')
            self.complete,self.stage = True,'complete'
            return self._hint('wait','complete',battle_medicine_complete=True,
                              enemy_turn_resolved=True,survival_approved=False)
        possible = list(used.values()) + [_command_view(player,enemy,c) for c in _COMMAND]
        if self.enemy_action is not None:
            possible += [_dialog(player,enemy,a,b,arrow) for key,(a,b) in prompts.items()
                         if prompt_allowed(key)
                         for arrow in (False,True)]
        if any(_partial(rows,t) for t in possible):
            self.final_frame = self.final_packet = None
            return self._wait('known_native_retaliation_partial')
        return self._fail('retaliation_unknown_or_unsupported')
