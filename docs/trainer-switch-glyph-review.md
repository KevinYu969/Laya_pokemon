---
type: evidence
updated: 2026-10-24
---

# 三樓半血換人：原生 Get'm 合併字形停檢

2026-10-24台北07:51:19.454141，Silph三樓`map208 (18,7)`、campaign frame1036697，系統停在`trainer_half_hp_pending_observation_or_enemy_changed`。卡比獸36級82/173，Laya已透過正常PKMN→隊伍→SWITCH選擇大嘴雀35級108/108；敵方為28級引夢貘人。其他隊員仍健康，這是辨識停檢，沒有新增戰敗或倒帶。

固定紅版字型將`'m`編成單一實體字格`$E5`。`Get'm! FEAROW!`的該格位於x4、y14，舊版一般單字格解析拒絕它。修正只適用已有半血換人owner、`switch_requested=True`、相同隊伍／敵方／目標，且整頁原始字格與摘要吻合的來源台詞；沒有放寬通用固定傷害解析。

固定來源[PrintSendOutMonMessage](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/engine/battle/common_text.asm)與[戰鬥主迴圈](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/engine/battle/core.asm)顯示印完台詞後會繼續繪HUD與出場動畫，沒有外層A等待。對此合字頁只有限WAIT；舊HUD尚未換好也不送A。最初要求等完整新隊員指令頁才結案，後續實戰證明此條件過嚴，修正如下；未知字格或其他敵人仍停檢。

獨立checkpoint複本只做無按鍵檢查，原檔雜湊保持。load後tick0 decoder為空白，不能當成原暫停幀HUD證據；無鍵tick1才見FEAROW／108/108與完整原生合字，local frame1不能冒稱campaign frame1036697。即時PNG與tilemap讀值可能有繪圖時間差。

作者先以半血換人／固定傷害／戰鬥共185項測試通過，父層另做完整回歸與獨立反例覆核。恢復只熱載程式、延續同一待完成換人；不刪pending、不重建基線、不寫遊戲記憶體或讀回舊局。此頁記工程修正，後續實戰結果另追加。

## 換人後敵方先行動：第二次真實停檢

08:07:01.527273，保留同局恢復後，只有兩筆被動WAIT就到campaign frame1036953：完整大嘴雀35級108/108，原生`Enemy HYPNO / used DISABLE!`。控制器仍在等新指令頁而停於`trainer_half_hp_pending_ui_unverified`。第一版並沒有誤按A，但忽略換人已消耗我方回合、敵方會先出招的來源時序。

固定來源core:2409–2438設定已用回合並正常SendOutMon，主迴圈324–338先選敵方招式，才回下一輪指令。新窄修保留兩個採樣入口：完整Get'm原生頁加正確新隊員HUD可完成換人交接，但本筆仍只WAIT；仍是舊HUD則保持有界等待。若取樣已錯過該頁，只接受本次已觀測的同敵`USED DISABLE!`完整兩行與完整新隊員HP／等級／狀態及其餘格一致，交回原戰鬥管線，本筆也只WAIT。沒有泛開所有敵方文字或由人工直接清pending。

新版相關202項測試由作者與父層分別通過；此前5272項完整回歸屬第一版快照，不能冒稱已涵蓋本次後補。後續測試及實戰結果分別記錄。
