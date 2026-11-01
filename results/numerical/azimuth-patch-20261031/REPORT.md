# Azimuth 應用層編號補丁與回歸驗收（2026-10-31）

狀態：原始碼完成，APP_VERSION 仍為 0.6.5，既有 EXE／ZIP 未重新封裝。LibEphemeris、所有原產品基準與 Swiss 基準均保留。此次候選捕捉另存本目錄，沒有另封正式基準。

## 結果

| 項目 | 完全基準 2016 例 | 舊 1287 例 |
|---|---:|---:|
| 成功建立完整星盤 | 1987 | 1247 |
| 原有其他 helper 案例成功 | 0 | 30 |
| 預期拒絕／錯誤 | 29 | 10 |
| 宮號有變更的星盤 | 78 | 58 |
| 變更宮號的點 | 1548 | 1150 |
| 其中 MC 改為第十宮 | 66 | 48 |
| 其中其他點 | 1482 | 1102 |
| 所有原始 house_pos 逐值保留 | 39740 | 24940 |
| 所有角度、宮頭、非 H 結果逐值保留 | 是 | 是 |

舊 1287 例包含 1257 個完整出生條件案例及 30 個宮頭／相位／時標 helper 案例；不是 1287 張可出圖星盤。實際結果為 1277 ok、10 個預期錯誤（AmbiguousTimeError 1、UserError 8、ValueError 1）。其中 1247 張有完整星盤。所有接受／拒絕狀態與補丁前相同，沒有新增失敗。

精確影響比較對象是上一輪已含 C/R、T 拒絕說明與 T ASC 修正的 `polich-asc-20261031/product` 與 `legacy-product`。本次僅 H 歸宮、政策／補正 metadata 與提示變更；非 H 原始／數值結果完全相同。完全基準 1872 例、舊 1186 例連 metadata 都逐值相同；其餘為 144／101 張 H 政策更新，其中只有 78／58 張整數宮號改變。不能把 metadata 改變說成整份 JSON 未變。

## 實作範圍與原理

- 新增 `desktop/azimuth.py`，由 `ChartEngine.calculate` 為每張 H 星盤建立一次編號對應，`house_number2` 將原始連續座標換算後才取 floor。H 政策為 `lib-house-pos-azimuth-aligned-v5`；其他宮制維持 v4。
- 使用獨立 Cartesian 黃道→赤道→當地地平分量，驗證十二宮頭確實為相隔 30° 的空間方向；從宮頭確認起點 α₁（0° 或 180°）與方向 s（+1 或 −1），不是只按半球判斷。
- 換算：α = (原始 house_pos − 1) × 30°；新連續宮位 = 1 + [s × (α − α₁) mod 360°] / 30°。原始 house_pos、天體實際黃經／黃緯完整保存，不改 LibEphemeris。
- 幾何驗證容差 1e-7 度只用來檢查對應，不能當作邊界進位容差。確認黃緯為 0、與某宮頭的黃經角差 ≤1e-10 度且連續宮位殘差 ≤1e-9 宮時，才維持該宮頭的端點歸屬。一般 .99999 不一律進位。
- 天頂 zenith／天底 nadir 的水平投影長度 ≤1e-12、無效宮頭、與原始 API 方向不符或過期對應上下文，均拒絕；實際排盤轉為中英文原因與換宮制建議。沒有自動 fallback。
- 圖面仍依黃經繪製；非零黃緯天體的空間歸宮仍可能與二維黃經區間不同。所謂圖面／表格一致，是採用相同宮頭編號及同份計算結果，不是把黃緯丟掉強迫落入圖面扇區。
- 新計算顯示「已依宮頭編號校正」；舊計算資料的「存在已知編號差異」提示保留，不把舊結果誤標成已校正。中英文說明文章、離線附錄及 Qt 翻譯同步更新。

## 哪些案例受影響

| 幾何類別 | 完全基準 | 舊案例 | 每張變更 |
|---|---:|---:|---:|
| α₁=0°、s=−1 | 60 | 42 | 20 點，含 MC |
| α₁=180°、s=+1 | 6 | 6 | 20 點，含 MC |
| α₁=180°、s=−1 | 12 | 10 | 19 點，MC 原本就是 10 |

- [完全基準：78 個案例與每例 Swiss 宮號差異數／宮頭最大角差](complete-affected-cases-with-swiss.csv)
- [完全基準：1548 個變更點，含前後宮號及 Swiss 原值](complete-changed-points-with-swiss.csv)
- [舊案例：58 個案例與每例 Swiss 差異](legacy-affected-cases-with-swiss.csv)
- [舊案例：1150 個變更點，含前後宮號及 Swiss 原值](legacy-changed-points-with-swiss.csv)

代表案例：`complete-1904-01-H`（Melbourne，南半球正向）、`complete-1904-02-H`（Bangkok，北半球正向，宮號不變）、`complete-1904-03-H`（Darwin，南半球反向，MC 原本正確但其他 19 點改變）、`complete-1936-09-H`（Manila，北半球反向）。

## 與 Swiss 的宮號差異

| 對照範圍 | 補丁前 MC 差異 | 補丁後 MC 差異 | 補丁後其他點差異 |
|---|---:|---:|---:|
| 完全基準，1987 張可比 | 66 | 0 | 78 張／1482 點 |
| 舊 1200 主案例 | 42 | 0 | 42 張／798 點 |
| 舊邊界 47 張可比 | 6 | 0 | 16 張／304 點 |
| 舊案例合計 1247 張可比 | 48 | 0 | 58 張／1102 點 |

每張受影響盤的其餘 19 個點都與封存 Swiss 回傳不同，包含 ASC、幸運點、南北交點、行星與小天體；這不表示這些點的黃經或黃緯改變。Swiss 原值不改寫，差異沒有豁免為通過。

- [完全基準：全部 Swiss 宮號差異](complete-swiss-house-differences.csv)
- [舊案例（含新補充邊界）：全部 Swiss 宮號差異](legacy-swiss-house-differences.csv)
- [完整比較報告](swiss-comparison/REPORT.md)、[舊 1200 例比較報告](legacy-swiss-comparison/REPORT.md)。比較器仍正確回傳 review-required／退出碼 1；這是保留宮號差異與既有例外，不是捕捉失敗。

完全基準的 5 個 T 預期單方拒絕、31 張／57 個 Koch 雙方未定義保留；其他問題未動。舊主案例 Koch 23 張／32 點雙方未定義亦保留。

## 與 Swiss 的宮頭與天體座標差

**補丁前後所有產品角度逐值完全相同，宮頭的補丁造成角差為 0。** 下表是產品對 Swiss 的角差，單位為角秒：

| 範圍 | H 宮頭最大黃經差 | 所有宮制宮頭最大黃經差 | 天體／衍生點最大黃經差 | 最大球面角距 |
|---|---:|---:|---:|
| 完全基準 | 0.002619757083 | 0.017651131373 | 1.506332452232 | 1.531876488327 |
| 舊案例（含邊界） | 0.006110244112 | 1.704252654827 | 2.074552711173 | 1.963023576039 |

全部可比較角度仍嚴格小於 30 角秒。宮號差異與角度容差分開處理。

- 完全基準 H 最大：`complete-1958-10-H`，宮頭 2；產品 42.983035317056874°、Swiss 42.98303458934657°。
- 舊案例 H 最大：`edge-azimuth-main-2023-05`，宮頭 6；產品 354.021173499425°、Swiss 354.02117519671503°。
- 全宮制最大：完全基準 `complete-2012-08-R` 宮頭 12；舊案例 `edge-range-last` 宮頭 8（1.704252655 角秒）。後者屬本輪新補充的邊界外部對照；原 1200 主案例最大仍是 0.004678166 角秒，不能把新增範圍的最大值當成補丁使精度退步。
- [完全基準全部 1728 個 H 宮頭雙方座標](complete-azimuth-cusps-vs-swiss.csv)
- [舊案例全部 1212 個 H 宮頭雙方座標](legacy-azimuth-cusps-vs-swiss.csv)
- [全統計與最大差原值](swiss-summary.json)；其他宮制每筆座標在兩份 comparison/all-comparisons.csv 與 boundary-comparisons.csv。

## 補充 Swiss 邊界對照的範圍

舊 Swiss 基準只有 1200 主案例，原檔保留。本輪用既有隔離 CPython 3.11.16 與同一 Swiss 2.10.03 模組／星曆資料，另存 `boundary-swiss.json`。只共用民用時間解析產生的 TT／UT1，Swiss 自算天體、宮頭與歸宮；沒有把產品座標餵入。模組與資料雜湊符合封存版本，guard events 為空。

87 個邊界輸入中，30 個是 helper-only 不適用完整星盤 Swiss 比較，4 個民用時間本來就無法解析，4 個極區 P/K 被 Swiss 拒絕，49 個 Swiss 成功。其中 `edge-range-before`／`edge-range-after` 被產品既有日期範圍限制拒絕，另 47 張雙方成功並全部比較。16 張受影響的舊 H 邊界盤全數包含；詳細結果見 [邊界結果](boundary-outcomes.csv) 與 [逐項比較](boundary-comparisons.csv)。本次沒有更改這些原有產品限制。

## 測試與圖面／匯出驗收

- 最終 110 項桌面測試、10 項 house_number2 測試通過。新增測試涵蓋四種編號組合、赤道正常／退化、十二宮頭及兩側、獨立球面幾何的 120 個非零黃緯點、無效原始回傳、不同 API 約定及過期對應上下文。
- 在兩套實際捕捉的全部 H 盤上，2940 個宮頭身分與 11760 個兩側偏移（±1e-6／±1e-8 度）核對通過。每個 MC 都歸入 10。原始 API 保留與非 H 完整精確比較由 `audit.py` 驗證。
- 四種代表盤 × 中英文：真實桌面表單重算與捕捉精確一致，桌面全部天體宮號、宮頭表、PNG／SVG／HTML 共用結果；前後 paint_wheel SVG 逐字一致，圖形幾何未移動。使用暫存 ProfileStore，未存取個人資料庫。
- Edge 離線 1300／800／480／320 px 共 32 組檢查通過，沒有橫向溢出、外部請求或頁面錯誤。
- 8 份 A4 橫向 PDF 共 49 頁，全部頁碼、尺寸及表格完整性通過。已目視檢查全部八個星盤頁、代表桌面、表格、完整文件縮圖及雙語附錄／說明視窗；沒有發現裁切、文字重疊或缺字。
- 驗收環境為 Windows Qt offscreen 與 Edge headless；沒有重建或宣稱已驗收既有 EXE／ZIP。代表圖面與 PDF 位於 `visuals/`，檢查紀錄為 desktop-checks.json、browser-checks.json、pdf-checks.json、help/checks.json。

原始耗時保留：完全捕捉 workers=12，wall_seconds=19.828869600081816、pool_wall_seconds=13.572986799990758；舊 1287 捕捉 elapsed_seconds=137.49128389998805。這輪與測試同時執行，不是可直接比較的受控速度基準。

## 保護與重現

842 個原基準／參考／依賴／封裝等既有檔案雜湊未變；繼承診斷清單中的 11 個應用／回歸工具來源及交接文件，屬此次明確授權的編輯，逐一列在 impact.json。新來源與全部驗收證據另封 EVIDENCE-SHA256.json。所有原始 fixtures 保留。

```powershell
.venv-desktop/Scripts/python.exe -B results/numerical/azimuth-patch-20261031/audit.py
.venv-desktop/Scripts/python.exe -B results/numerical/azimuth-patch-20261031/summarize_swiss.py
.venv-desktop/Scripts/python.exe -B -m unittest discover -s tests -p test_house*.py -v
.venv-desktop/Scripts/python.exe -B -m unittest discover -s tests -p test_desktop*.py -v
```

新捕捉須使用另一個未存在的輸出目錄，不能覆寫本次候選或任何 regression 基準。原精確回歸入口仍對舊基準，會呈現已知修正與政策差異；不能為消除差異更新原基準。

`desktop-tests.log` 是首次測試，含三項舊測試假設未更新所致失敗；之後只調整測試的 H 契約與 HTML escaping，最終完整結果以 `desktop-tests-final.log` 為準。沒有藉由放寬產品數值容差來使測試通過。
