# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Generate the human report from measured results, never hand-enter measurements."""
from common import ROOT, read, sha

def main():
    folder=ROOT/'results/observations'
    s=read(folder/'summary.json'); core=read(folder/'core.json'); ref=read(folder/'reference.json')
    for name,digest in s['hashes'].items():
        if sha(folder/name)!=digest: raise ValueError('Stale summary: '+name)
    def group(body,quality='unflagged',mode='iau1976_1980'):
        return next(g for g in s['groups'] if (g['body'],g['quality'],g['mode'])==(body,quality,mode))
    names={'Uranus':'天王星','Neptune':'海王星','Pluto':'冥王星（探索性）'}
    lines=['# 1991 年實測觀測比對：CMC1–11 × LibEphemeris × Swiss Ephemeris','',
        '這輪已使用望遠鏡觀測所得的公開位置資料，而非第三套計算星曆。結果是：兩套引擎與觀測的典型差距約 0.2～0.3 角秒；這批資料無法分辨哪套引擎具有更高的絕對精度。', '',
        '## 資料與樣本','',
        '資料為 CDS I/256，Carlsberg Meridian Catalogues 1–11（1999），望遠鏡位於西班牙 La Palma，合作機構包括 Royal Greenwich Observatory。此官方彙整版取代 I/205（CMC7）；不是直接使用舊 CMC7 檔案。早期觀測已依 Hipparcos 重新校正至 ICRF，仍以 IAU 1976 體系的當日地心視赤經／赤緯刊載。', '',
        f"完整 planet.dat 有 {s['catalogue_records']:,} 筆，1991 年所有天體共 {s['all_objects_1991']:,} 筆。本次選取天王星、海王星、冥王星，共 {s['selected']} 筆，全部計算；{s['selected_flagged']} 筆原始 `*` 品質標記另列，主表使用其餘 279 筆。沒有按殘差大小剔除觀測。赤經缺值 {s['selected_missing_ra']} 筆，赤緯缺值 {s['selected_missing_dec']} 筆。", '',
        '原始 `*` 代表內部誤差超過 0.75 角秒；它不代表這次觀測減計算的差必然超過 0.75 角秒。來源文件更細述該標記範圍為大於 0.75、小於 1.15 角秒。', '',
        '| 天體 | 原始筆數 | 無品質警示 | 觀測日期（TT） |', '|---|---:|---:|---|']
    for b in names:
        c=s['coverage'][b]
        lines.append(f"| {names[b]} | {group(b,'all')['records']} | {group(b)['records']} | {c['first_tt']}～{c['last_tt']} |")
    lines += ['', '選取範圍是完整 1991 年，但只有當年實際收錄的觀測，並非每天都有，也不是全年均勻抽樣。木星、土星主要對應衛星觀測，沒有把衛星當行星；本次沒有測試其餘七個主要天體或宮位。', '',
        '## 對齊與指標','',
        '1. 直接讀取觀測欄位 JD(TT)，選取 `2448257.5 <= JD(TT) < 2448622.5`。不把它當 UTC，也不再走 UT1→TT。',
        '2. 各引擎使用 `calc(TT, body, SWIEPH | EQUATORIAL | J2000 | NONUT)` 輸出地心視位置的平赤道／平春分點 J2000 表示。保留光行時、光行差與引力偏折；不使用 TRUEPOS、NOABERR、NOGDEFL 或 TOPOCTR。',
        '3. 用同一個 ERFA `pnm80`（IAU 1976 歲差、1980 章動）轉至當日真赤道／真春分點。這是依文件進行的名義座標對齊，不是重演當年每晚完整歸算，亦未加入依殘差擬合的修正量。',
        '4. 保存各引擎原生當日視赤經／赤緯作為模型敏感度對照。新舊模型的差不可當作觀測誤差，也不可因某一模型較貼近這批觀測，就宣稱它比較真實。',
        '5. 表中角距是球面上兩位置的最短角距，以向量 cross/dot 的 atan2 計算。另保存有正負號的「觀測－計算」赤經差乘 cos(赤緯)、赤緯差。RA 的時間秒乘 15 才是赤道上的角秒。', '',
        '中位數表示一半紀錄的差距低於此值；P95 表示至少 95% 低於此值；RMS 為差距平方平均後開根號，較受大差距影響。全部單位為角秒，均未減去平均偏移。', '',
        '## 主要結果：無品質警示、共同 IAU 1976/1980 表示','',
        '| 天體 | 引擎 | 中位數 | RMS | P95 | 最大角距 |', '|---|---|---:|---:|---:|---:|']
    for b in names:
        g=group(b)
        for e,label in [('core','LibEphemeris'),('reference','Swiss')]:
            v=g[e]['separation_arcsec']
            lines.append(f"| {names[b]} | {label} | {v['median']:.6f} | {v['rms']:.6f} | {v['p95']:.6f} | {v['max']:.6f} |")
    lines += ['', '小數多位是為重現計算，不代表觀測具有該位數的精度。', '',
        '| 天體 | 兩引擎彼此最大角距 | Lib 平均赤經差 × cosδ | Lib 平均赤緯差 |', '|---|---:|---:|---:|']
    for b in names:
        g=group(b)
        lines.append(f"| {names[b]} | {g['inter_engine']['max']:.6f} | {g['core']['oc_ra_cosdec_arcsec']['mean']:+.6f} | {g['core']['oc_dec_arcsec']['mean']:+.6f} |")
    lines += ['', '天王星的平均赤緯偏移約 +0.12 角秒，因此不能把所有殘差都稱為零均值的隨機雜訊；本輪沒有估計它有多少來自觀測歸算、參考框架、目標中心定義或星曆。', '',
        '## 品質標記與座標模型對照','', '| 天體 | 品質標記筆數 | 保留全部資料的 Lib RMS | 原生當日模型 Lib RMS（無警示） | 原生與共同舊模型最大角距 |', '|---|---:|---:|---:|---:|']
    for b in names:
        g=group(b); allg=group(b,'all'); native=group(b,mode='native')
        lines.append(f"| {names[b]} | {group(b,'flagged')['records']} | {allg['core']['separation_arcsec']['rms']:.6f} | {native['core']['separation_arcsec']['rms']:.6f} | {g['core']['frame_change_arcsec']['max']:.6f} |")
    lines += ['', '兩種座標處理的差距在本樣本約 0.02～0.04 角秒；沒有改變「兩引擎與觀測的差距遠大於彼此差距」的結論。這個對照不是完整的座標誤差上限，也不能保證原始觀測歸算已被完全重建。', '',
        '## 可以與不可以推論的事','',
        '- 這是現有核心配置的外部觀測相容性檢查。兩套計算在這三個目標／1991 年的結果非常接近；這批觀測不足以裁定孰優，也不能把觀測殘差直接視為引擎的絕對誤差。',
        '- 重要的目標定義限制：本輪核心實際使用 DE440s 的系統重心，NAIF 7、8、9，未裝 planet-center SPK。觀測表描述經照明與視差校正的行星視位置；行星本體中心、整個系統重心與未解析雙星的光心不能直接視為相同。因此天王星、海王星結果仍含中心定義限制；冥王星尤其只能列為探索性，尚未處理 Pluto–Charon 中心／光心差。沒有宣稱完成本體中心的嚴格等價比對。',
        '- CMC 刊載的是校正過的望遠鏡觀測，不是無誤差真值。原始赤經以 0.001 時間秒、赤緯以 0.01 角秒刊載；僅這些欄位的量化就比兩引擎差距粗。TT 刊載至 0.000001 日，約 0.0864 秒。',
        '- 先前提到「約 0.1 角秒」不能當成每筆資料的固定誤差或合格線。官方說明區分多次平均的目錄位置與單次觀測；單次誤差隨天頂距與亮度改變，另外仍有系統性偏移。沒有使用假設 0.1 角秒的統一 sigma 進行顯著性檢定。',
        '- 兩引擎底層都是 JPL 系列星曆：本輪 Lib 用 DE440s，Swiss 參考檔為 DE441 系列。CMC 外行星觀測曾用於 DE405 的建立；本輪未逐筆查明其在 DE440/441 的使用情形。不能稱為完全獨立、從未參與星曆擬合的盲測。',
        '- 這次直接驗證 LibEphemeris 計算核心，不重新驗證 Kerykeion 高階出生資料輸入流程。宮頭是依時間、地點與宮制定義出的幾何位置，本觀測表沒有實測宮頭，不能用此結果替宮位背書。', '',
        '## 可重現執行與檔案','',
        '在已完成原有環境與星曆準備後：', '', '```powershell',
        '# 僅首次需要下載；既有檔案逐一校驗雜湊',
        r'.\.venv-core\Scripts\python.exe scripts\prepare_observations.py',
        '# 後續完全離線比對；會保存舊 results 到 history',
        r'.\run-observations.ps1', '```', '',
        '`observation-data-sources.lock.json` 保存來源 URL、壓縮檔與解壓檔 SHA-256。`results/observations/residuals.csv` 保留每筆來源行號、TT、日期、品質標記、實測與兩套計算的赤經赤緯及殘差。`summary.json` 保存各組統計與月份覆蓋。`core.json`／`reference.json` 保存原始輸出、旗標、套件版本、資料雜湊與執行秒數。', '',
        f"本次 core 計算 {core['elapsed_seconds']:.6f} 秒；reference {ref['elapsed_seconds']:.6f} 秒。這是各 worker 的原始牆鐘時間，並非正式效能競賽。核心 guard 自我測試 {core['guard_self_test']}；意外攔截 {len(core['unexpected_guard_events'])} 次，Swiss 安裝／載入均為空。guard 是 Python 層儀表，不是 OS 隔離保證。", '',
        '## 來源','',
        '- [CDS I/256 官方資料與說明](https://cdsarc.cds.unistra.fr/ftp/I/256/ReadMe)：欄位定義、替代目錄、記錄數。',
        '- [官方完整歸算說明（LaTeX 壓縮檔）](https://cdsarc.cds.unistra.fr/ftp/I/256/intcmc11.tex.gz)：ICRF 重校、照明與視差處理、單次觀測誤差、資料格式。已保存解壓原文至 data/observations/intcmc11.tex。',
        '- [官方觀測表](https://cdsarc.cds.unistra.fr/ftp/I/256/planet.dat.gz)。',
        '- [Morrison & Evans 1998](https://people.ast.cam.ac.uk/~dwe/papers/me1998.pdf)：CMC 觀測的系統誤差，以及它與 DE405 擬合資料的關係；不據此宣稱 DE440/441 的實際精度。',
        '- ERFA 2.0.1.5 本地 `pnm80` 文件：輸入平赤道 J2000 向量，輸出 IAU 1976/1980 當日真赤道向量。', '']
    (ROOT/'OBSERVATIONS_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Wrote OBSERVATIONS_REPORT.md')

if __name__=='__main__': main()
