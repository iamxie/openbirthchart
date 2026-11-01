# 87 邊界基準 v2：現行雙黃緯模式

建立日期：2026-11-01。57 排盤＋19 時標＋6 宮頭 helper＋5 相位 helper，共 87 個固定條件。每份保留 87 筆，包含成功、預期錯誤及明列的不具直接對照條件項目。

| 模式 | 產品（LibEphemeris＋應用修正） | Swiss 獨立對照／覆蓋紀錄 | 配對比較 |
|---|---|---|---|
| 實際黃緯 | [product/actual](product/actual/BASELINE.json) | [swiss/actual](swiss/actual/BASELINE.json) | [比較](comparison/actual/REPORT.md) |
| 零黃緯 | [product/zero](product/zero/BASELINE.json) | [swiss/zero](swiss/zero/BASELINE.json) | [比較](comparison/zero/REPORT.md) |

四份均完整獨立複算、精確核對及 SHA-256 封存；目錄中保存 cases.json、results.jsonl.gz、checkpoints、來源與環境、manifest.json、BASELINE.json、SHA256SUMS.json。不得改寫封存內容。

產品每模式：47 星盤＋30 helper 成功、10 預期錯誤。Swiss 每模式：50 星盤＋19 時標成功、4 極區宮制錯誤、14 不具直接對照條件。不可把 Swiss 的 87 筆紀錄當成 87 次成功計算。
47 星盤可以直接配對比較；19 時標用原生 utc_to_jd 獨立比較 TT／UT1，差異以秒列出；其餘案例均保留具名結果與理由。

**原 regression/baselines/0.6.5 的 boundary 87 部分及舊 Azimuth 補充 Swiss 邊界對照已作廢，只保留歷史。** main-v2 1200／complete-v2 2016 及其路由不變。[現行指標／作廢範圍](../boundary-current.json)。
從專案根目錄執行 `./verify-boundary-numerics.ps1` 驗證兩模式，可指定 -Mode actual／zero。原 verify-numerics.ps1 與 verify-complete-numerics.ps1 維持原狀。

[完整報告及逐例清單](../../results/numerical/boundary-dual-20261101/REPORT.md)；[驗證紀錄](../../results/numerical/boundary-dual-20261101/verification.json)；[原始耗時](../../results/numerical/boundary-dual-20261101/timings.csv)。
