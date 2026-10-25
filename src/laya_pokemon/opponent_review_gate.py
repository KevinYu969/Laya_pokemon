"""夏伯專用邊界：初次入場僅有界等待／單次確認，風速狗出現即停。"""
import math
import re
import time

PROFILE = 'blaine-arcanine-before-action-v1'
VISIBLE_PROFILE = 'gen1-visible-tile-text-candidates-v1-unvalidated'
SIGNAL_PROFILE = 'blaine-intro-raw2-type0-same-frame-v1'
MAX_WAITS = 30
MAX_SECONDS = 60
# Preserve the owner and budget when campaign_route reloads this module.
_INTRO = globals().get('_INTRO')


def read_intro_signal(pyboy):
    """Read only; double-read D057/D05A and frame without ticking or input."""
    result = dict(profile=SIGNAL_PROFILE, read_valid=False, owner_id=id(pyboy),
                  frame_before=None, frame_after=None, raw=None, battle_type=None)
    try:
        before = pyboy.frame_count
        first = (pyboy.memory[0xD057], pyboy.memory[0xD05A])
        second = (pyboy.memory[0xD057], pyboy.memory[0xD05A])
        after = pyboy.frame_count
    except Exception:
        return result
    result.update(frame_before=before, frame_after=after,
                  raw=first[0], battle_type=first[1])
    result['read_valid'] = (type(before) is int and before >= 0 and before == after
                            and type(after) is int and first == second
                            and all(type(v) is int and 0 <= v <= 255 for v in first + second))
    return result


def _review(reason):
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason=reason, opponent_review_profile=PROFILE)


def _rows(text):
    """Require the real decoder packet, including exact cells and derived lines."""
    if (type(text) is not dict or text.get('profile') != VISIBLE_PROFILE
            or type(text.get('window_visible')) is not bool):
        return None
    cells = text.get('cells')
    if (type(cells) is not list or len(cells) != 18
            or any(type(row) is not list or len(row) != 20
                   or any(type(c) is not str or len(c) != 1 for c in row) for row in cells)):
        return None
    rows = [''.join(row) for row in cells]
    indices = [i for i, row in enumerate(rows) if re.search(r'[A-Za-z0-9]{2,}', row)]
    if (text.get('line_rows') != indices[:12]
            or text.get('lines') != [rows[i].rstrip() for i in indices[:12]]):
        return None
    valid = (text.get('read_valid') is True and text.get('alignment_verified') is True
             and text.get('read_error') is None)
    # Exact source-calibrated silhouette transition, never an A authorization.
    silhouette = (text.get('read_valid') is False and text.get('alignment_verified') is False
                  and text.get('read_error') == 'visible_tile_alignment_incomplete'
                  and text['window_visible'] is False and all(row == ' ' * 20 for row in rows))
    return (rows, valid, silhouette) if valid or silhouette else None


def _wants(rows):
    if any(row != ' ' * 20 for i, row in enumerate(rows) if i not in {14, 16}):
        return None
    first, second = rows[14].rstrip(), rows[16].rstrip()
    if first == ' BLAINE wants' and second == ' to fight!        ▼':
        return 'complete'
    # Only prefixes of the two exact source lines; arbitrary text cannot wait.
    if (first and ' BLAINE wants'.startswith(first)
            and ' to fight!'.startswith(second)
            and (not second or first == ' BLAINE wants')):
        return 'partial'
    return None


def _partial_sendout(rows, species):
    if any(rows[i] != ' ' * 20 for i in {12, 13, 15, 17}):
        return False
    first, second = rows[14].rstrip(), rows[16].rstrip()
    return (bool(first) and ' BLAINE sent'.startswith(first)
            and (' out ' + species + '!').startswith(second)
            and (not second or first == ' BLAINE sent'))


def _budget(owner, frame, now):
    global _INTRO
    if owner is None:
        return 'opponent_review_intro_owner_unverified'
    if type(now) not in {int, float} or not math.isfinite(now) or now < 0:
        return 'opponent_review_intro_clock_unverified'
    if _INTRO is None:
        _INTRO = dict(owner=owner, first_frame=frame, last_frame=None, started=now,
                      last_clock=now, waits=0, acknowledged=False, initialized=False, halted=None,
                      pending_frame=None, pending_previous=None)
    if _INTRO['owner'] is not owner:
        return 'opponent_review_intro_owner_changed'
    if _INTRO['halted']:
        return _INTRO['halted']
    if now < _INTRO['last_clock']:
        _INTRO['halted'] = 'opponent_review_intro_clock_regressed'
    elif now - _INTRO['started'] >= MAX_SECONDS:
        _INTRO['halted'] = 'opponent_review_intro_time_exhausted'
    elif _INTRO['last_frame'] is not None and frame <= _INTRO['last_frame']:
        _INTRO['halted'] = 'opponent_review_intro_frame_not_progressing'
    elif _INTRO['waits'] >= MAX_WAITS:
        _INTRO['halted'] = 'opponent_review_intro_wait_exhausted'
    _INTRO['last_clock'] = now
    return _INTRO['halted']


def context(state, step, text=None, *, previous=None, signal=None, owner=None, now=None):
    if not isinstance(step, dict) or 'opponent_review' not in step:
        return None
    if (step.get('opponent_review') != PROFILE or step.get('kind') != 'interact'
            or type(step.get('map_id')) is not int or step['map_id'] != 166
            or type(step.get('target')) is not list or step['target'] != [3, 4]
            or any(type(v) is not int for v in step['target'])
            or step.get('face') != 'up' or step.get('event') != 'beat_blaine'):
        return _review('opponent_review_intent_unverified')
    if not isinstance(state, dict):
        return _review('opponent_review_state_unverified')
    loc, b, frame = state.get('location'), state.get('battle_state'), state.get('frame')
    if (type(loc) is not dict or loc != dict(map_id=166, x=3, y=4)
            or any(type(v) is not int for v in loc.values())
            or type(frame) is not int or frame < 0 or not isinstance(b, dict)
            or type(b.get('observation_frame')) is not int or b['observation_frame'] != frame):
        return _review('opponent_review_observation_unverified')
    if b.get('active') is False and type(b.get('raw')) is int and b['raw'] == 0 and b.get('kind') == 'none':
        return None
    if b.get('active') is not True or type(b.get('raw')) is not int or b['raw'] != 2 or b.get('kind') != 'trainer':
        return _review('opponent_review_trainer_unverified')
    species = b.get('opponent_species')
    if species == 'ARCANINE':
        return _review('blaine_arcanine_medicine_calibration')
    known = type(species) is str and species in {'GROWLITHE', 'PONYTA', 'RAPIDASH'}
    if _INTRO is not None:
        if _INTRO['owner'] is not owner:
            return _review('opponent_review_intro_owner_changed')
        if _INTRO['halted']:
            return _review(_INTRO['halted'])
        if _INTRO['initialized']:
            # Existing battle guards retain all ordinary UI and attrition handling.
            return None if known else _review('opponent_review_identity_unverified')
    if (type(signal) is not dict or signal.get('profile') != SIGNAL_PROFILE
            or signal.get('read_valid') is not True or owner is None
            or type(signal.get('owner_id')) is not int or signal['owner_id'] != id(owner)
            or any(type(signal.get(k)) is not int for k in ('frame_before', 'frame_after', 'raw', 'battle_type'))
            or not (signal['frame_before'] == signal['frame_after'] == frame
                    and signal['raw'] == 2 and signal['battle_type'] == 0)):
        return _review('opponent_review_intro_signal_unverified')
    if _INTRO is not None:
        if _INTRO['owner'] is not owner:
            return _review('opponent_review_intro_owner_changed')
        if _INTRO['halted']:
            return _review(_INTRO['halted'])
    if (type(previous) not in {list, tuple} or len(previous) > 8
            or any(type(action) is not str or action not in {'a', 'b', 'wait', 'up', 'down', 'left', 'right', 'start', 'select'} for action in previous)):
        return _review('opponent_review_intro_previous_unverified')
    parsed = _rows(text)
    if parsed is None:
        return _review('opponent_review_intro_text_unverified')
    rows, valid, silhouette = parsed
    visible = known and valid and any(row.strip() == species for row in rows[:4])
    if _INTRO is not None and _INTRO.get('pending_frame') is not None:
        pending = _INTRO['pending_frame']
        if frame > pending:
            action = previous[-1] if previous else None
            expected = (_INTRO['pending_previous'] + (action,))[-8:]
            if not visible and (action not in {'a', 'wait'} or tuple(previous) != expected):
                return _review('opponent_review_intro_action_receipt_unverified')
            _INTRO['pending_frame'] = _INTRO['pending_previous'] = None
            if action == 'a' and tuple(previous) == expected:
                _INTRO['acknowledged'] = True
            elif action == 'wait' and tuple(previous) == expected:
                _INTRO['waits'] += 1
    sent_out = (known and valid and _INTRO is not None and _INTRO['acknowledged']
                and rows[14].strip() == 'BLAINE sent'
                and rows[16].strip().removesuffix('▼').rstrip() == 'out ' + species + '!')
    if sent_out:
        # The actual A already completed the intro. Recognize this receipt after
        # an engineering pause without issuing another A or resetting a budget.
        _INTRO['initialized'] = True
        return dict(phase='battle_animation',objective='Wait.',available_actions=['wait'],
                    battle_tactic='observed_native_blaine_sendout',opponent_review_profile=PROFILE)
    if visible:
        reason = _budget(owner, frame, time.monotonic() if now is None else now)
        if reason:
            return _review(reason)
        _INTRO['initialized'] = True
        return None
    wants = _wants(rows) if valid and text['window_visible'] is True else None
    blank = all(row == ' ' * 20 for row in rows)
    partial_sendout = (known and valid and text['window_visible'] is True
                       and _INTRO is not None and _INTRO['acknowledged']
                       and _partial_sendout(rows, species))
    if not (blank or wants or partial_sendout):
        return _review('opponent_review_identity_unverified')
    reason = _budget(owner, frame, time.monotonic() if now is None else now)
    if reason:
        return _review(reason)
    _INTRO['last_frame'] = frame
    if wants == 'complete' and not _INTRO['acknowledged']:
        _INTRO['pending_frame'] = frame
        _INTRO['pending_previous'] = tuple(previous)
        return dict(phase='battle_dialogue', objective='Confirm the current selection.',
                    available_actions=['a', 'wait'], battle_tactic='acknowledge_verified_blaine_intro_once',
                    opponent_review_profile=PROFILE)
    _INTRO['waits'] += 1
    return dict(phase='battle_animation', objective='Wait.', available_actions=['wait'],
                battle_tactic='wait_verified_blaine_intro', opponent_review_profile=PROFILE,
                opponent_intro_waits=_INTRO['waits'], opponent_intro_silhouette=silhouette)
