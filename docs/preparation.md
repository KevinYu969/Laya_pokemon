<!-- 自動匯出的公開備份；請於私人主檔更新，再重新匯出。 -->
---
type: evidence
updated: 2026-10-22
author: codex
---

# Laya Pokemon 實驗準備

關聯：CURRENT-STATE。Kevin 於 2026-10-22 詢問 Laya 快速決策模型控制寶可夢模擬器所需軟硬體；本輪為準備研究，尚未安裝、推論、訓練或量測遊戲成效。建議不是 Kevin 已接受的實作決策。

## 已確認的本機條件

- 私人機器 <LOCAL_MACHINE>；CIM 讀回 NUC15CRHC5、Intel Core 5 210H（8 核心／12 執行緒）、32GB RAM、Intel Graphics。
- 上游 Laya 支援 CPU，英文 checkpoint 421M 參數；本機適合先做單實例 CPU 原型。尚未驗證本機套件相容性、記憶體峰值或延遲。
- 實務建議：16GB RAM 起步、32GB 較寬裕，SSD 預留 10–20GB 放環境、模型快取、存檔與紀錄。這些是準備預算，不是官方最低規格。大量影片錄製另計空間；GPU 加速留待瓶頸量測後決定。

## 軟體與路線

- 建議 Python 3.11 獨立虛擬環境；Laya 官方要求 Python >=3.10，依賴 PyTorch、transformers、safetensors 等。
- 完整 GB 紅／藍版冒險：PyBoy、使用者有權使用的 ROM、與該 ROM 版本相符的遊戲狀態解析及存檔。PyBoy 提供按鍵、逐幀執行、記憶體、畫面與 Red/Blue wrapper；仍需自己做 Laya 整合。
- 只驗證戰鬥選招：本機 Pokemon Showdown + poke-env；需要 Node.js 執行 Showdown。此路線直接提供結構化戰鬥資料，整合範圍比完整跑圖小。
- Laya 接收文字／JSON 狀態與候選選項，回傳選擇及機率；畫面需先轉成它能處理的狀態。CPU 原型優先直接讀取模擬器狀態，視覺理解可另成實驗。
- 必要橋接：遊戲狀態 → 精簡 JSON（目前場景、座標／鄰近可通行資訊、目標、HP、招式／PP、選單狀態）及合法候選動作 → Laya → 驗證選項 → 按鍵及幀數 → 新狀態。對手資料只包含玩家可觀測資訊。
- 英文狀態先固定英文 checkpoint，避免語言路由或模型重載干擾比較；模型、runtime 版本、提示、動作集合與存檔需記錄。
- 若後續目標是完整流程／徽章，研究任務狀態機或高階規劃模型；這是後續架構候選，非本輪必要安裝或已驗證能力。

## 首輪驗證建議

- 固定短路線、對話與單場戰鬥存檔，各重複測試；保留相同起點、可觀測資訊、候選動作及步數預算。
- 比較隨機合法動作、簡單規則、Laya；規劃器輔助可另列條件，避免把規則與路徑搜尋的成果都算成模型能力。
- JSONL／CSV 記錄任務成功率、步數、卡住／重複動作、純推論 p50/p95、含解析及模擬器的端到端延遲、RAM 峰值。先暖機，冷啟動另外記錄。
- Laya 分數不是經遊戲資料校準的正確率；官方 GPU 延遲不是本機實測。

## 研究來源（2026-10-22 查閱）

- [Laya 上游 README](https://github.com/NandhaKishorM/laya)：安裝、CPU device、結構化決策介面。
- [Laya pyproject.toml](https://github.com/NandhaKishorM/laya/blob/main/pyproject.toml)：Python 及套件依賴。
- [Laya 官方 model card](https://huggingface.co/convaiinnovations/laya)：英文 421M、multilingual 322M 與 checkpoint 範圍。
- [PyBoy 文件](https://docs.pyboy.dk/)：Python 控制、記憶體、逐幀執行、畫面。
- [PyBoy Pokemon Gen1 wrapper](https://docs.pyboy.dk/plugins/game_wrapper_pokemon_gen1.html)：Red/Blue wrapper。
- [poke-env Getting Started](https://poke-env.readthedocs.io/en/stable/getting_started.html)：Python 與本機 Showdown 設定。
