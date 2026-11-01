# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Generate a separately scoped UTC report from measured results."""
from datetime import datetime,timedelta
from common import ROOT,read,sha
from compare_utc import band

def main():
    s=read(ROOT/'results/utc/summary.json');cases=read(ROOT/'utc-cases.json')
    core=read(ROOT/'results/utc/core.json');ref=read(ROOT/'results/utc/reference.json')
    old=read(ROOT/'results/summary.json')
    t=s['user_birth']['time'];measured=[r for r in cases['times'] if r['measured_time']]
    def p(group,stage):return s['statistics'][group]['planets'][stage]['longitude_arcsec']['max']
    def h(group,stage):return s['statistics'][group]['houses'][stage]['max']
    def label(value):return 'PASS' if value else 'FAIL'
    rows=[
        '# UTC 雙路徑計算驗證', '',
        f'實測開始：{core["started_utc"]}。使用上一輪相同版本／JPL DE440s，新增獨立時間資料；Swiss 仍只在比較環境。', '',
        '**結論：直接由 UTC 取得 TT 後，行星差異明顯縮小；有觀測時間資料的樣本，行星與宮位均通過原定門檻。無觀測資料的模型情境仍有宮位差異，不能宣布所有年代都已通過。**', '',
        '## 主要結果', '',
        '以下皆為與 Swiss 的最大差距。每欄都在同一組 UTC 案例上比較；不是絕對天文真值的不確定度。', '',
        '| 時間資料類別 | UTC 案例 | 原生 UT1→TT 行星黃經（角秒） | UTC→TT 行星黃經（角秒） | 雙時間＋原生模型宮位／角點（角秒） |',
        '|---|---:|---:|---:|---:|',
    ]
    names={'observed':'IERS 已觀測（最終值／快速值）','iers_prediction':'IERS 短期預測','model_scenario':'超出觀測／閏秒資料的模型情境'}
    for group,name in names.items():
        rows.append(f'| {name} | {s["time_counts"][group]} | {p(group,"native"):.6f} | {p(group,"split"):.6f} | {h(group,"split"):.6f} |')
    rows += [f'| 全部（不可當作全部已觀測） | {s["epochs"]} | {p("all","native"):.6f} | {p("all","split"):.6f} | {h("all","split"):.6f} |', '',
        f'觀測組實際採樣日期：{min(r["utc"] for r in measured)} 至 {max(r["utc"] for r in measured)}；並非每天密集掃描。觀測組有 {s["house_counts"]["observed"]} 個宮位案例。', '',
        f'**角度換算：1 度 = 60 角分 = 3,600 角秒。**本輪模型組宮位最大差 {h("model_scenario","split"):.6f} 角秒 = {h("model_scenario","split")/3600:.9f} 度，約為一度的 1/{3600/h("model_scenario","split"):.2f}。角度小不等於所有分類都不受影響；只有足夠靠近宮頭的點才可能因此換宮，這輪沒有密集搜尋邊界事件。', '',
        '## 這輪真正做了什麼', '',
        '1. **UTC→TT**：ERFA 的 UTC→TAI→TT，使用固定 IERS 閏秒表。行星直接呼叫 `calc(TT)`，不再讓 `calc_ut()` 自行決定計算時刻。這次只測日、月及水星至冥王星，共十個天體的地心視位置。',
        '2. **UTC→UT1**：有資料時從 IERS 讀取 UT1−UTC。跨日插值先轉成連續的 UT1−TAI，並在 TAI 時間軸上插值，再還原差額，避免把閏秒抹平成地球轉速變化。',
        '3. **原生宮位 API 的雙時間接法**：宮位函式只收 UT1，內部還會重建 TT。因此以已算出的 TT−UT1 設定兩套引擎公開的 `set_delta_t_userdef()`，讓同一時刻使用一致差額；每次計算後恢復自動值。沒有修改上游套件檔案。',
        '4. **額外模型控制實驗**：用 ERFA `gst06a(UT1, TT)`、`obl06(TT)`、`nut06a(TT)` 得到共同天空角度，再各自呼叫 `houses_armc()`。這個額外實驗同時統一天文模型，不能把它冒充只改時間路徑的效果。', '',
        'UT1 和 TT 都代表同一個物理時刻，只是刻度不同；「兩路」不是各自任選兩個不一致的時間。', '',
        '## 宮位仍差在哪裡', '',
        '| 比較組態 | 觀測日期最大差（角秒） | 模型情境最大差（角秒） | 全部最大差（角秒） |',
        '|---|---:|---:|---:|',
    ]
    explanations={
        'native':'兩邊都給相同 UT1，各用預設 ΔT／宮位模型',
        'split':'兩邊用共同 TT−UT1，但保留各自宮位天文模型',
        'split_vs_swiss_default':'核心雙時間／原生模型，對 Swiss 預設宮位',
        'standard_control':'兩邊共用 ERFA 天空角度（只比較宮位幾何）',
        'standard_vs_swiss_split':'核心 ERFA 角度，對 Swiss 雙時間／原生模型',
        'standard_vs_swiss_default':'核心 ERFA 角度，對 Swiss 預設宮位'}
    for stage,text in explanations.items():
        rows.append(f'| {text} | {h("observed",stage):.6f} | {h("model_scenario",stage):.6f} | {h("all",stage):.6f} |')
    rows += ['',
        f'共同 ERFA 角度下，全部宮位幾何差距最大 {h("all","standard_control"):.6f} 角秒。但核心使用 ERFA、Swiss 保留預設模型時，差距仍達 {h("all","standard_vs_swiss_default"):.6f} 角秒。因此不能用共同角度的控制組宣稱「已完全吻合 Swiss 預設排盤」。', '',
        '**原生 API 的限制：**LibEphemeris 的長期恆星時在範圍接縫會另算 1850／2050 年的校準偏移。`set_delta_t_userdef()` 是全域固定值，對該內部日期也會生效；所以遠期 split 結果含有這個 API 行為，不能解讀成只改了當下 TT 的純粹效果。公開 setter 適合作此實測，但正式雙時間介面宜直接接收 UT1、TT，避免隱藏的其他日期換算。ERFA 控制路徑已示範不經此 setter 的做法。', '',
        '此外 setter 是可變全域狀態；目前各 worker 單執行緒、獨立 process，不能直接搬去多使用者並行服務。', '',
        '## 你的時間例子', '',
        '`1999-04-25 13:25:31 +00:00`：', '',
        f'- TAI−UTC = {t["tai_minus_utc"]:.0f} 秒，TT−UTC = {t["tai_minus_utc"]+32.184:.3f} 秒，所以 TT 為 **13:26:35.184**。',
        f'- IERS UT1−UTC = **{t["dut1_seconds"]:.9f} 秒**，所以 UT1 約為 **13:25:{31+t["dut1_seconds"]:.9f}**。',
        f'- 兩種時間差 TT−UT1 = {t["delta_t_seconds"]:.9f} 秒。',
        f'- 直接使用 TT 後，十個實體天體黃經最大差 **{max(abs(r["longitude_arcsec"]) for r in s["user_birth"]["planet_rows"] if r["stage"]=="split"):.6f} 角秒**。',
        '- 此例只指定出生時間，沒有提供出生地。測試中的台南等六地是測試座標，不是推定你的出生地。', '',
        '## 年代範圍與資料來源', '',
        f'- 上一輪 {old["counts"]["epochs"]} 個日期中，排除 {len(cases["excluded"])} 個 1972 年以前的案例；本輪限定現代 UTC，不替早期年代編造 UTC 定義。保留其餘格點，再加使用者日期、閏秒三個時刻及近期日期，共 {s["epochs"]} 個案例。',
        f'- IERS 資料取自 Astropy 維護的 `astropy-iers-data {cases["time_manifest"]["version"]}` 固定 wheel，因直接官方下載當時未能取得；檔案雜湊與原始來源 URL 見 time-data-sources.lock.json。沒有新增 Swiss 依賴，也沒有安裝 Astropy。',
        '- 這份資料的 final_B 至 2026-09-01；rapid_A 至 2026-10-08；2026-10-09 起為 prediction_A。使用檔案內的狀態旗標分類，不能用套件版本日期推定全部資料皆已觀測。',
        f'- EOP 檔可用日期節點：{(datetime(1858,11,17)+timedelta(days=cases["eop_mjd_range"][0])).date()} 至 {(datetime(1858,11,17)+timedelta(days=cases["eop_mjd_range"][1])).date()}；插值須有前後兩點。',
        f'- 閏秒表註記失效日：{t["leap_table_expiry"]}。超出這個日期時保留最後已知偏移，只作明確標註的假設情境。',
        '- EOP 範圍外的 UT1 使用 Skyfield 的 ΔT 模型推估，因此這組不是真正有觀測支援的直接 UTC→UT1；不是宣稱已避開地球自轉的預測不確定性。包含 1972 年無此表資料的案例，以及遠期未來。預設轉換函式會拒絕超界，測試明確開啟 allow_model 才允許。',
        '- 全部組的最大值不能與上一輪直接當作同一樣本的改善倍數：UTC 輸入代表的物理時刻與先前把數值 JD 當 UT1 不同，日期範圍也不同。上方 native 與 split 欄才是本輪同組案例比較。', '',
        '## 精度、完整性與獨立性檢查', '',
        f'- 每個引擎 {s["planet_rows_each"]} 筆行星結果；{s["house_cases"]} 個宮位案例、三組設定，共 {s["house_rows_each"]} 筆宮位向量。角差使用跨 0° 的最短差，缺漏、重複、非有限值都拒絕。',
        f'- ERFA UTC→TT 與獨立 Skyfield UTC→TT 的最大時間差：{s["max_independent_tt_check_seconds"]:.12g} 秒。兩者仍共用已知閏秒事實，這是實作交叉驗證，非另一份絕對時間觀測。',
        f'- 核心 Swiss／網路 guard：{label(s["independence_pass"])}；核心無已安裝／已載入 Swiss，計算違規事件 {len(core["unexpected_guard_events"])}。時間資料準備與計算分離。',
        '- 驗證包含 1999 已知 TT−UTC 差額、IERS 節點復現、閏秒前中後連續性、非法閏秒拒絕、模型超界不能靜默採用、樣本缺漏拒絕。測試命令為 `python -m unittest discover -s tests -v`。', '',
        '| 驗收項目 | 觀測資料組 | 全部（含模型情境） |', '|---|---|---|',
    ]
    for key,name in [('positions_1arcsec','行星位置 ≤1 角秒'),('speed_1arcsec_day','黃經速度 ≤1 角秒／日'),
                     ('distance_1e-6au','距離 ≤10⁻⁶ AU'),('houses_1arcsec','原生模型宮位 ≤1 角秒')]:
        rows.append(f'| {name} | {label(s["gates"]["observed_split_"+key])} | {label(s["gates"]["all_split_"+key])} |')
    rows += ['',
        '## 實作狀態', '',
        '這是計算核心的第二輪實驗，已實作並實測 UTC 雙路徑。**Kerykeion 高階出生資料 factory 尚未接入這個新入口**；不能把上一輪 Kerykeion 整合通過當成本輪新路徑的整合證據。沒有 UI，沒有修改第三方套件，也沒有以 Swiss 數值校準核心時間或角度。', '',
        'ERFA 角度路徑使用標準歲差／章動模型，未加入觀測的極移或天極偏移；目前目標是傳統地心星盤的一致性比較，沒有宣稱完整觀測站指向精度或所有年代的絕對精度。', '',
        f'原始 worker wall time：core {s["elapsed_seconds"]["core"]:.9f} 秒；reference {s["elapsed_seconds"]["reference"]:.9f} 秒。工作內容包含不同儀器與查核，不能直接視為公平效能排名。', '',
        f'utc-cases.json SHA-256：`{sha(ROOT/"utc-cases.json")}`。原始輪次仍在 results/，本輪在 results/utc/；重跑保留歷史。', '',
        '## 重跑與證據', '',
        '先執行 `scripts/prepare_time_data.py` 準備固定資料，再執行 `run-utc.ps1`。完整命令見 README。回傳 2 表示完整情境的數值門檻未全過，不代表沒有產生結果。', '',
        '- [本輪摘要與門檻](results/utc/summary.json)',
        '- [核心原始值](results/utc/core.json)／[Swiss 原始值](results/utc/reference.json)',
        '- [行星差異](results/utc/planet-differences.csv)／[宮位差異](results/utc/house-differences.csv)',
        '- [UTC、TT、UT1 與觀測資料來源](utc-cases.json)',
        '- [時間資料鎖定](time-data-sources.lock.json)',
        '- [第一輪報告](REPORT.md)', '',
    ]
    (ROOT/'UTC_REPORT.md').write_text('\n'.join(rows),encoding='utf-8')
    print('UTC_REPORT.md generated')

if __name__=='__main__':main()
