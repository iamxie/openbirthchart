# 87 邊界基準 v2：雙黃緯模式與 Swiss 可對照部分

建立日期：2026-11-01（Asia/Taipei）。固定 87 個邊界案例已用目前程式重算實際／零黃緯兩版；Swiss 可原生對照部分也各重算兩版。四份各保留 87 筆紀錄，均獨立完整複算、逐值精確核對及 SHA-256 封存。
**原 0.6.5 的 87 個邊界基準，以及舊 Azimuth 補充 Swiss 邊界對照，已作廢；歷史檔案原樣保留。** 已更新的 1200／2016 基準及其路由未改。
[現行指標與作廢範圍](../../../regression/boundary-current.json)；[四份封存入口](../../../regression/boundary-v2/README.md)。

## 87 例的組成及處理

原始案例包含 57 個 chart、19 個 time、6 個 house helper、5 個 aspect helper。只有 chart 的歸宮輸入切換黃緯，其餘 30 個 helper 沿用相同原始條件；因此「87 例」不能讀作「87 張星盤」。案例 ID、順序、出生條件、人工宮頭、相位容許度、UTC 閏秒等原始輸入均未改。

| 分類 | 每模式案例數 | 意義 |
|---|---:|---|
| 雙方完整星盤可比較 | 47 | 共用固定物理時刻，各自計算位置、宮頭與歸宮 |
| 獨立 UTC→TT／UT1 比較 | 19 | Swiss 原生 utc_to_jd；不共用產品 TT／UT1 |
| 雙方極區宮制拒絕 | 4 | 北／南緯 69.65° 的 Placidus、Koch |
| 只有產品拒絕、Swiss 可算 | 3 | 產品安全日期範圍前後端點及 UTC 秒 60 輸入 |
| 無法指定唯一有效物理時刻 | 3 | 未指定 fold、夏令時間缺口、Apia 跳日 |
| 沒有同義原生 Swiss API 的產品 helper | 11 | 6 個任意宮頭陣列邊界、5 個相位容許度邊界 |

產品每模式 77 ok＝47 星盤＋30 helper；10 個預期錯誤＝8 UserError、1 AmbiguousTimeError、1 ValueError。Swiss 每模式 69 成功＝50 星盤＋19 時標、4 原生宮制錯誤、14 明列未直接計算的項目。**14 個未直接計算項目沒有被冒充成 Swiss 成功或拒絕。**

產品為 LibEphemeris 3.2.2 加應用層修正，APP_VERSION 仍為 0.6.5；Swiss 2.10.03／pyswisseph 2.10.3.2 保留原生行為，未套用產品修正。

## 宮號、角度與方向差異

| 模式 | 可比星盤 | 宮號不同星盤／點 | ASC 不同 | MC 不同 | 未定義點 | 順逆行不同 | ≥30 角秒 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 實際黃緯 | 47 | 16／304 | 16 | 0 | 0 | 1 | 0 |
| 零黃緯 | 47 | 16／304 | 16 | 0 | 0 | 1 | 0 |

宮號差異全在 Azimuth。兩模式是同一組差異星盤／點；其中 53 點的具體宮號組合隨模式改變。角度小於門檻不會抹去宮號或順逆行差異。

| 比較範圍 | 最大黃經差（角秒） | 最大黃緯差（角秒） | 最大球面角距（角秒） |
|---|---:|---:|---:|
| 日月至冥王星（10 點） | 0.009256880548491608 | 0.00150820203765889 | 0.009378709791792216 |
| 16 個直接計算點 | 1.7943704431047536 | 0.6774642754749038 | 1.835634552125828 |
| 全部 20 點，含軸與衍生點 | 1.7943704431047536 | 0.6774642754749038 | 1.835634552125828 |
| 十二宮頭 | 1.7042526548266324 | 0.0 | 1.7042526548266321 |
| Azimuth 宮頭 | 0.006110244112278451 | 0.0 | 0.006110244112278451 |

以上最大值兩模式相同。最大天體黃經差在 `edge-range-first` 的灶神星；最大宮頭差在 `edge-range-last` 的第八宮頭。每張比較全部 20 點及 12 宮頭；不只比較畫面可見點。

### 水星停滯邊界的順逆行差異

- 實際黃緯：`edge-mercury-station-before`，2016-04-28T17:19:43 UTC；產品速度 5.402398528531194e-08 度／日，Swiss -1.5181874502096504e-07 度／日。產品順行、Swiss 逆行；兩者都是第 4 宮，黃經差 0.0010662786877446706 角秒。
- 零黃緯：`edge-mercury-station-before`，2016-04-28T17:19:43 UTC；產品速度 5.402398528531194e-08 度／日，Swiss -1.5181874502096504e-07 度／日。產品順行、Swiss 逆行；兩者都是第 4 宮，黃經差 0.0010662786877446706 角秒。

這是固定停滯點附近的方向旗標差，速度極接近零。沒有以角度容差隱藏它，也沒有在本輪修正速度或順逆行判定。[原始速度明細](retrograde-details.json)。

## 19 個獨立時標對照

這部分直接把原始 UTC（含合法秒 60）交給 Swiss utc_to_jd，與產品 TimeAuthority 的 TT／UT1 欄位比較；沒有借用產品時間當作 Swiss 答案。產品的 EOP 來源、預測／實測標記與閏秒假設、Swiss 函式參數及結果均保存。

- TT 最大絕對差：**4.023313522338867e-05 秒**（約 40.233135 微秒），案例 `edge-time-2016-12-31T23:59:59Z`。
- UT1 最大絕對差：**0.5629822611808777 秒**，案例 `edge-eop-2027-10-04T00:00:00--86401`，UTC 2027-10-02T23:59:59Z；產品標記為 `prediction_A`、非實測時間。
- 本表用封存的單段雙精度儒略日比較；最大 TT 差的量級等於該浮點表示的一個步距（4.023313522338867e-05 秒），不能把它直接解讀為實測誤差。
- UT1 數字應解讀為兩套獨立時標換算的輸出差；本輪沒有裁定哪個模型正確或修改 EOP／時標算法。時間差用秒記錄，沒有使用 30 角秒容差，也沒有自訂一個未經核准的時間通過門檻。
- 47 張可比較星盤仍採共享固定 TT／UT1；上述獨立時間差沒有灌回那些星盤，所以「角度 <30 角秒」與「時標相同」是不同命題。

## 預期拒絕及無法直接對照的具名案例

| 案例 | 分類 | 原因 |
|---|---|---|
| edge-range-before | product_only_rejection | {"source":"本版可計算 UTC 1850/01/02～2149/12/30；邊界預留給光行時與速度計算。","type":"UserError","values":{}} |
| edge-range-after | product_only_rejection | {"source":"本版可計算 UTC 1850/01/02～2149/12/30；邊界預留給光行時與速度計算。","type":"UserError","values":{}} |
| edge-fold-None | no_unique_instant | No unique physical instant: ambiguous local time without fold, or nonexistent local civil time. |
| edge-dst-gap | no_unique_instant | No unique physical instant: ambiguous local time without fold, or nonexistent local civil time. |
| edge-date-line-gap | no_unique_instant | No unique physical instant: ambiguous local time without fold, or nonexistent local civil time. |
| edge-polar-69.65-P | both_rejected | {"source":"此緯度無法使用 {system}，請改選 Equal 或 Whole Sign。","type":"UserError","values":{"system":"Placidus"}} |
| edge-polar-69.65-K | both_rejected | {"source":"此緯度無法使用 {system}，請改選 Equal 或 Whole Sign。","type":"UserError","values":{"system":"Koch"}} |
| edge-polar--69.65-P | both_rejected | {"source":"此緯度無法使用 {system}，請改選 Equal 或 Whole Sign。","type":"UserError","values":{"system":"Placidus"}} |
| edge-polar--69.65-K | both_rejected | {"source":"此緯度無法使用 {system}，請改選 Equal 或 Whole Sign。","type":"UserError","values":{"system":"Koch"}} |
| edge-utc-leap-second-input | product_only_rejection | Explicit UTC leap second is accepted by Swiss utc_to_jd; the product datetime input rejects it. No shared product time is available. |
| edge-cusp-0.0 | product_helper_no_native_equivalent | Product longitude-interval helper with an arbitrary supplied cusp array; no identical native Swiss API accepting that array. |
| edge-cusp-360.0 | product_helper_no_native_equivalent | Product longitude-interval helper with an arbitrary supplied cusp array; no identical native Swiss API accepting that array. |
| edge-cusp-359.999999 | product_helper_no_native_equivalent | Product longitude-interval helper with an arbitrary supplied cusp array; no identical native Swiss API accepting that array. |
| edge-cusp-29.999999 | product_helper_no_native_equivalent | Product longitude-interval helper with an arbitrary supplied cusp array; no identical native Swiss API accepting that array. |
| edge-cusp-30.0 | product_helper_no_native_equivalent | Product longitude-interval helper with an arbitrary supplied cusp array; no identical native Swiss API accepting that array. |
| edge-cusp-30.000001 | product_helper_no_native_equivalent | Product longitude-interval helper with an arbitrary supplied cusp array; no identical native Swiss API accepting that array. |
| edge-aspect-3.999999 | product_helper_no_native_equivalent | Product aspect/orb inclusion helper; Swiss has no equivalent native aspect catalogue and orb-boundary contract. |
| edge-aspect-4.0 | product_helper_no_native_equivalent | Product aspect/orb inclusion helper; Swiss has no equivalent native aspect catalogue and orb-boundary contract. |
| edge-aspect-4.000001 | product_helper_no_native_equivalent | Product aspect/orb inclusion helper; Swiss has no equivalent native aspect catalogue and orb-boundary contract. |
| edge-aspect-359.999999 | product_helper_no_native_equivalent | Product aspect/orb inclusion helper; Swiss has no equivalent native aspect catalogue and orb-boundary contract. |
| edge-aspect-360.0 | product_helper_no_native_equivalent | Product aspect/orb inclusion helper; Swiss has no equivalent native aspect catalogue and orb-boundary contract. |

其中 `edge-range-before`／`edge-range-after` 使用原先凍結且重新核對的共享時標，產品排盤依日期安全邊界拒絕。`edge-utc-leap-second-input` 為明確 UTC 閏秒，Swiss 原生 utc_to_jd 可處理，產品 datetime 輸入拒絕；Swiss 的完整星盤及其原生時標參數仍保存，但沒有可比產品星盤。
未指定 fold 或當地時間不存在的三例保持原樣；沒有代替使用者選時間。11 個產品 helper 都照原輸入重跑成功，未另造 Swiss 等價規則或杜撰日期／ARMC。

## 兩種黃緯模式的差異

| 引擎 | 受影響星盤 | 受影響點 | 真實坐標不變配對 | ASC／MC 宮號不變配對 | 不變 helper 紀錄 |
|---|---:|---:|---:|---:|---:|
| product | 23 | 62 | 940 | 94 | 30 |
| swiss | 24 | 63 | 1000 | 100 | 30 |

- [產品逐點模式變更](product-mode-changes.csv)、[Swiss 逐點模式變更](swiss-mode-changes.csv)。Swiss 多的一點是產品拒絕的 `edge-range-after`、18 號點：實際黃緯第 12 宮，零黃緯第 1 宮。
- 各引擎真實天體位置、宮頭、ASC／MC 坐標及宮號精確不變；30 helper 紀錄不因歸宮選項改變。

## 保存、重現與驗證

- 四份獨立完整複算的全部原始／數值結果與環境精確相同，僅排除耗時。每份有 cases.json、results.jsonl.gz、逐案 checkpoints、environment.json、source、manifest.json、BASELINE.json、SHA256SUMS.json；所有原始 API 值、有效宮號、補正及錯誤均保存。
- 產品 87 例兩模式與前輪 latitude-mode/final/legacy 中對應紀錄逐值精確相同。49 張先前成功的 Swiss 邊界星盤也精確延續，僅排除耗時及新增明確黃緯旗標；19 個原生時標與 UTC 閏秒星盤是本輪擴充的 Swiss 覆蓋。
- 36085 個原有保護項目雜湊不變，包含所有舊基準、1200／2016 現行封存與路由、前輪證據、應用／LibEphemeris 來源及既有交付包。
- `verify-boundary-numerics.ps1` 預設精確驗證兩模式，可用 -Mode actual／zero。原 verify-numerics.ps1 仍驗證 1200、verify-complete-numerics.ps1 仍驗證 2016，兩個入口檔案未更動。
- 沒有升級依賴或資料、修改應用算法、LibEphemeris、個人資料、圖面／匯出或重封裝 EXE／ZIP；UI／PDF 沿用前輪驗收。
- 有效獨立首輪／複算位於 runs/。pilot-swiss-actual 是早期未完成試跑：原時間案例 ID 含冒號，不能直接當 Windows 檢查點檔名；後續改用獨立的 boundary-001～087 檔名鍵，原案例 ID 與條件完全保留。pilot2 與 product pilot／pilot-comparison 僅是工具驗證，不是現行基準。
- [驗證紀錄](verification.json)、[四份精確複算](exact/)、[固定輸入驗證](sampling-verification.json)、[模式／範圍測試](mode-tests-final.log)、[完整性測試](integrity-tests.log)、[完整摘要](summary.json)。保留 review_required=true，因仍有已知差異、預期拒絕及不適用項目；不代表資料捕捉不完整。

## 詳細比對檔

- [實際黃緯比較](../../../regression/boundary-v2/comparison/actual/REPORT.md)：同目錄 all-comparisons.csv、house-differences.csv、time-comparisons.csv、outcomes.csv、not-comparable.csv、rejections.csv、exceptions.csv。
- [零黃緯比較](../../../regression/boundary-v2/comparison/zero/REPORT.md)：同樣保留所有表格。每張盤 20 個點／12 宮頭，時間差表另列，87 個案例全部有狀態。

## 原始耗時

單位為秒；pool 含程序啟動及檢查點，wall 另含來源／資料雜湊與封存結果。BLAS／OpenMP 每程序固定 1 執行緒。未估算費用。

| 引擎 | 模式 | 輪次 | 程序數 | pool 秒 | wall 秒 |
|---|---|---|---:|---:|---:|
| product | 實際黃緯 | first | 12 | 1.9694002000615 | 4.001668600016274 |
| product | 實際黃緯 | repeat | 12 | 1.978219100041315 | 3.879849400022067 |
| product | 零黃緯 | first | 12 | 1.8597139000194147 | 3.8789759998908266 |
| product | 零黃緯 | repeat | 12 | 2.0074543999508023 | 5.012952700024471 |
| swiss | 實際黃緯 | first | 4 | 0.9555561000015587 | 1.4997914000414312 |
| swiss | 實際黃緯 | repeat | 4 | 1.005533799994737 | 1.2173666000599042 |
| swiss | 零黃緯 | first | 4 | 0.955633100005798 | 1.3547920000273734 |
| swiss | 零黃緯 | repeat | 4 | 1.1942767000291497 | 1.8185984999872744 |

新入口已另外重跑兩模式，與封存原始／數值及環境精確一致：[實際黃緯](entrypoint-check/exact-actual.json)、[零黃緯](entrypoint-check/exact-zero.json)。入口耗時另保留於各輪 manifest.json。
最終路由、舊檔保留與四份封存複核為 `final-checks.json`；本輪完整證據索引為 `EVIDENCE-SHA256.json`。
