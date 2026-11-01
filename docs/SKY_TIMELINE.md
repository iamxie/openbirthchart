# 天象時間軸 / Sky timeline

此功能位於開發分支，尚未合併或公開發佈。輸入當地起訖時間（到分鐘）與
IANA 時區，按「開始計算」。不需要地點或個人檔案。

- 逆行檢查八顆天體：水、金、火、木、土、天、海、冥。日、月不列入逆行列。
- 相位包含日、月與上述八顆天體，45 組不重複配對；只計算 0、90、120、180 度。
- 合相預設容許度 4 度，其他三種各 3 度；可設定 0～15 度，邊界包含在內。
- 色帶表示容許度內的區間，菱形標示精確成相。同一段色帶可有多次成相；
  也可能始終未到精確角度。0 度容許度仍保留精確事件標記。
- 每分鐘都使用固定 LibEphemeris／Skyfield 行星路徑計算位置與速度。相位採黃經
  夾角；不計宮位、ASC／MC、小天體或本命盤相位。既有個人星盤引擎未更換。
- 在相鄰分鐘間補找事件邊界與精確角度；求根時間區間收斂至 0.125 秒以內。
  這是求根停止條件，不代表星曆或未來 UTC 的絕對誤差為 0.125 秒。
- 以逐分鐘狀態定義區間；極短且完全位於兩個樣本之間的「進入又離開容許度」
  不保證形成色帶。跨越精確角度或相對速度反轉附近的成相另有求根檢查。
- 查詢邊界若已在事件中，詳情會標示條件在起點／終點仍成立，不推測範圍外日期。

時間沿 UTC 軸每分鐘前進，再轉回所選時區顯示。跨夏令時間時不重複／漏算實際
時刻；重複的起訖鐘點須明確選擇第一次或第二次，不存在的鐘點會拒絕。
歷史時差變更若含非整分鐘秒數，請分段查詢。日期安全範圍沿用現有產品。

進度分別顯示準備、逐分鐘位置計算、事件時間精算及建立時間軸；數量是真實完成
數，不用定時動畫冒充進度。取得實際速度後才估計**目前階段**的剩餘時間。
取消會停止並回收背景程序，不把部分結果當成完整結果。修改輸入後，舊結果清除。

寬視窗右側顯示事件詳情；窄視窗以獨立詳情視窗保留時間軸空間。
低高度主視窗使用「功能」選單取代兩個功能分頁，保留既有星盤圖的空間。
篩選、縮放與選取不會重新計算。月／週／日尺度分別為 30／7／1 天的時間視窗。

## 開發與驗證

預設同時計算程序數為 `max(1, 實體核心數 - 4)`，並以實際批次數為上限。
核心辨識失敗時採單程序。這個設定不出現在使用者介面；不是 CPU affinity 的
硬性保留。每個程序的數學函式庫限制為單執行緒，避免巢狀平行過度佔用資源。
工作採有界批次，不建立或保存幾十萬份完整星盤。

`scripts/check_timeline.py` 可記錄實際運算與取消結果。桌面及 frozen EXE 的
`--timeline-smoke --smoke-output <new-directory>` 使用合成資料驗證進度、圖面與
取消，**測試時明確強制兩個程序**，以驗證 Windows frozen spawn；正常介面仍
使用上述自動政策。測試輸出記錄實際 worker PID、時間與環境，不顯示於產品介面。

```powershell
.venv-desktop/Scripts/python.exe -m unittest discover -s tests -p test_desktop_timeline.py -v
.venv-desktop/Scripts/python.exe scripts/check_timeline.py --minutes 960 --workers 4 --output results/timeline/check.json
.venv-desktop/Scripts/python.exe desktop_app.py --timeline-smoke --smoke-output results/timeline/ui-check
```

## English

The development-only Sky timeline needs a local start/end time and a time zone,
not a location or personal profile. It samples every minute, checks retrograde
motion for Mercury through Pluto, and checks all 45 pairs of the Sun, Moon and
eight planets for 0°, 90°, 120° and 180° aspects.

Bands show orb intervals; diamonds show numerically refined exact aspects.
Defaults are 4° for conjunctions and 3° otherwise. Multiple exact hits are kept.
Minute sampling defines interval detection; a very short orb excursion wholly
between samples is not guaranteed to produce a band. Exact crossings and nearby
relative-speed reversals receive additional root checks. Root brackets are
refined to 0.125 seconds; this is not an absolute astronomical accuracy claim.

DST transitions are resolved on a continuous UTC sampling axis. Ambiguous
endpoints require a fold choice, and nonexistent wall times are rejected.
Clipped intervals are labelled. Changing conditions clears obsolete results.

Progress reports actual completed work and a measured estimate for the current
stage. Cancel stops and joins worker processes. Hardware details stay out of
the normal UI. The default worker limit is physical cores minus four, with a
minimum of one; the explicit smoke mode forces two workers to exercise frozen
Windows spawning. No dependency versions, personal data or sealed baselines are
changed by this feature.
