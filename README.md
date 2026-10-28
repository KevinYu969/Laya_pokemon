# Laya × 寶可夢：從本機部署到可重現實測


**2026-10-28 實際進度：冠軍之路三樓首開關已過，四天王尚未破關。** 已把麻痺／混亂後逃跑失敗的教訓寫入本機策略；因尼多王倒下，正執行正常補給至中心的有限救援行程。game29已恢復真實畫面，原生當機原因與未保存範圍均明記。[最新時間與問題紀錄](docs/league-progress.md)。


[![Tests](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml/badge.svg)](https://github.com/KevinYu969/Laya_pokemon/actions/workflows/tests.yml)

用現有 NUC，把 **Laya 決策模型**接到 **PyBoy Game Boy 模擬器**，研究小模型如何從遊戲狀態選擇按鍵，以及整個控制迴圈的速度、穩定性與限制。

這裡會公開程式、部署方式、實驗摘要與問題處理，並累積 [Kevin 個人網站](https://kevinkayu.com) Local AI 實驗室的文章素材。

## 目前進度

**八枚徽章、聯盟前勁敵 BLUE 已擊敗。** 2026-10-28台北10:35:51實際觸發勁敵勝利事件，拉普拉斯與卡比獸皆42級，用2瓶Hyper Potion、未見新倒下，隨後正常回中心全隊補滿。[本場紀錄](docs/league-progress.md)保留確切時間、資源與修補問題；其餘四人35–37級仍待均衡培養，四天王、冠軍與名人堂尚未完成。

**冠軍之路第二層**：全部徽章檢查、衝浪、第一層首石與第二層首開關已實際完成；戰後健康檢查暫停補給，仍未勝四天王。[重要關卡時間](docs/league-progress.md)持續記錄。

第八館坂木勝利時間仍為2026-10-25台北20:24:35，該館零補藥、零新增倒下，正常取得TM27。[第八館收據](results/eighth-gym-campaign-20261025.json)與[完整戰影片驗收](results/giovanni-gym8-clips-20261025.json)保留原始切點。

- [最新學招、補給與問題紀錄](docs/cinnabar-supply-and-lapras38.md)：32隻野怪、拉普拉斯34→38，正常以冰凍光束替換唱歌；保衝浪／泰山壓頂／奇異之光。
- 夏伯戰耗盡10份高級傷藥，其他五員逐370筆保持、沒有新增倒下。已檢討先補藥而未優先收尾的浪費，後續採半血門檻及有條件傷害判斷；不宣稱存活或一擊必勝。
- [9,656項完整回歸切點](results/code-validation-league-regression5-20261028.json)185.73秒通過，347份來源前後SHA一致；涵蓋TM24、正常補血中斷、具名FNT中心救援、野生戰鬥教訓與原生錄影參數，不含尚在開發的野外FullHeal。CI依頁首連結確認。逐鍵本機離線Laya／快取，工程開發與審查另計，Strata配置不變。
- [七名館員逐場勝利時刻](docs/cinnabar-gym-review.md)保留16隻KO與正常補給；[本機PyBoy即時畫面](http://127.0.0.1:8767/)可看真遊戲影格。
- 正式素材索引64片／212PNG含QA。新增[坂木完整戰原速／四倍兩片與13圖](results/giovanni-gym8-clips-20261025.json)，逐幀與畫面已核；勁敵新keyframes另行整理，影片留本機，網站未發布，原生SDL問題尚未修復。

通關耗時以[里程碑時間軸](docs/campaign-timeline.md)記錄；牆鐘、工程停檢、模擬遊戲時間與後製倍速分開，尚未公布全程通關時間。[第七館前置與問題紀錄](docs/seventh-gym-progress.md)持續更新。

<details>
<summary>較早階段的固定驗收</summary>

**30級歷史驗收：2026-10-24 台北09:34:08.310437，拉普拉斯已正常練到30級，六人回淺紅中心全補。** 這段由拉普拉斯獨立接戰，EXP19595→33943（+14348），其他五員逐6370筆完整保持；54次新Laya／6311快取／5被動等待。新排程319.594秒完成並回城，端點差349.610秒另含起跑前等待；都不是全程破關時間。[30級收據](results/lapras30-checkpoint-20261024.json)

目前固定隊伍為卡比獸40／尼多王36／伊布35／妙蛙花35／大嘴雀36／拉普拉斯30，仍五徽章、未全六人35級；已轉回金黃市主線。新增[25級正常忘招影片](results/lapras25-body-slam-clips-20261024.json)：原速18秒／後製4倍速4.5秒，同270幀，六張正式圖與一張QA，本素材階段累計36片／126張PNG含QA。影片留本機，網站未發布；[真正即時畫面](http://127.0.0.1:8767/)持續由PyBoy提供。

**25級歷史驗收：2026-10-24 台北09:28:18.687818，拉普拉斯正常升25級，只忘叫聲學會泰山壓頂，六人已回淺紅中心補滿HP／狀態／PP。** 隊伍為尼多王36／拉普拉斯25／伊布35／妙蛙花35／大嘴雀36／卡比獸40，仍五枚徽章，尚未全六人35級、希魯夫坂木／第六館／聯盟未完成。[25級收據](results/lapras25-checkpoint-20261024.json)、[六人補練紀錄](docs/six-party-training-progress.md)與[時間軸](docs/campaign-timeline.md)保留固定端點。

從16級端點至這次中心驗收，拉普拉斯與卡比獸各增加14,405EXP，其他四員逐筆資料保持；23次正常回中心補給都有護士文字與恢復證據，選定觀測沒有倒下。25級遇到尚未支援的忘招頁時先停檢，核對固定紅版來源後在同場正常續行，保留水槍／唱歌／白霧。13,526筆動作包含72次新Laya判斷、13,420次快取、34次被動等待；1193.953秒端點差含514.179秒工程停檢，不能當純戰鬥或全程通關時間。

該切點[程式回歸收據](results/code-validation-lapras25-20261024.json)為5476項通過、26.52秒、1項既有SDL提示；5450是下方16級歷史切點。25級收據建立前已核的歷史備份為[`53b04cc6`](https://github.com/KevinYu969/Laya_pokemon/commit/53b04cc6)／284檔，[CI 40049407470成功](https://github.com/KevinYu969/Laya_pokemon/actions/runs/40049407470)，涵蓋先前5450版本；目前公開版本以倉庫提交與頁首Tests為準。34片／119張PNG（含QA）是該歷史切點，新25級影片另列於上方；網站尚未發布，原生SDL未修，8767仍顯示真PyBoy影格。後續補練另立工作，不回填此收據。

**16級歷史驗收：2026-10-24 台北09:08:24.734183，拉普拉斯正常升16級、第三槽學會唱歌，六人已回淺紅中心全補。** 這一段拉普拉斯EXP4668→5190、卡比獸67563→68085，各得522；另外四員保持。此切點隊伍為尼多王36／拉普拉斯16／伊布35／妙蛙花35／大嘴雀36／卡比獸37，仍五枚徽章，尚未全六人35級。補練持續中，本頁以固定收據更新，不以每秒變動改寫驗收結果。見[16級收據](results/lapras16-checkpoint-20261024.json)、[六人補練紀錄](docs/six-party-training-progress.md)與[時間軸](docs/campaign-timeline.md)。

這是正常換低等隊員出場、再換健康卡比獸接戰取得的分經驗，不是全隊被動共享。保留Ditto變身及擊倒後唱歌收尾的兩次工程停檢，再正常回城治療；沒有隊員倒下或回讀洗結果。新的全隊35目標另立有界工作，不能把16級檢查點寫成全隊已達標。

該切點新增[首場分經驗影片收據](results/six-party-shared-exp-clips-20261024.json)：只拍首輪波波戰兩員各得88EXP，1x模擬時間46.266667秒／後製4x11.566667秒，並非16級學唱歌影片。新增2片、4正式PNG與1QA，本素材階段累計34片／119張PNG（含QA）；影片與網站尚未發布。當時[本機回歸](results/code-validation-six-party-20261024.json)為5450項通過、31.88秒、1項既有SDL提示，測試不代替全程實戰或速度基準。原生SDL故障仍未修，[8767真實即時影格](http://127.0.0.1:8767/)目前由背景服務正常顯示。

**入隊後歷史切點：2026-10-24 台北08:39:04.208328，六人已正常回淺紅中心`map154 (3,4)`，HP／狀態／PP全滿，仍為五枚徽章。** 希魯夫3F火箭隊已勝、Card Key正常開門、7F勁敵BLUE已勝；08:22:41.084612正常領到15級拉普拉斯並選NO保留原名。該切點隊伍為卡比獸37／尼多王36／伊布35／妙蛙花35／大嘴雀36／拉普拉斯15；尚未全六人35級，希魯夫坂木、第六館與聯盟均未完成。見[主線進度](docs/silph-company-progress.md)、[勁敵收據](results/silph-rival-campaign-20261024.json)、[拉普拉斯收據](results/lapras-gift-campaign-20261024.json)與[時間軸](docs/campaign-timeline.md)。

[六人回城與往返校準收據](results/six-party-return-and-calibration-20261024.json)另核08:40:36正常從15號道路草地回中心，隊伍與EXP均保持；這只驗證正常路線，沒有把它寫成拉普拉斯已分到經驗或六人訓練成功。

勁敵戰保留卡比獸麻痺、56/177HP時正常換大嘴雀接戰，沒有倒下或回讀洗結果；戰後先正常回中心補滿。之後game23正常停止，game24從同一最新final接續，來源雜湊與首次完整進度／畫面一致，見[交接收據](results/session23-to24-continuity-20261024.json)。拉普拉斯加入時HP64/64、EXP4218、招式水槍／叫聲，原五名可讀資料及背包／金錢保持；這是NPC贈送成果，還不是完成最佳六人陣容或低等隊員訓練。

新增[勁敵完整戰影片收據](results/silph-rival-clips-20261024.json)：1x模擬時間327.333333秒／後製4x81.833333秒，8張正式PNG與1張QA，本素材階段累計32片／114張PNG（含QA）。影片與截圖保留本機，片長不作遊玩牆鐘或全程通關耗時。[影片索引](docs/accelerated-clips.md)列明原速、後製速度及範圍；網站尚未發布。

拉普拉斯領取接線當時完整回歸固定切點為**5362項通過**；後續六人分經驗與訓練不在該版本範圍，不能回填為當時已全測。本次整理前已核對的歷史GitHub備份為[`25739bcb`](https://github.com/KevinYu969/Laya_pokemon/commit/25739bcb4e3deca80a660677bcad852a3fa8b4f2)（261檔），[CI 40043474162成功](https://github.com/KevinYu969/Laya_pokemon/actions/runs/40043474162)；目前公開版本與驗證請以本倉庫提交及頁首Tests連結為準。原生SDL／GLFW事件阻塞仍未修，`8767`顯示的是真PyBoy framebuffer串流，不能說桌面視窗已修好。

**Card Key歷史固定切點：2026-10-24 台北07:42:07.531500，Card Key已正常取得並回金黃中心`map182 (3,4)`補滿五人HP／狀態／PP，金錢42656，仍為五枚徽章。** 卡比獸與尼多王36級，伊布、妙蛙花、大嘴雀35級。見[希魯夫公司進度](docs/silph-company-progress.md)、[Card Key實戰收據](results/silph-card-key-campaign-20261024.json)及[時間軸](docs/campaign-timeline.md)；本切點只驗收5F取卡與補給，後續3F、勁敵／坂木及第六館尚未列為完成。

5F實際打贏SCIENTIST的四隻26級寶可夢，以及ROCKET的33級阿柏怪，保留兩場完整原生勝利；卡比獸35→36、泰山壓頂消耗8PP，正常補給後恢復。取物閉合於07:39:27.349706，原有背包保持、只新增一份Card Key；完整`KEVIN found CARD KEY!`原像素截圖與QA留本機，本次未新增影片數。取卡主線162筆為5次新Laya推論／157次快取／0次被動controller；142.000秒端點差包含132.781秒工程停檢，不能當純遊玩或通關耗時。

**進市歷史切點：2026-10-24 台北07:34:16.540133，已正常進入金黃市寶可夢中心`map182 (3,4)`，五人HP／狀態／PP全滿，仍為五枚徽章。** 玉虹屋頂已正常買一瓶清水，再交給7號道路守衛取得通行；金錢40566→40366，買到的唯一一瓶水其後正常消耗，其他背包與隊伍資料保持。見[進入金黃市與兩次校準](docs/saffron-entry-progress.md)、[買水收據](results/celadon-water-purchase-20261024.json)、[守衛收據](results/route7-guard-water-20261024.json)及[時間軸](docs/campaign-timeline.md)。此段保留進市時的歷史驗收；後續Card Key與正常補給以上方新切點為準。

守衛流程保留兩次工程停檢：`I'm`的單tile`'m`、以及▼清掉第18格末點後的捲頁。兩次都維持同一交易與基線，只有一次RIGHT觸發、沒有重複給水；不是首次無卡關。買水新增[原速／4倍速兩片與5張PNG收據](results/celadon-water-clips-20261024.json)（4張正式截圖＋1張QA）；守衛再新增[24秒原速／6秒後製4倍速兩片與5張PNG收據](results/route7-guard-clips-20261024.json)，這個素材階段累計30片／105張PNG（含QA），並非歷來總數。影片留本機，播放長度不能當通關耗時。

**2026-10-24 台北05:35:47，第五館阿桔已勝，取得靈魂徽章與TM06，現共五枚徽章。** 尼多王升36，於雙彈瓦斯會心自爆時與對手同倒；原生判Kevin勝利。05:38:17已正常回中心補滿全隊HP／狀態／PP，其餘卡比獸、伊布、妙蛙花、大嘴雀35級。見[第五館與倒下檢討](docs/koga-gym-review.md)、[實戰收據](results/koga-gym-campaign-20261024.json)與[時間軸](docs/campaign-timeline.md)；八館與聯盟尚未完成。

**後續主線：2026-10-24 台北06:24:07取得HM03衝浪，06:30:20交回金牙、領取HM04怪力；兩招也已正常教會並關閉選單。** 尼多王以衝浪替換撞擊，06:54:14.286156完成閉合驗收；卡比獸以怪力替換頭錘，06:55:56.227746完成閉合驗收。新招PP均15，兩份HM各保留1份，其他招式與隊員資料保持，教學沒有扣款。主流程其後於06:59:50.161246正常回淺紅中心`map154 (3,4)`，全隊HP／狀態／PP全滿。見[狩獵區與領取收據](results/safari-zone-campaign-20261024.json)、[兩次教學收據](results/hm-teaching-campaign-20261024.json)與[問題修正紀錄](docs/safari-zone-progress.md)。

Surf教學經過五次工程停檢，包含長背包箭頭、原生prompt時序、忘招框重繪、學會收據確認與inactive START關頁校準；停止紀錄均保留，不能寫成首次無卡關。教學版本當時4545項回歸通過，購水前版本4764項通過；其後曾有4927項完整回歸通過（19.97秒），但早於後續Card Key時序修補與金黃市物件檢查，不能當成所有最新程式已全測。新候選及局部接線另行驗證，測試不能代替遊戲證據。教學成果只證明領取、教會及關頁，野外衝浪／推石仍待驗證。當時本機快照[5272項完整回歸通過](results/code-validation-saffron-20261024.json)（20.39秒、1項既有SDL提示），涵蓋守衛、金黃物件、卡片門橋接及半血換人合字；Lapras在該切點仍是純候選，後續runtime接線不在此測試範圍。當時已核備份為`bfd67be`（241檔），[CI 40038892963成功](https://github.com/KevinYu969/Laya_pokemon/actions/runs/40038892963)；最新備份與驗證切點另列於本頁上方。

**北返中繼歷史：2026-10-24 台北07:12:11，正常抵達玉虹百貨屋頂。** 14號道路中繼點重設造成的兩格空轉已保留並修正，之後多段樓梯實況正常。這是買水前的舊切點；最新結果以上述金黃中心驗收為準。[北返與導航檢討](docs/northbound-celadon-progress.md)及[兩次HM操作影片收據](results/hm-teaching-clips-20261024.json)已整理，影片留本機。

Windows 原生視窗的 SDL／GLFW 事件阻塞仍未修復；現階段以真實 PyBoy 運算並發布影格，可開啟[本機即時遊戲畫面](http://127.0.0.1:8767/)（[使用說明](docs/live-game-view.md)）。這不是 Showdown 回放，也不代表原生桌面視窗已修好。離線 Laya 與私人 Strata 配置維持。已有[一輪自動補練的原速／四倍速影片收據](results/fuchsia-training-clips-20261024.json)，影片與截圖保留本機。

**淺紅市已抵達：2026-10-24台北04:08:43**，五人已正常中心恢復HP／狀態／PP，大嘴雀中毒治好；妙蛙花34／大嘴雀33／尼多王32／伊布30／卡比獸30。沿路輪換的五名隊員都取得經驗，正在準備全隊補練與第五館。14號道路的程序停滯保留診斷，正常保存最新狀態再續行，沒有倒回戰前。見[淺紅市與重啟鏈收據](results/fuchsia-arrival-20261024.json)。

更新：**2026-10-24 台北03:39:36，已正常收服30級卡比獸，隊伍擴為五人；目前四枚徽章。** 同一場共投11顆超級球，20→9；完整核對Caught、圖鑑、暱稱選NO、第五名隊員及兩個關閉介面的野外影格，沒有回讀洗結果或新倒下。03:47:23已正常回紫苑中心補滿全隊，再由健康隊員輪換南下淺紅市。見[卡比獸收服與五人補給收據](results/route12-snorlax-capture-20261024.json)。第五館、聯盟與最佳六人隊仍未完成。

隊伍為卡比獸30／伊布30／大嘴雀32／尼多王31／妙蛙花33。伊布01:58:54正常練到30級，02:05:49購買20顆超級球；妙蛙草02:10自然進化並升33級，02:20正常笛子喚醒卡比獸。捕捉途中先後正常換上尼多王、大嘴雀承傷，血量與原投球基線保留。早期[10投進度](results/route12-snorlax-progress-20261024.json)保留為歷史，最新結果以上述收服收據為準。新增[訓練與進化6片／26圖](results/training-route12-clips-20261024.json)及[笛聲與前四投4片／16圖](results/snorlax-first-capture-clips-20261024.json)，素材留本機；[影片索引](docs/accelerated-clips.md)列明實際內容與播放時間。

寶可夢塔已完成：嘎啦嘎啦安息、三名塔頂火箭隊正常擊敗、富士老人救出，01:17:22已持有笛子、01:17:23領取事件成立。見[寶可夢塔收據](results/tower-journey-campaign-20261024.json)與[勁敵及龍怒教訓](results/tower-rival-campaign-20261024.json)。所有戰鬥／移動按鍵仍由本機Laya離線分類；私人Strata配置不變，工程與人工複核時間另計。

火箭隊基地坂木、透視鏡、月石正常進化、11段箭頭與B4F／B1F電梯已有[實戰收據](results/rocket-hideout-campaign-20261024.json)。新增素材共24支影片、80張精選PNG（基地16／46＋塔內8／34），影片只留本機；1x依模擬器影格，4x為後製，片長不能當通關耗時。

第四館莉佳於**2026-10-23台北22:44:13**取得彩虹徽章，已核對`beat_erika=true`、`badges_raw=15`與TM21實際入袋，完成逐館速度與邏輯檢討，再正常出館補滿全隊HP／PP。第四館完成時隊伍為大嘴雀29／尼多力諾26／妙蛙草30；妙蛙草已將毒粉換成飛葉快刀。見[第四館收據](results/fourth-gym-campaign-20261023.json)、[第四館4段影片驗證](results/fourth-gym-clips-20261023.json)與[里程碑時間表](docs/campaign-timeline.md)。

岩山隧道的**台北21:55:00全隊敗北**保留；逐幀保護保存並停住，檢討缺少補給路線仍深入、低血支援與藤鞭耗盡。正常回城保留經驗與金錢損失後續走，新損耗閘門已在22:06低血時實際攔下，經正常補給通過岩隧，再完成第四館。見[敗北與修復收據](results/rock-tunnel-loss-20261023.json)。第三館與更早歷史見[馬志士收據](results/third-gym-campaign-20261023.json)、[第三館5段影片](results/third-gym-clips-20261023.json)及[小霞收據](results/second-gym-campaign-20261023.json)。

第四館後已於**23:03:51正常領取25級伊布**，隊伍擴為四人；**23:19:36尼多力諾正常學會泡沫光線**，只替換瞪眼、消耗一份TM11並正常關閉選單。火箭隊守衛勝利後回中心補給，23:23:35觸發海報暗門並進入地下基地。見[組隊與教招收據](results/party-expansion-campaign-20261023.json)、[伊布／隊伍影片收據](results/party-expansion-clips-20261023.json)。四人仍須輪換訓練，尚未組成最佳六人隊。

本機Laya離線分類按鍵、私人Strata選階段；主程式與模型常駐，60秒切存檔／錄影，不再每分鐘重載。第一枚灰色徽章的存檔回讀見[首館成果](results/first-gym-campaign-20261023.json)。

2026-10-23 的歷史整隊檢查點：**台北17:47:46，烈雀18／尼多力諾18／妙蛙草22級**。兩位備用隊員原本各3級，經正常SWITCH換首位、換人分經驗，再自行野戰升級；不是全隊自動共享EXP，當時尚非所有隊員同級。見[12級檢查點](results/balanced-training-checkpoint-20261023.json)與[18級檢查點](results/balanced-training-18-checkpoint-20261023.json)。

保留失敗：第三道路整隊敗北未回讀洗結果；另有22級學毒粉時誤刪撞擊的控制錯誤，實際招式已變更，沒有SDK寫回。後續已實戰驗證尼多力諾23級略過聚氣、妙蛙草以居合斬替換叫聲、30級飛葉快刀替換毒粉，以及大嘴雀25級略過鸚鵡學舌；逐項核對真實招式與收尾。已加入分頁狀態鎖、戰敗檢討與正常補給，持續記錄[問題與教訓](docs/battle-lessons.md)。

已產生**4分8.53秒第一道館成果影片**（480×432、30fps），包含館內對戰、小剛與領獎收尾；[公開驗證摘要](results/first-gym-clip-20261023.json)。影片留本機，按原時間順序串接並移除重複卡住畫面，完整原片保留；播放時間為模擬時間，省略推論等待。未上傳影片或發布網站。

這是控制器提供尋路、選單及戰術子目標，再由本機Laya分類按鍵的實機成果；**尚未完成八館、聯盟與全程自主通關驗證**。研究所首戰的敗北紀錄保留，沒有回讀戰前改寫勝負。歷史見[雙模型實測](results/strata-live-20261023.json)、[組隊摘要](results/team-building-20261023.json)、[開場摘要](results/live-run-20261023.json)。

本機已有 **21 秒命名短片**與 **90 秒離家到取得妙蛙種子的實測影片**，公開檔案驗證摘要見[命名紀錄](results/kevin-naming-clip-20261023.json)與[開場流程紀錄](results/opening-to-bulbasaur-clip-20261023.json)。影片留在本機，尚未對外發布。

另有 [110 秒首戰敗北紀錄](results/first-rival-battle-clip-20261023.json)、[90 秒升等／取得包裹紀錄](results/level6-and-parcel-clip-20261023.json)與[25 秒取得圖鑑紀錄](results/pokedex-clip-20261023.json)，保留成功與失敗樣本。

正式遊戲目標：**培養並升級隊伍 → 完成必要劇情 → 八枚道館徽章 → 四天王與冠軍 → 名人堂登錄**。目前控制器仍是分段驗證原型，尚未具備經驗證的全程自主通關能力。

已加入[紅／藍版組隊、學招與捕捉策略](docs/team-strategy.md)：以妙蛙花、尼多王、勇基拉、拉普拉斯、卡比獸、閃電鳥為暫定通關方向，已完成補球與首隻尼多朗♂捕捉。這是長程策略目標，並非六隻已取得；學招成功依上述各項實戰紀錄核對，其他學招、稀有怪削血與PC管理仍待實機校準，遇到未知流程會保存狀態停止。

| 項目 | 狀態 |
|---|---|
| Windows／Python 3.11 獨立環境 | 已部署；CPU PyTorch、Laya、PyBoy 相依檢查通過 |
| 真實 Laya 權重 | 已下載並固定 revision，CPU 推論成功 |
| 合成按鍵決策測試 | 7 個情境皆符合預期；只是介面與控制語意檢查 |
| PyBoy 桌面常駐控制與 JSONL 日誌 | 第一館與全員18級已驗證；60秒保存分段，單次模型操作逾時60秒，每館與真正戰敗強制檢討 |
| MP4 錄影管線 | 已產生並解碼驗證 2 秒／60 幀／30fps 測試片 |
| 寶可夢遊戲結果與影片 | 本機有 21 秒命名、90 秒取得初始流程與首輪卡關影片；公開摘要，影片尚未發布 |
| 短路線／對話／戰鬥對照 | 已規劃，尚無完成率數據 |

</details>

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

新增[加速操作與全隊訓練素材](docs/accelerated-clips.md)：移動12.67秒、戰鬥20秒、正常換首位9.33秒，以及換人分經驗訓練片段。所有影片留本機、逐幀解碼核對；4倍後製與依日誌重建牆鐘節奏均分別標示。新雙語網誌與5段影片頁已完成建置，Cloudflare登入待恢復，尚未發布。

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
- [紅版完整主線與組隊知識庫](docs/pokemon-red-strategy-guide.md)：供 Strata 檢索，涵蓋道館、主線依賴、傳說與四天王；不代表已全部通關。
- [戰敗教訓與恢復規則](docs/battle-lessons.md)：整隊敗北立即保存與暫停，完成原因、證據、調整及驗證後才續玩；單隻倒下正常換人。

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

新增[三段4倍速真PyBoy影片收據](results/victory3f-clips-20261028.json)：正常Hyper補血5.83秒、移動推石27.07秒、倒下後換人取勝10.90秒；3張原始截圖、8張核對圖均留本機，不隨Git上傳，也未發布至個人網站。
