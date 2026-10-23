# Laya × 寶可夢：從本機部署到可重現實測

[![Tests](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml/badge.svg)](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml)

用現有 NUC，把 **Laya 決策模型**接到 **PyBoy Game Boy 模擬器**，研究小模型如何從遊戲狀態選擇按鍵，以及整個控制迴圈的速度、穩定性與限制。

這裡會公開程式、部署方式、實驗摘要與問題處理，並累積 [Kevin 個人網站](https://kevinkayu.com) Local AI 實驗室的文章素材。

## 目前進度

更新：**2026-10-23**。目前缺少使用者有權使用的紅／藍版 ROM，**尚未啟動真正的紅／藍版遊戲，也沒有即時遊玩驗收或破關成果**。

| 項目 | 狀態 |
|---|---|
| Windows／Python 3.11 獨立環境 | 已部署；CPU PyTorch、Laya、PyBoy 相依檢查通過 |
| 真實 Laya 權重 | 已下載並固定 revision，CPU 推論成功 |
| 合成按鍵決策測試 | 7 個情境皆符合預期；只是介面與控制語意檢查 |
| PyBoy 桌面限步控制與 JSONL 日誌 | 已實作；已補 ROM 完整性檢查與模型等待時的視窗事件處理；真實 ROM 整合尚待驗證 |
| MP4 錄影管線 | 已產生並解碼驗證 2 秒／60 幀／30fps 測試片 |
| 寶可夢遊戲結果與影片 | 待提供英文紅／藍版 ROM 及測試存檔後實測 |
| 短路線／對話／戰鬥對照 | 已規劃，尚無完成率數據 |

## 已測到什麼？

測試硬體：**Intel Core 5 210H、32GB RAM，CPU 4 執行緒**。

| 2026-10-22 合成控制檢查 | 本機結果 |
|---|---|
| Laya | 0.4.13，`convaiinnovations/laya` |
| 模型 revision | `7b928d828b7b0e022f929d9bd2e44165aa270148` |
| 合成情境 | 7／7 符合預期 |
| 模型推論 p50／p95 | 約 1328／1444 毫秒（7 個暖機後樣本） |
| 模型已快取時的下載檢查與載入 | 約 5.98 秒 |
| 推論後程序 RSS | 約 2.05GB；這是當下用量，尚非峰值測量 |

這些結果來自明確指令的合成情境，不代表遊戲任務成功率。原始版本、程式雜湊與測試摘要見 [results/](results/)。

## 如何運作

`PyBoy 狀態 → 精簡 JSON 與候選按鍵 → Laya 選擇 → 按鍵及等待幀數 → 新狀態與紀錄`

- Laya 處理文字／JSON 狀態及候選選項，回傳選擇與分數。
- 目前觀測為螢幕中央小範圍碰撞資料與隊伍摘要；觀測 profile 尚待對照真實 ROM 校準。
- 控制集合為方向鍵、A、B、START、等待；目前尚未依牆壁或選單狀態過濾為遊戲語意上的合法動作。
- 初版 `play` 是有限步的控制展示，尚未提供經驗證的走路／對話／戰鬥成功判定。
- 後續會在相同起點、資訊與動作預算下比較隨機、簡單規則及 Laya；若加入尋路或高階規劃，另外標示其貢獻。

## 快速開始（Windows PowerShell）

準備 Python 3.11、Git 與約 10–20GB 可用空間。第一次載入模型需要網路，權重會放在專案 `.cache/`。

```powershell
git clone https://github.com/KevinYu969/Laya_pokemon.git
cd Laya_pokemon
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m laya_pokemon.cli doctor
.\.venv\Scripts\python.exe -m pytest -q
```

若 Python 3.11 未由 `py` launcher 管理，使用 `-Python '你的 python.exe 完整路徑'`。要依本次版本安裝，可用 `bootstrap.ps1 -Locked`；版本清單以 Windows CPU 環境為準。

### 先測模型，不需要 ROM

```powershell
.\.venv\Scripts\python.exe -m laya_pokemon.cli model-smoke --output outputs/runs/model-smoke-001 --revision 7b928d828b7b0e022f929d9bd2e44165aa270148
```

會保存環境、模型 revision、逐題決策、推論時間與失敗紀錄。每次請使用新的輸出目錄。

### 接上使用者自己的遊戲檔案

自行準備有權使用的英文版 Pokemon Red／Blue ROM，放在 `roms/`；PyBoy 存檔放在 `saves/`。這些檔案不會提交 Git。

已查閱 Nintendo 官方產品頁，目前未找到可供 PyBoy 使用的官方 `.gb` 下載。若已有實體卡匣，可用具遊戲資料匯出功能的卡匣讀取器取得檔案；目前沒有替使用者購買硬體或取得遊戲。參考：[Nintendo 紅版產品頁](https://www.nintendo.com/en-gb/Games/Game-Boy/Pokemon-Red-Version-266109.html)、[GB Operator 官方功能](https://www.epilogue.co/product/gb-operator)。

```powershell
.\scripts\start-live.ps1 -Rom .\roms\pokemon_red.gb
```

啟動器會先執行 `check-rom`，再以 SDL2 四倍視窗、已快取的固定模型版本、最多 300 次決策與 MP4 紀錄啟動；也可加 `-State .\saves\start.state`。只有一個 `.gb` 時可省略 `-Rom`。ROM 結構檢查包含 logo、容量、標頭及全檔 checksum，通過不代表已證明來源、語言或遊戲真偽。

首次下載模型需先完成上面的 `model-smoke`；`play` 預設離線讀取固定 revision。即時視窗使用 1 倍遊戲速度；模型載入與思考期間遊戲暫停、SDL 事件持續更新，標題會顯示 `PAUSED`，因此不會將模型等待誤算成遊戲時間。關閉視窗可正常停止，執行上限為 600 秒。沒有 `--state` 時先推進 120 個開機幀；開場／命名／導航仍待真正 ROM 校準，不能保證完成任務。

另有 Showdown 固定入門對戰的獨立測試，僅驗證選招與對戰引擎串接；它不是 Game Boy 紅／藍版，回放不作為本專案即時遊玩的驗收。

## 影片成果

真正的遊戲影片會放在這裡，搭配 ROM／存檔雜湊、模型版本、執行設定和同次 run 的數據。

- 已驗證的是錄影管線測試，畫面明示 **NO GAMEPLAY**。
- `play --video` 預定輸出 `gameplay.mp4`、`steps.jsonl`、`summary.json` 與最後一幀。
- 影片採模擬器時間回放，約每 2 個模擬器幀擷取 1 幀、30fps；模型等待時間保存在 JSONL，播放速度不等於實際操作速度。
- 初版不錄音。影片先留在本機，審閱後再以 GitHub Release 或影片平台連結分享，避免大量二進位檔進入日常備份。

錄影功能可獨立驗證：

```powershell
.\.venv\Scripts\python.exe -m laya_pokemon.cli recording-smoke --output outputs/recording-check.mp4
```

## 計畫、問題與備份

- [部署計畫與實驗日誌](docs/experiment-plan-and-log.md)：待辦、方法、問題與修復過程。
- [前期軟硬體研究](docs/preparation.md)：模型與模擬器的選擇。
- [備份方式](docs/backup.md)：公開檔案範圍、定期同步與復原。
- [實測摘要](results/)：保留成功與失敗結果，尚未量測的項目維持待測。

公開筆記由私人主檔單向匯出，移除個人路徑與主機識別；ROM、存檔、模型權重、虛擬環境、憑證與原始私人日誌均排除。

## 下一步

- [x] CPU 環境、真實權重與錄影管線。
- [x] 基本按鍵控制、日誌及錯誤處理測試。
- [ ] 取得使用者 ROM／存檔，校準觀測與按鍵行為。
- [ ] 建立可驗證成功的短路線、對話與單場戰鬥案例。
- [ ] 相同條件的隨機／規則／Laya 對照。
- [ ] 真實遊戲影片與繁體中文實驗文章。

## 來源

[Laya](https://github.com/NandhaKishorM/laya) · [模型卡](https://huggingface.co/convaiinnovations/laya) · [PyBoy](https://docs.pyboy.dk/) · [Gen 1 wrapper](https://docs.pyboy.dk/plugins/game_wrapper_pokemon_gen1.html)

Laya 與 PyBoy 的程式、模型與商標各依上游條款。本專案未附遊戲 ROM、圖像資產或模型權重。
