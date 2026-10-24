---
type: evidence
updated: 2026-10-24
---

# 三樓半血換人：原生 Get'm 合併字形停檢

2026-10-24台北07:51:19.454141，Silph三樓`map208 (18,7)`、campaign frame1036697，系統停在`trainer_half_hp_pending_observation_or_enemy_changed`。卡比獸36級82/173，Laya已透過正常PKMN→隊伍→SWITCH選擇大嘴雀35級108/108；敵方為28級引夢貘人。其他隊員仍健康，這是辨識停檢，沒有新增戰敗或倒帶。

固定紅版字型將`'m`編成單一實體字格`$E5`。`Get'm! FEAROW!`的該格位於x4、y14，舊版一般單字格解析拒絕它。修正只適用已有半血換人owner、`switch_requested=True`、相同隊伍／敵方／目標，且整頁原始字格與摘要吻合的來源台詞；沒有放寬通用固定傷害解析。

固定來源[PrintSendOutMonMessage](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/engine/battle/common_text.asm)與[戰鬥主迴圈](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/engine/battle/core.asm)顯示印完台詞後會繼續繪HUD與出場動畫，沒有外層A等待。對此合字頁只有限WAIT、保持原pending；舊HUD尚未換好也不送A。後續完整新隊員戰鬥選單才讓既有管線結案，未知字格或其他敵人仍停檢。

獨立checkpoint複本只做無按鍵檢查，原檔雜湊保持。load後tick0 decoder為空白，不能當成原暫停幀HUD證據；無鍵tick1才見FEAROW／108/108與完整原生合字，local frame1不能冒稱campaign frame1036697。即時PNG與tilemap讀值可能有繪圖時間差。

作者先以半血換人／固定傷害／戰鬥共185項測試通過，父層另做完整回歸與獨立反例覆核。恢復只熱載程式、延續同一待完成換人；不刪pending、不重建基線、不寫遊戲記憶體或讀回舊局。此頁記工程修正，後續實戰結果另追加。
