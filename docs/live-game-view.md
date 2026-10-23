---
type: experiment-note
updated: 2026-10-24
---

# PyBoy 即時遊戲顯示

Windows 原生視窗曾連續停在 SDL `SDL_PumpEvents()`，另一個已安裝的 GLFW 後端也停在 `poll_events()`。為讓遊戲運算持續，新增可選的 `--window null --live-view`：PyBoy 照常執行紅版，由原本離線 Laya 選按鍵，並直接匯出正在執行的 framebuffer。

每 250ms 最多發布一次原尺寸 160×144 PNG，與白名單遊戲摘要。摘要包含影格、時間、階段、暫停原因、最近觀測位置、最多六名隊員與徽章；不包含 ROM、存檔、原始觀測或模型連線資訊。PNG 與 JSON 各自原子替換，短暫讀鎖只略過該次畫面輸出。畫面與摘要並非跨檔交易，介面標示隊伍與座標來自最近一次控制器觀測。

## 本機觀看

啟動遊戲時加上 `--window null --live-view`，再使用另一個終端：

```powershell
.venv\Scripts\python.exe scripts\serve_live_game.py --run outputs/<本次執行>/game --port 8767
```

在同一台電腦開啟 <http://127.0.0.1:8767/>。伺服器只綁定 loopback，只提供首頁、目前 PNG 與摘要三個路由。沒有檔案目錄瀏覽或遊戲控制端點。

頁面會顯示執行、檢討暫停或停止。影格超過五秒未更新時會顯示時間，避免把停住的畫面當成持續遊玩。這是當前 PyBoy 真圖串流，與素材 MP4 分開；影格播放時間也不等於從開場到通關的牆鐘耗時。

## 已驗證與限制

- PNG 尺寸、原像素、節流、公開欄位、Windows 共享鎖與其他例外都有測試；HTTP parser 測試確認其他檔案與操作路由不能存取。
- 頁面 JavaScript 另以 Node 語法檢查。本機 HTTP 的 HTML、摘要、PNG 都已實際取得 200；Chromium 自動開頁受工具政策限制，沒有宣稱完成瀏覽器畫面驗收。
- 此頁目前只供觀看。原生視窗的 Windows 事件阻塞仍待排除，沒有把更換 renderer 當成已修好。
- 原始 60 秒檢查點、60 秒推論期限、戰敗與每館檢討維持。原生呼叫若不返回，輪詢式推論期限不能保證中斷它；這是分離運算與顯示的原因。

[SDL 官方說明](https://wiki.libsdl.org/SDL3/AppFreezeDuringDrag)記錄 Windows 視窗操作可能阻塞事件 pump。這與本次堆疊的阻塞類型相符，仍不能證明本次有人拖曳視窗或確定根因。
