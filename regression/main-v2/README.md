# 1200 例主基準 v2：現行雙黃緯模式

沿用原固定 1200 個 balanced 主案例，不含另外 87 個 boundary。每份都已重新計算、獨立複算精確核對及 SHA-256 封存。

| 模式 | 產品（LibEphemeris＋應用修正） | Swiss 對照 | 配對比較 |
|---|---|---|---|
| 實際黃緯 | [product/actual](product/actual/BASELINE.json) | [swiss/actual](swiss/actual/BASELINE.json) | [比較](comparison/actual/REPORT.md) |
| 零黃緯 | [product/zero](product/zero/BASELINE.json) | [swiss/zero](swiss/zero/BASELINE.json) | [比較](comparison/zero/REPORT.md) |

每份目錄內含 cases.json、results.jsonl.gz、逐案 checkpoints、完整來源與環境、manifest.json、BASELINE.json、SHA256SUMS.json。真實天體黃緯照常保存，零黃緯只影響歸宮輸入。不要改寫封存目錄。

**原 regression/baselines/0.6.5 的 1200 主案例部分及 regression/references/swiss-2.10.03-0.6.3 已作廢，只留歷史。** 原產品檔同時含 87 個邊界案例，整份歷史檔案原樣保留；本輪未替換那 87 例。2016 例 complete-v2 與路由不變。
現行路由及作廢範圍：[main-current.json](../main-current.json)。從專案根目錄執行 `./verify-numerics.ps1` 預設驗證新 1200 例兩模式，-Mode actual／zero 可選一種；-Legacy1287 才使用歷史版本。直接使用 numerical_regression.py 的舊 CLI 仍為歷史 1287 格式，不是現行 1200 入口。

[完整報告與逐筆清單](../../results/numerical/main-dual-20261031/REPORT.md)；[驗證紀錄](../../results/numerical/main-dual-20261031/verification.json)；[原始耗時](../../results/numerical/main-dual-20261031/timings.csv)。
