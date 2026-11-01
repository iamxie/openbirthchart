# 87 邊界案例：產品與 Swiss 比較

模式：actual；完整保留 87 筆輸入／狀態，分類為 {"both_rejected":4,"chart_compared":47,"no_unique_instant":3,"product_helper_no_native_equivalent":11,"product_only_rejection":3,"time_compared":19}。

- 可比星盤 47 張；宮號差異 16 張／304 點；ASC 16、MC 0。
- 可比較角度 ≥30 角秒：0；天體最大黃經差 1.7943704431047536 角秒，宮頭 1.7042526548266324 角秒。
- 時標獨立對照 19 例；TT 最大絕對差 4.023313522338867e-05 秒；UT1 0.5629822611808777 秒。這不是角度誤差，也未用 30 角秒門檻判定時間正確。

- all-comparisons.csv 保存所有星盤點與宮頭；house-differences.csv 是宮號差異。time-comparisons.csv 分開保存每例時標結果與來源。
- outcomes.csv 包含全部 87 例；not-comparable.csv 列明未指定唯一物理時間及沒有原生 Swiss 對應 API 的測試；rejections.csv 保留預期拒絕及錯誤。
- 共用 TT／UT1 的星盤比較不獨立驗證時區。UTC 閏秒排盤的 Swiss 輸出使用其原生 utc_to_jd，產品拒絕該輸入，沒有假造可比產品星盤。
- 未定義、預期拒絕、未能對照皆不當成成功同宮。Swiss 沒有模仿產品任意宮頭陣列或相位容許度規則。
- 兩模式只改歸宮時傳入的黃緯；真實座標、獨立時標測試及不適用項目的原始輸入都保留。
