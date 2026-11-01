# Polich–Page 唯一性守門、雙語文章與影響報告

日期：2026-11-01。狀態：已完成原始碼實作與驗證，APP_VERSION 仍為 0.6.5；未重封裝 EXE／ZIP，未替換任何正式基準。使用者授權及界線見 [SCOPE.md](SCOPE.md)。

## 結果與影響

程式先驗證 T 的連續黃道宮位圈族，再驗證每個點只有一個局部連續的解。幾何折返／退化、個別天體多解均拒絕整張星盤。只有精確零黃緯宮頭身分與唯一性成立，且原始殘差很小時才補正；不再無條件把 T ASC 指定為 1。

| 固定套件 | 模式 | 舊成功 | 新成功 | 舊／新拒絕或預期錯誤 | 新增拒絕 | 存活盤精確宮頭小數座標改變數 |
|---|---|---:|---:|---:|---:|---:|
| complete-v2，2016 | actual | 1987 | 1983 | 29 → 33 | 4 | 173 |
| complete-v2，2016 | zero | 1987 | 1984 | 29 → 32 | 3 | 174 |
| main-v2，1200 | actual | 1200 | 1200 | 0 → 0 | 0 | 114 |
| main-v2，1200 | zero | 1200 | 1200 | 0 → 0 | 0 | 114 |
| boundary-v2，87 | actual | 77 | 77 | 10 → 10 | 0 | 0 |
| boundary-v2，87 | zero | 77 | 77 | 10 → 10 | 0 | 0 |

六份共 **6606 條固定條件**，沒有重抽案例。邊界每模式 77 ok 是 47 星盤＋30 helper，不能稱為 77 張星盤。所有捕捉均無 unexpected errors 或 runtime guard events。

**存活星盤整數宮號變更為 0；所有原始 API 宮位回傳與參數保留。** 精確宮頭小數座標的改變是端點殘差補正，例如 `1.0000000223517418 → 1`、`10.000000022351742 → 10`，不是一般天體重新歸宮。T 政策、補正原因與新增幾何證據 metadata 亦有改變，不能宣稱 T 整份 JSON 與舊版完全相同。

非 T 以及原有拒絕完整逐值一致（僅排除每筆耗時）。每模式完全套件 1877 筆、主套件 1115 筆、邊界 87 筆連 metadata 都不變。其餘為原成功 T：完全 139、主 85；共核對 **8960 個 T 原始 house_pos**，包括新增拒絕盤的 20 點。其他宮制藉完整紀錄精確比對確認不變。天體座標、宮頭、時標、存活盤相位及其他 chart 欄位均精確保存。

- [機器可讀完整影響](impact.json)
- [新增拒絕逐筆清單](new-refusals.csv)
- [精確宮頭小數變更逐筆清單](fractional-cusp-changes.csv)
- [最終逐值審計紀錄](audit-precision-final.log)，實作於 [audit.py](audit.py)

## 新增拒絕的實際案例

| 案例 | 原因 | actual | zero |
|---|---|---|---|
| complete-1914-05-T | 黃道宮位圈族在宮頭之間折返 | 拒絕整盤 | 拒絕整盤 |
| complete-2000-07-T | 同上 | 拒絕整盤 | 拒絕整盤 |
| complete-2027-04-T | 同上 | 拒絕整盤 | 拒絕整盤 |
| complete-1914-06-T | 黃道圈族正常，但月亮／水星／金星各有三個空間解 | 拒絕整盤 | 可排盤 |

正常殘差對照 `complete-1904-11-T` 保留原始 ASC `12.999998569488525`，驗證唯一後補為 1。先前另外五個宮頭交錯拒絕的訊息與結果均未改變。其他宮制的有效反向支援及 Koch 個別點未定義政策不變，也未擴充原有 T 極區反向排列政策。

1914-06 的三根連續宮位座標：

| 點 ID／名稱 | 根 1 | 根 2 | 根 3 |
|---|---:|---:|---:|
| 1／月亮 | 10.529301051643877 | 12.602981570755142 | 1.2914967585399533 |
| 2／水星 | 7.0144007619562005 | 6.9606796228550065 | 5.514632732286756 |
| 3／金星 | 7.016859870776167 | 6.889826489925936 | 6.313932177715406 |

前輪[根因診斷](../polich-neighborhood-root-cause-20261101/REPORT.md)已說明部分天體檢查只限函式所選象限。本輪搜尋相關半圈的兩個象限，才找出這三點的其他根；沒有把前輪「正常 ASC 對照」擴張成所有天體全域唯一的聲明。

## 實作原理與數值界線

新增 `desktop/polich.py`，正式路徑仍是 `ChartEngine.calculate → house_number2 → LibEphemeris.house_pos`，原函式不改。T 政策為 `lib-house-pos-polich-unique-v5`，非 T 政策不動。

令 q 為從 MC 起的宮位圈參數：0°＝MC、30°＝第十一宮頭、60°＝第十二宮頭、90°＝ASC、120°＝第二宮頭、150°＝第三宮頭、180°＝IC。東側 k(q) 為 q/90（0～90）或 (180−q)/90（90～180）；西側鏡射，對蹠子午面不重複計根。

黃道正向式令 a＝ARMC、e＝黃赤交角、φ＝地理緯度、r＝π/180：

```text
x(q) = cos(a+q) cos(e) − k(q) tan(φ) sin(e)
y(q) = sin(a+q)
λ(q) = atan2(y(q), x(q))
N(q) = r cos(e) + tan(φ) sin(e) [k' sin(a+q) − k r cos(a+q)]
N'(q) = tan(φ) sin(e) k r² sin(a+q)
```

角度輸入為度，三角函式內轉弧度。N 是黃經導數的分子；每段所有極值出現在端點或 sin(a+q)=0。因此不只抽樣十二宮頭，而是檢查全部解析候選極值，要求縮放後 N 嚴格為正並遠離退化；對蹠半圈重複同樣判準。另以獨立正向式重建十二宮頭確認所驗證的族正是原宮頭族。

天體獨立旋轉到赤經／赤緯，令 H 為其相對子午圈的東側等效角距、δ 為赤緯：

```text
F(q) = sin(δ) tan(φ) k(q) − cos(δ) sin(H−q)
F'(q) = sin(δ) tan(φ) k' + r cos(δ) cos(H−q)
```

解析找出 F' 的所有臨界點，在各單調區段夾根，合併兩象限共用的 q=90 端點。要求恰好一根，拒絕切根、低斜率與接合處不一致。這可發現跨原函式搜尋象限的三根，而不依函式自身分支作唯一性判斷。

| 守門條件 | 數值／單位 | 用途 |
|---|---|---|
| 縮放平面 F 殘差 guard | 2e-14，無因次 | 浮點端點／切根與邊界不可分辨 |
| F' 斜率 guard | 1e-12，每參數度 | 拒絕病態／非簡單根 |
| 族的縮放導數／退化 guard | 1e-12 | 整圈正向有效性 |
| 宮頭獨立重建 | 1e-10 度 | 確認原宮頭與所驗證族一致 |
| 原始平面緯度殘差上限 | 1.1e-6 度 | 對照原迭代 1e-6° 停止條件 |
| 精確宮頭原始宮位殘差上限 | 1e-5 宮 | 只容許小殘差，不能接受遠方另一根 |
| 獨立根距宮頭端點上限 | 1e-10 宮 | 證明根是該端點 |

**身分條件本身沒有近似帶**：歸宮黃緯必須為 0，輸入黃經減去宮頭黃經的整圈餘數必須正好為 0。以上度數、宮位座標與無因次殘差不可混用，也不是 Swiss 外部角差的 30 角秒門檻。補正證據保存在 `polich_geometry.cusp_identity`；保留 `raw_position`。

### 額外確認的近宮頭精度問題

正常 1904-11 第 2 宮頭減 1e-6° 的點，獨立唯一位置約 `1.9999999861928757`，原始函式卻回 `2.0000000298023224`。兩者很近，但取整後分處兩宮。這個點不是宮頭，不能使用第 2 類身分補正。

因此新增保守拒絕：一般點的原始整數宮號若與獨立唯一根不同，或最近宮位邊界的平面殘差小到無法確認側別，保留原值、拒絕整盤。使用獨立的「原始求解值與已驗證邊界不一致／精度不足」雙語訊息，不誤稱幾何多解，也不另選數值覆寫。固定 6606 條件未增加此類拒絕；加密的合成鄰域探測則確實觸發。

## 驗證

- 最終 **125 項 desktop 測試、10 項 house_number2 測試、6 項完整回歸工具測試全部通過**。涵蓋正常與三個折返真實盤、1914-06 個別天體三根、兩模式、隱藏點仍須檢查、全部宮頭、南北鏡射、赤道、切根、赤道極點、錯誤 frame、無效原始回傳，以及非宮頭數值跨界。
- 224 組不同 T 幾何 × 12 宮頭 × 5 偏移（−1e-6、−1e-8、0、+1e-8、+1e-6°）＝**13440 次公開 API 探測**。11520 可接受、1740 近邊界精度拒絕、180 折返族拒絕。每個接受的非宮頭點都在預期邊界側；拒絕不補正、不產生宮號。[全原始探測](cusp-probes.jsonl.gz)
- 7956 次獨立 Cartesian 平面法向量內積密集掃描（每次 36001 參數點）與解析根數一致；8846 根的最大獨立內積殘差 `2.5727033350908535e-15`。密集掃描只作獨立有限樣本檢查，不取代解析臨界點法，也不宣稱能窮盡任意輸入。[幾何摘要](geometry-checks.json)／[重現程式](geometry_checks.py)
- Qt worker 多解失敗只發出 failed，不發成功訊號。失敗清除 chart、圖面、宮頭／天體／相位表及矩陣；export_ready 也回 false，不能繞過停用按鈕匯出上一張圖。中英文訊息與數值原因分流均測試。
- 368 個翻譯條目已編譯，無 unfinished。以實際內附 Noto Sans TC 字型、Windows Qt offscreen 檢查並目視四個新對話框，無缺字或裁切。[檢查紀錄](dialog-checks.json)／[最終截圖](visuals-final/zh-TW-refusal-0.png)。沒有宣稱已驗收重封裝版或在真實顯示器上操作。
- [desktop 最終紀錄](test_desktopall-final.log)、[歸宮測試](test_house_number2-final.log)、[回歸工具測試](harness-tests.log)。桌面紀錄中的模擬 comparator failure JSON 是測試預期輸出，整套 unittest 為 OK。

最終完整數值／原始比對使用 `captures-final/`。`captures/` 為加入近邊界精度守門之前的第一次捕捉，保留作開發證據；兩次固定案例的接受／拒絕數相同。最初審計工具在 boundary helper 的 input=null 處失敗，已修正審計腳本而沒有修改任何計算資料；初始失敗紀錄保留。初始對話框截圖省略應用程式的內附字型載入而缺字，修正驗證器後以 `visuals-final/` 為準；產品啟動程式原本就會載入字型，未更動。

## 文件交付與資料保護

- [Polich–Page 中英文文章](../../../docs/polich-page-unique-placement.md)：第 2、3、4 類政策及數值邊界例外。
- [Azimuth 與 Swiss 差異中英文文章](../../../docs/azimuth-swiss-differences.md)：完成另一個文章 TODO，含五個具名案例、十二宮頭、兩模式、圖面及匯出連結。[原始文章資料](article-cases.json)直接抽自原封存，無重取樣或改寫 Swiss。
- [文章索引](../../../docs/README.md)連結既有 Koch 與宮頭交錯說明。原 Polich 文章只加新政策交叉連結；既有內建 Azimuth 說明及 HTML 未動。新文章是獨立文件，未自動嵌入 UI／匯出附錄。
- HANDOFF、TODO、DESKTOP_README 已更新最新入口、結果與未完成界線。閏秒辨識與一般 GitHub 回報流程仍待辦，不在本次「完成文章」授權範圍；水星與 TT／UT1 差異依既有決定不處理。
- [保護驗證](preservation.json)逐一核對開始時記錄的 25091 個既有檔案，涵蓋 regression（含 current 指標）、vendor 與安裝的 LibEphemeris、依賴鎖定及 dist。捕捉環境另外精確核對星曆／資料／依賴／Python 與舊版相同。未使用個人 ProfileStore；UI 測試使用暫存資料庫。
- 修改前來源在 `before/`；最終來源在 `source-final/`；[來源變更清單](source-changes.json)、[最終來源雜湊](SOURCE-SHA256.json)、[證據雜湊](EVIDENCE-SHA256.json)另存。無 `.git` 工作樹，使用前後來源及 SHA-256 追溯。

原正式基準不變，所以 `verify-complete-numerics.ps1`／`verify-numerics.ps1` 對舊基準會顯示這次授權的 T 政策、殘差與拒絕差異，**不是聲稱舊精確回歸全等通過**。不得為了轉綠覆寫封存或 current.json。H 原有 Swiss 宮號差異仍保留；本輪沒有重算 Swiss，也沒有宣稱上游已採相同 T 拒絕政策。

## 原始耗時與重現

[validation-timings.jsonl](validation-timings.jsonl)包含初輪與最終輪的外層原始秒數；每次捕捉另有 session 的 wall／pool 秒數與每筆原始耗時。最終外層秒數依序為：

| 工作 | 秒 |
|---|---:|
| 完全 actual | 35.72521459998097 |
| 完全 zero | 36.09590770001523 |
| 主案例 actual | 42.05241250002291 |
| 主案例 zero | 36.2983424999984 |
| 邊界 actual | 4.81132570002228 |
| 邊界 zero | 5.514911400037818 |
| desktop 測試 | 201.19174379995093 |
| house_number2 測試 | 0.9144218000583351 |

工作部分重疊且含環境雜湊／啟動開銷，這不是受控效能基準，不換算成本。

```powershell
.venv-desktop/Scripts/python.exe -B results/numerical/polich-unique-20261101/audit.py
.venv-desktop/Scripts/python.exe -B -m unittest discover -s tests -p test_desktop*.py
.venv-desktop/Scripts/python.exe -B -m unittest discover -s tests -p test_house_number2.py
.venv-desktop/Scripts/python.exe -B -m unittest discover -s tests -p test_complete_regression.py
```

重做捕捉時，使用 `scripts/complete_regression.py run --cases <原 v2 cases.json> --engine product --workers 12 --output <全新目錄>`。不要覆寫本目錄或既有基準。重做審計／幾何證據亦宜複製腳本並指定另一個證據目錄，以保留本輪已雜湊的結果。
