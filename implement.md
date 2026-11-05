# Open BirthChart v0.7.0 程式碼審查：待修改項目

審查日期：2026-11-05。審查範圍：`desktop/` 全部 34 個檔案、`desktop_app.py`、`scripts/`、
`*.ps1`、`EphemerisDesktop.spec`、`requirements/`、五份 `*lock.json`、`config/`、`tests/`。

審查方式：逐檔靜態追蹤，沒有實機量測。每一項標示信心等級：

- **CONFIRMED**：從入口到結果的程式路徑已完整讀過，問題必然發生。
- **PLAUSIBLE**：路徑存在但需要特定條件（錯誤路徑、特定環境）才會觸發。

執行本文件時的通用規則（與 `AGENTS.md` 一致）：

1. 每個章節獨立開一條分支、獨立 commit，不要混在一起。
2. 不得更動任何數值計算程式（`model.py` 的計算部分、`house_positions.py`、
   `polich.py`、`azimuth.py`、`timeline.py` 的事件偵測、`utc_times.py`），
   也不得更動 pinned 依賴、星曆資料、歷史回歸封存。
3. 每一項都要先寫一個會失敗的測試（或可重現的手動步驟），修完後證明它通過。
   測試只能用合成資料，不能碰 `Documents/openbirthchart/` 下的真實資料庫。
4. 修改完成後至少跑 `scripts/run_desktop_tests.py` 與
   `desktop_app.py --smoke-output <tmp>`、`--timeline-smoke`，三者都必須通過。
5. 不要順手「美化」無關程式碼。這份清單以外的改動要另外提出理由。

---

## 第一優先：記憶體與資源

### 1.1 有 parent 的 QDialog 執行完沒有釋放（CONFIRMED，系統性）

**成因。** PySide6 中 `QDialog(parent)` 的 C++ 物件由 parent 持有。`exec()` 返回、
Python 變數離開作用域後，C++ 端的對話框與其全部子物件（QTextDocument、
QTableWidget、連接到它訊號的 Python 閉包）仍留在 `parent.children()`，直到
parent（也就是 `MainWindow`）被銷毀。程式自己在 `window.py:285`（GeocodeDialog）
與 `timeline_ui.py:815`（SkyPlayer）已經用 `deleteLater()` 正確處理，但以下十處沒有：

| 檔案與行號 | 每次呼叫殘留的物件 | 觸發方式 |
|---|---|---|
| `desktop/legal.py:10-20` | QDialog + QTabWidget + 3 個 QTextBrowser，各載一份完整排版的 LICENSE／NOTICE／THIRD_PARTY 文件 | 每按一次「關於與授權」 |
| `desktop/window.py:584-611` `choose_record` | QDialog + 一列一筆 profile 的 QTableWidget；`filter_rows`／`update_selection` 閉包抓住整個 `rows` 列表（含所有備註） | 每按一次「載入」，殘留量隨檔案數線性成長 |
| `desktop/help.py:29-44` | QDialog + 以 Markdown 排版的 `docs/azimuth.md` | 每按一次「閱讀 Azimuth 說明」 |
| `desktop/window.py:248-249` → `settings.py:30-46` | QDialog + 10 個 QDoubleSpinBox + 抓住 `controls` 的 reset lambda | 每按一次「設定」 |
| `desktop/window.py:257` → `dialogs.py:11` | LanguageDialog | 每按一次「語言」 |
| `desktop/window.py:439` → `dialogs.py:27` | ExportDialog（建構時重讀所有 labels.json） | 個人星盤「匯出文件」 |
| `desktop/timeline_ui.py:775` | ExportDialog | 天象時間軸「匯出文件」 |
| `desktop/window.py:488-509` `confirm_duplicate` | QDialog + QTableWidget + 抓住 `error.matches` 的閉包 | 每次儲存撞到重複檔案 |
| `desktop/window.py:523-529` `confirm_discard` | 以 `addButton` 組成的 QMessageBox(self) | 表單未儲存時按「新增」「載入」或關窗 |
| `desktop/timeline_ui.py:848-866` `open_history` | QDialog + QListWidget + 抓住 `dialog` 的 lambda | 每按一次「天象歷史」 |

**修法。** 統一採一種做法，不要混用：

```python
# 做法 A：exec() 後立即釋放（適用所有 exec() 的場合）
dialog=QDialog(self)
...
result=dialog.exec()
dialog.deleteLater()
if result!=QDialog.DialogCode.Accepted:return
```

`QMessageBox` 的靜態方法（`QMessageBox.warning(...)` 等）會自行刪除，不需要處理；
`confirm_discard` 用的是手動建構的 `QMessageBox(self)`，需要處理。

注意兩個陷阱：

- `deleteLater()` 之後不能再讀對話框上的 widget。`choose_orbs`、`choose_language`、
  `export`、`choose_record` 都在 `exec()` 後讀取控制項的值，必須先把值取出來存成
  Python 原生型別，再呼叫 `deleteLater()`。`lookup_coordinates` 現有寫法（先讀
  `dialog.key.text()`、`dialog.coordinates`，最後才 `deleteLater()`）是正確範本。
- `show_legal`／`show_azimuth_help` 是模組函式，對話框是區域變數，同樣適用做法 A。

**驗證。** 在 `tests/` 新增一個測試：對 `MainWindow` 記錄 `len(window.findChildren(QDialog))`，
用 `QTimer.singleShot(0, lambda: dialog.reject())` 自動關閉後重複呼叫 `choose_record()`
十次，`processEvents()` 並 `sendPostedEvents(None, QEvent.Type.DeferredDelete)` 後，
`QDialog` 子物件數量必須回到原值。對 `show_legal` 做同樣的測試。

### 1.2 取消或失敗的天象計算不會刪除已寫入的 frames（CONFIRMED，磁碟成長）

**定位。** `desktop/sky_history.py:80-83` `abort()` 只把 `runs.status` 改成
`cancelled`／`failed`。`TimelineWorker.run`（`timeline_ui.py:84-108`）在取樣前就
`begin()`，每 60 個採樣點就 `append()` 一批。整個模組沒有任何 `DELETE`，UI 也沒有
刪除歷史的功能。

**影響。** 取消一次一年範圍的計算約留下 52,560 筆 frames（每筆 160 bytes 加 row
overhead，約 10 MB 以上），永遠無法從程式內回收。`list_complete()` 正確地不會列出
這些 run，所以功能面沒錯，純粹是磁碟資源。

**修法。**

```python
def abort(self, run_id, status):
    if status not in ('cancelled','failed'):raise ValueError(status)
    with closing(self.connect()) as db, db:
        db.execute("DELETE FROM frames WHERE run_id=? AND EXISTS("
                   "SELECT 1 FROM runs WHERE id=? AND status='running')",(run_id,run_id))
        db.execute("UPDATE runs SET status=?,saved=0 WHERE id=? AND status='running'",(status,run_id))
```

保留 `runs` 的那一列作為稽核紀錄，只刪 frames。另外加一個啟動時的清理：
`SkyHistory.connect()` 之後若發現 `status='running'` 但程式剛啟動（代表上次是異常
結束），同樣視為 `failed` 並清 frames。要不要提供「刪除歷史」的 UI 由作者決定，
不在本清單強制範圍。

**驗證。** 在 `tests/test_desktop_sky_history.py` 加一個案例：`begin` → `append` 一批
→ `abort(run,'cancelled')` → 斷言 `SELECT COUNT(*) FROM frames WHERE run_id=?` 為 0，
且 `list_complete()` 不含該 run。

### 1.3 `SkyPlayer` 建構失敗時半成品對話框殘留（PLAUSIBLE，錯誤路徑）

**定位。** `desktop/sky_player.py:197-232`：整個 widget tree（SkyView、10 個
PlanetLabel、28 條相位線、slider、6 個按鈕）在第 228 行 `FrameReader(...)` 之前就
建好。`FrameReader` 一旦拋例外（`UserError`、`sqlite3.OperationalError`），例外離開
`__init__`，`timeline_ui.py:822` 的 `self.player` 不會被賦值，但那個已經有 parent 的
QDialog 永遠掛在 `TimelinePage` 底下。第 229-232 行的 `try/except BaseException` 只
保護 `show_frame(0)`。

**修法。** 把 `self.reader=FrameReader(path,result.history_id)` 移到 `super().__init__`
之後、建任何 widget 之前。同時在 `TimelinePage.show_player` 改成：

```python
player=None
try:
    player=SkyPlayer(self.history_path,self.result,self)
    self.player=player;player.show()
except Exception as exc:
    if player is not None:player.deleteLater()
    QMessageBox.warning(self,tr('無法播放'),error_text(exc))
```

（第二層保護是為了未來任何在 FrameReader 之後新增的建構步驟。）

### 1.4 `FrameReader.__init__` 的 SELECT 不在保護範圍（PLAUSIBLE）

**定位。** `desktop/sky_history.py:106-110`。`connect()` 自己失敗時會關連線，但
第 107 行的 `self.db.execute(...)` 若拋例外（例如 `database is locked`），連線只能靠
GC 關閉。

**修法。**

```python
self.db=SkyHistory(path).connect()
try:
    row=self.db.execute(...).fetchone()
    if not row:raise UserError('這份天象歷史尚未完成，無法播放。')
except BaseException:
    self.db.close();raise
```

### 1.5 `export_chart` 的 QPainter 沒有 try/finally（PLAUSIBLE）

**定位。** `desktop/chart.py:207-210`。`paint_chart` 若拋例外（例如 `house_direction`
的 ValueError），一個仍為 active 的 QPainter 壓在 2800×2000 的 ARGB QImage（約 22 MB）
或已開啟檔案的 QSvgGenerator 上，直到 GC。同檔案 `report.py:42-44` 的 `svg_image`
寫法是正確的，照搬即可：

```python
painter=QPainter(device)
if not painter.isActive():raise OSError(tr('無法建立圖片。'))
try:
    if format!='svg':painter.scale(size/1000,size/1000)
    paint_chart(painter,chart)
finally:painter.end()
```

### 1.6 Pool worker 沒有父程序存活檢查（PLAUSIBLE，異常終止才會發生）

**定位。** `desktop/timeline.py:435`。正常的取消、失敗、關窗三條路徑都會
`terminate()` + `join()`，寫得很乾淨；`timeline_smoke.py:115` 也驗證過合作式取消後
`active_children()` 為空。但 GUI 程序被工作管理員強制結束或當掉時，spawn 出來的
worker（每個都載著 ChartEngine 與星曆）會卡在 task queue 上直到重開機。

**修法。** 在 `_initialize_worker` 起一個 daemon thread：

```python
def _watch_parent():
    parent=mp.parent_process()
    while True:
        time.sleep(2)
        if parent is None or not parent.is_alive():os._exit(1)

def _initialize_worker():
    threading.Thread(target=_watch_parent,daemon=True).start()
    ...
```

`multiprocessing.parent_process()` 在 spawn 子程序中可用（Python 3.8+）。
`os._exit` 而非 `sys.exit`，因為 worker 主執行緒正阻塞在 queue 上。

**驗證。** 寫一個獨立的 pytest／unittest：啟動 `calculate_timeline` 於子程序，取得
worker PID 後 `kill` 父程序，等待 5 秒，斷言 worker PID 已不存在。此測試須標記為
慢速或選擇性執行。

---

## 第二優先：安全邊界與正式版行為

### 2.1 測試用的 RuntimeGuard 在正式版裡是開著的（CONFIRMED）

**定位。** `desktop_app.py:22-23` 在 `if args.smoke_output` 之前無條件 `install()`；
`desktop/timeline.py:147-148` 讓每個正式版 timeline worker 也裝一份。

**兩個後果。**

1. `scripts/guard.py:34-37` 的 `open` audit hook 會對「任何」小寫後含 `/data/reference/`、
   `/.venv-reference/`、`swisseph` 或以 `.se1` 結尾的路徑拋 `ForbiddenDependency`。
   `desktop/report.py:144` 的 `Path(path).write_text(...)` 寫的是使用者在
   `QFileDialog` 選的路徑。使用者把報告存到 `D:\data\reference\natal.html`，或任何
   名稱含 `swisseph` 的資料夾，匯出會失敗並顯示 `swiss_file: ...`。
2. `sys.addaudithook` 無法移除，且對程序內每一次 `open`、`import`、`compile` 都會
   執行，是純粹的額外成本。

**另一個相關的證據力問題。** `desktop_app.py:91-94` 把 `guard_events==[]` 記錄為
「無網路存取」。audit hook 只看得到 Python 層的 `socket.*`；`desktop/geocoding.py`
用的 `QNetworkAccessManager` 是 Qt 的 C++ 網路層，hook 完全看不到。`runtime.json`
只能證明「沒有 Python 層網路呼叫」。`guard.py` 的 docstring 已經誠實地說它不是沙箱，
README 也沒有過度宣稱，這點要繼續保持，但 smoke 輸出的欄位名稱應改成
`python_level_guard_events` 之類，避免讀者誤解。

**修法。**

- `desktop_app.py`：只在 `args.smoke_output` 時才 `install()`。正式啟動不裝。
- `desktop/timeline.py`：`calculate_timeline` 加參數 `guard=False`，透過
  `Pool(..., initializer=_initialize_worker, initargs=(guard,))` 傳給 worker；
  `TimelineWorker` 只在 smoke 模式傳 `True`。`timeline_smoke.py` 已經用猴補 `TimelineWorker`
  的方式注入 `workers=2`，同處再注入 `guard=True` 即可。
- 若作者仍希望正式版保留某種「防呆」，把 `open` hook 的路徑規則改成只比對
  `ROOT` 之下的絕對路徑，不要用子字串比對使用者的任意路徑。

**驗證。** 新增測試：在 smoke 模式外啟動 `MainWindow`，用合成 chart 呼叫
`export_html(chart, tmp/'data'/'reference'/'x.html')`，必須成功寫出檔案。

### 2.2 座標查詢回應的大小上限在下載完成後才檢查（PLAUSIBLE，低風險）

**定位。** `desktop/geocoding.py:107`。`bytesAvailable()>1000000` 的檢查在
`finished` 之後執行，此時 Qt 已把整個 body 放進記憶體。惡意或故障的伺服器可以在
15 秒逾時內塞進很大的回應。這不是 RCE，是本機記憶體被塞滿的問題。

**修法。** 在 `lookup()` 連接 `reply.downloadProgress`：

```python
def progress(received,total):
    if received>1000000 or total>1000000:
        self.timed_out=False;self.oversized=True;self.reply.abort()
self.reply.downloadProgress.connect(progress)
```

並在 `completed()` 把 `oversized` 轉成現有的「服務回應過大」訊息。

### 2.3 API key 放在 URL query string（紀錄即可，不強制修）

**定位。** `desktop/geocoding.py:25`。註解已說明供應商的 header 方式會回 401，所以是
刻意為之；代價是 key 會進入對方與中間代理的存取紀錄。目前程式已做到：不跟隨轉址
（避免 key 被帶到別的主機）、不記錄 URL、不顯示 `errorString()`。若供應商日後支援
header 認證，應立即改用。此項不需動手，但要寫進 `README` 的隱私段落讓使用者知道。

---

## 第三優先：架構

### 3.1 未宣告的動態屬性 `TimelineResult.history_id`（CONFIRMED）

**定位。** `desktop/timeline.py:108-118` 的 `TimelineResult` 沒有 `history_id` 欄位，
但 `sky_history.py:99` 與 `timeline_ui.py:97` 直接 `result.history_id=run_id` 賦值，
再由 `timeline_ui.py:596`、`:818` 用 `getattr(self.result,'history_id',None)` 讀回。
設計意圖（本機識別碼不進可攜的天象 JSON）是正確的，但實作方式讓型別檢查、IDE 與
後續維護者都看不到這個欄位，`asdict()` 只是碰巧忽略它。

**修法。**

```python
@dataclass
class TimelineResult:
    ...
    zodiac_segments: list[ZodiacSegment] = field(default_factory=list)
    history_id: int | None = field(default=None, compare=False)

def result_dict(result):
    data=asdict(result);data.pop('history_id',None);return data
```

讀取端全部改成 `result.history_id`，刪掉 `getattr`。`sky_history.load()` 要確認
存檔的 JSON 不含 `history_id`（舊檔已經沒有，新檔由 `result_dict` 保證）。

**驗證。** 既有 `tests/test_desktop_sky_history.py` 應全部通過；加一個斷言
`'history_id' not in result_dict(result)`。

### 3.2 `TimelineWorker` 從 parent widget 偷讀設定（CONFIRMED）

**定位。** `desktop/timeline_ui.py:82` `self.history_path=getattr(parent,'history_path',None)`。
QThread 子類別去讀 parent widget 的屬性，是把 UI 的物件圖當成設定來源。

**修法。** 建構參數明確化：`TimelineWorker(request, parent=None, workers=None,
history_path=None, guard=False)`，由 `TimelinePage.start_calculation` 傳入
`history_path=self.history_path`。`timeline_smoke.py:45` 的猴補 lambda 要同步更新簽章。

### 3.3 執行期共用程式碼放在 `scripts/` 裡（CONFIRMED，最大的結構債）

**定位。** `desktop/` 有十多處 `from common import ...`（`model.py`、`aspects.py`、
`help.py`、`i18n.py`、`legal.py`、`leap_seconds.py`、`report.py`、`theme.py`、
`zodiac.py`、`timeline_smoke.py`、`sky_player_smoke.py`）、`model.py:19` 的
`from utc_times import TimeAuthority`、`timeline.py:147` 的 `from guard import RuntimeGuard`。
全部靠 `desktop_app.py:9` 與 `EphemerisDesktop.spec:10,27` 的 `sys.path.insert(0,'scripts')`
才找得到，而 `scripts/` 同時放了七十多支開發工具。

**風險。** `scripts/` 排在 `sys.path[0]`，任何日後新增、名稱與標準庫或第三方套件相同的
工具腳本（例如 `scripts/json.py`、`scripts/tomllib.py`）會直接遮蔽正式程式的 import。
目前檢查過沒有衝突，但這是靠運氣維持的。

**修法。** 分兩步，第一步不改任何邏輯：

1. 新建套件 `desktop/core/`（或獨立的 `openbirthchart_core/`），把 `scripts/common.py`、
   `scripts/utc_times.py`、`scripts/guard.py` 移入，`scripts/` 保留同名的薄轉接檔
   （`from desktop.core.common import *`）讓現有工具腳本不用一次全改。
2. `desktop/` 內改成相對匯入；`desktop_app.py` 與 `EphemerisDesktop.spec` 移除
   `scripts` 的 `sys.path` 注入；`spec` 的 `pathex` 只留 `root`。
3. `common.ROOT` 在 frozen 模式讀 `sys._MEIPASS`，搬移後位置不變，但要重新確認
   `Path(__file__).resolve().parents[N]` 的 N。

**驗證。** `python -c "import desktop.model"` 在不設 `PYTHONPATH` 的情況下成功；
`desktop_app.py --smoke-output` 與 `--timeline-smoke` 通過；在 Windows 乾淨環境用
`build-desktop.ps1` 打包後跑 `verify_desktop_package.py`。

### 3.4 `ProfileStore._connect()` 每次連線都寫入（CONFIRMED）

**定位。** `desktop/storage.py:90-109`。每次 `_connect()`，包含純讀取的 `list()`、
`load()`、`load_orbs()`、`load_ui_language()`、`load_geocode_key()`，都執行
`CREATE TABLE IF NOT EXISTS`、`ALTER TABLE`（條件式）與 `PRAGMA user_version=2`，
而 `PRAGMA user_version=N` 是寫入操作，會開寫入交易並更動檔案。`sky_history.py:33-47`
的 `connect()` 同樣每次 `executescript` + `commit`，且 `append()` 每 60 個採樣點
呼叫一次。

**影響。** 預設路徑在 `Documents/openbirthchart/`，Windows 上常被 OneDrive 同步；
每次讀取都改檔案 mtime 會造成不必要的同步，也提高 `database is locked` 的機率
（`timeout=5`）。

**修法。** 只在 `user_version` 低於目標版本時才執行遷移：

```python
version=connection.execute('PRAGMA user_version').fetchone()[0]
if version not in (0,1,2):raise UserError(...)
if version<2:
    with connection:
        ...DDL...
        connection.execute('PRAGMA user_version = 2')
return connection
```

`sky_history.connect()` 同理，`version<FORMAT` 才建表。

**驗證。** 測試：建好資料庫後記錄檔案 `st_mtime_ns`，連續呼叫 `list()` 三次，
mtime 不得改變。

### 3.5 每個 timeline worker 啟動都重算全部星曆資料的 SHA-256（PLAUSIBLE，效能）

**定位。** `desktop/model.py:214-218` `ChartEngine.__init__` 對兩份 lock 清單的所有
檔案做 `sha()`，含約 57 MB 的 `de440s.bsp`。`timeline.py:150` 讓每個 worker 各做一次，
四個 worker 就是四次全量 hash，而父程序啟動時其實已經驗過。

**修法。** `ChartEngine.__init__(self, verify_data=True)`；父程序在建 Pool 前確定自己
已經驗過（`MainWindow.engine` 存在，或自行驗一次），再以 `initargs` 傳
`verify_data=False` 給 worker。正式版的完整性保證不變：仍由父程序在同一次啟動中驗證。
不接受的替代方案：拿掉驗證。

### 3.6 `MainWindow` 約 600 行（建議，不強制）

`desktop/window.py` 把表單、時區回饋、資料庫存取、重複檔案確認、匯出全放在一個
類別。建議第一刀把 profile 的載入／儲存／重複確認（`save_record`、`confirm_duplicate`、
`choose_record`、`load_record`、`new_record`、`restore_profile`）抽成 `ProfileController`
或獨立 mixin，`MainWindow` 只保留 widget 建構與訊號接線。做這一項之前先完成 1.1，
否則兩邊會互相干擾。

---

## 第四優先：開發與發行工具鏈

### 4.1 發行閘門全部是裸 `assert`（CONFIRMED）

**定位。**

- `scripts/verify_release_numerics.py:32-62`：10 個 `assert`，包含 engine 比對、案例
  數、「無 guard 事件」、環境相等、版本、`assert not failures`。
- `scripts/verify_desktop_package.py:18-44`：18 個 `assert`，包含 manifest hash、
  不含 `.se1`／swisseph、隨附文件與字型一致。
- `scripts/generate_complete_cases.py:41-77` `validate()`（20 個 assert），被
  `complete_regression.validate_suite()` 與 `finalize_latitude_mode.py:12-23` 呼叫。
- `scripts/latitude_mode_audit.py:49,74-75`。
- `build-desktop.ps1` 呼叫這些腳本時沒有 `-E`／`-I`，所有 `.ps1` 都沒有清除
  `PYTHONOPTIMIZE`。

**失敗情境。** 開發機或 CI 環境有 `PYTHONOPTIMIZE=1`（或任何人加了 `-O`）：
`verify_release_numerics.py` 仍會重算 6,606 個案例，但什麼都不比對，寫出
`status='passed'` 的 `verification.json`，PyInstaller 繼續打包；
`verify_desktop_package.py` 產出的 ZIP 與 `.sha256` 標示 `all_hashes_verified: True`，
但實際上一個都沒驗。

**修法。** 兩件都做：

1. 把每個 `assert cond, msg` 改成 `if not cond: raise VerificationError(msg)`，
   `numerical_regression.py` 與 `complete_regression.py` 已經是這種寫法，照抄即可。
2. 所有 `.ps1` 呼叫驗證腳本時加 `-E -I`（`python.exe -E -I scripts/...`），讓環境變數
   與使用者 site-packages 都無法影響閘門。

**驗證。** `PYTHONOPTIMIZE=1 python scripts/verify_desktop_package.py <被竄改的包>`
必須失敗。

### 4.2 `prepare_data.fetch()` 先搬檔再驗 hash（CONFIRMED，可用性問題）

**定位。** `scripts/prepare_data.py:34` `partial.replace(path)` 在第 35-38 行算 digest
之前。呼叫端（`prepare_data.py:45-46`、`prepare_desktop_data.py:23-24`、
`prepare_runtime_data.py:13`、`prepare_time_data.py:17`、`prepare_observations.py:16-17`）
發現不符會 raise，但壞檔已經在正式位置。下次執行第 18 行 `if not path.exists()`
跳過下載，再驗再失敗，永遠卡住，錯誤訊息也沒有說要刪哪個檔。

安全影響已被下游擋住：worker、`numerical_regression.provenance()`、
`ChartEngine.__init__` 都會再驗一次，未驗證的位元組不會進入計算或打包。

**修法。**

```python
digest=hashlib.file_digest(partial.open('rb'),'sha256').hexdigest()
if expected and digest!=expected:
    bad=partial.with_suffix(partial.suffix+'.bad')
    partial.replace(bad)
    raise ValueError(f'{url} 的 SHA-256 不符。已下載內容移至 {bad}，請刪除後重試，'
                     f'或確認來源是否已變更。預期 {expected}，實得 {digest}')
partial.replace(path)
```

`fetch()` 需要多接一個 `expected` 參數，由各 `prepare_*` 傳入。

另外 `prepare_data.py:49-56` 的 bootstrap 分支（`data-sources.lock.json` 不存在時向
GitHub API 查 `aloistr/swisseph@master` 的當前 commit 並寫下 hash）是 trust-on-first-use，
只有刪掉已追蹤的 lock 才會走到。建議把這段移到獨立的 `scripts/bootstrap_lock.py`，
需要明確旗標才能執行，避免誤刪 lock 後靜默重新信任。

### 4.3 決定閘門語意的函式重複定義（CONFIRMED）

- `sha()` 在 8 個檔案各寫一份：`common.py:37`、`numerical_regression.py:39`、
  `complete_regression.py:33`、`swiss_reference.py:24`、`generate_complete_cases.py:36`、
  `latitude_mode_audit.py:18`、`prepare_public_release.py:14`、`verify_desktop_package.py:10`。
- `exact()`（決定所有回歸比對成敗的浮點十六進位編碼）在 `numerical_regression.py:52-58`
  與 `complete_regression.py:41-48` 各一份。目前兩份相同，但改其中一份不會動到另一個
  閘門。`complete_regression.py` 已從 `numerical_regression` 匯入 `execute_case`、
  `provenance`，直接一併匯入 `exact` 即可。
- `scripts/main_latitude_baselines.py:87-96`、`boundary_latitude_baselines.py:143-151`、
  `complete_latitude_baselines.py:68-81` 三段近乎相同的「讀 pinned executable 並驗其
  hash」程式碼。這段邏輯本身也有問題：它把 JSON 裡的 `executable` 路徑跟同一份 JSON
  裡的 `executable_sha256` 比，只證明該 JSON 自我一致，證明不了直譯器就是 pinned 的
  那一個。應合併成 `complete_regression.py` 裡的一個函式，並把預期 hash 來源改成
  版本控制內的 `BASELINE.json`。

**修法。** 全部收斂到 `common.py`（或 3.3 搬移後的 `desktop/core/common.py`），其他
檔案只 import。這一項純重構，完成後 `verify-numerics.ps1` 的輸出必須與重構前逐位元
相同。

### 4.4 `prepare_public_release.py` 的隱私過濾漏掉 SQLite 附屬檔（CONFIRMED，低）

**定位。** `scripts/prepare_public_release.py:36,88` 只排除 `.sqlite/.db/.pem/.key/.pfx`。
`.sqlite-wal`、`.sqlite-shm`、`-journal`（`.gitignore:14` 顯示專案預期它們會出現）
會通過過濾。`evidence_paths()`（43-59）把 docs 連結到的 `.json/.log/.md` 都收進 ZIP，
其中 `environment.json` 與已提交的 `regression/main-v2/swiss/actual/BASELINE.json`
含作者機器的絕對路徑（`D:\Codex\OpenBirthChart\...`）。沒有憑證外洩，屬輕微資訊揭露。

**修法。** 排除清單加上 `-wal`、`-shm`、`-journal` 後綴；若要處理絕對路徑，在產生
證據檔時把 `ROOT` 之下的路徑寫成相對路徑，但已封存的歷史原值依規則不得改動，
只能在新產生的檔案上處理。

### 4.5 其他小項（PLAUSIBLE 或建議）

- `scripts/complete_regression.py:232-240`：第一個 `future.result()` 例外離開 `with`
  時 `shutdown(wait=True)` 沒帶 `cancel_futures=True`，剩餘工作會全部算完才報錯。
  `RUNNING.lock` 只在 `finally` 移除，硬殺後 `--resume` 遇到裸 `FileExistsError` 沒有提示。
- `scripts/complete_regression.py:71` `_time_cache={}` 從未使用，刪除。
- `scripts/diagnose.py:43` `importlib.import_module('libephemeris.houses')` 之後存取私有
  `_house_armc_obliquity`。改成明確 `from libephemeris.houses import ...` 並註明依賴私有 API。
- `setup.ps1:11-12`、`setup-desktop.ps1:6` 用 `uv venv --python 3.12` 讓 patch 版本浮動，
  `docs/BUILDING.md:23` 卻寫 3.12.14。改成 `--python 3.12.14` 或在文件說明兩者的關係。
- `prepare_sources.ps1:13-19` 先 `checkout` 再比對 commit SHA；`run.ps1:26` 執行
  `vendor/libephemeris/scripts/check_algorithm_provenance.py`（第三方程式）前，
  `audit_dependencies.py` 只驗 commit 不驗工作樹是否乾淨。加一行
  `git -C vendor/libephemeris diff --quiet` 檢查。

---

## 不需要修、但審查時確認過的事項

以下是查過沒有問題的部分，列出來是為了讓後續維護者知道涵蓋範圍，不要在這些地方
做不必要的「修正」：

- 對外網路僅三處（座標查詢、開地圖、說明視窗的外部連結），全是使用者主動觸發；
  沒有監聽埠、自動更新、eval、exec、pickle、shell=True、TLS 驗證繞過。
- 所有 SQL 都是參數化查詢。匯出 HTML 對姓名、備註、時區都有 `html.escape`；
  `string.Template.substitute` 不會二次展開值裡的 `$`。
- `TimelineInput.resolve()` 用 `ZoneInfo(zone)` 驗證時區字串，`zoneinfo` 本身拒絕
  含 `..` 的相對路徑，且 `reset_tzpath(())` 只允許隨附的 tzdata。
- 兩個 QThread（`Calculation`、`TimelineWorker`）都有 parent、單例保護、
  `finished` 後 `deleteLater()`。
- `calculate_timeline` 的 Pool 在成功、取消、例外三條路徑都 `close/join` 或
  `terminate/join`；BLAS 環境變數在 `finally` 還原；跨程序只傳 60×10×2 的 float64 區塊。
- 所有 QTimer 都有 parent 且會停；播放器的 graphics item 只建一次；所有 `lru_cache`
  都有上限；`ChartWidget.set_chart` 會刪舊 label；訊號只在建構時連接一次。
- 五份 lock 清單的每個下載都是 HTTPS 且 SHA-256 先驗再用；`uv pip sync --require-hashes`；
  PyInstaller spec 排除 swisseph 並在打包前後各驗一次。
- 數值回歸的 seal 與 checkpoint 有竄改偵測測試覆蓋。

## 建議的執行順序

1. 1.1（對話框釋放）與 1.5、1.4（try/finally）：純局部修改，一次 PR。
2. 2.1（正式版拿掉 RuntimeGuard）：影響 smoke 流程，需同步改 `timeline_smoke.py`。
3. 4.1（assert 改 raise、`-E -I`）：發行前必做。
4. 1.2、1.3（sky_history 清理、SkyPlayer 建構順序）。
5. 3.1、3.2、3.4（dataclass 欄位、Worker 參數、連線只在遷移時寫入）。
6. 4.2、4.3、4.4、4.5（工具鏈）。
7. 3.3（`scripts/` 搬遷）與 3.5（hash 只驗一次）：改動面最大，最後做，需 Windows 打包驗證。
8. 3.6（MainWindow 拆分）：選擇性。
