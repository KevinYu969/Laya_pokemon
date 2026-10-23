---
type: evidence
updated: 2026-10-23
---

# 加速操作、換首位與全隊練等影片

影片留本機，GitHub僅備份本說明與整理收據；沒有上傳ROM、存檔或原始輸出。

| 片段 | 本機檔案（專案相對路徑） | 時長與速度 |
|---|---|---|
| 小霞、藍色徽章與TM11完整分段 | `outputs/videos/second-gym-cleared-20261023/second-gym-cleared-4x.mp4` | 38.73秒；完整原始分段後製4倍 |
| 小霞戰鬥節錄 | `outputs/videos/misty-battle-20261023/battle-4x.mp4` | 20秒；後製4倍模擬時間 |
| 小霞戰鬥節奏重建 | `outputs/videos/misty-battle-20261023/battle-wall-clock-reconstructed.mp4` | 5.93秒；依每步耗時重採樣 |
| 全員18級後正常換首位 | `outputs/videos/party-level18-20261023/party-1x.mp4` | 9.33秒；1倍模擬時間 |
| 月見山化石訓練家戰鬥節錄 | `outputs/videos/mt-moon-battle-20261023/battle-4x.mp4` | 20秒；後製4倍模擬時間 |
| 月見山戰鬥節奏重建 | `outputs/videos/mt-moon-battle-20261023/battle-wall-clock-reconstructed.mp4` | 7.27秒；依日誌重採樣 |
| 移動與接近訓練家 | `outputs/videos/accelerated-movement-v2-20261023/movement-4x.mp4` | 12.67秒；後製4倍模擬時間 |
| 快速戰鬥選單 | `outputs/videos/accelerated-battle-v3-20261023/battle-4x.mp4` | 20秒；後製4倍模擬時間 |
| 操作牆鐘節奏重建 | `outputs/videos/accelerated-battle-v3-20261023/battle-wall-clock-reconstructed.mp4` | 12.73秒；依每步耗時重採樣 |
| 正常換首位 | `outputs/videos/party-switch-complete-20261023/party-switch-complete.mp4` | 9.33秒；1倍模擬時間，Spearow換到首位 |
| 換人分經驗練等節錄 | `outputs/videos/balanced-training-20261023/battle-4x.mp4` | 20秒；後製4倍模擬時間 |
| 練等操作牆鐘節奏重建 | `outputs/videos/balanced-training-20261023/battle-wall-clock-reconstructed.mp4` | 6秒；依每步耗時重採樣 |

模擬時間影片省略模型等待；後製4倍不能當模型推論速度。牆鐘重建片使用原始影格，依相鄰日誌wall_seconds差額扣除review_pause_seconds，再重採樣；單步內等待位置近似，不是未剪輯桌面錄影。剪接保留原順序，原始影片留存。沒有生成或重演遊戲結果。

所有列出的MP4均逐幀解碼核對，收據記來源run、步驟、SHA與播放幀數。首版剪輯曾將FFmpeg輸出-t誤當來源範圍，速度／範圍不符，保留為私人草稿；修正成輸入-t並加入時長比對，以上v2/v3為驗證後版本。第一版換位片停在目標選擇頁，另接續下一原始分段至實際隊伍改序，成為9.33秒完整版。

## 全隊訓練

`balanced_training`選最低等級／經驗隊員，透過正常START→POKéMON→SWITCH選單換首位；戰鬥時讓低等隊員出場，再切健康強隊員接戰以分享經驗。每場記各成員的level、EXP、HP與隊伍順序，不以首位升級代表全隊升級。

第一輪全員至少12級，完成後停下核對再提高門檻、縮小等級差。這不是所有隊員已同級，也不是已完成最佳六人陣容。第一世代只有實際參戰且未倒下的隊員可獲分配，不能假設全隊共享EXP。

實測問題：換位目標頁同時有靜態▷與活動▶，已優先活動游標；原草地巡邏座標不是草地，改讀真實grass tile=82；戰鬥PKMN為合成字形，改用已核對FIGHT/ITEM/RUN二乘二選單右上格；護理師HEAL/CANCEL不能當隊伍取消。首隻烈雀曾倒下且沒有EXP，保留失敗；修正後已確認烈雀、尼多朗都獨立升級。

全員12級檢查點於2026-10-23台北17:32:29實際達成（烈雀12、尼多朗12、妙蛙草21），之後續練全員18級。另發生學招誤刪撞擊的控制錯誤，已留在[教訓](battle-lessons.md)及整理收據，沒有回讀洗結果；改由10級以上隊員直接野戰，不再每場把經驗分給主力。

全員18級檢查點於台北17:47:46完成：烈雀18、尼多力諾18、妙蛙草22。已正常保存後回主線並進入月見山；第二枚徽章與聯盟尚未完成。完整檢查點收據見`results/balanced-training-18-checkpoint-20261023.json`。

後續更新：第二枚藍色徽章已於台北18:19:12實際取得，隊伍妙蛙草24／尼多力諾19／烈雀18；逐館檢討後已正常回中心補滿HP／PP。第二館成果與速度檢討見`results/second-gym-campaign-20261023.json`。聯盟仍未完成。

## 網站

已在既有網站專案準備雙語文章與6段影片頁，含小霞成果，使用`build:pages`保留造訪計數Worker。54頁靜態檢查通過，網站既有53項測試亦曾通過。Cloudflare CLI登入過期；瀏覽器存取Cloudflare受政策限制，本機瀏覽器驗收也遭URL政策拒絕，因此未發布，沒有嘗試繞過瀏覽器政策。

## 主線續玩素材（2026-10-23）

以下追加10個影片版本，來源為實際執行09、10、13的已關閉PyBoy錄影；原始影格未生成或重演。相對路徑均指本專案本機檔案，MP4沒有上傳GitHub。

| 片段 | 本機檔案（專案相對路徑） | 時長、來源與剪輯方式 |
|---|---|---|
| 華藍市勁敵BLUE完整戰鬥 | `outputs/videos/cerulean-rival-20261023/cerulean-rival-post4x.mp4` | 40.47秒；09／video-000步52–142，後製4倍，含開場、四名對手、勝利與獎金 |
| 正輝、細胞分離器與船票 | `outputs/videos/bill-journey-20261023/bill-help-ticket-post4x.mp4` | 28.13秒；10／video-000步367–449，後製4倍，含進屋、協助、取得船票與離屋 |
| 25號道路登山男戰鬥節錄 | `outputs/videos/route25-battle-20261023/battle-4x.mp4` | 20秒；09／video-003步816–861局部，來源上限80秒，後製4倍；不是勁敵或道館戰 |
| 同場登山男戰鬥節奏重建 | `outputs/videos/route25-battle-20261023/battle-wall-clock-reconstructed.mp4` | 11.53秒；09／video-003步816–930，依每步耗時重採樣，等待位置近似 |
| 尼多力諾換首位準備勁敵戰 | `outputs/videos/cerulean-party-reorder-20261023/party-1x.mp4` | 8.67秒；09／video-000步1–13，1倍模擬時間；步14以實際隊序核對 |
| HM01教學完整選項 | `outputs/videos/cut-teaching-20261023/cut-teaching-emulated1x.mp4` | 34秒；13步487–537跨video-004／005／006／007，1倍模擬時間 |
| HM01教學快速版 | `outputs/videos/cut-teaching-20261023/cut-teaching-post4x.mp4` | 8.50秒；與上一列相同來源，後製4倍，保留選Growl、遺忘與學會CUT |
| 野外砍樹並走入枯葉道館 | `outputs/videos/cut-tree-entry-20261023/cut-tree-entry-post4x.mp4` | 4秒；13／video-009步777–800，後製4倍，正常隊伍CUT選單與移動 |
| 垃圾桶機關失敗與成功剪選 | `outputs/videos/vermilion-switches-20261023/vermilion-switches-selected-post4x.mp4` | 10.40秒；13步1023–1040及1416–1444，跨video-010／011／012，後製4倍並拼接兩段 |
| 馬志士完整戰鬥、徽章與TM24 | `outputs/videos/third-gym-cleared-20261023/lt-surge-full-badge-post4x.mp4` | 57.40秒；13／video-012步1483–1613，後製4倍，含主動換人、勝利、雷電徽章與獎勵 |

4倍是**後製播放速度**；1倍也是模擬時間，兩者均省略模型推論與人工檢討等待，不能當成模型判斷速度、實際操作速度或通關耗時。牆鐘節奏重建也不是未剪輯的桌面錄影。影片所含動作、來源模擬秒數與日誌實際時間分開記錄；日誌區間另拆出模型等待及檢討暫停，不能拿片長替代這些時間。

登山男4倍版受80秒來源上限限制，實際只涵蓋步816–861，最後一步部分截取；原剪輯腳本的候選區間816–930不是此20秒影片全部收錄的範圍。垃圾桶影片只保留一次找錯重置及最後成功開門；中間其他搜索與四次重置未收錄，不能將10.40秒剪選當作完整71次搜索過程或破解總耗時。

HM教學於台北2026-10-23 21:21:52實際核對妙蛙草招式為`[77,15,73,22]`：只替換Growl（45），保留Vine Whip（22）。野外CUT於21:24:30核對樹格`0x3D→0x2C`。第三枚雷電徽章於21:29:45取得，`badges_raw=7`；館戰中妙蛙草22／76 HP時主動換上尼多力諾，沒有把這次換人寫成妙蛙草倒下或全隊戰敗。這是第三館成果，聯盟尚未完成。

09／10來源、逐幀解碼及SHA收據：`results/cerulean-journey-clips-20261023.json`。正輝船票於台北20:45:10本次取得；新加入監測的`got_nugget`於20:46:21首次觀測到既有旗標，不當成金珠橋完成時間。13的五個影片版本、六張原影格截圖、來源分段SHA、事件UTC／台北時間及等待拆分見`results/third-gym-clips-20261023.json`。

## 岩隧失敗與修復素材（2026-10-23）

| 片段 | 本機檔案 | 實際內容 |
|---|---|---|
| 封招修正與換人獲勝 | `outputs/videos/rock-tunnel-lessons-20261023/disable-fix-switch-victory-post4x.mp4` | 32.733秒；步3290–3371。先排除被封的啄，亂擊未命中，再正常換尼多力諾以角撞擊勝出 |
| 藤鞭耗盡、全敗與自然恢復 | `outputs/videos/rock-tunnel-lessons-20261023/rock-tunnel-pp-exhaustion-blackout-recovery-post4x.mp4` | 38.567秒；步4107–4189。保留弱效居合斬、BLACKED OUT及正常中心恢復，結尾定格3秒 |

兩片均後製4倍並省略工程／檢討等待；不是實際牆鐘耗時。金錢由23145降至11572、經驗及已勝訓練家保留，沒有回讀洗掉敗北。來源23,903幀與成品完整解碼，10張截圖及25份檔案SHA核對；見`results/rock-tunnel-lessons-clips-20261023.json`。14的新低血閘門攔截屬後續實戰，沒有倒剪回13冒充已避免這次敗北。
