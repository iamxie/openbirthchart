<!-- language:zh-TW -->
# Polich–Page：何時補正宮頭，何時拒絕整張星盤？

適用：Open BirthChart v0.6.6，已包含 2026-11-01 的唯一性／連續性修正。原版 v0.6.5 EXE／ZIP 不含這些修正。這是本程式的輸出政策，不代表 Swiss 官方採用相同政策。

程式只在能確認唯一、連續的歸宮關係時輸出 T／Polich–Page 星盤。求解器回傳一個數字，可能只是從多個答案裡選到其中一個；單靠回傳成功或與另一套軟體一致，不能證明解唯一。

## 2．確實重合宮頭，只有微小殘差：可以補正

假設第一宮頭已算出，一個點使用**完全相同的黃經，而且黃緯為零**。若整套宮位幾何正常，獨立求根也確認它只有第一宮頭這一個解，便能確認它的端點身分。

此時原函式可能回傳 `12.999998569488525`，因為迭代在容差內停止；循環座標的下一個端點是 13，也就是下一圈的 1。這種情況可以把有效宮位位置補為 1，原值照樣保存。實例是 `complete-1904-11-T`：Reykjavík，1904-11-21 11:25:33，`Atlantic/Reykjavik`，北緯 64.13548°、西經 21.89541°。歷史時區由固定資料解析，不能直接當成今日 UTC+0。

補正必須同時具備四項證據：

1. **宮頭身分**：歸宮輸入黃緯為零，黃經與本次計算的某一宮頭完全重合（允許整圈等價）。只有「名叫 ASC」或「很靠近宮頭」不算。
2. **整圈正常**：宮位圈與黃道的連續對應沒有折返、重疊或退化；不只檢查十二個離散宮頭。
3. **該點唯一**：搜尋完整相關半圈的兩個象限，只有一個可接受的解，且局部斜率沒有退化；地平線接合處也須兩側一致。
4. **只是小殘差**：原始值符合原求解器的平面殘差界線，且距離已證實的宮頭端點足夠小。不能把相距很遠的另一根叫作誤差。

目前原始平面殘差上限為 0.0000011°，精確宮頭的宮位座標差上限為 0.00001 宮。後者是數值殘差的上限，**不是黃經上的吸附範圍，也不是占星容許度**。另有獨立宮頭重建與病態斜率檢查；各門檻及證據保存在驗證紀錄。一般天體即使離宮頭只有 0.00000001°，也不因靠近而被吸到下一宮。

如果一般近宮頭點的原始值已跨到獨立唯一解的另一側，或浮點精度不足以確認它在哪一側，就拒絕整盤，另用「原始求解值與邊界不一致／精度不足」說明。這是數值可靠性問題，不能誤稱為幾何多解，也不能藉補正把非宮頭點變成宮頭。

## 3．整套連續歸宮關係折返：拒絕整張星盤

Polich–Page 使用一族宮位圈。沿著這些圈前進時，如果它們在黃道上的交點先前進、再退回，同一個黃經便可能對應不同的宮位位置。即使十二個標示宮頭看起來順序正常，中間也可能折返。

例如 `complete-1914-05-T` 的 ASC 黃經約為 233.958732725°。從 MC 起算的宮位圈參數到約 65.181644° 時，已到達這個黃經；曲線繼續前進後折回，在 90° 的 ASC 再次到達。兩個解都符合方程。原始回傳約 `12.17272162437439`，不是接近 1 的微小尾數。

| 固定案例 | 精確 ASC 的原始宮位座標 | 新處理 |
|---|---:|---|
| complete-1914-05-T | 12.17272162437439 | 兩種黃緯模式均拒絕整盤 |
| complete-2000-07-T | 12.575937747955322 | 兩種模式均拒絕整盤 |
| complete-2027-04-T | 12.555481433868408 | 兩種模式均拒絕整盤 |

三例之前的「精確 ASC 指定為第一宮」只能改掉單一端點，不能接好旁邊的曲線。因此本次移除這種無條件指定。增加迭代次數也只能更精確地找到各個解，不能把多解變成唯一解。這些問題不完全以極圈為界，也不能僅依地理緯度判斷。

先前五張宮頭已交錯／重疊的 T 星盤仍拒絕；它們和本次「離散宮頭之間隱藏折返」是不同的攔截情形。參見[宮頭交錯說明](polich-page.md)。

## 4．宮頭正常，但個別非零黃緯天體有多解：仍拒絕整張星盤

宮頭是宮位圈與**黃道**的交點。天體有黃緯時，位於黃道平面之外；黃道上的對應正常，不保證該天體也只落在一個宮位圈上。因此每個實際參與計算的點都必須另查。

`complete-1914-06-T` 是具體例子：Reykjavík，1914-06-09 01:58:03，`Atlantic/Reykjavik`，北緯 64.13548°、西經 21.89541°。它的黃道宮頭關係正常，但以實際黃緯檢查時：

| 天體 | 獨立求得的連續宮位座標，顯示至小數六位 |
|---|---|
| 月亮 | 10.529301、12.602982、1.291497 |
| 水星 | 7.014401、6.960680、5.514633 |
| 金星 | 7.016860、6.889826、6.313932 |

這些是同一個點的多個幾何解，不是三次計算的隨機誤差。即使只有一個天體如此，本程式也不輸出部分星盤、不任選第一根。隱藏小天體只是顯示設定，不能繞過整份已計算點集的檢查。

此例在**使用者明確選擇**零黃緯模式時可以排盤，因為那是在計算黃道投影的另一個問題；並不代表實際黃緯的多解已被修復。程式不會為了算成功，自動關掉黃緯或改用另一個宮制。上節三張折返盤在零黃緯模式仍會拒絕。

## 使用者會看到什麼？

無法建立唯一且連續的結果時，顯示中英文原因：此時間／地點的 Polich–Page 幾何有多解、折返或退化，無法取得唯一且連續的歸宮，因此停止整張排盤，請改選其他宮位制重算。計算失敗也會清除上一張結果並停用匯出，避免誤把舊星盤當成新結果。

拒絕表示**目前所選幾何與輸出要求無法得到可接受的唯一結果**，不是出生資料已損壞，也不是天體位置本身不能計算。原始 API 回傳、呼叫參數、座標及診斷仍存於驗證捕捉；不把拒絕資料當作可供解讀的星盤。

## Swiss、文獻與驗證界線

[Swiss 官方介面文件第 16 節](https://www.astro.com/swisseph/swephprg.htm)說明連續宮位座標及黃緯輸入，也列入 T；該節沒有給出本篇這種完整的 T 多解拒絕規則。官方所稱幾何歸宮，不能直接解讀為對所有輸入保證全域唯一。

本地以 Swiss **2.10.03 公開 API** 的對照重現：三個折返例在極接近宮頭時回傳 1，離開那個極小範圍仍回到第十二宮的內部解。這是指定版本的實測，不推論其未檢視的內部程式，也不宣稱所有版本相同。[原始診斷與公開 API 證據](../results/numerical/polich-neighborhood-root-cause-20261101/REPORT.md)

Michael Wackford 的 [*Topocentric Houses: Loose ends and Unrapt parallels*](https://skyscript.co.uk/pdf/TopocentricHouses.pdf)討論宮位圈交叉與同一位置可能有多重歸屬。它是作者對幾何的分析，不是 Swiss 的 API 規格。本程式的拒絕政策則由本地方程、具名案例及產品決策共同支持。

新驗證擴大到完整相關半圈，而先前診斷的部分天體檢查只搜尋原函式所選的象限；因此先前把 1914-06 當作 ASC 正常對照，並不表示已證明其所有非零黃緯天體唯一。[實作、完整影響與限制](../results/numerical/polich-unique-20261101/REPORT.md)。舊基準、Swiss 對照及原始 fixtures 均保留；候選捕捉不是新正式基準。有限樣本驗收與浮點數守門條件，也不等於任意輸入的形式化證明。

<!-- language:en-US -->
# Polich–Page: when to correct a cusp and when to refuse the entire chart

Applies to Open BirthChart v0.6.6, which includes the uniqueness and continuity changes dated 2026-11-01. The original v0.6.5 EXE/ZIP does not include these changes. This is the application's output policy, not a claim about Swiss policy.

A T / Polich–Page chart is returned only when placement can be established as unique and continuous. A solver returning one number may simply have selected one of several answers. Successful calculation, or agreement with another program, does not prove uniqueness.

## 2. Exact cusp identity with a small residual: correction is allowed

A point with zero ecliptic latitude and **exactly the longitude of a calculated cusp** has a verifiable endpoint identity, provided the full family is valid and independent root enumeration finds only that solution.

The original solver may return `12.999998569488525` because iteration stopped within tolerance. The next endpoint, 13, wraps to 1. Its effective position may then be corrected to 1 while preserving the raw return. This occurs in `complete-1904-11-T`: Reykjavík, 1904-11-21 11:25:33, `Atlantic/Reykjavik`, latitude +64.13548°, longitude −21.89541°. The archived historical time-zone conversion must not be replaced with today's UTC+0 assumption.

Four checks are required:

1. **Identity:** zero placement latitude and exact longitude equality with a cusp, modulo a full turn. An ASC label or proximity alone is insufficient.
2. **Valid family:** the continuous ecliptic mapping has no fold, overlap or degeneracy. Checking twelve discrete cusps alone is insufficient.
3. **Unique point:** both quadrants of the relevant half-circle are searched. There must be one acceptable root with a nondegenerate local slope, including consistent one-sided slopes at the horizon join.
4. **Small residual:** the library value satisfies its plane-residual limit and lies sufficiently close to the independently established endpoint. A distant second root is not roundoff.

The current raw plane-residual limit is 0.0000011°, and the exact-cusp house-coordinate residual limit is 0.00001 house. The latter is **not a longitude snap range or an astrological orb**. Independent cusp reconstruction and conditioning checks also apply, with evidence retained in the audit. An ordinary body only 0.00000001° from a cusp is not pulled onto it.

If a raw near-cusp value lies across the boundary from the independent unique root, or floating-point precision cannot establish which side the point occupies, the whole chart is refused with a separate boundary/precision explanation. This numerical reliability issue must not be mislabeled as geometric multiplicity or repaired by pretending an ordinary point is a cusp.

## 3. The continuous family folds: refuse the entire chart

Polich–Page uses a family of house circles. If their ecliptic intersections advance and then reverse, one longitude can correspond to several house positions. The reversal can occur between apparently ordered numbered cusps.

For `complete-1914-05-T`, the ASC longitude is approximately 233.958732725°. A circle parameter measured from the MC reaches that longitude near 65.181644°, advances beyond it, then returns at the ASC parameter of 90°. Both satisfy the equations. The raw position `12.17272162437439` is far from a tiny residual at 1.

| Fixed case | Raw position at the exact ASC | New treatment |
|---|---:|---|
| complete-1914-05-T | 12.17272162437439 | Refuse in both latitude modes |
| complete-2000-07-T | 12.575937747955322 | Refuse in both modes |
| complete-2027-04-T | 12.555481433868408 | Refuse in both modes |

Assigning the exact ASC to house 1 changes one endpoint but cannot repair its neighborhood. That unconditional override is removed. More iterations locate the separate roots more precisely; they do not make them one root. These cases are not confined to locations inside the polar circles, so latitude alone is not a valid decision rule.

The five previously refused T charts with interleaved or coincident cusps remain refused. They are distinct from the hidden folds between discrete cusps discussed here. See [the interleaved-cusp article](polich-page.md).

## 4. Valid cusps but an ambiguous nonzero-latitude body: still refuse the entire chart

Cusps describe intersections with the **ecliptic**. A body with nonzero latitude is outside that plane, so a valid ecliptic mapping does not guarantee unique placement for the body. Every calculated point needs its own check.

`complete-1914-06-T`, Reykjavík, 1914-06-09 01:58:03, `Atlantic/Reykjavik`, latitude +64.13548°, longitude −21.89541°, has a valid ecliptic family but these actual-latitude solutions:

| Body | Independent continuous house coordinates, rounded to six decimals |
|---|---|
| Moon | 10.529301, 12.602982, 1.291497 |
| Mercury | 7.014401, 6.960680, 5.514633 |
| Venus | 7.016860, 6.889826, 6.313932 |

These are multiple geometric solutions for each point, not random disagreement between repeated calculations. Even one ambiguous body is enough to refuse the whole chart. The program neither returns a partial chart nor chooses the first root. Hiding minor bodies affects presentation and does not bypass checks on the calculated point set.

This particular chart succeeds when the **user explicitly selects** zero-latitude placement, which asks a different question about ecliptic projections. It does not resolve the actual-latitude ambiguity. The application never turns latitude off or switches systems automatically to obtain a result. The three folded charts above still fail in zero-latitude mode.

## What the user sees

The bilingual message explains that multiple solutions, a fold or a degeneracy prevent unique and continuous Polich–Page placement, refuses the entire chart, and asks the user to select another house system. A failed calculation clears the previous chart and disables export, preventing an older result from being mistaken for the requested one.

Refusal means the selected geometry cannot meet the required unique-result policy. It does not mean the birth data are corrupted or that celestial coordinates cannot be calculated. Verification captures retain raw returns, arguments, coordinates and diagnostic evidence without presenting refused data as an interpretable chart.

## Swiss, literature and validation limits

[Section 16 of the Swiss interface documentation](https://www.astro.com/swisseph/swephprg.htm) describes continuous house coordinates and ecliptic-latitude input, including T. That section does not specify the comprehensive T ambiguity-refusal policy used here. Describing a method as geometrical is not itself a guarantee of global uniqueness for every input.

Local public-API tests of **Swiss 2.10.03** returned 1 extremely close to the cusps in the three folded cases but returned an internal twelfth-house solution farther away. This is a version-specific observation, not a claim about uninspected implementation details or every release. [Original diagnosis and API evidence](../results/numerical/polich-neighborhood-root-cause-20261101/REPORT.md)

Michael Wackford's [*Topocentric Houses: Loose ends and Unrapt parallels*](https://skyscript.co.uk/pdf/TopocentricHouses.pdf) discusses intersecting house circles and multiple assignments. It is the author's geometric analysis, not a Swiss API contract. Our refusal policy is supported by local equations, named cases and an explicit product decision.

The new validation searches the full relevant half-circle. Some earlier diagnostic point checks searched only the library-selected quadrant; calling 1914-06 a normal ASC control therefore did not establish uniqueness for all its nonzero-latitude bodies. See the [implementation and impact report](../results/numerical/polich-unique-20261101/REPORT.md). Original baselines, Swiss references and fixtures are retained. Candidate captures are not replacement baselines, and finite tests with floating-point guards are not a formal proof for arbitrary inputs.
