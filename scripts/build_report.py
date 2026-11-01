# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Generate the human report from measured artifacts, never from rounded constants."""
import csv
from common import ROOT, BODIES, read, sha

def main():
    s=read(ROOT/'results/summary.json')
    d=read(ROOT/'results/diagnostic-summary.json')
    c=read(ROOT/'results/core.json')
    r=read(ROOT/'results/reference.json')
    audit=read(ROOT/'results/dependency-audit.json')
    contracts=read(ROOT/'results/core-contracts.json')
    cases=read(ROOT/'cases.json')
    with (ROOT/'results/planet-differences.csv').open(encoding='utf-8',newline='') as f: planets=list(csv.DictReader(f))
    with (ROOT/'results/house-differences.csv').open(encoding='utf-8',newline='') as f: houses=list(csv.DictReader(f))
    def maximum(rows, key): return max(abs(float(row[key])) for row in rows)
    physical=[row for row in planets if row['body'] in BODIES[:10]]
    tt=[row for row in physical if row['scale']=='TT']
    ut=[row for row in physical if row['scale']=='UT1']
    yn=lambda value:'PASS' if value else 'FAIL'
    lines=[
        '# 計算核心驗證報告', '',
        f'本報告由 `scripts/build_report.py` 根據原始測量產生。主測試開始：{c["started_utc"]}；完成：{c["completed_utc"]}。', '',
        '**結論：本次測試組態可在沒有 Swiss 執行套件／星曆資料的核心環境運作；全部精度驗收門檻尚未通過。**', '',
        f'相同 TT 時刻，十個實體天體黃經最大差 {maximum(tt,"longitude_arcsec"):.6f} 角秒；各自使用原生 UT1 換算時，最大差 {maximum(ut,"longitude_arcsec"):.6f} 角秒。宮位／角點最大差 {maximum(houses,"difference_arcsec"):.6f} 角秒。', '',
        '這是與 Swiss 的一致性測量，不是對絕對天文真值的證明。沒有因為測量結果而放寬門檻，也沒有用 Swiss 輸出修正主測試。', '',
        '## 固定版本與隔離', '',
        '| 項目 | 實測版本／設定 |', '|---|---|',
        f'| Core Python | {c["python"].split()[0]} |',
        f'| Kerykeion | {c["packages"]["kerykeion"]} |',
        f'| LibEphemeris | {c["packages"]["libephemeris"]} |',
        f'| Skyfield | {c["packages"]["skyfield"]} |',
        f'| Reference Python | {r["python"].split()[0]} |',
        f'| pyswisseph / Swiss library | {r["packages"]["pyswisseph"]} / {r["swiss_library_version"]} |',
        f'| 核心 backend / mode | {c["backend"]} / {c["mode"]} |',
        '| 核心資料 | JPL DE440s；外行星使用系統重心，未配置額外行星中心 SPK |',
        f'| Swiss 星曆的 DE 編號 | {sorted(set(item[3] for item in r["swiss_files"]))}；確認未退回 Moshier |', '',
        '兩個獨立 venv／Python process。核心沒有安裝 pyswisseph；參考環境沒有安裝 Kerykeion 或 LibEphemeris。測試前清除繼承的相關環境變數，指定本專案空白設定檔、Skyfield 模式、sealed 網路政策、固定 kernel，停用自動 SPK 與 IERS ΔT。完整設定見 `results/core.json` 的 configuration。', '',
        '## 驗收門檻', '',
        '門檻在首次完整實測前寫入 `cases.json`：位置／宮位 1 角秒、黃經速度 1 角秒／日、距離 10⁻⁶ AU；整合一致性 10⁻⁶ 角秒。這是本專案測試目標，不是廠商保證。', '',
        '| 檢查 | 結果 |', '|---|---|',
    ]
    lines += [f'| `{key}` | {yn(value)} |' for key,value in s['gates'].items()]
    lines += [f'| 靜態依賴檢查 | {yn(audit["hard_dependency_pass"])} |',
        f'| 安裝來源比對與 generator 掃描 | {yn(audit["source_audit_pass"])} |',
        f'| 時區／DST／超界／極區契約 | {yn(contracts["pass"])}；{len(contracts["checks"])} 項 |', '',
        '## 測試涵蓋', '',
        f'- {s["counts"]["epochs"]} 個時刻，1850–2149 每年一個固定種子抽樣；另加 2024–2026 每月、世紀／閏日／選定邊界日期。不是連續時域的最大誤差保證。',
        f'- 日、月、水、金、火、木、土、天王、海王、冥王，以及探索性平均／真月交點；TT、UT1 各跑一次，每個引擎 {s["counts"]["planet_rows_each"]} 筆。',
        '- 使用熱帶黃道、地心視位置、日期黃道框架；相同旗標語義，速度、距離也比較。TT 測試把同一數值 JD 當 TT；UT1 測試把同一數值 JD 當 UT1。calendar_label 只標識採樣日期，兩種尺度不是同一物理時刻。',
        f'- {s["counts"]["house_cases_each"]} 組宮位：六地點、P/K/O/E/W 五宮制，每組 12 宮頭與 8 角點，共 {len(houses)} 個比較值。緯度包括 ±65.5°。',
        f'- {s["counts"]["charts"]} 個 Kerykeion 完整資料模型與 natal chart data；P/A/W 三宮制（A 為 Equal）。直接 LibEphemeris 與整合輸出共 {s["integration_arcsec"]["n"]} 個位置／宮頭比較，最大差 {s["integration_arcsec"]["max"]:.9f} 角秒。',
        f'- 星座／逆行分類抽樣差異：{len(s["categorical_disagreements"])} 筆；見 summary.json。接近分界的事件時間仍需專門密集搜尋。', '',
        '## 行星結果', '',
        '下表為最大黃經差（角秒）；月交點不列入實體天體驗收。完整黃緯、距離、速度、P95、median 見 summary.json。', '',
        '| 天體 | 相同 TT | 原生 UT1 |', '|---|---:|---:|',
    ]
    for name in BODIES:
        lines.append(f'| {name} | {s["planetary_statistics"][f"TT/{name}"]["longitude_arcsec"]["max"]:.6f} | {s["planetary_statistics"][f"UT1/{name}"]["longitude_arcsec"]["max"]:.6f} |')
    lines += ['', '| 尺度 | 最大黃緯差（角秒） | 最大黃經速度差（角秒／日） | 最大距離差（AU） |', '|---|---:|---:|---:|']
    for scale,rows in [('TT',tt),('UT1',ut)]:
        lines.append(f'| {scale} | {maximum(rows,"latitude_arcsec"):.6f} | {maximum(rows,"speed_arcsec_per_day"):.6f} | {maximum(rows,"distance_au"):.9g} |')
    lines += ['', '## 宮位與日期範圍', '', '| 宮制 | 最大宮頭差（角秒） | 最大角點差（角秒） |', '|---|---:|---:|']
    for system in ('P','K','O','E','W'):
        lines.append(f'| {system} | {s["house_statistics"][system+"/cusps"]["max"]:.6f} | {s["house_statistics"][system+"/angles"]["max"]:.6f} |')
    epoch_year={e['id']:int(e['calendar_label'][:4]) for e in cases['epochs']}
    house_year={h['id']:epoch_year[h['epoch']] for h in cases['houses']}
    lines += ['', '以下分段為診斷摘要，不改動全範圍驗收：', '', '| 採樣年份 | 原生 UT1 黃經最大差（角秒） | 宮位／角點最大差（角秒） |', '|---|---:|---:|']
    for lower,upper in [(1850,2049),(2050,2149)]:
        p=[row for row in ut if lower<=epoch_year[row['id'].split(':')[0]]<=upper]
        h=[row for row in houses if lower<=house_year[row['id']]<=upper]
        lines.append(f'| {lower}–{upper} | {maximum(p,"longitude_arcsec"):.6f} | {maximum(h,"difference_arcsec"):.6f} |')
    lines += ['', '## 差異診斷', '',
        f'1. 各模型把 UT1 轉成 TT 時採用的 ΔT 不同。抽樣最大 Skyfield 與 Swiss ΔT 差為 {max(abs(x["skyfield_delta_t_diff_seconds"]) for x in d["times"]):.6f} 秒。診斷中把 TT 時刻對齊後，{d["aligned_ut_planet_count"]} 個行星樣本的最大黃經差降到 {d["max_aligned_ut_planet_longitude_arcsec"]:.6f} 角秒。',
        f'2. 對宮位給予相同 ARMC（當地子午線赤經）與黃赤交角，{d["geometry_comparisons"]} 個幾何比較最大差 {d["max_geometry_arcsec"]:.6f} 角秒。原主測試時刻改用共用 ARMC／黃赤交角後，最大差 {d["max_house_with_shared_armc_obliquity_arcsec"]:.6f} 角秒。這支持主要差距來自上游時間／座標模型，而非宮位三角計算本身。',
        f'3. 恆星時最大差 {max(abs(x["sidtime_diff_arcsec"]) for x in d["times"]):.6f} 角秒；高緯度宮位會放大此輸入差。另以 ERFA gst06a 作診斷比較，原始差異見 diagnostic-summary.json；不能直接把 Swiss 當作唯一正確模型。',
        '4. LibEphemeris 的長期恆星時實作在 1850–2050 與範圍外使用不同處理；資料核心亦為 DE440 對 DE441。未修改上游公式來追平參考。', '',
        '**診斷腳本會讀取已保存的 Swiss 數值作為共用輸入；這只用於分離差異來源。主核心 worker 不讀參考結果、Swiss 星曆或參考 venv，正式核心不需要診斷腳本。**', '',
        '## Swiss 獨立性：已證明的範圍', '',
        f'- 核心已安裝 Swiss 套件：{c["installed_swiss"]}；已載入 Swiss module：{c["loaded_swiss"]}。',
        f'- 安裝來源盤點 {len(audit["source_inventory"])} 個 Kerykeion／LibEphemeris Python 檔；所有核心套件的直接 Swiss import {len(audit["direct_swiss_imports"])} 個，Swiss 二進位／.se1 檔 {len(audit["swiss_binary_or_data_files"])} 個。',
        f'- LibEphemeris tag 原始碼 commit `{audit["source_checkout_commit"]}`；與 wheel Python 原始碼標準化文字比對，差異 {len(audit["libephemeris_source_mismatches"])} 個。掃描 {len(audit["source_generation_scan"])} 個開發／生成腳本。',
        '- 上游 algorithm provenance registry 結構檢查已執行；結果見 upstream-provenance-structure.txt。這只是來源紀錄覆蓋檢查，不是獨立推導或完整 Git 歷史的證明。',
        f'- import/file/network guard 自我測試：{c["guard_self_test"]}；正式主計算違規事件 {len(c["unexpected_guard_events"])}。契約測試亦沒有違規事件。',
        '- Kerykeion 上游仍存在可選 Swiss adapter。此專案強制 libephemeris 並攔截 Swiss import；本次驗證的是指定版本與組態，並非宣稱上游所有設定都沒有 Swiss 路徑。',
        '- CPython audit hook 是測試儀器，不是作業系統安全邊界；未宣稱阻擋所有可能繞過 Python 的原生程式。未進行完整歷史／著作權來源認證。', '',
        '實際觀測到的資料讀取（含 SHA-256）保存在 core.json；以下是檔名：', '',
    ]
    lines += [f'- `{item["path"].replace(chr(92),"/").split("/")[-1]}`' for item in c['data_reads']]
    lines += ['', '## 時區與邊界', '']
    lines += [f'- {yn(check["passed"])}：`{check["name"]}`' for check in contracts['checks']]
    lines += ['',
        '極區低階 P/K 宮位 API 會拒絕無定義輸入；Kerykeion 的高階 API 則有明確記錄的 Porphyry 替代。若將來推出 UI，須顯示實際採用宮制。', '',
        'Kerykeion 時區測試驗證相同 UTC 時刻、秒數與 DST 歧義；本次不等同於完整 UTC→UT1（含 DUT1／IERS）高精度驗收。未用缺乏精確歷史時區資料的出生時間驗證古代曆法。', '',
        '## 原始時間與可重現性', '',
        f'- core worker wall time：{s["wall_seconds"]["core"]:.9f} 秒。',
        f'- reference worker wall time：{s["wall_seconds"]["reference"]:.9f} 秒。',
        '- 上述是此機器此輪完整 worker 的原始量測，包含啟動、查核與不同工作內容，不是公平的單次排盤效能基準。每次計算耗時亦保存在 raw JSON。',
        f'- cases.json SHA-256：`{sha(ROOT/"cases.json")}`。',
        '- Python dependencies 有完整版本與雜湊鎖定；星曆來源與 SHA-256 見 data-sources.lock.json；每次重跑先將上一輪結果複製到 results/history。', '',
        '## 下一階段決策', '',
        '可以採用此路線繼續開發計算核心，但不能宣布「1850–2149 全範圍原生排盤已通過 1 角秒一致性」。應先明確制定 UTC/UT1/TT、ΔT、恆星時與框架模型政策，使用獨立天文標準驗證，然後重跑相同門檻。', '',
        '尚未涵蓋：恆星黃道與 ayanamsa、凱龍／小行星、恆星、地表視差、事件根求解、完整相位解讀、所有宮制、超出 DE440s 的年代、所有作業系統／打包、更新配送。平均／真交點只作探索性數值比較。沒有 UI，也沒有建立自動更新機制。', '',
        '## 結果檔', '',
        '- [驗收與統計](results/summary.json)',
        '- [核心原始輸出](results/core.json)／[參考原始輸出](results/reference.json)',
        '- [行星差異 CSV](results/planet-differences.csv)／[宮位差異 CSV](results/house-differences.csv)',
        '- [依賴與來源檢查](results/dependency-audit.json)',
        '- [診斷摘要](results/diagnostic-summary.json)／[整合契約](results/core-contracts.json)',
        '- [上游 provenance 結構檢查](results/upstream-provenance-structure.txt)', '',
    ]
    (ROOT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('REPORT.md generated from current raw results')

if __name__=='__main__': main()
