"""敗北停機鎖：唯讀證據、單次事件、具體檢討後才能繼續。"""
import json


def frame_loss_signal(memory):
    """已鎖定英文紅版：每幀只讀戰鬥旗標與最多六隻HP，避免跨按鍵取樣漏掉敗北。"""
    raw=memory[0xD057]
    if raw==255:
        return True
    if raw not in {1,2}:
        return False
    count=memory[0xD163]
    return 1<=count<=6 and all(memory[0xD16B+44*i+1]==0 and memory[0xD16B+44*i+2]==0 for i in range(count))


class LossGuard:
    def __init__(self):
        self.in_battle = False
        self.latched = False
        self.last_battle = None

    def observe(self, state):
        battle = state.get('battle_state', {})
        active = battle.get('active') is True
        if active:
            self.in_battle = True
            self.last_battle = battle.copy()
        party = state.get('progress', {}).get('party', [])
        text = ' '.join(state.get('visible_text_candidates', [])).upper()
        signals = []
        if battle.get('kind') == 'lost_transition':
            signals.append('lost_transition')
        if self.in_battle and party and all(mon.get('hp') == 0 for mon in party):
            signals.append('all_party_fainted')
        if self.in_battle and ('BLACKED OUT' in text or 'BLACKED OUT' in text.replace('  ', ' ')):
            signals.append('visible_blackout')
        if signals and not self.latched:
            self.latched = True
            return {'signals': signals, 'last_battle': self.last_battle,
                    'party': party, 'location': state.get('location'),
                    'visible_text': state.get('visible_text_candidates', [])}
        if not active and not signals and party and any(mon.get('hp', 0) > 0 for mon in party):
            self.in_battle = False
            self.latched = False
        return None


def parse_loss_review(text):
    """不能只改路線／放空白檔解除敗北鎖；不執行模型輸出中的任何程式。"""
    try:
        result = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(result, dict):
        return None
    fields = ('cause', 'evidence', 'adjustments', 'validation')
    if not all(isinstance(result.get(key), str) and result[key].strip() for key in fields):
        return None
    return {key: result[key][:4000] for key in fields}
