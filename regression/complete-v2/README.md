# 完全基準 v2：現行雙黃緯模式

這是固定 2016 條件的四份新封存。產品採用目前 LibEphemeris 加應用層修正；Swiss 獨立計算。實際黃緯與零黃緯只影響歸宮輸入，天體真實坐標照常保存。

| 模式 | 我們版本（Lib-EPH based + 修正） | Swiss 對照 | 配對比較 |
|---|---|---|---|
| 實際黃緯 | [product/actual](product/actual/BASELINE.json) | [swiss/actual](swiss/actual/BASELINE.json) | [比較](comparison/actual/REPORT.md) |
| 零黃緯 | [product/zero](product/zero/BASELINE.json) | [swiss/zero](swiss/zero/BASELINE.json) | [比較](comparison/zero/REPORT.md) |

每個目錄都保存 2016 例（含拒絕），內含固定輸入、原始結果、來源／依賴／資料／執行檔雜湊、逐組檢查點、獨立複算證明及 SHA256SUMS.json。不得改寫已封存目錄；有核准的數值變更時另建版本。

舊 complete-v1/product-0.6.5 與 complete-v1/swiss-2.10.03 已作廢，只留歷史追溯；舊 cases.json 的取樣條件仍有效，沒有重抽任何日期、時間、城市或宮制。舊 1287 例與其基準未替換。
現行路由及廢止紀錄：[complete-current.json](../complete-current.json)。日後不要依 complete-v1 歷史 README 判斷現行基準。

從專案根目錄執行 `./verify-complete-numerics.ps1` 可重算產品兩模式並逐值精確比對；`-Mode actual`／`-Mode zero` 可單獨選擇。原 `verify-numerics.ps1` 的舊 1287 例路由不變。
Swiss 外部比較另行執行 scripts/compare_complete.py，輸入同模式兩份資料；有已知差異時回傳 1 並保存 review_required=true，不表示資料捕捉失敗。

[本輪完整報告](../../results/numerical/complete-dual-20261031/REPORT.md)；[驗證紀錄](../../results/numerical/complete-dual-20261031/verification.json)；[原始耗時](../../results/numerical/complete-dual-20261031/timings.csv)。
