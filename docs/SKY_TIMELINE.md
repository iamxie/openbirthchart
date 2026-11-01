# 天象時間軸 / Sky timeline

此功能位於開發分支，尚未合併或公開發佈。輸入當地起訖時間（到分鐘）與
IANA 時區，按「開始計算」。不需要地點或個人檔案。

- 逆行檢查水、金、火、木、土、天、海、冥；日、月不列逆行。
- 相位僅含水星至冥王星八顆行星的 28 組配對（不含日、月），只計算 0、90、120、180 度。
- 色帶代表容許度內區間，菱形代表精確成相；同一色帶可保留多次成相。
  零容許度只顯示精確事件，不把單一成相延伸成整段色帶。
- 每十分鐘使用固定 LibEphemeris／Skyfield 路徑計算黃經與當下速度。
  始末時刻一定包含，最後不足十分鐘的區段也會檢查。
- 以速度變號搜尋轉逆／順行；以有方向的角度搜尋相位目標及容許度邊界。
  相對速度變號時先定位極值再分段求根，即使兩端都在容許度外，仍檢查短暫
  進出與多次成相。合相／對分使用圓周角度處理，不將 0／360 度跳接當成事件。
- 局部二分求根的時間區間收斂至 0.125 秒以內，事件結果保留秒級顯示。
  這是數值停止條件，不代表星曆或未來 UTC 的絕對誤差為 0.125 秒。
- 區間依精算後的邊界重建；起訖時已符合條件會標示截斷，不推測查詢外日期。

有限取樣不是對任意曲線的完備證明：若同一十分鐘內有多個未在端點速度顯露的
轉折，仍需更密的驗證。此演算法針對目前固定引擎的八顆天體；新增其他運動模型
或天體時須重新驗證，不能直接沿用完整性結論。診斷 CLI 可選 60 秒掃描來比較。
既有個人星盤的位置／宮位計算引擎不變。

時間沿 UTC 軸掃描，再轉回所選時區；跨夏令時間不漏算／重複實際時刻。
重複鐘點須選第一次或第二次，不存在的鐘點拒絕。日期安全範圍沿用現有產品。

## 全域相位容許度

上方「設定」是唯一修改入口，包含個人星盤的十種相位；天象時間軸取用其中四種。
預設值沿用原星盤（0 度 4 度；90／120／180 度各 3 度），支援 0～15 度、一位小數。
「套用」後保存至 Documents/openbirthchart/data.sqlite 的 app_settings/aspect_orbs，
重開保留；「取消」不存；「恢復預設值」先填回預設，仍需套用才保存。

新個人檔案只保存個人輸入，不包含另一套容許度。舊檔案讀入時忽略其獨立容許度，
下次保存會使用簡化格式，不會反向覆蓋全域設定。沒有批次刪除或重建個人資料。
個人星盤立即用已有位置重判相位；時間軸清除舊結果，提示手動重新計算。
正在計算時不能套用容許度變更，需完成或取消後再改；寫入失敗不改目前有效設定。
報告保留該次結果實際使用的容許度，供追溯。

## 操作與進度

日期／時間共用個人星盤的文字輸入元件、內距及區塊樣式；時間軸時間欄只接受 HH:mm。
進度依序顯示掃描區間、細查事件及建立區間，數量均為真實完成數；測得速度後才
估計目前階段剩餘時間。取消會停止並回收背景程序，不交付不完整結果。

時間軸使用完整寬度；點選色帶開啟可縮放的事件詳情視窗。低高度使用「功能」選單切換頁面。
篩選、縮放與選取不會重新計算。月／週／日是 30／7／1 天的時間視窗。

## 開發與驗證

預設程序數為 max(1, 邏輯處理器數 - 4)，並以實際批次數為上限；Windows 跨處理器
群組計數。16 個邏輯處理器會使用 12 個程序。此政策不設定 CPU affinity，亦不將
硬體資訊放進正常 UI。每個程序限制數學函式庫為單執行緒，工作採有界批次。

scripts/check_timeline.py 記錄實際運算、PID、進度及取消結果；--sample-step 60 可
用較密掃描驗證。--timeline-smoke --smoke-output <new-directory> 是隔離的 UI／EXE
診斷模式，明確強制兩程序驗證 frozen spawn，另驗證全域設定保存、圖面及取消。
正常啟動仍使用自動政策；診斷不使用個人資料庫。

## English

The development Sky timeline accepts minute-resolution local endpoints and an IANA
zone. It scans every ten minutes, including both endpoints, then refines stationary
points, exact aspects and orb boundaries. Retrograde checks exclude the Sun and Moon;
aspects use the 28 pairs from Mercury through Pluto, excluding the Sun and Moon for 0°, 90°, 120° and 180°.

Directed angular crossings and relative-speed extrema allow short orb visits and
multiple exact hits between coarse samples to be found. Refined boundaries define
bands; zero orbs yield exact markers only. Root brackets stop within 0.125 seconds,
which is a numerical criterion, not an absolute astronomical accuracy claim. Finite
sampling is not a completeness proof for arbitrary curves with multiple hidden turns;
changes to bodies or motion models require renewed validation.

Settings is the sole aspect-orb editor. Values persist in SQLite app_settings and
apply to both modes. Personal profiles no longer store editable orb rules; legacy
rules are ignored on load. Birth-chart aspects refresh from existing positions;
timeline results are cleared for manual recalculation. Running calculations block
settings changes. Failed saves leave effective settings unchanged.

The worker limit is logical processors minus four, with a minimum of one and a cap
based on available batches. The explicit smoke mode overrides this to two workers.
Progress counts actual work and estimates only the current stage. Cancellation joins
workers. Pinned numerical dependencies and ephemeris data are unchanged.

## 星座歷程、同時事件與文件匯出

色帶以虛線標示換座，相位色帶上／下列分別對應第一／第二顆天體。
較窄區段不硬塞文字，懸停可讀星座順序，點選可讀完整起訖表。
使用與位置引擎相同的地心回歸黃道十二星座；不是天文星座邊界。
沿十分鐘掃描的黃經跨越 30 度倍數時局部求根；絕對速度反轉也分段查找，
因此保留順行跨座、逆行跨回及同一段內多次換座。切點歸入後一段；查詢最後端點包含。
星座計算沿用事件求根的停止條件與有限取樣限制，不改既有逆行／相位定義。

詳情分「星座歷程與精確成相」及「同時事件」兩頁，能返回上一個事件。
同時事件預設取整段區間交集，也可切至事件開始、每次精確成相、事件結束當下。
列表使用所有計算結果，不受圖面篩選影響，顯示實際重疊起訖及重疊期間的星座。
僅共用一個端點也列為同一瞬間，不誤稱整段時間都同時發生。

「匯出文件」可選全部結果，或所選事件（附重疊事件列表）。文件語系獨立於 UI，
目前提供繁體中文與英文。範本沿用 templates/report/<locale> 的 labels.json、style.css，
並新增 timeline-labels.json、timeline.html、timeline.css；複製語系資料夾即可擴充。
HTML 單檔內嵌 CSS／SVG，無外部字型、網路資源或 JavaScript；包含查詢條件、時區與
UTC 時差、本次容許度、事件星座分段及精確成相。全部匯出不受畫面篩選影響。
圖頁每頁最多 30 個經過日、12 列；所選事件匯出會聚焦該段。較短色帶仍可從文字詳表閱讀。
列印沿用 A4 橫向與頁碼，長表格自動續頁並重複表頭；長查詢會有較多頁，可改匯出所選事件。
運算未完成、取消或更改條件後不可匯出舊結果。

### Zodiac history, concurrent events and export

Bands mark tropical geocentric sign ingresses with dashed lines, with the first body
above the second for aspects. Tooltips and a resizable detail window expose narrow
segments and retrograde re-entries. Ingress roots reuse the bounded coarse scan and
absolute-speed extrema, with the same finite-sampling limitations as event search.

The concurrent-events tab uses interval intersections by default, or the selected
event's start, exact hits or end. It uses all results regardless of chart filters;
shared endpoints are simultaneous instants. Linked events support back navigation.

Offline HTML export offers all results or the selected event with overlaps. Document
language is independent of the UI. Copy the existing report language folder including
timeline.html, timeline.css and timeline-labels.json to add a language. Embedded
SVG/CSS, accessible text tables, A4 landscape, continued tables and page numbers
follow the natal report conventions; no network resources or JavaScript are needed.


## 2026-11-02 顯示規則調整

天象相位完全排除太陽及月亮（包括日月配對），工作程序也只計算水星至冥王星的
位置與星座歷程。個人星盤計算規則保持原狀。天象篩選與文件均反映八顆／28 對。
按鈕及匯出視窗統一稱「匯出文件」；輸出格式仍為離線單檔 HTML。

時間軸與文件共用配色：0° 金色（相互增強）、120° 綠色（吉相）、90° 灰紫色
（相互削弱）、180° 紅色（凶相），逆行保留棕色。圖例以文字明示本功能採用的
解讀，不僅依賴顏色區分；不影響相位計算條件或容許度。

匯出文件先呈現甘特圖，再列查詢設定／事件列表，最後是事件詳情；列印也依此順序。
空結果仍在頂端顯示時間軸區及無事件提示。

The timeline excludes both luminaries from position sampling, sign histories and
all aspect pairs; natal-chart rules are unchanged. The button is named Export Report.
Timeline and report share gold (mutual strengthening), green (favorable), muted purple
(mutual weakening), and red (adverse) for 0/120/90/180 degrees respectively. Labels
state the interpretation as well as the angle. Reports place the Gantt chart first,
followed by settings/catalog and event details, on screen and in print.
