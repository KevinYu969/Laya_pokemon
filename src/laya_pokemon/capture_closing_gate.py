"""低血時僅允許已選NO的捕獲交易完成野外WAIT驗收；不能導航或投球。"""
from . import capture_transaction as tx
from . import capture_completion as completion


def eligible(state, plan, step_id):
    if plan.get('mode') != 'league_campaign': return False
    active = {key for key, value in tx._SESSIONS.items() if not value.get('done')}
    if active != {step_id}: return False
    step = next((x for x in plan.get('steps', []) if x.get('id') == step_id), None)
    if (not step or step.get('kind') != 'interact' or step.get('map_id') != 23
            or step.get('target') != [10,61] or step.get('mechanic') != tx.MECHANIC
            or step.get('capture_intent') != tx.snorlax_capture.INTENT
            or any(type(step['capture_intent'].get(k)) is not type(v)
                   for k,v in tx.snorlax_capture.INTENT.items())): return False
    record=tx._SESSIONS[step_id]
    binding=(23,(10,61),tuple(sorted(step['capture_intent'].items())))
    c=record.get('completion')
    # 正常工程熱載會產生同module/name的新class，舊物件仍須可完成。
    if (c is None or type(c).__module__ != completion.__name__
            or type(c).__name__ != 'CaptureCompletionController'
            or record.get('binding') != binding or record.get('switch') is not None
            or record.get('bridge_error') or c.error is not None
            or c.stage != 'closing' or c.no_confirmed is not True
            or c.intent != completion.INTENT or c.completion is not None): return False
    if not completion._stance(state.get('location')) or completion._battle(state.get('battle_state')) != 'none':
        return False
    party=completion._party(state.get('progress'))
    return party is not None and len(party)==5 and all(m['hp']>0 for m in party)


def restrict(result):
    context, step_id=result
    if context.get('available_actions') != ['wait']:
        return tx._review('capture_closing_gate_rejected_non_wait_action'), step_id
    return context, step_id
