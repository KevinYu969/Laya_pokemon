# 在自己的電腦上讓 Laya 玩寶可夢

更新：2026-10-28。這份是從乾淨下載開始的入口；舊實驗指令與存檔名稱不必照抄。

Laya 在 CPU 上選按鍵，不需要 RTX 5090 或 Kevin 的 Qwen 模型。高階階段安排有三種選擇：固定控制器、自己架的地端模型、自己付費的雲端 API。這是可修改的實驗程式；八枚徽章是作者在持續除錯與人工檢討後的成果，這個新手入口目前做到開局與第一道館流程，遇到未支援狀況會保存並停止。它不會自動修程式，也不保證一次成功或無人打完八館。

## 1. 安裝

需要 Git、64-bit Python 3.11，以及自己有權使用的英文 Pokémon Red ROM。程式不附、不下載 ROM、他人存檔、遊戲影片或模型權重；下載權重是後面明確執行的步驟。Windows 是本次實際驗證平台；macOS/Linux 可使用下方命令，尚未做實機遊戲驗收。

```powershell
git clone https://github.com/KevinYu969/Laya_pokemon.git
cd Laya_pokemon
.\scripts\bootstrap.ps1 -Locked
.\.venv\Scripts\Activate.ps1
python scripts/reader.py recommend
python scripts/reader.py download-laya
```

如果 PowerShell 不允許執行啟用腳本，不必變更整台電腦的執行政策；把後文的 `python` 改成 `.\.venv\Scripts\python.exe`。`bootstrap.ps1` 也可依下一段用 Python/pip 逐步安裝。

macOS/Linux（Python 3.11；依賴安裝可能需要該平台的編譯工具）：

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
# Linux CPU wheel；Apple Silicon 直接 pip install torch
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e '.[dev]'
python -m pip check
python scripts/reader.py recommend
python scripts/reader.py download-laya
```

`download-laya` 下載固定 revision `7b928d828b7b0e022f929d9bd2e44165aa270148` 到專案忽略的 `.cache/`。後續遊戲子程序只載入快取、CPU 推論。第一次模型載入可能慢，短片還沒有動作時先看本次 `game-00.log`。安裝失敗先確認 Python 版本，別把原始錯誤日誌直接貼到公開 Issue。

## 2. 選一種高階決策方式

### A. 先跑看看，不裝第二個模型

```sh
python scripts/reader.py setup --backend offline
python scripts/reader.py probe
```

這個模式由已實作的控制器選階段，Laya 選按鍵。它沒有呼叫高階 LLM，不能拿來宣稱測過雙模型協作。

### B. 地端模型：依可用記憶體選擇

先從 [Ollama 官方網站](https://ollama.com/download)安裝並啟動 Ollama，再執行：

```sh
python scripts/reader.py setup --backend local --download
python scripts/reader.py probe
```

程式讀取總 RAM、可用 RAM、磁碟空間；有 `nvidia-smi` 時另列 GPU/VRAM。建議以 CPU 可負擔為基準，不假設每台都有 NVIDIA GPU，也不把 VRAM 和 RAM 相加：

| 偵測條件 | 起始建議 |
| --- | --- |
| 至少 24 GiB RAM，當下至少 16 GiB 可用 | `qwen3:8b`，權重約 5.2 GB |
| 至少約 16 GB RAM（15 GiB），當下至少 10 GiB 可用 | `qwen3:4b`，權重約 2.5 GB |
| 低於以上條件 | 不自動下載；先用 A，或自行選 C |

這是保留作業系統、Laya 與 context 空間的保守起點，不是效能保證。權重大小不等於執行記憶體。`--download` 才會下載；較小模型也可能回錯格式或選擇停止，不能當作作者 Qwen 的等效結果。GPU 使用率可用 `ollama ps` 另看。

已有自己的私人 API，可省略下載並指定實際模型：

```sh
python scripts/reader.py setup --backend local --base-url http://127.0.0.1:8080/v1 --model YOUR_LOADED_MODEL --api-key-env LAYA_PLANNER_API_KEY
```

只接受 localhost、私人 LAN 或 Tailscale。請確保服務真的在本機推論，沒有自行代理到雲端。自動下載僅使用明確的本地 Qwen 標籤，不使用 Ollama cloud 標籤。

### C. 雲端 API：使用自己的服務與金鑰

支援有 `/v1/models`、`/v1/chat/completions` 及 JSON object 回覆的相容服務。並非每一家「相容」API 都支援同樣欄位，先跑 `probe`，不相容就停止，不自動換模型。服務需接受 `temperature=0`、`max_tokens=512`、`response_format=json_object`，且模型 ID 必須列在 `/models`。

```sh
python scripts/reader.py setup --backend cloud --base-url https://YOUR_PROVIDER/v1 --model YOUR_MODEL_ID --api-key-env LAYA_PLANNER_API_KEY --allow-cloud
```

將自己的 key 設進目前終端的 `LAYA_PLANNER_API_KEY`。不要放進設定檔或命令列參數。PowerShell 可以隱藏輸入：

```powershell
$readerSecret = Read-Host 'API key' -AsSecureString
$env:LAYA_PLANNER_API_KEY = [System.Net.NetworkCredential]::new('', $readerSecret).Password
Remove-Variable readerSecret
python scripts/reader.py probe --allow-cloud
# 使用完畢清掉目前終端的 key：
# Remove-Item Env:LAYA_PLANNER_API_KEY
```

`probe` 會發一次合成測試請求，可能計費。正式 `play --allow-cloud` 才會送出結構化遊戲摘要（地圖、隊伍、背包、對話、進度）與儲存庫內的公開策略摘錄；不送 ROM、存檔或桌面截圖。每輪最多一次決策請求、預設三輪，無自動重試。模型選擇的 stage 仍受本機白名單限制，不能執行 shell 或任意程式。服務定價與資料保留依你選的供應商規則。

設定只存於 `.local/reader.json`，已排除 Git。`setup` 不覆寫既有設定；切換方式時明確編輯該檔，再跑 probe。每次 probe/play 使用雲端都必須加 `--allow-cloud`，沒有隱性 fallback。

## 3. 開始遊戲與看畫面

自備 ROM 放到 `roms/pokemon_red.gb`，或用 `--rom` 指定檔案。自動路線只支援已驗證的英文 Red revision，SHA-256 為：

```text
5ca7ba01642a3b27b0cc0b5349b52792795b62d3ed977e98a09390659af96b7b
```

```sh
python scripts/reader.py play --rom roms/pokemon_red.gb
# 只有選 C 才加 --allow-cloud
```

不需要作者的存檔，第一次從開場開始。終端會列 `http://127.0.0.1:.../`，打開即可看即時畫面。它只在自己電腦上提供本輪影格與摘要，沒有遊戲操作、目錄瀏覽或 ROM 下載。預設避開 SDL 原生視窗；想試原生視窗可加 `--window`。瀏覽器關閉不會停止遊戲，請在終端 Ctrl+C。

每輪最多約 60 秒遊戲控制預算，模型載入及收尾另計；預設三輪、`--episodes` 可選 1–20。模型慢或遇到不認得的狀況會停下，不會悄悄重跑或倒帶。每次啟動建立新目錄 `outputs/reader/<時間>/`，摘要的 `latest_state` 是接續點：

```sh
python scripts/reader.py play --rom roms/pokemon_red.gb --state outputs/reader/YOUR_RUN/game-02/final.state --episodes 3
```

請用摘要列出的實際路徑，不一定是 `game-02`。原存檔保持不變。每輪有 `gameplay.mp4`、`last-frame.png`、`steps.jsonl`、`final.state`；影片可直接用本機播放器看，預設不快轉，加 `--fast-forward` 才快轉。

第一道館之後的實驗控制器與路線仍在 repo，屬進階流程，請讀 [local-planner](local-planner.md)、[campaign 進度](league-progress.md)，不要跳過工程檢討閘門。換小模型或雲端模型只改階段安排，不會補出尚未實作的遊戲機制。

## 安全與故障回報

請勿上傳 `.local/`、`.cache/`、`.env*`、`outputs/`、`roms/`、`saves/` 或權重；即使是影片也先看過。API key 不會傳給遊戲子程序，HTTP 重新導向被拒絕；API 失敗不記原始 response body。詳見[本次公開檢查](public-review-20261028.md)。

回報時提供 Python/OS 版本、公開 commit、使用模式與已遮蔽的錯誤類型。不要提供 key、私人端點、ROM、存檔、完整使用者路徑或未整理的 logs。

官方參考：[Ollama API 相容範圍](https://docs.ollama.com/api/openai-compatibility)、[Qwen3 4B](https://ollama.com/library/qwen3:4b)、[Qwen3 8B](https://ollama.com/library/qwen3:8b)。替代模型尚未重跑作者的八館實驗；通過 probe 只代表通訊與輸出格式相容。

## English overview

Use Python 3.11, install the project, then run `python scripts/reader.py recommend` and `download-laya`. Supply your own authorized English Pokémon Red ROM matching the SHA above. Choose `setup --backend offline` (fixed stages + CPU Laya), `setup --backend local --download` (Ollama recommendation), or an explicitly configured HTTPS cloud provider with your own environment-variable key and `--allow-cloud`. Run `probe`, then `play --rom <file>`. Cloud probe/play require `--allow-cloud` every time and may incur charges.

The terminal prints a loopback-only browser viewer. Default runs are bounded to three episodes and preserve a fresh recording and save for each episode. Resume using `--state` with the actual `latest_state` in the summary. No ROMs, saves, credentials or model weights are distributed. This beginner flow targets the opening and first gym, not an unattended eight-gym run. Later routes in this research repository still require engineering review. Small/cloud model compatibility checks are not gameplay-quality benchmarks.
