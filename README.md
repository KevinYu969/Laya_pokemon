# Laya × 寶可夢：從本機部署到可重現實測

[![Tests](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml/badge.svg)](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml)

用現有 NUC，把 **Laya 決策模型**接到 **PyBoy Game Boy 模擬器**，研究小模型如何從遊戲狀態選擇按鍵，以及整個控制迴圈的速度、穩定性與限制。

這裡會公開程式、部署方式、實驗摘要與問題處理，並累積 [Kevin 個人網站](https://kevinkayu.com) Local AI 實驗室的文章素材。

## 目前進度

更新：**2026-10-23**。已在紅版的 PyBoy 桌面即時畫面中，由本機離線 Laya 選擇按鍵，完成玩家 **KEVIN**、勁敵 **BLUE** 命名、離開自家、在真新鎮觸發大木博士劇情，並取得 **等級 5 的妙蛙種子（HP 19／19）**。遊戲取得對話與唯讀隊伍資料相互核對，見[實測摘要](results/live-run-20261023.json)。**尚未完成第一場對戰、挑戰道館或通關；這是單次分段流程證據，尚無成功率數據。**

本機已有 **21 秒命名實測短片**，公開檔案驗證摘要見 [命名影片紀錄](results/kevin-naming-clip-20261023.json)。影片留在本機，尚未對外發布。

正式遊戲目標：**培養並升級隊伍 → 完成必要劇情 → 八枚道館徽章 → 四天王與冠軍 → 名人堂登錄**。目前控制器仍是分段驗證原型，尚未具備經驗證的全程自主通關能力。

| 項目 | 狀態 |
|---|---|
| Windows／Python 3.11 獨立環境 | 已部署；CPU PyTorch、Laya、PyBoy 相依檢查通過 |
| 真實 Laya 權重 | 已下載並固定 revision，CPU 推論成功 |
| 合成按鍵決策測試 | 7 個情境皆符合預期；只是介面與控制語意檢查 |
| PyBoy 桌面限步控制與 JSONL 日誌 | 紅版即時視窗已驗證；完成命名、離家與博士開場，取得等級 5 妙蛙種子 |
| MP4 錄影管線 | 已產生並解碼驗證 2 秒／60 幀／30fps 測試片 |
| 寶可夢遊戲結果與影片 | 本機已有 21 秒命名短片及首輪 116.4 秒卡關影片；公開摘要，影片尚未發布 |
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
- 目前分類輸入為目標、可見 tile 字碼的文字候選、階段提示與隊伍摘要；非像素 OCR，未完整處理 sprite 遮罩，持續對照真實畫面校準。最近三次按鍵、警告及畫面雜湊保留於稽核日誌，避免分類輸入過長或重複動作造成錨定。
- Python 控制器解析可見文字與命名字格，提供場景提示、下一個命名字元、已核對的 waypoint、碰撞格 BFS 路徑及候選按鍵遮罩，再由本機 Laya 分類選出按鍵。這些工程輔助的貢獻另外記錄；目前成果不代表模型自主理解地圖或自行通關。
- `progress.jsonl` 唯讀追蹤隊伍、徽章與限定劇情事件；未初始化或未校準訊號保留 unknown，名人堂不因單一 RAM bit 自動宣告完成。
- 控制集合為方向鍵、A、B、START、等待；已依部分選單與局部移動目標縮小候選集合，碰撞 BFS 只使用已辨識的可走格。這仍不是完整、經校準的遊戲合法動作判定。
- 初版 `play` 是有限步的控制展示，尚未提供經驗證的走路／對話／戰鬥成功判定。
- `--offline` 使用已快取、固定 revision 的 Laya 權重在 CPU 推論；遊戲程序阻擋 Python 網路連線，沒有 GPT fallback。Codex 做工程、除錯及查攻略仍會使用 Codex 額度，與本機遊戲分類分開。
- 使用者已允許卡關時查閱攻略與公開原始碼，將有來源的策略整理成 Markdown，再回饋本機控制流程；按鍵選擇仍由本機 Laya 執行。研究參考資料見文末來源。
- 後續會在相同起點、資訊與動作預算下比較隨機、簡單規則及 Laya；比較時須固定並標示場景提示、尋路及候選遮罩的輔助條件。

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

已查閱 Nintendo 官方產品頁，目前未找到可供 PyBoy 使用的官方 `.gb` 下載。若已有實體卡匣，可用具遊戲資料匯出功能的卡匣讀取器取得檔案；本儲存庫不提供 ROM。參考：[Nintendo 紅版產品頁](https://www.nintendo.com/en-gb/Games/Game-Boy/Pokemon-Red-Version-266109.html)、[GB Operator 官方功能](https://www.epilogue.co/product/gb-operator)。

```powershell
.\scripts\start-live.ps1 -Rom .\roms\pokemon_red.gb
```

啟動器會先執行 `check-rom`，再以 SDL2 四倍視窗、已快取的固定模型版本、最多 300 次決策與 MP4 紀錄啟動；也可加 `-State .\saves\start.state`。只有一個 `.gb` 時可省略 `-Rom`。ROM 結構檢查包含 logo、容量、標頭及全檔 checksum，通過不代表已證明來源、語言或遊戲真偽。

首次下載模型需先完成上面的 `model-smoke`；`play` 預設離線讀取固定 revision。即時視窗使用 1 倍遊戲速度；模型載入與思考期間遊戲暫停、SDL 事件持續更新，標題會顯示 `PAUSED`，因此不會將模型等待誤算成遊戲時間。關閉視窗可正常停止，執行上限為 600 秒。沒有 `--state` 時先推進 120 個開機幀；目前驗證至取得初始寶可夢，不能保證完成後續任務。

本次實驗路線須額外啟用 `--opening-route`，並只接受已核對的紅版 SHA；範圍截至取得妙蛙種子，之後等待，尚未提供對戰策略。可透過 `--strategy-file` 讀取本機 JSON 的 `starter` 欄位，但目前已驗證的路線只支援 `BULBASAUR`。一般啟動器沒有預設開啟這條實驗路線。

另有 Showdown 固定入門對戰的獨立測試，僅驗證選招與對戰引擎串接；它不是 Game Boy 紅／藍版，回放不作為本專案即時遊玩的驗收。

## 影片成果

最新本機短片為 `outputs/videos/kevin-naming-20261023.mp4`，共 21 秒，記錄真實命名過程；[公開影片紀錄](results/kevin-naming-clip-20261023.json)提供整理過的摘要。MP4 不提交 GitHub，目前沒有公開影片連結。

另保留首輪真實遊戲的失敗案例：116.4 秒、3492 幀、30fps、無聲，到達大木博士歡迎對話後卡住。這段歷史影片不代表目前進度；後續結果已推進至取得初始寶可夢。影片與對應 run 的版本、設定、按鍵及畫面證據一起保存在本機。

- 獨立錄影管線測試片明示 **NO GAMEPLAY**，與上述真實遊戲影片分開保存。
- `play --video` 會輸出 `gameplay.mp4`、`steps.jsonl`、`summary.json` 與最後一幀。
- 新版逐次保存按鍵前後 PNG、畫面雜湊及本機 checkpoint；輸出檔全部留在忽略目錄，遊戲存檔不進公開 Git。
- 影片採模擬器時間回放，約每 2 個模擬器幀擷取 1 幀、30fps；模型等待時間保存在 JSONL，播放速度不等於實際操作速度。
- 初版不錄音。影片留在本機，不納入 GitHub 備份；未來對外分享的影片平台與內容另行審閱。

錄影功能可獨立驗證：

```powershell
.\.venv\Scripts\python.exe -m laya_pokemon.cli recording-smoke --output outputs/recording-check.mp4
```

## 計畫、問題與備份

- [部署計畫與實驗日誌](docs/experiment-plan-and-log.md)：待辦、方法、問題與修復過程。
- [前期軟硬體研究](docs/preparation.md)：模型與模擬器的選擇。
- [備份方式](docs/backup.md)：公開檔案範圍、定期同步與復原。
- [實測摘要](results/)：保留成功與失敗結果，尚未量測的項目維持待測。

公開筆記由私人主檔單向匯出，移除個人路徑與主機識別；ROM、存檔、模型權重、影片、虛擬環境、憑證與原始私人日誌均排除。公開 `results/` 僅保存整理過的摘要，不包含私人狀態或原始輸出。

## 下一步

- [x] CPU 環境、真實權重與錄影管線。
- [x] 基本按鍵控制、日誌及錯誤處理測試。
- [x] 本機紅版載入、原生 PyBoy 桌面視窗、離線 Laya 按鍵與首輪遊戲錄影。
- [x] 真實紅版玩家 KEVIN、勁敵 BLUE 命名，以及 21 秒命名短片。
- [x] 從自家二樓繞過植物、下到一樓；保留 waypoint 與碰撞 BFS 的控制器貢獻。
- [x] 走出自家、觸發大木博士劇情，取得等級 5 妙蛙種子；本輪路線止於此。
- [ ] 接續研究所的勁敵對戰，校準戰鬥觀測與選招。
- [ ] 擴充並校準屋外導航、對話與戰鬥觀測。
- [ ] 建立可驗證成功的短路線、對話與單場戰鬥案例。
- [ ] 相同條件的隨機／規則／Laya 對照。
- [ ] 真實遊戲影片與繁體中文實驗文章。

## 來源

[Laya](https://github.com/NandhaKishorM/laya) · [模型卡](https://huggingface.co/convaiinnovations/laya) · [PyBoy](https://docs.pyboy.dk/) · [Gen 1 wrapper](https://docs.pyboy.dk/plugins/game_wrapper_pokemon_gen1.html)

開場策略與觀測參考原始碼：

- [命名盤與輸入流程](https://github.com/pret/pokered/blob/master/engine/menus/naming_screen.asm)、[英文字格](https://github.com/pret/pokered/blob/master/data/text/alphabets.asm)。
- [自家二樓出口](https://github.com/pret/pokered/blob/master/data/maps/objects/RedsHouse2F.asm)、[一樓出口](https://github.com/pret/pokered/blob/master/data/maps/objects/RedsHouse1F.asm)。
- [Pallet Town 的大木博士觸發劇情](https://github.com/pret/pokered/blob/master/scripts/PalletTown.asm)、[研究所選初始寶可夢流程](https://github.com/pret/pokered/blob/master/scripts/OaksLab.asm)。
- [PokemonRedExperiments 使用的 RAM 座標位址](https://github.com/PWhiddy/PokemonRedExperiments/blob/master/baselines/memory_addresses.py)。

Laya 與 PyBoy 的程式、模型與商標各依上游條款。本專案未附遊戲 ROM、圖像資產或模型權重。
