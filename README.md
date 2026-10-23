# Laya × 寶可夢：從本機部署到可重現實測

[![Tests](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml/badge.svg)](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml)

用現有 NUC，把 **Laya 決策模型**接到 **PyBoy Game Boy 模擬器**，研究小模型如何從遊戲狀態選擇按鍵，以及整個控制迴圈的速度、穩定性與限制。

這裡會公開程式、部署方式、實驗摘要與問題處理，並累積 [Kevin 個人網站](https://kevinkayu.com) Local AI 實驗室的文章素材。

## 目前進度

更新：**2026-10-23：第一道館已破關，取得灰色徽章。** 本機Laya搭配私人Strata階段監督器，從既有存檔繼續訓練、治療、穿越常磐森林並擊敗小剛。已核對勝利／領徽章畫面、`beat_brock=true`、`badges_raw=1`及最終存檔回讀；通關後保存停止。詳見[首館成果與存檔鏈驗證](results/first-gym-campaign-20261023.json)、[實驗日誌第22節](docs/experiment-plan-and-log.md)。

目前隊伍：**妙蛙種子15級，HP33/41，EXP2395**；另有**尼多朗♂3級、烈雀3級**，6顆精靈球、3,096元及TM34。首位從7級正常練到13級學會藤鞭，再於道館升到15級；對地鼠、穿山鼠、小拳石、大岩蛇皆選藤鞭。本輪未新增捕捉，隊員沒有共享經驗或自動平均升級。長期最佳隊伍仍在建置。

已產生**4分8.53秒第一道館成果影片**（480×432、30fps），包含館內對戰、小剛與領獎收尾；[公開驗證摘要](results/first-gym-clip-20261023.json)。影片留本機，按原時間順序串接並移除重複卡住畫面，完整原片保留；播放時間為模擬時間，省略推論等待。未上傳影片或發布網站。

這是控制器提供尋路、選單及戰術子目標，再由本機Laya分類按鍵的實機成果；**尚未完成八館、聯盟與全程自主通關驗證**。研究所首戰的敗北紀錄保留，沒有回讀戰前改寫勝負。歷史見[雙模型實測](results/strata-live-20261023.json)、[組隊摘要](results/team-building-20261023.json)、[開場摘要](results/live-run-20261023.json)。

本機已有 **21 秒命名短片**與 **90 秒離家到取得妙蛙種子的實測影片**，公開檔案驗證摘要見[命名紀錄](results/kevin-naming-clip-20261023.json)與[開場流程紀錄](results/opening-to-bulbasaur-clip-20261023.json)。影片留在本機，尚未對外發布。

另有 [110 秒首戰敗北紀錄](results/first-rival-battle-clip-20261023.json)、[90 秒升等／取得包裹紀錄](results/level6-and-parcel-clip-20261023.json)與[25 秒取得圖鑑紀錄](results/pokedex-clip-20261023.json)，保留成功與失敗樣本。

正式遊戲目標：**培養並升級隊伍 → 完成必要劇情 → 八枚道館徽章 → 四天王與冠軍 → 名人堂登錄**。目前控制器仍是分段驗證原型，尚未具備經驗證的全程自主通關能力。

已加入[紅／藍版組隊、學招與捕捉策略](docs/team-strategy.md)：以妙蛙花、尼多王、勇基拉、拉普拉斯、卡比獸、閃電鳥為暫定通關方向，已完成補球與首隻尼多朗♂捕捉。這是長程策略目標，並非六隻已取得；四招已滿的忘招介面、稀有怪削血與PC管理仍待實機校準，遇到未知流程會保存狀態停止。

| 項目 | 狀態 |
|---|---|
| Windows／Python 3.11 獨立環境 | 已部署；CPU PyTorch、Laya、PyBoy 相依檢查通過 |
| 真實 Laya 權重 | 已下載並固定 revision，CPU 推論成功 |
| 合成按鍵決策測試 | 7 個情境皆符合預期；只是介面與控制語意檢查 |
| PyBoy 桌面限步控制與 JSONL 日誌 | 完成首戰敗北、野生戰獲勝、升至等級 6、治療、交還包裹與取得圖鑑；每輪上限 60 秒 |
| MP4 錄影管線 | 已產生並解碼驗證 2 秒／60 幀／30fps 測試片 |
| 寶可夢遊戲結果與影片 | 本機有 21 秒命名、90 秒取得初始流程與首輪卡關影片；公開摘要，影片尚未發布 |
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

已實測[Strata地端階段監督器](docs/local-planner.md)：`qwen3.8-flash-next-iq3_s`選高階階段，離線Laya選按鍵，迴圈不依賴Computer Use。完成一輪測試及另外兩輪自動續接，三輪保存狀態雜湊鏈相符；後續首館任務的33輪存檔鏈亦已核對，227測試通過。仍只支援已實作階段，詳見[橋接就緒度](results/strata-bridge-readiness-20261023.json)。

`PyBoy 狀態 → 精簡 JSON 與候選按鍵 → Laya 選擇 → 按鍵及等待幀數 → 新狀態與紀錄`

- Laya 處理文字／JSON 狀態及候選選項，回傳選擇與分數。
- 目前分類輸入為目標、可見 tile 字碼的文字候選、階段提示與隊伍摘要；非像素 OCR，未完整處理 sprite 遮罩，持續對照真實畫面校準。最近三次按鍵、警告及畫面雜湊保留於稽核日誌，避免分類輸入過長或重複動作造成錨定。
- Python 控制器解析可見文字與命名字格，提供場景提示、下一個命名字元、已核對的 waypoint、碰撞格 BFS 路徑及候選按鍵遮罩，再由本機 Laya 分類選出按鍵。這些工程輔助的貢獻另外記錄；目前成果不代表模型自主理解地圖或自行通關。
- 初期戰鬥原為 FIGHT／TACKLE 基線；現在控制器加入第一世代威力、命中、屬性與PP的招式評分，以及未持有目標的捕捉子目標，Laya在按鍵層分類。這些規則不是模型自行發現的完整戰術，完整換人／道具戰術仍待校準。野生戰可見HUD HP不高於一半時撤退、到常磐市後治療；party HP可能落後，撤退判斷用右側可見HUD並排除PP。
- `progress.jsonl` 唯讀追蹤隊伍、徽章與限定劇情事件；未初始化或未校準訊號保留 unknown，名人堂不因單一 RAM bit 自動宣告完成。
- 控制集合為方向鍵、A、B、START、等待；已依部分選單與局部移動目標縮小候選集合，碰撞 BFS 只使用已辨識的可走格。這仍不是完整、經校準的遊戲合法動作判定。
- `play` 保留有限步與60秒檢查點；`--until-first-gym`持續保存續接至明確首館里程碑，首館勝利與徽章已實測核對。其他任務的成功判定需逐段校準。
- `--offline` 使用已快取、固定 revision 的 Laya 權重在 CPU 推論；遊戲程序阻擋 Python 網路連線，沒有 GPT fallback。Codex 做工程、除錯及查攻略仍會使用 Codex 額度，與本機遊戲分類分開。
- 使用者已允許卡關時查閱攻略與公開原始碼，將有來源的策略整理成 Markdown，再回饋本機控制流程；按鍵選擇仍由本機 Laya 執行。研究參考資料見文末來源。
- 後續會在相同起點、資訊與動作預算下比較隨機、簡單規則及 Laya；比較時須固定並標示場景提示、尋路及候選遮罩的輔助條件。

## 人工玩與掛機接手

已新增[獨立人工遊玩入口、鍵盤表及效能分析](docs/manual-and-autoplay.md)：A鍵確認、S鍵取消；人工模式不載入模型，另存進度。現有AI流程尚無同視窗即時切換控制權功能。

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

首次下載模型需先完成上面的 `model-smoke`；`play` 預設離線讀取固定 revision。即時視窗使用 1 倍遊戲速度；模型載入與思考期間遊戲暫停、SDL 事件持續更新，標題會顯示 `PAUSED`，因此不會將模型等待誤算成遊戲時間。關閉視窗可正常停止；依使用者要求，**每輪執行上限改為 60 秒**，包含模型載入與分類，結束時保存本機存檔及錄影。這會縮短每輪除錯等待，不改變推論或遊戲速度。沒有 `--state` 時先推進 120 個開機幀；控制器仍只涵蓋經分段實測的初期流程，不能保證完成後續任務。

本次實驗路線須額外啟用 `--opening-route`，並只接受已核對的紅版 SHA；`--strategy-file` 指定本機 JSON，例如 `{"starter":"BULBASAUR","stage":"lab_rival"}`。目前支援 `starter`（取得初始）、`lab_rival`（首戰）、`to_parcel`（前往商店）與 `deliver_parcel`（治療並交還包裹）階段；可用範圍及待驗結果見實測摘要，程式存在不代表整段已驗收。已核對的初始路線只支援 `BULBASAUR`。一般啟動器沒有預設開啟實驗路線。

另有 Showdown 固定入門對戰的獨立測試，僅驗證選招與對戰引擎串接；它不是 Game Boy 紅／藍版，回放不作為本專案即時遊玩的驗收。

## 影片成果

新增 **59.33秒 Strata＋Laya真實紅版影片**，包含烈雀捕捉、登錄收尾與後續野生對戰；公開[驗證收據](results/strata-live-clip-20261023.json)，MP4留在本機`outputs/videos/strata-laya-live-20261023.mp4`。此輪控制與續接無Computer Use呼叫。

新增 **30秒升等／學寄生種子／捕捉尼多朗♂** 剪輯，公開[影片驗證收據](results/team-building-clip-20261023.json)，MP4位於本機`outputs/videos/team-building-20261023.mp4`。它由兩段真實PyBoy錄影剪接，省略模型等待；不是牆鐘速度或全程自主通關證據。

本機短片 `outputs/videos/kevin-naming-20261023.mp4` 共 21 秒，記錄真實命名過程；`outputs/videos/opening-to-bulbasaur-20261023.mp4` 共 90 秒，涵蓋出門、博士劇情與取得妙蛙種子。兩段皆已解碼核對首尾，摘要見[命名影片紀錄](results/kevin-naming-clip-20261023.json)與[開場流程紀錄](results/opening-to-bulbasaur-clip-20261023.json)。MP4 不提交 GitHub，目前沒有公開影片連結。

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
- [x] 走出自家、觸發大木博士劇情，取得等級 5 妙蛙種子。
- [x] 自然觸發並完成研究所勁敵對戰，記錄實際敗北與限制。
- [x] 擊倒一號道路的小拉達與波波，升至等級 6，取得博士包裹。
- [x] 實際完成常磐中心治療、交還包裹並取得圖鑑，對話與後續事件旗標核對。
- [x] 低血量野生戰實際逃跑、補球與捕獲首隻3級尼多朗♂；妙蛙種子升7級、學寄生種子。
- [ ] 實際觸發並驗證矮坡 helper；不能把單元測試當實際成功。
- [ ] 擴充招式、道具、換人與捕捉策略，建立與 TACKLE 子目標基線的比較。
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
