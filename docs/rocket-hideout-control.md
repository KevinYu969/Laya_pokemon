---
type: implementation-notes
updated: 2026-10-23
---

# 火箭隊基地：箭頭、鑰匙與正常遊戲控制

已正常打贏遊戲中心守衛、回中心補給，台北23:23:35.632412按海報開關進入基地；B3F三段箭頭與B4F守衛戰完成，正常再對話並撿取電梯鑰匙。尼多力諾升至27級，尚未擊敗基地坂木或取得透視鏡。

箭頭不由外部逐格重播RLE。控制器只在已核對站位發出一次方向子目標，交本機Laya分類；踏入後由遊戲自行滑行，外部只等待。停止須同時核對預期落點、停止格`0x5E`、移動狀態清零及兩個連續且不同的觀測影格。離開落點即清除穩定樣本，同一影格若位置／旗標矛盾則停止檢討。

唯讀getter在同一影格讀取`CD38`模擬輸入索引、`CD6B`輸入忽略遮罩、`CFC5`步行計數與`D736 bit7`旋轉旗標，前後影格必須一致；未知讀值不以零代替。背景格網另保留真正逐格相等的可見座標、觀測影格及位置，不能填一個合成`verified=true`解鎖。

普通路段沿固定來源路線並避開所有其他箭頭觸發格；滑行期間不累計一般導航卡住次數或學習失敗邊。每段完成有不同的存檔／截圖名稱，避免後一段覆蓋前一段證據。

實戰首段於台北23:38:51.827147核對map201 `(13,11)→(10,11)`；後兩段23:40:23及23:40:24完成。返程亦發現樓梯的來源落點不等於實際走出位置：B4F回B3F後會走到`(19,19)`，不能沿來源起點再踩`(19,18)`樓梯回彈。現在普通路段避開該格，依真實格網接回安全路徑。

鑰匙、透視鏡以背包實際持有判斷，沒有虛構`got_lift_key`或`got_silph_scope`事件；守衛掉鑰匙與已撿取分開，遊戲中心守衛也沒有獨立的beat事件。新增事件首次可讀就為True只算基線，不能杜撰完成時間。

固定來源：[B3F腳本](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/scripts/RocketHideoutB3F.asm)、[B4F腳本](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/scripts/RocketHideoutB4F.asm)、[WRAM宣告](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/ram/wram.asm)、[移動旗標](https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/constants/ram_constants.asm)。RAM位置以配置重算及[官方PyBoy 2.8.1常數](https://github.com/Baekalfen/PyBoy/blob/v2.8.1/pyboy/plugins/game_wrapper_pokemon_gen1_constants.py)多個錨點交叉核對；測試用的來源座標／事件資料保存在`tests/data/rocket-source-fixture.json`，不依賴私人輸出或ROM。
