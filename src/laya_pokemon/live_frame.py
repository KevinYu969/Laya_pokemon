"""將真實 framebuffer 節流匯出；只附公開遊戲摘要，不接收控制輸入。"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time


def _number(value, low, high):
    return value if type(value) is int and low <= value <= high else None


def _label(value, pattern):
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else None


class LiveFramePublisher:
    """每 250ms 發布真實 RGB 圖及固定白名單摘要；共享鎖只略過本次。"""

    def __init__(self, output: Path, *, clock=time.monotonic):
        self.output = Path(output)
        self.clock = clock
        self.last_attempt = None
        self.summary = {
            'status': 'running', 'phase': None, 'review_reason': None,
            'location': None, 'party': [], 'badges_raw': None,
        }

    def update_summary(self, state, *, status='running', review_reason=None):
        """複製少量已觀測欄位，絕不保留原 state、背包、路徑或模型設定。"""
        if not isinstance(state, dict):
            raise TypeError('state 必須為 dict')
        progress = state.get('progress')
        progress = progress if isinstance(progress, dict) else {}
        location = state.get('location')
        location = ({key: _number(location.get(key), 0, 255) for key in ('map_id', 'x', 'y')}
                    if isinstance(location, dict) else None)
        party = progress.get('party')
        party = party if isinstance(party, list) else []
        self.summary = {
            'status': 'running',
            'phase': _label(state.get('phase'), r'[a-z][a-z0-9_]{0,95}'),
            'review_reason': None,
            'location': location,
            'party': [
                {
                    'species_name': _label(mon.get('species_name'), r"[A-Z][A-Z0-9_ .♀♂'-]{0,19}"),
                    'level': _number(mon.get('level'), 1, 100),
                    'hp': _number(mon.get('hp'), 0, 65535),
                    'max_hp': _number(mon.get('max_hp'), 1, 65535),
                    'status': _number(mon.get('status'), 0, 255),
                }
                for mon in party[:6] if isinstance(mon, dict)
            ],
            'badges_raw': _number(progress.get('badges_raw'), 0, 255),
        }
        self.update_status(status, review_reason=review_reason)

    def update_status(self, status, *, review_reason=None):
        """狀態切換沿用最後已驗白名單，不讀取模擬器記憶體。"""
        if status not in {'running', 'paused_for_review', 'stopped'}:
            raise ValueError('未知 live view 狀態')
        self.summary['status'] = status
        self.summary['review_reason'] = _label(review_reason, r'[a-z][a-z0-9_]{0,127}')

    def publish(self, framebuffer, frame_number, *, force=False):
        """原尺寸真圖只作 RGB 轉換；每檔 tmp+replace，非 PermissionError 照常拋出。"""
        now = self.clock()
        if not force and self.last_attempt is not None and now - self.last_attempt < .25:
            return False
        if type(frame_number) is not int or frame_number < 0:
            raise ValueError('frame 必須為非負整數')
        import numpy as np
        from PIL import Image
        pixels = np.asarray(framebuffer)
        if pixels.dtype != np.uint8 or pixels.shape not in {(144, 160, 3), (144, 160, 4)}:
            raise ValueError('framebuffer 必須為 160×144 uint8 RGB/RGBA 真實畫面')
        payload = {'frame': frame_number, 'at': datetime.now(timezone.utc).isoformat(), **self.summary}
        image_tmp = self.output / 'live-frame.png.tmp'
        json_tmp = self.output / 'live-frame.json.tmp'
        self.last_attempt = now
        try:
            Image.fromarray(pixels[..., :3]).save(image_tmp, format='PNG')
            json_tmp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
            image_tmp.replace(self.output / 'live-frame.png')
            json_tmp.replace(self.output / 'live-frame.json')
        except PermissionError:
            return False
        return True
