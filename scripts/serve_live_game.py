"""只在本機顯示目前 PyBoy 真實影格；不提供操作、ROM 或存檔下載。"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PAGE = r'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Laya × PyBoy 即時遊玩</title><style>
*{box-sizing:border-box}body{margin:0;background:#101914;color:#e7f1dc;font:16px system-ui,sans-serif}
main{max-width:1200px;margin:auto;padding:24px}h1{font-size:26px;margin:0 0 8px}p{color:#aac5ac}
.layout{display:grid;grid-template-columns:minmax(320px,2fr) minmax(250px,1fr);gap:24px;margin-top:20px}
.screen{background:#070c08;padding:12px;border:1px solid #416848;border-radius:12px;align-self:start}
img{display:block;width:100%;aspect-ratio:10/9;object-fit:contain;image-rendering:pixelated;background:#9bbc0f}
article{border:1px solid #416848;padding:16px;border-radius:12px;margin-bottom:12px}.label{color:#a8ce9a}
#status{font-size:21px;color:#bbf59a}#metrics{line-height:1.8;white-space:pre-line}.party{padding:12px 0;border-top:1px solid #2b4931}.party:first-child{border:0}
.hp{height:7px;background:#29402e;margin-top:7px}.hp>i{display:block;height:100%;background:#8ddf75}
small{color:#abc0ad}a{color:#b4ec9a}@media(max-width:780px){.layout{grid-template-columns:1fr}main{padding:14px}}
</style><main><h1>Laya × PyBoy｜寶可夢紅版即時遊玩</h1>
<p>目前由離線 Laya 操作；畫面直接來自執行中的 PyBoy。原生視窗事件阻塞檢修期間，改以本機即時串流顯示。</p>
<div class="layout"><div class="screen"><img id="game" alt="正在等待 PyBoy 即時影格"></div>
<section><article><div id="status">等待遊戲影格</div><p id="freshness">連線中…</p><div id="metrics"></div></article>
<article><div class="label">目前隊伍</div><div id="party"></div></article>
<small>隊伍與座標為最近一次控制器觀測，畫面可能略晚。檢討暫停時會顯示原因；此頁只顯示畫面，不發送按鍵。頁面播放時間不能當通關耗時。</small></section></div></main>
<script>
const el=id=>document.getElementById(id);let busy=false,latest=null,lastFrame=null;
function age(){if(!latest)return;const seconds=Math.max(0,(Date.now()-Date.parse(latest.at))/1000);const paused=latest.status==='paused_for_review';el('freshness').textContent=seconds<5?'最近影格：'+seconds.toFixed(1)+' 秒前':(paused?'檢討暫停；':'串流暫無更新；')+'最近影格 '+Math.floor(seconds)+' 秒前';}
async function refresh(){if(busy)return;busy=true;try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error('等待 PyBoy 發布');latest=await r.json();
el('status').textContent=latest.status==='paused_for_review'?'已保存，等待檢討':latest.status==='stopped'?'遊戲已停止':'PyBoy 即時執行中';
el('metrics').textContent='影格 '+latest.frame+'\n階段 '+(latest.phase||'初始化')+'\n'+(latest.location?'地圖 '+latest.location.map_id+'・座標 '+latest.location.x+', '+latest.location.y:'')+(latest.review_reason?'\n檢討 '+latest.review_reason:'');
if(lastFrame!==latest.frame){el('game').src='/live-frame.png?frame='+latest.frame+'&at='+encodeURIComponent(latest.at);lastFrame=latest.frame;}
el('party').replaceChildren(...(latest.party||[]).map(p=>{const div=document.createElement('div');div.className='party';const text=document.createElement('div');text.textContent=p.species_name+'　Lv.'+p.level+'　'+p.hp+'/'+p.max_hp+(p.status?'　狀態 '+p.status:'');const bar=document.createElement('div');bar.className='hp';const fill=document.createElement('i');fill.style.width=Math.max(0,Math.min(100,100*p.hp/Math.max(1,p.max_hp)))+'%';bar.append(fill);div.append(text,bar);return div;}));age();
}catch(e){el('status').textContent='等待遊戲影格';el('freshness').textContent=e.message;}finally{busy=false;}}
setInterval(refresh,250);setInterval(age,1000);refresh();
</script></html>'''


def handler_for(run: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlsplit(self.path).path
            if route == '/':
                payload, content_type = PAGE.encode('utf-8'), 'text/html; charset=utf-8'
            elif route in {'/api/status', '/live-frame.png'}:
                name = 'live-frame.json' if route == '/api/status' else 'live-frame.png'
                try:
                    payload = (run / name).read_bytes()
                except (FileNotFoundError, PermissionError):
                    self.send_error(503, 'Waiting for PyBoy frame'); return
                if route == '/api/status':
                    try: json.loads(payload)
                    except (ValueError, UnicodeError):
                        self.send_error(503, 'Frame metadata updating'); return
                content_type = 'application/json; charset=utf-8' if route == '/api/status' else 'image/png'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try: self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError): pass

        def log_message(self, *_):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run = (root / args.run).resolve()
    if not run.is_relative_to(root / 'outputs') or not run.is_dir():
        raise ValueError('只能顯示本專案 outputs 中的實際遊戲目錄')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(run))
    print(f'PyBoy 即時顯示 http://127.0.0.1:{args.port}/', flush=True)
    try: server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__':
    main()
