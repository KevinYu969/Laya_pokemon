---
type: evidence
updated: 2026-10-23
---

# 加速操作、換首位與全隊練等影片

影片留本機，GitHub僅備份本說明與整理收據；沒有上傳ROM、存檔或原始輸出。

| 片段 | 本機檔案（專案相對路徑） | 時長與速度 |
|---|---|---|
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

## 網站

已在既有網站專案準備雙語文章與5段影片頁，使用`build:pages`保留造訪計數Worker。54頁靜態檢查與53項網站測試通過。Cloudflare CLI登入過期；瀏覽器存取Cloudflare受政策限制，本機瀏覽器驗收也遭URL政策拒絕，因此未發布，沒有嘗試繞過瀏覽器政策。
