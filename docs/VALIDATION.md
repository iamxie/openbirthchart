# 驗證方法與已知差異 / Validation and known differences

產品：LibEphemeris 3.2.2 加 OpenBirthChart 應用層政策。參考：獨立環境的 pyswisseph 2.10.3.2／Swiss。Swiss 的模組與 `.se1` 資料不作為桌面執行依賴；驗證來源、版本與既有差異如實保留，不是官方認證或背書。

## 固定案例

| 套件 | 每模式筆數 | 模式 |
| --- | ---: | --- |
| main-v2 | 1200 | actual／zero |
| complete-v2 | 2016（不是 2060） | actual／zero |
| boundary-v2 | 87 | actual／zero |

總計 6606 條固定條件，部分條件跨套件重複，不宣稱為去重後的案例數。87 包含星盤與 helper，不等於 87 張成功星盤。三個 `verify-*-numerics.ps1` 入口預設各模式 12 個 worker，各模式依序；封存核對與比較也需要時間。

正式舊封存保留原值與 source/environment，T 唯一性及閏秒拒絕說明等已接受修正會在精確回歸中顯示差異。發佈驗證另明確指定 `validation/reviewed` 的修正後來源，只允許 raw/version 改變，其他數值與狀態精確比較。不得用 Swiss 的 `<30 角秒` 外部角度門檻，取代有效整數宮號的一致性或版本內精確比較。

## 已知差異與政策

- H／Azimuth：一般點與 Swiss 的宮號差異保留，MC 第四／十宮編號矛盾已修正；MC 一致不能推論所有點一致。
- T／Polich–Page：多解、折返或個別點無法唯一歸宮時整盤拒絕；不為了符合 Swiss 的單一回傳而任選一根。
- Koch：已知原始 0 哨兵代表個別未定義，不是第零宮。
- 水星停滯附近約 0.2 時間秒、TT 約 40 微秒、UT1 約 0.563 時間秒的既有差異保留。這些是時間單位，不是角秒。
- 閏秒排盤仍不支援，明確拒絕而不改輸入。

完整原始封存與歷史證據隨完整來源包提供。Git 精簡目錄只提供輸入及文件；要跑全部既有測試，先從同版完整來源包補入 `regression/` 與 `validation/`。部分歷史文章連到 `results/` 下的原始證據，也在完整來源包的精選證據中；歷史紀錄提及的舊 EXE 不代表仍提供下載。

## English

Production calculations use pinned LibEphemeris plus application policies. Independent Swiss/pyswisseph comparisons retain their version and original outputs, without claiming endorsement or universal equivalence. Swiss binaries/data are not desktop runtime dependencies.

The fixed suites contain 1200, 2016 and 87 cases per latitude mode (6606 total); duplicates across suites are not treated as unique cases. Boundary tests include helpers. Verification uses 12 worker processes per mode. Numerical equality and valid house-number agreement are distinct checks; an angular tolerance cannot excuse a house-number mismatch.

Original baselines remain immutable. Accepted T and leap-second changes can differ from those archives; the release gate explicitly uses a reviewed post-fix reference and allows only the application's version field to differ. Large archives and selected historical evidence are supplied in the complete source ZIP, not all committed into Git. Existing H and time-scale differences are documented rather than hidden.
