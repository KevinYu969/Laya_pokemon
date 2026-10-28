"""可核對的正常遊戲行程；路線資料可熱更新，不寫遊戲記憶體。"""
import importlib
import json
import time
from . import team_strategy
importlib.reload(team_strategy)
from . import party_control,balanced_training
if 'waypoint' in globals():
    importlib.reload(party_control)
    importlib.reload(balanced_training)
from . import world_map
importlib.reload(world_map)
from . import victory_road_navigation
importlib.reload(victory_road_navigation)
from . import victory_ladder_settle
importlib.reload(victory_ladder_settle)
from . import victory_east_entry
importlib.reload(victory_east_entry)
read_world_grid,world_direction=world_map.read_world_grid,world_map.world_direction
_LEARNED_EDGES=globals().get('_LEARNED_EDGES',{})
_LAST_ATTEMPT=globals().get('_LAST_ATTEMPT')
_FIELD_CONTROLLERS=globals().get('_FIELD_CONTROLLERS',{})
_GYM_CONTROLLERS=globals().get('_GYM_CONTROLLERS',{})
_SCRIPT_WAITS=globals().get('_SCRIPT_WAITS',{})
_VIA_PROGRESS=globals().get('_VIA_PROGRESS',{})
_REVIEWED_NPC_EDGE_RETRIES=globals().get('_REVIEWED_NPC_EDGE_RETRIES',set())
from . import field_moves as field_moves_module
importlib.reload(field_moves_module)
from . import gym_switches as gym_switches_module
importlib.reload(gym_switches_module)
from . import campaign_transactions
importlib.reload(campaign_transactions)
from . import capture_transaction
importlib.reload(capture_transaction)
from . import campaign_safety,capture_closing_gate
from . import safari_entry
importlib.reload(safari_entry)
from . import hm_teaching_bridge
importlib.reload(hm_teaching_bridge)
from . import vending_bridge
importlib.reload(vending_bridge)
from . import saffron_guard_bridge
importlib.reload(saffron_guard_bridge)
from . import silph_card_bridge
importlib.reload(silph_card_bridge)
from . import silph_rival_wait
importlib.reload(silph_rival_wait)
from . import silph_giovanni_wait
importlib.reload(silph_giovanni_wait)
from . import league_native_wait
importlib.reload(league_native_wait)
from . import e4_coordinate
importlib.reload(e4_coordinate)
from . import sabrina_native_warp
importlib.reload(sabrina_native_warp)
from . import lapras_bridge
importlib.reload(lapras_bridge)
from . import player_pc_bridge
importlib.reload(player_pc_bridge)
from . import cinnabar_purchase_bridge
importlib.reload(cinnabar_purchase_bridge)
from . import opponent_review_gate
importlib.reload(opponent_review_gate)
from . import battle_medicine_bridge,blaine_supply_policy,blaine_supply_dispatch
importlib.reload(battle_medicine_bridge)
importlib.reload(blaine_supply_policy)
importlib.reload(blaine_supply_dispatch)
from . import trainer_medicine_ui_bridge,trainer_medicine_policy,trainer_medicine_dispatch
importlib.reload(trainer_medicine_ui_bridge)
importlib.reload(trainer_medicine_policy)
importlib.reload(trainer_medicine_dispatch)
from . import fly_pallet_bridge
importlib.reload(fly_pallet_bridge)
from . import fly_viridian_bridge
importlib.reload(fly_viridian_bridge)
from . import pallet_surf_bridge
importlib.reload(pallet_surf_bridge)
from . import route21_water_bridge
importlib.reload(route21_water_bridge)
from . import mansion_native_landing
importlib.reload(mansion_native_landing)
from . import mansion_transition_ready
importlib.reload(mansion_transition_ready)
from . import mansion_statue_bridge
importlib.reload(mansion_statue_bridge)
from . import mansion_secret_key_bridge
importlib.reload(mansion_secret_key_bridge)
from . import (victory_strength_bridge,victory_first_boulder_bridge,
               victory_later_boulders_bridge,route23_bridge,route23_land_guards_bridge,
               league_training_batch_bridge,overworld_hyper_bridge,tm24_teaching_bridge)
_LEAGUE_FIELDS=(victory_strength_bridge,victory_first_boulder_bridge,
               victory_later_boulders_bridge,route23_bridge,route23_land_guards_bridge,
               league_training_batch_bridge,overworld_hyper_bridge,tm24_teaching_bridge)
for _bridge in _LEAGUE_FIELDS:importlib.reload(_bridge)
del _bridge
from . import owned_field_medicine
importlib.reload(owned_field_medicine)
from . import training_switch_review
importlib.reload(training_switch_review)
from . import plan_snapshot_cache_install
importlib.reload(plan_snapshot_cache_install)
from . import league_recovery
importlib.reload(league_recovery)
from . import recovery_field_medicine
importlib.reload(recovery_field_medicine)
from . import reviewed_hole_layout
importlib.reload(reviewed_hole_layout)
from . import reviewed_native_fall
importlib.reload(reviewed_native_fall)
_NATIVE_FALL_REVIEW_CAPSULE = {'evidence': {'preflight_sha256': '858dc6a8ed19b9f29aec39ce30cebcc95983451cac1fa8532ceb291e094af0a4',
              'review_sha256': '40bcfe4dcd399cb837dc05821484da4aa0f9df07579174e078529bf77f39cd0a',
              'state_sha256': 'a49b27c4868ca9da561bb9610553fd1a8afdc47d38d02685e75cb2e4c3e795ad'},
 'game_id': 'game29',
 'kind': 'reviewed_native_fall_198_194_20261028',
 'landing_location': {'map_id': 194, 'x': 22, 'y': 16},
 'original_step_id': 'league28-fnt-recovery-02',
 'original_step_sha256': '17e70cdf8a2fb1d9d964a1594ec3422d0c38b9068edc1623624227262ec5d1b9',
 'recovery_capsule_sha256': '8065ae7f61687c0f71e31cb5bd6d4f60721045bbabe25c9d1873741b0b7d15fd',
 'source_frame': 7513,
 'source_location': {'map_id': 198, 'x': 23, 'y': 15},
 'source_progress_sha256': '15bed7a5c90f0d9ec756e1c3a4428ef1f0c270fa9d8e78bdc276cae207bf1a0e',
 'steps_sha256': '7c526265631f16b037969d66773d0f9264ab37c5e5f67c1362335c4f276daefc',
 'training_job_sha256': '91fa844146ffb294fa0f089d91368b17c47ff9f0502adf0f1f946c7b9baebd2b'}
_HOLE_LAYOUT_REVIEW_CAPSULE = {'evidence': {'preflight_sha256': '48b19783531d936ea9bbe505cd44a424ec09e7a1de6a0d2c4ba00871402b28dd',
              'review_sha256': '1ca24415b4dd99a733047963b3b8df9f064d56f1bed5e7f293de1e275bb73abd',
              'state_sha256': 'e2854324e82f59d2d8813712f2d759ce0ba9a4c2a22641785b31d79be23f0c75'},
 'game_id': 'game29',
 'kind': 'reviewed_3f_hole_aux8_layout_v1',
 'original_step_id': 'league28-fnt-recovery-01',
 'original_step_sha256': '6e0199a4813d2a132b71e201770bcdef76d259f112cf03fc0b7cb0cdd4109ab7',
 'recovery_capsule_sha256': '8065ae7f61687c0f71e31cb5bd6d4f60721045bbabe25c9d1873741b0b7d15fd',
 'source_frame': 7233,
 'source_layout': 'reviewed_3f_hole_aux8_13_13_20261028',
 'source_location': {'map_id': 198, 'x': 21, 'y': 15},
 'source_progress_sha256': '15bed7a5c90f0d9ec756e1c3a4428ef1f0c270fa9d8e78bdc276cae207bf1a0e',
 'steps_sha256': '7c526265631f16b037969d66773d0f9264ab37c5e5f67c1362335c4f276daefc',
 'training_job_sha256': '91fa844146ffb294fa0f089d91368b17c47ff9f0502adf0f1f946c7b9baebd2b'}
_RECOVERY_FULL_HEAL_EVIDENCE={
    'review_sha256':'042cc762cf2702d5bd72b064365caa3604f44f4aa2cf8b476ee7fce8335968d6',
    'state_sha256':'5cc613d6aa9122030f54f8e114390ecee0d8ac6a50e68f445f0b5905b98b3809'}
from . import league_training_supervisor,league_training_proof
importlib.reload(league_training_supervisor)
importlib.reload(league_training_proof)
_TRAINING_BATCH_PROOFS=globals().get('_TRAINING_BATCH_PROOFS',{})
importlib.reload(campaign_safety)
importlib.reload(capture_closing_gate)
for controller in _GYM_CONTROLLERS.values():controller._last_now=None


def _native_wait_clock(step_id,frame):
    """延續既有clock，只加入真正前進的模擬幀；工程停檢不退款或耗預算。"""
    c=league_native_wait._WAITS.get(step_id)
    if c is None:return None
    last_frame,last_now=getattr(c,'last_frame',None),getattr(c,'last_now',None)
    if (type(frame) is int and type(last_frame) is int and 0<=last_frame<=frame
            and league_native_wait._clock(last_now)):
        return last_now+(frame-last_frame)/60
    return float('nan')  # 交純controller拒絕；不得以新wall clock修復非法舊欄位。


_TM24_RETURN_REVIEW_CAPSULE = {'evidence': {'preflight_sha256': 'f855a3fa75e03e61d62346cf6b8d71c12fdc76dd19e14c95783c922958dbf547',
              'review_sha256': 'aba4a5b7bbc3c0317f1d99c44497f9fc1254f196a5b88e308de072a328936cda',
              'state_sha256': 'e42fe436f414122f47e7c8129d9a08797758a13cbfbd75a2b2bede197ffea716'},
 'game_id': 'game29',
 'kind': 'tm24_native_return_redraw_review19073_v1',
 'original_step_id': 'game29-indigo-lapras-tm24-20261028',
 'original_step_sha256': '471e9ed19fde89c4a661bf7fa7c70ab119d26517c66399c1cacba055863828aa',
 'plan_bytes_sha256': 'fe52e2c3c979c27573c365daf9eff4c730befce1742908c313c841762a828f9e',
 'source_frame': 19073,
 'source_location': {'map_id': 174, 'x': 7, 'y': 7},
 'source_progress_sha256': '7a6924ad5a0e0dd4fa82e92cf961044801ad2b84f6f95244a9c42c2c08e8341f',
 'training_job_sha256': 'b7e9ffa51e38f7901204e1e8b12ae00abecc42cdcbb37c398db7e4a51aebe6bf'}
_TM24_RETURN_PLAN_CANONICAL_SHA256 = '080360fac74b6bbbd7d4c63e78ba3230736ba48f9512a8094064a0afb3a27dd6'


_BATCH_TURN_REVIEW_CAPSULE = {'actual_action_frame': 23673,
 'baseline_sha256': '6689f9d51ce7ab8165e3179491a2dad02bbf205868d2dca5e99a7fa6ce393046',
 'binding_sha256': '93c365a277428572faa3ca72b2ef86c380938ebab0846653a94c2e98f3436080',
 'calls': 149,
 'displacements': 2,
 'evidence': {'preflight_sha256': 'e7f633c1021dc393419c18bc8c2ba31c1329fdbd85df48e0a432b524fb775123',
              'review_sha256': '447706ef6bb895538d1b23c49b1c1264deae1d70ad884f3af0208a24dbd7c6b6',
              'state_sha256': 'e76501526abd833119eb32830f89613a6b5e82ee84bb28b0cc0983eb16317b14'},
 'first_wild_frame': 23713,
 'game_id': 'game29',
 'historical_walk_sha256': '8b8d77cf6152da6f3690b4983d2e26c760a31b841af215c1fe56809975a678bf',
 'historical_wild_sha256': 'cf08750b3fdf5ea37ea0a7f2ccd1f8b654d9b861748fedd133cfb05fa564011f',
 'kind': 'reviewed_training_turn_return30833_v1',
 'last_frame': 30833,
 'original_step_id': 'root-calibration-game29-20261028-out-067',
 'pending': {'action': 'down',
             'executed': True,
             'expected': [28, 8],
             'frame': 23673,
             'player': [28, 7]},
 'plan_bytes_sha256': '432b4056ceeb469d62539d5b68659bc03357c467b2aef4f06f1a383582fc9f7e',
 'requests': 3,
 'source_location': {'map_id': 194, 'x': 28, 'y': 7},
 'source_packet_sha256': '757bd2f50d6e129a47e7fedc7cddc903a34fada3f094f6df51306cd72573a2bf',
 'source_progress_sha256': '727b0bec570b16b1c511fc7dc6103bfe8938904a940fadf9ec18538a9b9b498a',
 'waits': 129}
_BATCH_TURN_PLAN_CANONICAL_SHA256 = '74e1eb74747aa8e120e5d1216d776d03667b2be905fdbf4ce4e7b428258f6a46'
_BATCH_TURN_NATIVE_WITNESS_SHA256 = 'ee037a62d72a361f9f39eb551df0de0222b10bd99d3c5002edd02980d2899013'


_TRAINING_FNT_STEP = 'league-six-party45-game29-20261028-069-067'
_TRAINING_FNT_CAP_BYTES_SHA = 'd612826b098aa53a4997960d4cf599d6250bace8348c93b78f2073a5487722c6'
_TRAINING_FNT_CAP_CANONICAL_SHA = 'e6d1633738687c674bb5914ec78b8339499ad9a9fefcdab9c2e304f4c46d7c4e'


def _read_training_fnt_review_capsule():
    from pathlib import Path
    from hashlib import sha256
    import json
    root=Path(__file__).resolve().parents[2]
    raw=(root/'.local/training382449-faint-review.json').read_bytes()
    if sha256(raw).hexdigest()!=_TRAINING_FNT_CAP_BYTES_SHA:raise ValueError('fnt_capsule_bytes_changed')
    cap=json.loads(raw)
    if owned_field_medicine.canonical_sha256(cap)!=_TRAINING_FNT_CAP_CANONICAL_SHA:raise ValueError('fnt_capsule_changed')
    for label,key,suffix in [('review','review_sha256','json'),('state','state_sha256','state'),('plan','plan_bytes_sha256','json')]:
        proof=(root/f'.local/gym-reviewed-history/training382449-before-fnt-recovery-{label}.{suffix}').read_bytes()
        if sha256(proof).hexdigest()!=cap[key]:raise ValueError('fnt_original_evidence_changed')
    for role,file,line_no in [('faint','steps-064.jsonl',77),('enemy_ko','steps-065.jsonl',5),('reward','steps-065.jsonl',6)]:
        event=cap['source_events'][role]
        if event['file']!=file or event['line_number']!=line_no:raise ValueError('fnt_source_changed')
        line=(root/'outputs/league-campaign-20261028-29/game'/file).read_bytes().splitlines()[line_no-1]
        if sha256(line).hexdigest()!=event['line_sha256'] or json.loads(line)!=event['record']:
            raise ValueError('fnt_source_record_changed')
    return cap


def _training_fnt_abort_review_context(pyboy,state,plan,step_id):
    """Reviewed one-member faint; keep the failed batch and use normal nurse recovery."""
    b=league_training_batch_bridge;key=_TRAINING_FNT_STEP
    records=getattr(b,'_REVIEWED_ABORTS',None)
    record=records.get(key) if type(records) is dict else None
    if type(record) is dict and record.get('done') is True and step_id!=key:return None
    c=b._CONTROLLERS.get(key) if type(b._CONTROLLERS) is dict else None
    if c is None:return None
    def reject(reason):
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='training_fnt_abort_parent_'+reason),step_id
    try:
        peers=_field_medicine_peers();done=type(record) is dict and record.get('done') is True
        expected=set() if done else {key}
        if (step_id!=key or type(peers) is not dict or set(peers)!=owned_field_medicine.PEER_NAMES
                or any(type(v) is not set or (v!=expected if k=='league_training_batch' else bool(v)) for k,v in peers.items())
                or owned_field_medicine._active()!=set() or b._active()!=expected or b._OWNERS.get(key) is not pyboy
                or any(x is not b and x._active()!=set() for x in _LEAGUE_FIELDS)):
            return reject('owner_or_peers_unverified')
        cap=_read_training_fnt_review_capsule()
        if (type(state) is not dict or type(state.get('frame')) is not int or not 382449<=state['frame']<=382529
                or pyboy.frame_count!=state['frame'] or owned_field_medicine.canonical_sha256(plan)!=cap['plan_sha256']):
            return reject('native_plan_or_frame_unverified')
        from .observation import read_visible_text
        result=b.reviewed_fnt_abort(pyboy,state,plan,key,read_visible_text(pyboy),
            read_world_grid(pyboy,state['location']),cap,expected_capsule_sha256=_TRAINING_FNT_CAP_CANONICAL_SHA,
            original_controller=c,original_binding=b._BINDINGS.get(key),
            original_pending=c.pending,original_last_packet=c.last_packet)
        return _eevee37_closed_abort_cleanup(pyboy,result)
    except (OSError,AttributeError,KeyError,TypeError,ValueError,IndexError):return reject('evidence_or_preflight_unverified')




_TRAINING_ESCAPE_STEP = 'league-six-party45-game29-20261028-025-067'
_TRAINING_ESCAPE_CAP_BYTES_SHA = '65078447b775b6c9dca8d2797e00f7aa43cb5e397d41f836edd1200c9e12bfa4'
_TRAINING_ESCAPE_CAP_CANONICAL_SHA = '9e71713eaa0434b173a4333745e04a231efd1dbcd19932e3d61da0e79f89cb3a'


def _read_training_escape_review_capsule():
    from pathlib import Path
    from hashlib import sha256
    import json
    root=Path(__file__).resolve().parents[2]
    raw=(root/'.local/training160497-reviewed-abort.json').read_bytes()
    if sha256(raw).hexdigest()!=_TRAINING_ESCAPE_CAP_BYTES_SHA:raise ValueError('capsule_bytes_changed')
    cap=json.loads(raw)
    if owned_field_medicine.canonical_sha256(cap)!=_TRAINING_ESCAPE_CAP_CANONICAL_SHA:raise ValueError('capsule_changed')
    for label,key,suffix in [('review','original_review_sha256','json'),('state','source_state_sha256','state'),('plan','plan_bytes_sha256','json')]:
        proof=(root/f'.local/gym-reviewed-history/training160497-before-diagnostic-{label}.{suffix}').read_bytes()
        if sha256(proof).hexdigest()!=cap[key]:raise ValueError('original_evidence_changed')
    escape=cap['source_escape']
    if escape['file']!='steps-030.jsonl' or escape['line_number']!=29:raise ValueError('escape_source_changed')
    line=(root/'outputs/league-campaign-20261028-29/game/steps-030.jsonl').read_bytes().splitlines()[28]
    if sha256(line).hexdigest()!=escape['line_sha256'] or json.loads(line)!=escape['record']:
        raise ValueError('escape_record_changed')
    return cap


def _training_escape_abort_review_context(pyboy,state,plan,step_id):
    """Root's named no-reward escape review; never records a victory."""
    b=league_training_batch_bridge;key=_TRAINING_ESCAPE_STEP
    records=getattr(b,'_REVIEWED_ABORTS',None)
    record=records.get(key) if type(records) is dict else None
    if type(record) is dict and record.get('done') is True and step_id!=key:return None
    c=b._CONTROLLERS.get(key) if type(b._CONTROLLERS) is dict else None
    if c is None or getattr(c,'error',None)!='league_training_batch_single_wild_reward_or_pp_bound_unverified':return None
    def reject(reason):
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='training_escape_abort_parent_'+reason),step_id
    try:
        peers=_field_medicine_peers();done=type(record) is dict and record.get('done') is True
        expected=set() if done else {key}
        if (step_id!=key or type(peers) is not dict or set(peers)!=owned_field_medicine.PEER_NAMES
                or any(type(v) is not set or (v!=expected if k=='league_training_batch' else bool(v)) for k,v in peers.items())
                or owned_field_medicine._active()!=set() or b._active()!=expected
                or b._OWNERS.get(key) is not pyboy or any(x is not b and x._active()!=set() for x in _LEAGUE_FIELDS)):
            return reject('owner_or_peers_unverified')
        cap=_read_training_escape_review_capsule()
        h=owned_field_medicine.canonical_sha256
        if (type(state) is not dict or type(state.get('frame')) is not int or not 160497<=state['frame']<=160577
                or pyboy.frame_count!=state['frame'] or h(plan)!=cap['plan_sha256']
                or id(c)!=cap['controller_identity'] or id(pyboy)!=cap['native_identity']):
            return reject('native_plan_or_frame_unverified')
        from .observation import read_visible_text
        text=read_visible_text(pyboy);grid=read_world_grid(pyboy,state['location'])
        result=b.reviewed_abort(pyboy,state,plan,key,text,grid,cap,
            expected_capsule_sha256=_TRAINING_ESCAPE_CAP_CANONICAL_SHA,
            original_controller=c,original_binding=b._BINDINGS.get(key),
            original_pending=c.pending,original_last_packet=c.last_packet)
        return _eevee37_closed_abort_cleanup(pyboy,result)
    except (OSError,AttributeError,KeyError,TypeError,ValueError,IndexError):
        return reject('evidence_or_preflight_unverified')




def _training_turn_return_review_context(pyboy,state,plan,step_id,previous):
    """只復核已真遇怪取消移動的30833，原等待數不清零。"""
    b=league_training_batch_bridge;c=b._CONTROLLERS.get(step_id) if type(b._CONTROLLERS) is dict else None
    if c is None or getattr(c,'error',None)!='league_training_batch_wait_budget_exhausted':return None
    def reject(reason):
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='training_turn_return_parent_'+reason),step_id
    try:
        cap=_BATCH_TURN_REVIEW_CAPSULE;h=owned_field_medicine.canonical_sha256
        peers=_field_medicine_peers()
        if (type(peers) is not dict or set(peers)!=owned_field_medicine.PEER_NAMES
                or any(type(v) is not set or (v!={step_id} if k=='league_training_batch' else bool(v))
                       for k,v in peers.items()) or owned_field_medicine._active()!=set()
                or b._active()!={step_id} or type(b._ERRORS) is not dict or b._ERRORS
                or b._OWNERS.get(step_id) is not pyboy
                or any(x is not b and x._active()!=set() for x in _LEAGUE_FIELDS)
                or step_id!=cap['original_step_id'] or h(plan)!=_BATCH_TURN_PLAN_CANONICAL_SHA256
                or type(state) is not dict or state.get('frame')!=30833 or pyboy.frame_count!=30833
                or c.last_frame!=30833 or h(c.last_packet)!=cap['source_packet_sha256']
                or h(c.baseline)!=cap['baseline_sha256'] or h(c.pending)!=h(cap['pending'])
                or h(b._BINDINGS.get(step_id))!=cap['binding_sha256']):
            return reject('owner_plan_or_original_packet_unverified')
        # 原程序唯讀快照的identity只在本機，不把程序識別放進公開設定。
        from pathlib import Path
        import json
        witness=json.loads((Path(__file__).resolve().parents[2]/'.local/batch30833-native-witness.json').read_text(encoding='utf-8'))
        if (h(witness)!=_BATCH_TURN_NATIVE_WITNESS_SHA256 or witness['controller_identity']!=id(c)
                or witness['native_identity']!=id(pyboy) or h(cap)!=h(b.batch.TURN_RETURN_REVIEW)):
            return reject('same_native_controller_unverified')
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        from .progress import read_progress
        from .observation import read_visible_text
        frame=pyboy.frame_count;text=read_visible_text(pyboy);grid=read_world_grid(pyboy,state['location'])
        signal=b.batch.read_training_observation(pyboy,frame,sdk);progress=read_progress(pyboy,sdk)
        old=c.last_packet
        if (pyboy.frame_count!=frame or h(progress)!=cap['source_progress_sha256']
                or h(progress)!=h(state['progress']) or h(text)!=h(old[1]) or h(grid)!=h(old[2])
                or h(signal)!=h(old[3]) or h(previous)!=h(old[4]) or old[5]!=step_id
                or state['location']!=cap['source_location']
                or h(state['battle_state'])!=h(old[0]['battle_state'])):
            return reject('fresh_source_world_unverified')
        c.__class__=b.batch.TrainingBatch
        return c.review_cancelled_turn_return(review_capsule=cap,source_evidence=cap['evidence']),step_id
    except (OSError,AttributeError,KeyError,TypeError,ValueError,IndexError):
        return reject('preflight_unverified')


def _tm24_return_review_context(pyboy,state,plan,step_id,previous):
    """僅19073已學招/消耗後的重繪誤判；保同owner與已花預算。"""
    b=tm24_teaching_bridge;c=b._CONTROLLERS.get(step_id) if type(b._CONTROLLERS) is dict else None
    if c is None or getattr(c,'error',None)!='tm24_unknown_or_out_of_stage_source_page':return None
    def reject():
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='tm24_return_parent_preflight_unverified'),step_id
    try:
        cap=_TM24_RETURN_REVIEW_CAPSULE;h=owned_field_medicine.canonical_sha256
        peers=_field_medicine_peers()
        if (type(peers) is not dict or set(peers)!=owned_field_medicine.PEER_NAMES
                or any(type(v) is not set or (v!={step_id} if k=='tm24_teaching' else bool(v))
                       for k,v in peers.items()) or owned_field_medicine._active()!=set()
                or b._registry_problem() or b._active()!={step_id}
                or any(x is not b and x._active()!=set() for x in _LEAGUE_FIELDS)
                or step_id!=cap['original_step_id'] or h(plan)!=_TM24_RETURN_PLAN_CANONICAL_SHA256
                or type(state) is not dict or state.get('frame')!=19073 or pyboy.frame_count!=19073
                or state.get('location')!=cap['source_location'] or c.last_frame!=19073
                or not b._known_controller(c) or type(c.last_packet) is not tuple or len(c.last_packet)!=7
                or getattr(c,'native_return_review_history',None)):
            return reject()
        owner=b._OWNERS.get(step_id);binding=b._BINDINGS.get(step_id)
        step=next(s for s in plan['steps'] if s['id']==step_id)
        if (type(owner) is not dict or owner.get('pyboy') is not pyboy or owner.get('controller') is not c
                or binding!=dict(step=step,job=plan['training_job'])
                or h(step)!=cap['original_step_sha256'] or h(plan['training_job'])!=cap['training_job_sha256']
                or h(cap)!=h(b.tm24_teaching.NATIVE_RETURN_REVIEW)):
            return reject()
        from .progress import read_progress
        from .observation import read_visible_text
        before=pyboy.frame_count;text=read_visible_text(pyboy);progress=read_progress(pyboy)
        grid=read_world_grid(pyboy,state['location'])
        movement=b.read_rocket_movement(pyboy,observation_frame=before)
        packet=(text,progress,state['location'],state['battle_state'],movement,
                b._world_ready(text,grid,before),previous)
        if (pyboy.frame_count!=before or h(progress)!=cap['source_progress_sha256']
                or h(progress)!=h(state['progress']) or h(packet)!=h(c.last_packet)):
            return reject()
        # 與原bridge相同熱更方式；保留controller本體、binding與最後封包對象。
        c.__class__=b.tm24_teaching.TM24TeachingController
        result=c.review_native_return_redraw(review_capsule=cap,source_evidence=cap['evidence'])
        return result,step_id
    except (AttributeError,KeyError,TypeError,ValueError,IndexError,StopIteration):
        return reject()


def _victory_east_entry_context(pyboy,state,plan,step_id):
    """校準與每趟訓練的東入口載圖僅WAIT，原導航仍驗真到達。"""
    loc=state.get('location') if type(state) is dict else None
    if not victory_east_entry.applies(plan,step_id,loc):return None
    kwargs=dict(shared=owned_field_medicine,native_owner=pyboy,
        game_id='game29',peer_owners=_field_medicine_peers())
    gate=victory_east_entry.preflight(pyboy,state,plan,step_id,**kwargs)
    if gate is not None:return gate
    from .observation import read_visible_text
    text=read_visible_text(pyboy);grid=read_world_grid(pyboy,loc)
    ready=campaign_transactions.verified_blank_transaction_world(text,grid)
    npcs=victory_road_navigation.read_victory_road_npcs(pyboy,grid,loc,
        world_map_module=world_map,boulder_module=victory_later_boulders_bridge.boulder,
        overworld_ready=ready)
    return victory_east_entry.context(pyboy,state,plan,step_id,text,grid,npcs,**kwargs)


def _victory_ladder_settle_context(pyboy,state,plan,step_id):
    """兩個固定樓梯先等待載圖穩定，之後仍由原導航驗目的地。"""
    location=state.get('location') if type(state) is dict else None
    if not victory_ladder_settle.applies(step_id,location):return None
    kwargs=dict(shared=owned_field_medicine,recovery=league_recovery,
        native_owner=pyboy,game_id='game29',peer_owners=_field_medicine_peers())
    gate=victory_ladder_settle.preflight(pyboy,state,plan,step_id,**kwargs)
    if gate is not None:return gate
    from .observation import read_visible_text
    text=read_visible_text(pyboy);grid=read_world_grid(pyboy,state['location'])
    ready=campaign_transactions.verified_blank_transaction_world(text,grid)
    npcs=victory_road_navigation.read_victory_road_npcs(pyboy,grid,state['location'],
        world_map_module=world_map,boulder_module=victory_later_boulders_bridge.boulder,
        overworld_ready=ready)
    return victory_ladder_settle.context(pyboy,state,plan,step_id,text,grid,npcs,**kwargs)


def _reviewed_native_fall_context(pyboy,state,plan,step_id):
    """既定落洞僅WAIT；在換步與field UI前等待真落點閉合。"""
    if not reviewed_native_fall.applies(plan,step_id):return None
    kwargs=dict(bridge=victory_later_boulders_bridge,shared=owned_field_medicine,
        recovery=league_recovery,native_owner=pyboy,game_id='game29',
        review_capsule=_NATIVE_FALL_REVIEW_CAPSULE,source_evidence=reviewed_native_fall.EVIDENCE,
        peer_owners=_field_medicine_peers())
    gate=reviewed_native_fall.preflight(pyboy,state,plan,step_id,**kwargs)
    if gate is not None:return gate
    from .observation import read_visible_text
    return reviewed_native_fall.context(pyboy,state,plan,step_id,
        read_visible_text(pyboy),read_world_grid(pyboy,state['location']),**kwargs)


def _eevee37_closed_abort_cleanup(pyboy,result):
    from . import eevee37_dispatch_adapter as adapter
    if adapter._CONTEXT is not None and league_training_batch_bridge._active()==set():
        if not adapter.unregister_closed_context(pyboy):return adapter.review_context(),result[1]
    return result


def _read_eevee37_dismiss_review():
    from pathlib import Path
    from hashlib import sha256
    root=Path(__file__).resolve().parents[2]
    raw=(root/'.local/eevee37-619401-reviewed-dismiss.json').read_bytes()
    if sha256(raw).hexdigest()!='14528eff40b245f1d5c83be9a8dd11980164011d08a30ca249b28b31f159894c':
        raise ValueError('original_dismiss_capsule_changed')
    cap=json.loads(raw)
    if owned_field_medicine.canonical_sha256(cap)!='8e3d36027ee4dc1d9f564f9a79f25e0aef97ec2cc480e0ade2abe30bb1e44eb9':
        raise ValueError('original_dismiss_capsule_unverified')
    for label,ext in (('plan','json'),('review','json'),('state','state'),('summary','json')):
        data=(root/f'.local/gym-reviewed-history/eevee37-619401-before-dismiss-repair-{label}.{ext}').read_bytes()
        if sha256(data).hexdigest()!=cap['source_evidence_sha256'][label]:
            raise ValueError('original_dismiss_evidence_changed')
    for frame,event in cap['source_events'].items():
        if event['file']!='steps-100.jsonl' or frame not in ('618121','618161','618201','618241'):
            raise ValueError('original_dismiss_event_unknown')
        line=(root/'outputs/league-campaign-20261028-29/game/steps-100.jsonl').read_bytes().splitlines()[event['line_number']-1]
        if sha256(line).hexdigest()!=event['line_sha256'] or json.loads(line)['state']['frame']!=int(frame):
            raise ValueError('original_dismiss_event_changed')
    return cap


def _eevee37_owned_learning_context(pyboy,state,plan,step_id,text):
    """Only the first verified Trying page opens this bounded learning handoff."""
    from . import eevee37_dispatch_adapter as adapter,game,levelup_moves
    b=league_training_batch_bridge
    first=(state.get('phase')=='strategy_review'
        and state.get('review_reason')=='eevee37_trusted_dispatch_binding_missing')
    if adapter._CONTEXT is None and not first:return None,None
    rejected=adapter.review_context()
    if rejected:return rejected,None
    c=b._CONTROLLERS.get(step_id)
    if adapter._CONTEXT is None:
        # Review time never resets spent work.  Only future emulator frames charge
        # the original field clock; the supervisor's wall deadline still advances.
        if (c is None or c.error is not None or c.calls>=b.batch.MAX_CALLS
                or type(c.started) not in (int,float) or type(c.last_now) not in (int,float)
                or not 0<=c.last_now-c.started<b.batch.MAX_SECONDS):
            return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='eevee37_original_batch_headroom_missing'),None
        if not adapter.register_trusted_context(pyboy,plan,step_id,batch_bridge=b,
                levelup_module=levelup_moves,peer_owners=_field_medicine_peers()):
            return adapter.review_context(),None
        if not adapter.install_actual_dispatch_hook(pyboy,game.advance_action):
            return adapter.review_context(),None
        takeover=adapter.first_missing_binding_takeover(state,text,state.get('progress'))
        # The original batch already recorded this exact frame and old packet.
        # Return the trusted new UI hint without re-entering that batch frame.
        if takeover is None:
            takeover=dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='eevee37_first_trying_takeover_missing')
        return takeover,None
    try:
        owned=adapter._validate_context()
        if owned['native'] is not pyboy or owned['controller'] is not c or owned['step_id']!=step_id:
            raise ValueError('original_owner_changed')
        if adapter._sha(plan)!=owned['plan_sha']:raise ValueError('original_plan_changed')
        obs=owned.get('observation');binding=obs.get('binding') if type(obs) is dict else None
        proof=owned['proof'].original_controller(binding) if binding is not None else None
        if (state.get('phase')=='strategy_review'
                and state.get('review_reason')=='eevee37_source_wait_budget_exhausted'
                and state.get('frame')==619401):
            cap=_read_eevee37_dismiss_review()
            if (cap['original_step_id']!=step_id or cap['source_progress']!=state.get('progress')
                    or cap['source_location']!=state.get('location')
                    or time.time()>=cap['original_deadline']
                    or owned_field_medicine.canonical_sha256(plan)!=owned['plan_sha']):
                raise ValueError('original_dismiss_review_state_changed')
            if not adapter.register_trusted_context(pyboy,plan,step_id,batch_bridge=b,
                    levelup_module=levelup_moves,peer_owners=_field_medicine_peers()):
                return adapter.review_context(),None
            binding=adapter.current_binding(text,state['progress'])
            if binding is None:raise ValueError('reviewed_dismiss_fresh_binding_missing')
            if levelup_moves._SESSION is not proof.core_session:
                raise ValueError('reviewed_dismiss_original_core_registry_changed')
            from pathlib import Path
            audit=Path(__file__).resolve().parents[2]/'.local/eevee37-619401-runtime-migration-audit.json'
            if not audit.exists():
                record=dict(frame=binding['frame'],error=proof.error,calls=proof.calls,waits=proof.waits,
                    started=proof.started,pending=proof.pending,dismiss_ack=proof.dismiss_ack,
                    learned_frames=proof.learned_frames,core_session=proof.core_session,
                    original_packet_sha256=adapter._sha(proof.last_packet),
                    current_packet_sha256=adapter._sha((dict(text,observation_frame=binding['frame']),
                        state['progress'],binding['battle_state'])))
                with audit.open('x',encoding='utf-8') as stream:
                    stream.write(json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
            hint=owned['proof'].review_ignored_early_dismiss(binding,cap,
                expected_capsule_sha256='8e3d36027ee4dc1d9f564f9a79f25e0aef97ec2cc480e0ade2abe30bb1e44eb9',
                original_proof=proof,original_core_session=levelup_moves._SESSION,
                text=text,progress=state['progress'])
            if hint is None:raise ValueError('original_dismiss_migration_rejected')
            return hint,None
        if proof is not None and proof.complete is True:
            approval=b.consume_owned_eevee37_learning(pyboy,plan,step_id,
                original_controller=c,original_binding=owned['binding'],original_proof=proof,
                learning_binding=binding)
            if approval is None:raise ValueError('completed_original_learning_not_consumed')
        return None,owned_field_medicine.frame_clock(c,state.get('frame'))
    except (OSError,IndexError,KeyError,TypeError,ValueError,AttributeError):
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='eevee37_owned_learning_handoff_unverified'),None


def _league_field_context(pyboy,state,plan,step_id,step,previous):
    """新聯盟field共用入口；先保原owner及互斥，再讀UI，不代替各交易驗收。"""
    def review(reason):
        return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                 'review_reason':'league_field_'+reason},step_id)
    medicine_owners=owned_field_medicine._active()
    if medicine_owners is None:return review('registry_unverified')
    if medicine_owners:return review('other_transaction_active')
    active=[]
    for bridge in _LEAGUE_FIELDS:
        owners=bridge._active()
        if owners is None:return review('registry_unverified')
        if owners:active.append((bridge,owners))
    if len(active)>1:return review('multiple_owners_active')
    if active and active[0][1]!={step_id}:return review('owner_changed')
    matches=[b for b in _LEAGUE_FIELDS if b.applies(step_id,step)]
    if not matches:return None
    if len(matches)!=1:return review('multiple_intents_or_owners')
    bridge=matches[0]
    legacy=(battle_medicine_bridge,trainer_medicine_ui_bridge,mansion_secret_key_bridge,
        mansion_statue_bridge,mansion_transition_ready,mansion_native_landing,
        route21_water_bridge,pallet_surf_bridge,fly_pallet_bridge,fly_viridian_bridge,
        safari_entry,hm_teaching_bridge,vending_bridge,saffron_guard_bridge,
        silph_card_bridge,lapras_bridge,player_pc_bridge,cinnabar_purchase_bridge,campaign_transactions)
    for peer in legacy:
        bindings=getattr(peer,'_BINDINGS',None);done=getattr(peer,'_COMPLETED',None)
        controllers=getattr(peer,'_CONTROLLERS',{})
        if type(bindings) is not dict or type(done) is not set or type(controllers) is not dict:
            return review('peer_registry_unverified')
        if (set(bindings)|set(controllers))-done:return review('other_transaction_active')
    if type(capture_transaction._SESSIONS) is not dict:return review('capture_registry_unverified')
    if (safari_entry._RUN_CONTROLLER is not None
            or any(type(s) is not dict or s.get('done') is not True for s in capture_transaction._SESSIONS.values())
            or any(c.waiting for c in league_native_wait._WAITS.values())):
        return review('other_transaction_active')
    from .observation import read_visible_text
    kwargs={'peer_owners':()} if bridge is tm24_teaching_bridge else {}
    recovery_bench=league_recovery.allowance(plan,step_id,state.get('progress'))
    if recovery_bench and bridge in (victory_strength_bridge,victory_later_boulders_bridge):
        kwargs['reviewed_fainted_bench']=recovery_bench
    if bridge is victory_later_boulders_bridge:
        controller=bridge._CONTROLLERS.get(step_id)
        if (getattr(controller,'medical_interruption_history',None)
                or getattr(controller,'source_layout_review_history',None)):
            kwargs['now']=owned_field_medicine.frame_clock(controller,state.get('frame'))
    layout_kwargs=None
    if bridge is victory_later_boulders_bridge and reviewed_hole_layout.applies(step_id,bridge=bridge):
        layout_kwargs=dict(bridge=bridge,shared=owned_field_medicine,recovery=league_recovery,
            native_owner=pyboy,game_id='game29',review_capsule=_HOLE_LAYOUT_REVIEW_CAPSULE,
            source_evidence=reviewed_hole_layout.EVIDENCE,peer_owners=_field_medicine_peers())
        gate=reviewed_hole_layout.preflight(pyboy,state,plan,step_id,**layout_kwargs)
        if gate is not None:return gate
    if bridge is league_training_batch_bridge:
        reviewed_batch=_training_turn_return_review_context(pyboy,state,plan,step_id,previous)
        if reviewed_batch is not None:return reviewed_batch
        batch_controller=bridge._CONTROLLERS.get(step_id)
        if getattr(batch_controller,'cancelled_walk_review_history',None):
            kwargs['now']=owned_field_medicine.frame_clock(batch_controller,state.get('frame'))
    if bridge is tm24_teaching_bridge:
        reviewed_tm=_tm24_return_review_context(pyboy,state,plan,step_id,previous)
        if reviewed_tm is not None:return reviewed_tm
    text=read_visible_text(pyboy);grid=read_world_grid(pyboy,state['location'])
    if layout_kwargs is not None:
        reviewed=reviewed_hole_layout.context(pyboy,state,plan,step_id,text,grid,previous,**layout_kwargs)
        if reviewed is not None:return reviewed
        kwargs.update(source_layout=reviewed_hole_layout.LAYOUT,
            now=owned_field_medicine.frame_clock(bridge._CONTROLLERS[step_id],state.get('frame')))
    if bridge is league_training_batch_bridge:
        if bridge._OWNERS.get(step_id) is pyboy:
            cached=plan_snapshot_cache_install.install_for_owned_campaign(pyboy)
            if cached is True:
                from pathlib import Path
                audit=Path(__file__).resolve().parents[2]/'.local/plan-cache-installed-game29-20261028.json'
                if not audit.exists():
                    record=dict(at=time.time(),frame=state.get('frame'),step_id=step_id,
                        source_snapshot_sha256=plan_snapshot_cache_install.SNAPSHOT_SOURCE_SHA,
                        cache_source_sha256=plan_snapshot_cache_install.CACHE_FILE_SHA,
                        only_plan_loading_changed=True,cloud_classification=False)
                    try:
                        with audit.open('x',encoding='utf-8') as stream:
                            stream.write(json.dumps(record,sort_keys=True,indent=2)+'\n')
                    except OSError:
                        pass  # Optional timing audit cannot interrupt real play.
        if training_switch_review.applies(state,step_id):
            hint,clock=training_switch_review.context(pyboy,state,plan,step_id,text,
                bridge=bridge,peers=_field_medicine_peers())
            if hint is not None:return hint,step_id
            if clock is not None:kwargs['now']=clock
        hint,clock=_eevee37_owned_learning_context(pyboy,state,plan,step_id,text)
        if hint is not None:return hint,step_id
        if clock is not None:kwargs['now']=clock
    result=bridge.context(pyboy,state,plan,step_id,text,grid,previous,**kwargs)
    return _retain_training_batch_proof(state,plan,result,native_owner=pyboy)


def _field_medicine_peers():
    """僅讀owner登記；專用補血入口須在讀UI之前核完整互斥。"""
    inventory={}
    fields=(('victory_later_boulder',victory_later_boulders_bridge),
        ('overworld_hyper',overworld_hyper_bridge),('victory_strength',victory_strength_bridge),
        ('victory_first_boulder',victory_first_boulder_bridge),('route23',route23_bridge),
        ('route23_land_guards',route23_land_guards_bridge),('league_training_batch',league_training_batch_bridge),
        ('league_training_proof',league_training_proof))
    for name,bridge in fields:
        try:
            owners=bridge._active()
            if name=='league_training_proof' and type(owners) is set:
                owners={'training-proof'} if owners else set()
            inventory[name]=owners
        except Exception:inventory[name]=None
    tm=globals().get('tm24_teaching_bridge')
    try:inventory['tm24_teaching']=tm._active() if tm is not None else set()
    except Exception:inventory['tm24_teaching']=None
    legacy=(('battle_medicine',battle_medicine_bridge),('trainer_medicine_ui',trainer_medicine_ui_bridge),
        ('mansion_secret_key',mansion_secret_key_bridge),('mansion_statue',mansion_statue_bridge),
        ('mansion_transition_ready',mansion_transition_ready),('mansion_native_landing',mansion_native_landing),
        ('route21_water',route21_water_bridge),('pallet_surf',pallet_surf_bridge),('fly_pallet',fly_pallet_bridge),
        ('fly_viridian',fly_viridian_bridge),('safari_entry',safari_entry),('hm_teaching',hm_teaching_bridge),
        ('vending',vending_bridge),('saffron_guard',saffron_guard_bridge),('silph_card',silph_card_bridge),
        ('lapras',lapras_bridge),('player_pc',player_pc_bridge),('cinnabar_purchase',cinnabar_purchase_bridge),
        ('campaign_transactions',campaign_transactions))
    for name,bridge in legacy:
        bindings=getattr(bridge,'_BINDINGS',None);done=getattr(bridge,'_COMPLETED',None)
        controllers=getattr(bridge,'_CONTROLLERS',{});errors=getattr(bridge,'_ERRORS',{})
        if (type(bindings) is not dict or type(done) is not set or type(controllers) is not dict
                or type(errors) is not dict):inventory[name]=None
        else:inventory[name]=((set(bindings)|set(controllers))-done)|set(errors)
    try:
        inventory['safari_run']=set() if safari_entry._RUN_CONTROLLER is None else {'safari-run'}
        sessions=capture_transaction._SESSIONS
        inventory['capture_transaction']=(None if type(sessions) is not dict else
            {'capture-session'} if any(type(v) is not dict or v.get('done') is not True for v in sessions.values()) else set())
        waits=league_native_wait._WAITS
        inventory['native_wait']=(None if type(waits) is not dict else
            {'native-wait'} if any(c.waiting for c in waits.values()) else set())
        inventory['legacy_field']=(None if type(_FIELD_CONTROLLERS) is not dict else
            {'legacy-field'} if any(c.stage!='complete' for c in _FIELD_CONTROLLERS.values()) else set())
        inventory['legacy_gym']=(None if type(_GYM_CONTROLLERS) is not dict else
            {'legacy-gym'} if any(c.state!='complete' for c in _GYM_CONTROLLERS.values()) else set())
    except Exception:
        for name in ('safari_run','capture_transaction','native_wait','legacy_field','legacy_gym'):inventory[name]=None
    return inventory


def _owned_field_medicine_context(pyboy,state,plan,step_id,previous,attrition=None):
    if recovery_field_medicine.applies(plan,step_id,shared=owned_field_medicine):
        kwargs=dict(game_id='game29',native_owner=pyboy,source_evidence=_RECOVERY_FULL_HEAL_EVIDENCE,
            shared=owned_field_medicine,hyper_bridge=overworld_hyper_bridge,recovery=league_recovery,
            peer_owners=_field_medicine_peers(),attrition=attrition)
        gate=recovery_field_medicine.preflight(pyboy,state,plan,step_id,**kwargs)
        if gate is not None:return gate
        from .observation import read_visible_text
        return recovery_field_medicine.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
            read_world_grid(pyboy,state['location']),previous,**kwargs)
    if not owned_field_medicine.applies(plan,step_id):return None
    kwargs=dict(game_id='game28',native_owner=pyboy,later_bridge=victory_later_boulders_bridge,
        hyper_bridge=overworld_hyper_bridge,peer_owners=_field_medicine_peers(),attrition=attrition)
    gate=owned_field_medicine.preflight(pyboy,state,plan,step_id,**kwargs)
    if gate is not None:return gate
    from .observation import read_visible_text
    return owned_field_medicine.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
        read_world_grid(pyboy,state['location']),previous,**kwargs)


def _retain_training_batch_proof(state,plan,result,*,native_owner=None):
    """只在真bridge完成當輪投影；不在EOF回推，也保存attrition收尾的完成。"""
    if (result is None or plan.get('training_job')!=league_training_supervisor.JOB
            or plan.get('training_supervisor')!=league_training_proof.MARKER):return result
    context,next_id=result
    if context.get('field_move_kind')!='league-training-batch' or context.get('field_move_complete') is not True:return result
    try:
        key=context['training_batch_owner_step']
        authority=league_training_batch_bridge.completed_learning_authority(native_owner,key)
        projection=league_training_supervisor.project_completed_batch(plan,context,state,
            learning_authority=authority)
        if key in _TRAINING_BATCH_PROOFS and _TRAINING_BATCH_PROOFS[key]!=projection:
            raise ValueError('original_batch_projection_changed')
        _TRAINING_BATCH_PROOFS[key]=projection
        if not training_switch_review.finish(native_owner,key,state['frame'],bridge=league_training_batch_bridge):
            raise ValueError('original_switch_clock_completion_unverified')
        from . import eevee37_dispatch_adapter as adapter
        if adapter._CONTEXT is not None and not adapter.unregister_closed_context(native_owner):
            raise ValueError('original_learning_unregister_rejected')
    except Exception:
        return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                 'review_reason':'league_training_true_batch_projection_unverified'},next_id)
    return result


def _training_proof_owner_guard(pyboy,plan):
    """已開EOF owner不可藉改marker、plan或tail開始另一段送鍵。"""
    active=league_training_proof._active()
    if active is None:return league_training_proof._review('registries_unknown'),'complete'
    if not active:return None
    key=next(iter(active));c=league_training_proof._SESSIONS.get(key)
    try:
        valid=(len(active)==1 and c is not None and league_training_proof._OWNERS.get(key) is pyboy
            and plan.get('training_supervisor')==league_training_proof.MARKER
            and plan.get('training_job')==league_training_proof.JOB
            and c.binding==league_training_proof.canonical(plan))
    except Exception:valid=False
    if not valid:return league_training_proof._fail(key,'active_owner_plan_or_session_changed'),'complete'
    if not _training_peers_clear():return league_training_proof._fail(key,'active_field_or_legacy_owner'),'complete'
    if c.error is not None:return league_training_proof._review(c.error),'complete'
    return None


def _training_peers_clear():
    peers=(battle_medicine_bridge,trainer_medicine_ui_bridge,mansion_secret_key_bridge,
        mansion_statue_bridge,mansion_transition_ready,mansion_native_landing,route21_water_bridge,
        pallet_surf_bridge,fly_pallet_bridge,fly_viridian_bridge,safari_entry,hm_teaching_bridge,
        vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
        cinnabar_purchase_bridge,campaign_transactions)
    try:
        if owned_field_medicine._active() is None or bool(owned_field_medicine._active()):return False
        if any(b._active() is None or bool(b._active()) for b in _LEAGUE_FIELDS):return False
        for b in peers:
            bindings=getattr(b,'_BINDINGS',None);done=getattr(b,'_COMPLETED',None);controllers=getattr(b,'_CONTROLLERS',{})
            if type(bindings) is not dict or type(done) is not set or type(controllers) is not dict:return False
            if (set(bindings)|set(controllers))-done:return False
        if (safari_entry._RUN_CONTROLLER is not None or type(capture_transaction._SESSIONS) is not dict
                or any(type(s) is not dict or s.get('done') is not True for s in capture_transaction._SESSIONS.values())
                or any(c.waiting for c in league_native_wait._WAITS.values())
                or any(c.stage!='complete' for c in _FIELD_CONTROLLERS.values())
                or any(c.state!='complete' for c in _GYM_CONTROLLERS.values())):return False
    except Exception:return False
    return True


def _training_eof_context(pyboy,state,plan):
    if not league_training_proof.applies(plan):return None
    from .observation import read_visible_text
    from .rocket_movement import read_rocket_movement
    step=plan.get('steps',[])[-1] if plan.get('steps') else {}
    key=(league_training_proof.JOB,step.get('id'))
    if not _training_peers_clear():return league_training_proof._fail(key,'active_field_or_legacy_owner')
    try:
        return league_training_proof.context(state,plan,text=read_visible_text(pyboy),
            grid=read_world_grid(pyboy,state['location']),
            movement=read_rocket_movement(pyboy,observation_frame=state.get('frame')),
            native_owner=pyboy,peers_clear=True,
            full_party_healed=healthy(state['progress'],require_full_pp=True),validation=league_training_supervisor,
            stored_batch_proof=_TRAINING_BATCH_PROOFS.get(step.get('id')))
    except Exception:
        return league_training_proof._fail(key,'readonly_world_getter_failed')


def _e4_coordinate_context(pyboy,state,step,text,previous):
    """接同frame已release的原生owner；保原生終點見證後才普通走近NPC。"""
    c=league_native_wait._WAITS.get(step.get('id'));point=state.get('location',{})
    at_target=[point.get('x'),point.get('y')]==step.get('target')
    grid=read_world_grid(pyboy,point) if at_target else None
    return e4_coordinate.at_target(pyboy,state,step,text,grid,previous,
        native_controller=c,now=getattr(c,'last_now',None))


def switch_context(pyboy,state,plan,step_id,previous):
    fnt_abort=_training_fnt_abort_review_context(pyboy,state,plan,step_id)
    if fnt_abort is not None:return fnt_abort
    escape_abort=_training_escape_abort_review_context(pyboy,state,plan,step_id)
    if escape_abort is not None:return escape_abort
    proof_guard=_training_proof_owner_guard(pyboy,plan)
    if proof_guard is not None:return proof_guard
    east_entry=_victory_east_entry_context(pyboy,state,plan,step_id)
    if east_entry is not None:return east_entry
    ladder=_victory_ladder_settle_context(pyboy,state,plan,step_id)
    if ladder is not None:return ladder
    native_fall=_reviewed_native_fall_context(pyboy,state,plan,step_id)
    if native_fall is not None:return native_fall
    medicine=_owned_field_medicine_context(pyboy,state,plan,step_id,previous)
    if medicine is not None:return medicine
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    league_field=_league_field_context(pyboy,state,plan,step_id,step,previous)
    if league_field is not None:return league_field
    active_medicine=trainer_medicine_ui_bridge._active()
    if active_medicine:
        bindings=trainer_medicine_ui_bridge._BINDINGS
        if (len(active_medicine)!=1 or any(type(bindings.get(owner)) is not dict
                or bindings[owner].get('step_id')!=step_id for owner in active_medicine)):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'trainer_medicine_owner_changed'},step_id)
        from .observation import read_visible_text
        return trainer_medicine_dispatch.context(pyboy,state,plan,step_id,read_visible_text(pyboy),previous)
    native_active=any(c.waiting for c in league_native_wait._WAITS.values())
    native_signature=league_native_wait._signature(step)
    native_location=state.get('location',{}) if isinstance(state,dict) else {}
    native_ready=(native_signature is not None and native_location.get('map_id')==step['map_id']
        and (step['map_id']!=33 or [native_location.get('x'),native_location.get('y')]==[29,4]
             or step_id in league_native_wait._WAITS))
    if native_active or native_ready:
        from .observation import read_visible_text
        native_text=read_visible_text(pyboy)
        native=league_native_wait.context(pyboy,state,step,native_text,previous,
            now=_native_wait_clock(step_id,state.get('frame')),
            review_capsule=plan.get('native_dialogue_review'),
            checkpoint_resume_capsule=plan.get('checkpoint_resume_capsule'),
            final_a_review_capsule=plan.get('native_final_a_review'))
        if native is not None:
            if native.get('phase')=='overworld' and native.get('available_actions')==['wait']:
                native={**native,'phase':'league_native_wait'}
            return native,step_id
        if step['map_id'] in e4_coordinate.CONFIG and not satisfied(step,state['progress']):
            coordinate=_e4_coordinate_context(pyboy,state,step,native_text,previous)
            if coordinate is not None:return coordinate,step_id
    if fly_viridian_bridge.applies(step_id,step):
        active_fly=set(fly_viridian_bridge._BINDINGS)-fly_viridian_bridge._COMPLETED
        if active_fly and active_fly!={step_id}:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'fly_viridian_owner_changed'},step_id)
        bridges=(battle_medicine_bridge,mansion_secret_key_bridge,mansion_statue_bridge,
                 mansion_transition_ready,mansion_native_landing,route21_water_bridge,
                 pallet_surf_bridge,fly_pallet_bridge,safari_entry,hm_teaching_bridge,
                 vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,
                 player_pc_bridge,cinnabar_purchase_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'fly_viridian_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return fly_viridian_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                          read_world_grid(pyboy,state['location']),previous)
    if battle_medicine_bridge.applies(step_id,step):
        if battle_medicine_bridge._signature(step_id,step) is None:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'blaine_supply_fixed_step_unverified'},step_id)
        bridges=(mansion_secret_key_bridge,mansion_statue_bridge,mansion_transition_ready,
                 mansion_native_landing,route21_water_bridge,pallet_surf_bridge,
                 fly_pallet_bridge,safari_entry,hm_teaching_bridge,vending_bridge,
                 saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
                 cinnabar_purchase_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'blaine_supply_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return blaine_supply_dispatch.context(pyboy,state,plan,step_id,read_visible_text(pyboy),previous)
    if step and 'opponent_review' in step:
        from .observation import read_visible_text
        opponent_gate=opponent_review_gate.context(state,step,read_visible_text(pyboy),previous=previous,
            signal=opponent_review_gate.read_intro_signal(pyboy),owner=pyboy)
        if opponent_gate is not None:return opponent_gate,step_id
    if trainer_medicine_ui_bridge.applies(step_id,step):
        from .observation import read_visible_text
        medicine=trainer_medicine_dispatch.context(pyboy,state,plan,step_id,read_visible_text(pyboy),previous)
        if medicine is not None:return medicine
    if cinnabar_purchase_bridge.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_statue_bridge,mansion_transition_ready,
                 mansion_native_landing,route21_water_bridge,pallet_surf_bridge,
                 fly_pallet_bridge,safari_entry,hm_teaching_bridge,vending_bridge,
                 saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
                 campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'cinnabar_purchase_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return cinnabar_purchase_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                                read_world_grid(pyboy,state['location']),previous)
    if mansion_secret_key_bridge.applies(step_id,step):
        bridges=(mansion_statue_bridge,mansion_transition_ready,mansion_native_landing,
                 route21_water_bridge,pallet_surf_bridge,fly_pallet_bridge,safari_entry,
                 hm_teaching_bridge,vending_bridge,saffron_guard_bridge,silph_card_bridge,
                 lapras_bridge,player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_secret_key_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return mansion_secret_key_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                                read_world_grid(pyboy,state['location']),previous)
    if mansion_statue_bridge.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_transition_ready,mansion_native_landing,route21_water_bridge,pallet_surf_bridge,
                 fly_pallet_bridge,safari_entry,hm_teaching_bridge,vending_bridge,
                 saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
                 campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_statue_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return mansion_statue_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                               read_world_grid(pyboy,state['location']),previous)
    if route21_water_bridge.applies(step_id,step):
        bridges=(pallet_surf_bridge,fly_pallet_bridge,safari_entry,hm_teaching_bridge,
                 vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,
                 player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'route21_water_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return route21_water_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                            read_world_grid(pyboy,state['location']),previous)
    if pallet_surf_bridge.applies(step_id,step):
        if (set(fly_pallet_bridge._BINDINGS)-fly_pallet_bridge._COMPLETED
                or set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED
                or set(player_pc_bridge._BINDINGS)-player_pc_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'pallet_surf_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return pallet_surf_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                          read_world_grid(pyboy,state['location']),previous)
    if fly_pallet_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED
                or set(player_pc_bridge._BINDINGS)-player_pc_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'fly_pallet_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return fly_pallet_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                         read_world_grid(pyboy,state['location']),previous)
    if player_pc_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'player_pc_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return player_pc_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                        read_world_grid(pyboy,state['location']),previous)
    if not step or step['kind']!='gym_switches':return None
    GymSwitchController=gym_switches_module.GymSwitchController
    from .observation import read_visible_text
    loc=state['location'];grid=read_world_grid(pyboy,loc)
    blocked=[tuple(p) for p in plan.get('blocked',{}).get(str(loc['map_id']),[])]
    npcs=world_map.read_npc_obstacles(pyboy,grid,blocked) if grid else None
    if npcs:blocked=list(set(blocked)|set(npcs['positions']))
    controller=_GYM_CONTROLLERS.setdefault(step_id,GymSwitchController())
    controller.__class__=GymSwitchController
    revision=step.get('reviewed_controller_revision',0)
    if revision>getattr(controller,'_reviewed_revision',0) and controller._review_reason==step.get('reviewed_controller_error'):
        controller._review_reason=None;controller._reviewed_revision=revision
    context=controller.context(read_visible_text(pyboy),loc,state['progress'],grid,battle_state=state.get('battle_state'),previous=previous,blocked=blocked)
    if context is None:return None
    next_id=step_id
    if context.get('gym_switches_complete'):
        index=plan['steps'].index(step)+1
        next_id=plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete'
    return context,next_id


def _training_batch_eof_attrition_context(pyboy,state,plan,step_id,attrition):
    """Let a verified completed batch finish its WAIT/EOF before returning to nurse."""
    if (step_id!='complete' or type(plan) is not dict
            or plan.get('training_job')!=league_training_supervisor.JOB
            or plan.get('training_supervisor')!=league_training_proof.MARKER
            or type(attrition) is not dict or attrition.get('review_reason')!='party_attrition_requires_center'
            or attrition.get('party_attrition',{}).get('fainted_party_indices')!=[]):return None
    steps=plan.get('steps');step=steps[-1] if type(steps) is list and steps else {}
    if step.get('mechanic')!='league_training_batch':return None
    def reject():
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='training_completed_batch_attrition_proof_unverified'),'complete'
    try:
        stored=_TRAINING_BATCH_PROOFS.get(step['id']);v=league_training_supervisor
        if (not _training_peers_clear() or type(stored) is not dict
                or stored.get('job')!=v.JOB or stored.get('owner_step')!=step['id']
                or stored.get('step_sha256')!=v.canonical_sha(step)
                or stored.get('location')!=state.get('location')
                or stored.get('progress_sha256')!=v.canonical_sha(state['progress'])):return reject()
        v.validate_party(state['progress']);v._stored_receipt(stored)
        frame=state['frame'];last=stored['closed_frames'][-1]
        if type(frame) is not int or type(last) is not int or frame<last:return reject()
        if frame>last:return _training_eof_context(pyboy,state,plan),'complete'
        from .observation import read_visible_text
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        b=league_training_batch_bridge.batch
        signal=b.read_training_observation(pyboy,frame,sdk)
        if (signal.get('read_valid') is not True or signal.get('idle') is not True
                or signal.get('progress')!=state['progress'] or signal.get('battle')!=state['battle_state']
                or not b.closed_world(read_visible_text(pyboy),read_world_grid(pyboy,state['location']),
                    (state['location']['x'],state['location']['y']),frame)):return reject()
        return dict(phase='training_batch_owned',objective='Wait.',available_actions=['wait'],
            training_completed_batch_attrition_wait=True,suppress_navigation_stall=True,
            suppress_blocked_edge_learning=True),'complete'
    except (AttributeError,KeyError,TypeError,ValueError,IndexError,league_training_supervisor.ReviewRequired):return reject()


def attrition_transition_context(pyboy,state,plan,step_id,attrition,previous=()):
    """只將已綁Lapras的來源命名未初始化過渡交專屬reader；其他損耗照常停。"""
    fnt_abort=_training_fnt_abort_review_context(pyboy,state,plan,step_id)
    if fnt_abort is not None:return fnt_abort
    escape_abort=_training_escape_abort_review_context(pyboy,state,plan,step_id)
    if escape_abort is not None:return escape_abort
    proof_guard=_training_proof_owner_guard(pyboy,plan)
    if proof_guard is not None:return proof_guard
    completed_batch=_training_batch_eof_attrition_context(pyboy,state,plan,step_id,attrition)
    if completed_batch is not None:return completed_batch
    active_eof=league_training_proof._active()
    if active_eof:return league_training_proof._fail(next(iter(active_eof)),'attrition_during_eof'),'complete'
    medicine=_owned_field_medicine_context(pyboy,state,plan,step_id,previous,attrition)
    if medicine is not None:return medicine
    hyper_steps=plan.get('steps',[]) if type(plan) is dict else []
    hyper_step=next((x for x in hyper_steps if type(x) is dict and x.get('id')==step_id),None) if type(hyper_steps) is list else None
    if overworld_hyper_bridge.applies(step_id,hyper_step):
        # 先過同一完整互斥，才讀畫面；只有原明示藥步與無FNT的requires_center可進。
        if (isinstance(attrition,dict) and attrition.get('review_reason')=='party_attrition_requires_center'
                and attrition.get('party_attrition',{}).get('fainted_party_indices')==[]
                and isinstance(state.get('progress',{}).get('party'),list)
                and all(type(m.get('hp')) is int and m['hp']>0 and m.get('status')==0 for m in state['progress']['party'])):
            return _league_field_context(pyboy,state,plan,step_id,hyper_step,previous)
        return None
    if league_training_batch_bridge._active()=={step_id}:
        peers=_field_medicine_peers()
        if (type(peers) is not dict or set(peers)!=owned_field_medicine.PEER_NAMES
                or any(type(v) is not set or v!=({step_id} if k=='league_training_batch' else set())
                       for k,v in peers.items())):
            return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='eevee37_attrition_peer_inventory_unverified'),step_id
        from .observation import read_visible_text
        text=read_visible_text(pyboy)
        switch_clock=None
        if training_switch_review.applies(state,step_id):
            hint,switch_clock=training_switch_review.context(pyboy,state,plan,step_id,text,
                bridge=league_training_batch_bridge,peers=peers)
            if hint is not None:return hint,step_id
        hint,clock=_eevee37_owned_learning_context(pyboy,state,plan,step_id,text)
        if hint is not None:return hint,step_id
        if clock is None:clock=switch_clock
        learning_clock={'now':clock} if clock is not None else {}
        closure=league_training_batch_bridge.pre_attrition_closure_context(pyboy,state,plan,step_id,attrition,
            text,read_world_grid(pyboy,state['location']),previous,**learning_clock)
        if closure is not None:return _retain_training_batch_proof(state,plan,closure,native_owner=pyboy)
    if (not isinstance(attrition,dict)
            or attrition.get('review_reason')!='party_attrition_state_unverified'
            or attrition.get('party_attrition',{}).get('issue')!='party_read_not_verified'):
        return None
    from .observation import read_visible_text
    return lapras_bridge.pre_attrition_context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                              read_world_grid(pyboy,state['location']))


def field_context(pyboy,state,plan,step_id):
    """僅精確field步驟可接管HM UI；其他未知學招仍由主程序暫停。"""
    fnt_abort=_training_fnt_abort_review_context(pyboy,state,plan,step_id)
    if fnt_abort is not None:return fnt_abort
    escape_abort=_training_escape_abort_review_context(pyboy,state,plan,step_id)
    if escape_abort is not None:return escape_abort
    proof_guard=_training_proof_owner_guard(pyboy,plan)
    if proof_guard is not None:return proof_guard
    east_entry=_victory_east_entry_context(pyboy,state,plan,step_id)
    if east_entry is not None:return east_entry
    ladder=_victory_ladder_settle_context(pyboy,state,plan,step_id)
    if ladder is not None:return ladder
    native_fall=_reviewed_native_fall_context(pyboy,state,plan,step_id)
    if native_fall is not None:return native_fall
    if (recovery_field_medicine.applies(plan,step_id,shared=owned_field_medicine)
            or owned_field_medicine.applies(plan,step_id)):return None
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if any(b.applies(step_id,step) for b in _LEAGUE_FIELDS):return None
    if (any(c.waiting for c in league_native_wait._WAITS.values())
            or league_native_wait._signature(step) is not None):
        return None  # 原生走位與intro只交有真previous的switch，不由field提早接管。
    if trainer_medicine_ui_bridge.applies(step_id,step):
        return None  # 真previous、補藥UI與後續既有battle只由switch_context接管。
    if fly_viridian_bridge.applies(step_id,step):
        return None  # 同一飛行交易與真previous只交switch_context。
    if battle_medicine_bridge.applies(step_id,step):
        return None  # 真previous與所有補藥／敵回合頁面由switch_context接管。
    if step and 'opponent_review' in step:
        return None  # 對戰intro必須接switch_context的真實previous。
    if cinnabar_purchase_bridge.applies(step_id,step):
        return None  # 固定購藥交易只由switch_context接主runner真previous。
    if mansion_secret_key_bridge.applies(step_id,step):
        return None  # 祕密鑰匙只由switch_context接主runner真previous。
    if mansion_transition_ready.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_native_landing,mansion_statue_bridge,route21_water_bridge,
                 pallet_surf_bridge,fly_pallet_bridge,safari_entry,hm_teaching_bridge,
                 vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,
                 player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_transition_other_transaction_active'},step_id)
        from .observation import read_visible_text
        text=read_visible_text(pyboy);grid=read_world_grid(pyboy,state['location'])
        reviewed=_review_mansion_standing_warp(pyboy,state,plan,step,text,grid)
        if reviewed is not None:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':reviewed},step_id)
        return mansion_transition_ready.context(pyboy,state,plan,step_id,text,grid)
    if mansion_native_landing.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_transition_ready,mansion_statue_bridge,route21_water_bridge,pallet_surf_bridge,fly_pallet_bridge,safari_entry,
                 hm_teaching_bridge,vending_bridge,saffron_guard_bridge,silph_card_bridge,
                 lapras_bridge,player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_landing_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return mansion_native_landing.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                               read_world_grid(pyboy,state['location']))
    if mansion_statue_bridge.applies(step_id,step):
        return None  # 原生雕像提示必由switch_context接真previous。
    if route21_water_bridge.applies(step_id,step):
        return None  # 第一個野戰觀測也先接真previous，水步收據後才交battle。
    if pallet_surf_bridge.applies(step_id,step):
        return None  # 下水全程由switch_context接真previous。
    if fly_pallet_bridge.applies(step_id,step):
        return None  # 由switch_context接真previous，攔截完整飛行直到落地閉合。
    if player_pc_bridge.applies(step_id,step):
        return None  # switch_context收到主runner真previous後才可推進PC交易。
    if lapras_bridge.applies(step_id,step):
        from .observation import read_visible_text
        return lapras_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                     read_world_grid(pyboy,state['location']))
    if silph_card_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'silph_card_bridge_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return silph_card_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                        read_world_grid(pyboy,state['location']))
    if saffron_guard_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'saffron_guard_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return saffron_guard_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                            read_world_grid(pyboy,state['location']))
    if vending_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'vending_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return vending_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                      read_world_grid(pyboy,state['location']))
    if hm_teaching_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'hm_teaching_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return hm_teaching_bridge.context(state,plan,step_id,read_visible_text(pyboy),
                                          read_world_grid(pyboy,state['location']))
    if safari_entry.applies(step_id,step,state):
        from .observation import read_visible_text
        return safari_entry.field_context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                         read_world_grid(pyboy,state['location']))
    if capture_transaction.applies(step_id,step):
        from .observation import read_visible_text
        closing=capture_closing_gate.eligible(state,plan,step_id)
        result=capture_transaction.context(pyboy,state,plan,step_id,read_visible_text(pyboy),read_world_grid(pyboy,state['location']))
        return capture_closing_gate.restrict(result) if closing else result
    if step and step.get('mechanic')=='sabrina_native_warp':
        if (set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'sabrina_native_warp_other_transaction_active'},step_id)
        return None  # 原生傳送由waypoint拿真previous動作序列；不交泛用interact交易。
    if campaign_transactions.applies(step_id,step):
        from .observation import read_visible_text
        return campaign_transactions.context(pyboy,state,plan,step_id,read_visible_text(pyboy),read_world_grid(pyboy,state['location']))
    if (step and step.get('kind')=='move' and plan.get('training_shared_experience') is True
            and plan.get('mode')=='league_campaign'):
        training=balanced_training.shared_experience_battle_context(pyboy,state,plan)
        if training is not None:return training,step_id
    if not step:return None
    if step['kind'] not in {'teach_cut','use_cut'}:return None
    if state.get('battle_state',{}).get('kind')!='none':return None
    loc=dict(state['location'])
    if loc['map_id']!=step['map_id'] or [loc['x'],loc['y']]!=step['target']:return None
    from .observation import read_visible_text
    CutController=field_moves_module.CutController
    loc['facing']={0:'down',4:'up',8:'left',12:'right'}.get(int(pyboy.memory[0xC109]))
    grid=read_world_grid(pyboy,loc)
    controller=_FIELD_CONTROLLERS.get(step_id)
    if controller is not None:
        controller.__class__=CutController
        revision=step.get('reviewed_controller_revision',0)
        if revision>getattr(controller,'_reviewed_revision',0) and controller.error==step.get('reviewed_controller_error'):
            controller.error=None;controller._reviewed_revision=revision
    if controller is None:
        if grid is None:return None
        if step['kind']=='use_cut' and loc['facing']!=step.get('face'):
            direction=step['face']
            return ({'phase':'field_move_menu','objective':f'Move {direction.upper()}.','available_actions':[direction,'wait'],'controller_menu_verified':True},step_id)
        candidates=[m['species'] for m in state['progress'].get('party',[])
                    if type(m.get('species')) is int and m['species'] in {9,154}
                    and (step['kind']=='teach_cut' or 15 in m.get('moves',[]))]
        if state['progress'].get('party_read_valid') is not True or len(candidates)!=1:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'unique_current_cut_user_unverified'},step_id)
        intent={'kind':step['kind'],'species':candidates[0],'replace_move':45}
        if step['kind']=='use_cut':intent.update(map_id=step['map_id'],tree_x=step['tree'][0],tree_y=step['tree'][1],tileset_id=step.get('tileset_id',0))
        controller=CutController(intent);_FIELD_CONTROLLERS[step_id]=controller
    reviewed_cut=_review_cut_six_party(controller,step,state)
    if reviewed_cut is not None:
        return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                 'review_reason':reviewed_cut},step_id)
    context=controller.context(read_visible_text(pyboy),state['progress'],location=loc,grid=grid,overworld_ready=grid is not None,battle_active=False)
    next_id=step_id
    if context.get('field_move_complete'):
        index=plan['steps'].index(step)+1
        next_id=plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete'
    return context,next_id


def _review_cut_six_party(controller,step,state):
    """僅續接16號路已選妙蛙花的六人背景誤拒；不重建Cut基線或等待額度。"""
    revision=step.get('reviewed_cut_six_party_revision')
    if revision is None or getattr(controller,'_reviewed_cut_six_party_revision',None)==revision:return None
    party=state.get('progress',{}).get('party',[])
    baseline=[(m.get('species'),list(m.get('moves',[]))) for m in party]
    if (type(revision) is not int or revision!=1 or state.get('frame')!=1436457
            or state.get('location')!={'map_id':27,'x':34,'y':10}
            or step.get('id')!='route16-native-cut' or step.get('kind')!='use_cut'
            or step.get('tree')!=[34,9] or step.get('map_id')!=27
            or controller.error!='cut_field_submenu_cursor_unverified'
            or controller.stage!='choose_user' or controller.field_user_confirmed is not True
            or controller.target_index!=3 or len(party)!=6 or party[3].get('species')!=154
            or controller.baseline!=baseline
            or controller.start_location!={'map_id':27,'x':34,'y':10,'facing':'up'}):
        return 'cut_six_party_named_review_unverified'
    controller.error=None;controller._reviewed_cut_six_party_revision=revision
    return None


def _review_mansion_standing_warp(pyboy,state,plan,step,text,grid):
    """只扣除已固定工程停檢的牆鐘；保留原交易與已耗用的全部預算。"""
    revision=step.get('reviewed_standing_warp_revision')
    if revision is None:return None
    module=mansion_transition_ready;r=module._CONTROLLERS.get(step.get('id'))
    if r is not None and r.get('reviewed_standing_warp_revision')==revision:return None
    reason='mansion_standing_warp_named_review_unverified'
    expected_binding=((216,23,22),165,(21,23),json.dumps('mansion-basement-approach-20261024',sort_keys=True,allow_nan=False))
    if (type(revision) is not int or revision!=1 or step.get('id')!='mansion-basement-stairs-ready-20261024'
            or plan.get('training_job')!='mansion-basement-approach-20261024'
            or step.get('map_id')!=216 or step.get('target')!=[23,22]
            or state.get('frame')!=1466785 or state.get('location')!={'map_id':216,'x':23,'y':22}
            or r is None or r.get('error') is not None or r.get('last_frame')!=1466785
            or r.get('waits')!=26 or r.get('calls')!=26 or r.get('closed_frame') is not None
            or module._BINDINGS.get(step['id'])!=expected_binding
            or set(module._BINDINGS)-module._COMPLETED!={step['id']}):return reason
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal=module.read_transition_movement(pyboy,observation_frame=state['frame'],constants=constants)
    p=state.get('progress');battle=state.get('battle_state',{})
    if (not isinstance(p,dict) or module._party(p) is None
            or (module._party(p),module._inventory(p.get('inventory')),p.get('money'))!=r['baseline']
            or signal.get('read_valid') is not True or signal.get('switch_on') is not True
            or signal.get('location')!=state['location'] or signal.get('movement_flags')!=4
            or any(signal.get(k)!=0 for k in ('simulated_remaining','joy_ignore','walk_counter'))
            or battle.get('active') is not False or battle.get('kind')!='none' or battle.get('raw')!=0
            or battle.get('observation_frame')!=state['frame']
            or module._text_status(text) is not True
            or module._grid_status(grid,state['frame'],state['location'],0x13) is not True):return reason
    now=time.monotonic();started,last=r.get('started'),r.get('last_now')
    if (any(type(v) not in (int,float) for v in (started,last,now))
            or not 0<=started<=last<=now or last-started>module.MAX_SECONDS):return reason
    excluded=now-last
    r['started']+=excluded;r['last_now']=now
    r['review_excluded_seconds']=r.get('review_excluded_seconds',0)+excluded
    r['review_elapsed_preserved']=last-started
    r['reviewed_standing_warp_revision']=revision
    return None


def satisfied(step,progress):
    if 'event' in step:return progress['story_event_bits'].get(step['event']) is True
    if 'item' in step:return any(i['item']==step['item'] for i in progress.get('inventory') or [])
    if 'badge' in step:return bool((progress.get('badges_raw') or 0)&step['badge'])
    return False


def attack_pp(mon):
    from .team_strategy import effective_power
    return sum(pp&63 for move,pp in zip(mon.get('moves',[]),mon.get('pp',[])) if effective_power(move,mon.get('species'))>0)


def healthy(progress, *, require_full_pp=False):
    party=progress['party']
    if require_full_pp:
        from .team_strategy import reference,move_key
        for mon in party:
            moves,pp=mon.get('moves'),mon.get('pp')
            if (not isinstance(moves,(list,tuple)) or not isinstance(pp,(list,tuple))
                    or len(moves)!=4 or len(pp)!=4):return False
            for move,remaining in zip(moves,pp):
                if type(move) is not int or type(remaining) is not int:return False
                if move==0:
                    if remaining!=0:return False
                    continue
                key=move_key(move)
                base=reference()['moves'].get(key,{}).get('pp')
                if type(base) is not int or remaining!=base:return False
    return bool(party) and all(m['hp']==m['max_hp'] and not m.get('status',0) for m in party) and attack_pp(party[0])>=3


def coordinate_script_wait(state, step):
    """固定來源嘎啦嘎啦／Silph勁敵與坂木座標等待；不輸出方向或A。"""
    if step.get('map_id') == 235 or step.get('event') == 'beat_silph_co_giovanni':
        return silph_giovanni_wait.silph_giovanni_script_wait(state,step)
    if step.get('map_id') == 212 or step.get('event') == 'beat_silph_co_rival':
        return silph_rival_wait.silph_rival_script_wait(state,step)
    def review(reason):
        return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                'review_reason':reason,'route_step':step['id']}
    if (step.get('await_script_event') is not True or step.get('kind')!='move'
            or step.get('map_id')!=147 or step.get('target')!=[10,16]
            or step.get('event')!='beat_ghost_marowak'):
        return review('coordinate_script_intent_unverified')
    battle=state.get('battle_state',{});progress=state.get('progress',{})
    if (battle.get('kind')!='none' or battle.get('active') is not False
            or progress.get('party_read_valid') is not True
            or progress.get('story_event_bits',{}).get('beat_ghost_marowak') is not False
            or not any(i.get('item')==72 and type(i.get('quantity')) is int and i['quantity']>0
                       for i in progress.get('inventory') or [])):
        return review('coordinate_script_prerequisites_unverified')
    now=time.monotonic();record=_SCRIPT_WAITS.setdefault(step['id'],{'started':now,'calls':0})
    record['calls']+=1
    if record['calls']>25 or now-record['started']>60:
        return review('coordinate_script_wait_exhausted')
    return {'phase':'overworld','objective':'Wait.','available_actions':['wait'],
            'goal':step['id'],'route_step':step['id'],'source_coordinate_script_wait':True,
            'source_commit':'a53671100ec22e5394ff26ec028d0812a238dae2',
            'phase_source':'PokemonTower6F.asm:25-47；保留10,16，讓原生座標腳本啟動，不把到站當成戰勝。'}


def _via_target(plan,step,position):
    """只消費實際抵達的下一中繼點；暫停、戰鬥與熱載入不重設游標。"""
    via=step.get('via',[])
    if not via:return step.get('target',list(position))
    # 工程解除的resume_revision與blocked修正不是新旅程；幾何或job改變才另建進度。
    fields=('id','kind','map_id','target','via','next_map','terminal',
            'event','item','badge','await_script_event','face','require_full_pp',
            'mechanic','landing','offpad')
    geometry=[{key:s[key] for key in fields if key in s} for s in plan['steps']]
    canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    job=plan.get('training_job')
    scope=('training_job',canonical(job)) if job not in (None,'',{},[]) else ('unscoped_route',)
    key=(scope,canonical(geometry),step['id'])
    following=_VIA_PROGRESS.get(key,0)
    while following<len(via) and tuple(via[following])==position:
        following+=1
    _VIA_PROGRESS[key]=following
    return via[following] if following<len(via) else step.get('target',list(position))


def native_warp_context(pyboy,state,step,previous):
    """全部getter在原模擬器同一frame；controller只給候選，不自行按鍵。"""
    from .observation import read_visible_text
    from .rocket_movement import read_rocket_movement
    grid=read_world_grid(pyboy,state['location'])
    return sabrina_native_warp.context(state,step,read_visible_text(pyboy),grid,
        read_rocket_movement(pyboy,observation_frame=state['frame']),previous)


def _reviewed_npc_edge_retry(state,step,grid,npcs,ready):
    """父層核正常出入館後，只撤銷該NPC曾擋住的一條導航快取。"""
    global _LAST_ATTEMPT
    marker=step.get('reviewed_npc_edge_retry')
    if marker is None:return None
    if (type(marker) is not dict or set(marker)!={'kind','frame','from','to'}
            or marker.get('kind')!='trainer_reset_after_normal_exit_v1'
            or type(marker.get('frame')) is not int or marker['frame']<0
            or marker.get('from')!=[10,4] or marker.get('to')!=[10,3]
            or any(type(v) is not int for k in ('from','to') for v in marker[k])):
        return 'npc_edge_retry_marker_unverified'
    key=(step['id'],json.dumps(marker,sort_keys=True))
    if key in _REVIEWED_NPC_EDGE_RETRIES:return None
    if (step.get('kind')!='move' or step.get('map_id')!=45
            or state.get('frame')!=marker['frame'] or type(state.get('frame')) is not int
            or state.get('location')!={'map_id':45,'x':10,'y':4} or ready is not True
            or not isinstance(grid,dict) or grid.get('observation_frame')!=marker['frame']
            or type(grid.get('observation_frame')) is not int
            or grid.get('verified_location')!=[45,10,4] or type(grid.get('screen_cells_verified')) is not int
            or grid['screen_cells_verified']<12 or not isinstance(npcs,dict)
            or type(npcs.get('source_anchor_matches')) is not int or npcs['source_anchor_matches']<9):
        return 'npc_edge_retry_closed_world_unverified'
    raw_positions=npcs.get('positions')
    if (not isinstance(raw_positions,(list,tuple))
            or any(not isinstance(p,(list,tuple)) or len(p)!=2
                   or any(type(v) is not int for v in p) for p in raw_positions)):
        return 'npc_edge_retry_trainer_reset_unverified'
    positions=set(map(tuple,raw_positions))
    try:free=grid['walkable'][4][10]==1 and grid['walkable'][3][10]==1
    except (KeyError,IndexError,TypeError):free=False
    edge=((10,4),(10,3))
    if not free or (10,3) in positions or not {(10,1),(13,5)}<=positions:
        return 'npc_edge_retry_trainer_reset_unverified'
    if edge not in _LEARNED_EDGES.get(45,set()):return 'npc_edge_retry_cached_edge_missing'
    _LEARNED_EDGES[45].discard(edge)
    if (_LAST_ATTEMPT and _LAST_ATTEMPT.get('key')==(45,10,4,step['id'])
            and _LAST_ATTEMPT.get('direction')=='up'):_LAST_ATTEMPT=None
    _REVIEWED_NPC_EDGE_RETRIES.add(key)
    return None


def waypoint(pyboy,state,plan,step_id,previous):
    global _LAST_ATTEMPT
    fnt_abort=_training_fnt_abort_review_context(pyboy,state,plan,step_id)
    if fnt_abort is not None:return fnt_abort
    escape_abort=_training_escape_abort_review_context(pyboy,state,plan,step_id)
    if escape_abort is not None:return escape_abort
    east_entry=_victory_east_entry_context(pyboy,state,plan,step_id)
    if east_entry is not None:return east_entry
    ladder=_victory_ladder_settle_context(pyboy,state,plan,step_id)
    if ladder is not None:return ladder
    native_fall=_reviewed_native_fall_context(pyboy,state,plan,step_id)
    if native_fall is not None:return native_fall
    steps=plan['steps'];ids=[s['id'] for s in steps]
    if len(ids)!=len(set(ids)):raise ValueError('路線ID重複')
    invalid=next((s for s in steps if s.get('mechanic')=='sabrina_native_warp'
                  and any(k in s for k in ('next_map','terminal','event','item','badge','await_script_event'))),None)
    if invalid is not None:
        return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                'review_reason':'sabrina_native_warp_generic_completion_forbidden','route_step':invalid['id']},invalid['id']
    index=len(steps) if step_id=='complete' else ids.index(step_id) if step_id in ids else 0
    loc=state['location'];progress=state['progress'];mid=loc['map_id'];x,y=loc['x'],loc['y']
    # 先承認已完成的轉場，再判斷補血繞路，避免「進中心→繞路出門→再進中心」循環。
    while index<len(steps) and (satisfied(steps[index],progress) or steps[index].get('next_map')==mid):index+=1
    current=steps[index] if index<len(steps) else {}
    lead=progress['party'][0] if progress.get('party') else None
    needs_heal=lead is not None and (lead['hp']*3<=lead['max_hp']*2 or lead.get('status',0) or attack_pp(lead)<3)
    detour=None
    if not plan.get('_detour'):
        if mid in {58,68,64} and current.get('map_id')!=mid:
            detour={'id':'detour-center','map_id':mid,'target':[3,3] if not healthy(progress) else [3,8],'kind':'heal' if not healthy(progress) else 'move','face':'up','terminal':True}
        elif mid==14 and needs_heal:detour={'id':'detour-return-pewter','map_id':14,'target':[-1,9],'kind':'move','terminal':True}
        elif mid==2 and current.get('map_id')==14:detour={'id':'detour-city','map_id':2,'target':[13,25] if not healthy(progress) else [40,17],'kind':'move','terminal':True}
        elif mid==35 and needs_heal:detour={'id':'detour-bridge-center','map_id':35,'target':[10,36],'kind':'move','terminal':True}
        elif mid==36 and needs_heal:detour={'id':'detour-route25-center','map_id':36,'target':[-1,8],'kind':'move','terminal':True}
        elif mid==35 and current.get('map_id')==36:detour={'id':'detour-return-route25','map_id':35,'target':[20,8],'kind':'move','terminal':True}
        elif mid==3 and current.get('map_id') in {35,36,88}:
            detour={'id':'detour-cerulean-center','map_id':3,'target':[19,17] if not healthy(progress) else [20,-1],'kind':'move','terminal':True}
    if detour:
        context,_=waypoint(pyboy,state,{'steps':[detour],'blocked':plan.get('blocked',{}),'_detour':True},detour['id'],previous)
        return context,current.get('id',step_id)
    # 只由實際執行的行程記錄失敗邊；外層主線不能清掉補血繞路的嘗試。
    if pyboy is not None and _LAST_ATTEMPT:
        old=_LAST_ATTEMPT
        if (mid,x,y,current.get('id'))==old['key'] and previous and previous[-1]==old['direction']:
            old['misses']+=1
            if old['misses']>=3:
                dx,dy={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}[old['direction']]
                _LEARNED_EDGES.setdefault(mid,set()).add(((x,y),(x+dx,y+dy)))
                _LAST_ATTEMPT=None
        else:_LAST_ATTEMPT=None
    while index<len(steps):
        step=steps[index]
        if satisfied(step,progress) or ('next_map' in step and mid==step['next_map']):index+=1;continue
        if mid!=step['map_id']:
            return {'phase':'campaign_review','review_reason':'unexpected_map','expected_map':step['map_id'],'route_step':step['id']},step['id']
        if step.get('mechanic')=='sabrina_native_warp':
            context=native_warp_context(pyboy,state,step,previous)
            if context is not None:
                if context.get('native_warp_complete') is True:
                    index+=1;continue
                return context,step['id']
        target=_via_target(plan,step,(x,y))
        target={'x':target[0],'y':target[1]}
        if 'await_script_event' in step and [x,y]==list(target.values()):
            if step['map_id'] in e4_coordinate.CONFIG:
                from .observation import read_visible_text
                coordinate=_e4_coordinate_context(pyboy,state,step,read_visible_text(pyboy),previous)
                if coordinate is None:
                    coordinate={'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                                'review_reason':'e4_coordinate_target_context_missing','route_step':step['id']}
                return coordinate,step['id']
            return coordinate_script_wait(state,step),step['id']
        if step['kind']=='heal' and healthy(progress,require_full_pp=step.get('require_full_pp') is True):index+=1;continue
        if step['kind']=='move' and [x,y]==list(target.values()) and 'next_map' not in step:index+=1;continue
        if (step['kind'] in {'teach_cut','use_cut','gym_switches'} or 'mechanic' in step) and [x,y]==list(target.values()):
            return {'phase':'overworld','objective':'Wait.','available_actions':['wait'],'goal':'field_transaction_pending'},step['id']
        if [x,y]==list(target.values()) and step['kind'] in {'interact','heal'}:
            direction=step.get('face','up')
            return {'phase':'overworld','objective':'Confirm the current selection.' if previous and previous[-1]==direction else f'Move {direction.upper()}.',
                    'available_actions':['a','b'] if previous and previous[-1]==direction else ['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'controller_interaction':True},step['id']
        grid=read_world_grid(pyboy,loc)
        blocked=[tuple(p) for p in plan.get('blocked',{}).get(str(mid),[])]
        from .observation import read_visible_text
        ready=campaign_transactions.ui_overworld_ready(read_visible_text(pyboy),grid) if pyboy is not None and grid else False
        if victory_road_navigation.applies(mid):
            npcs=victory_road_navigation.read_victory_road_npcs(pyboy,grid,loc,
                world_map_module=world_map,boulder_module=victory_later_boulders_bridge.boulder,
                overworld_ready=ready)
            if not npcs or npcs.get('read_valid') is not True:
                east_entry=_victory_east_entry_context(pyboy,state,plan,step['id'])
                if east_entry is not None:return east_entry
                ladder=_victory_ladder_settle_context(pyboy,state,plan,step['id'])
                if ladder is not None:return ladder
                return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                        'review_reason':npcs.get('review_reason','victory_navigation_receipt_missing') if isinstance(npcs,dict)
                                        else 'victory_navigation_receipt_missing'},step['id']
            blocked=victory_road_navigation.blocked_for_move(blocked,npcs,location=loc,target=target)
            if blocked is None:
                return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                        'review_reason':'victory_navigation_current_object_at_target'},step['id']
        else:
            npcs=(world_map.read_npc_obstacles(pyboy,grid,blocked,overworld_ready=True) if ready
                  else world_map.read_npc_obstacles(pyboy,grid,blocked)) if grid else None
            if npcs:
                hidden=npcs.get('hidden_source_positions',[]) if npcs.get('toggle_source_calibrated') is True else []
                blocked=list((set(blocked)-set(map(tuple,hidden)))|set(npcs['positions']))
        retry_error=_reviewed_npc_edge_retry(state,step,grid,npcs,ready)
        if retry_error:
            return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                    'review_reason':retry_error},step['id']
        cleared=[]
        if mid==3:
            if progress['story_event_bits'].get('got_ss_ticket'):cleared.append((27,12))
            if any(i['item']==228 for i in progress.get('inventory') or []):cleared.append((30,8))
        if mid==88 and progress['story_event_bits'].get('bill_said_use_cell_separator'):cleared.append((6,5))
        if mid==61:
            if progress['story_event_bits'].get('got_helix_fossil'):cleared.append((13,6))
            if progress['story_event_bits'].get('got_dome_fossil'):cleared.append((12,6))
        blocked=[p for p in blocked if p not in cleared]
        learned=_LEARNED_EDGES.get(mid,set())
        hint=world_direction(grid,loc,target,blocked,learned) if grid else None
        if not hint and abs(target['x']-x)+abs(target['y']-y)==1 and step.get('terminal') and ((x,y),(target['x'],target['y'])) not in learned:
            direction='up' if target['y']<y else 'down' if target['y']>y else 'left' if target['x']<x else 'right'
            hint={'direction':direction,'kind':'source_verified_terminal_step','path_length':1}
        if hint:
            if npcs:hint['npc_obstacles']=npcs
            if cleared:hint['cleared_story_objects']=cleared
            if learned:hint['observed_blocked_edges']=[list(edge) for edge in sorted(learned)]
            key=(mid,x,y,step['id'])
            if pyboy is not None and (_LAST_ATTEMPT is None or _LAST_ATTEMPT['key']!=key or _LAST_ATTEMPT['direction']!=hint['direction']):
                _LAST_ATTEMPT={'key':key,'direction':hint['direction'],'misses':0}
            # 唯一已復核的21033停檢：讓真邊界DOWN執行一次，解除舊連續停滯值。
            # 下一frame回原30次停滯檢查；不修改任何field交易的預算或pending。
            retry=(step['id']=='root-calibration-game29-20261028-out-004'
                and state.get('frame')==21033 and pyboy is not None and pyboy.frame_count==21033
                and plan.get('training_job')=='league-six-party45-game29-20261028'
                and loc=={'map_id':174,'x':7,'y':11} and target=={'x':7,'y':12}
                and ready is True and hint.get('kind')=='map_exit' and hint.get('direction')=='down'
                and grid.get('observation_frame')==21033
                and owned_field_medicine.canonical_sha256(progress)=='5dc6640dd6a7fd7800818a662ab1f9ccb3e966cf68bc32089c93a79fc4239eb0')
            extra=({'suppress_navigation_stall':True,'suppress_blocked_edge_learning':True,
                    'reviewed_boundary_exit_retry':True} if retry else {})
            return {'phase':'overworld','objective':f"Move {hint['direction'].upper()}.",'available_actions':['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'world_path_hint':hint,**extra},step['id']
        return {'phase':'overworld','objective':'Wait.','available_actions':['wait','b'],'navigation_warning':'no_verified_path',
                'goal':step['id'],'route_step':step['id']},step['id']
    training_proof=_training_eof_context(pyboy,state,plan)
    if training_proof is not None:return training_proof,'complete'
    return {'phase':'campaign_review','review_reason':'route_extension_required','route_step':'complete'},'complete'
