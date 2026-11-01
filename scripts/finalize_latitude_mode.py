# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Publish the bounded audit, detailed differences, and final evidence hashes."""
import csv,html,json,shutil,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from latitude_mode_audit import OUT,read,write,sha

summary=read(OUT/'summary.json');protected=read(OUT/'protected-before.json')
bad=[p for p,h in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
assert not bad,bad
with (OUT/'affected-planets.csv').open(encoding='utf-8-sig',newline='') as f:changes=list(csv.DictReader(f))
assert len(changes)==2351 and summary['paint_mismatches']==0
core=read(OUT/'final/complete-on/environment.json')['core_sources']
assert all(sha(ROOT/p)==h for p,h in core.items())
for suite in ('complete','legacy'):
    for mode in ('on','off'):assert read(OUT/'final'/f'{suite}-{mode}/environment.json')['core_sources']==core
browser=read(OUT/'browser-checks.json');pdf=read(OUT/'pdf-checks.json');exports=read(OUT/'export-checks.json')
assert len(browser['checks'])==128 and not browser['external'] and not browser['errors']
assert len(pdf)==len(exports)==32
for name in ('desktop-tests.log','house-tests.log','latitude-tests-final.log','report-tests-final.log','azimuth-help-tests-final.log'):
    assert (OUT/name).read_text(encoding='utf-8').rstrip().endswith('OK'),name
write(OUT/'preservation.json',dict(files=len(protected),changes=bad))
write(OUT/'verification.json',dict(preserved_files=len(protected),protected_changes=bad,
    desktop_tests=118,house_tests=10,rendered_charts=6468,rendered_visible_points=129350,paint_mismatches=0,
    responsive_checks=128,pdf_files=32,pdf_pages=sum(p['pages'] for p in pdf),
    scope='Current source, Qt offscreen and offline Edge headless; released EXE/ZIP not rebuilt'))

report=['# 歸宮納入天體黃緯：實作與完整驗證','',
'日期：2026-10-31。版本為目前 v0.6.5 未發佈來源；LibEphemeris 3.2.2 未修改。原正式基準、Swiss 參考、既有 EXE／ZIP 保留。',
'','## 行為與資料保存','',
'「歸宮納入天體黃緯」位於分宮制下方，預設開啟，隨個人檔案儲存。舊個人檔案缺少欄位時採開啟，不自動改寫個人資料庫。切換是計算條件變更：標示舊結果、停用匯出，重排後同步更新。',
'','- 開啟：將真實黃緯傳入正式 `house_number2 → house_pos`，保留 H 對齊補丁及軸點政策。',
'- 關閉：只將這條歸宮路徑的黃緯設為零；`points`／`all_points` 的原始黃緯及黃經不變。',
'- 開啟的內圈為宮位位置示意：將有效連續宮位座標的小數比例，線性映射到相應宮頭扇區，支援正向與反向。外緣空心點標真實黃經；原 ASC／MC 軸線仍依真實黃經。這不是等角天球投影，不能從內圈位置反讀星座度數。',
'- 關閉使用黃經輪盤。相位成員、數值及排序維持原黃經計算；圖面相位線表示關係，角度讀表格。兩種圖面都標出模式，使用者不必猜。',
'- Koch 未定義的點不分配內圈宮位，只畫外緣黃經標記與問號；圖面與表格、匯出一起解釋。',
'','## 完整重跑結果','',
'每種模式都實際計算完全 2016 例與舊 1287 例，並非只讀既有結果換標籤。使用 12 個獨立程序，保留原始 API 回傳、有效宮位座標、參數、每例與每輪耗時及依賴指紋。',
'','|樣本|每模式結果|切換受影響星盤|天體宮號／定義狀態變更|有效宮號換宮|Koch 未定義→可定義|',
'|---|---|---:|---:|---:|---:|',
'|完全 2016 例|1987 星盤成功、29 原有拒絕|714|1397|1340|57|',
'|舊 1287 例|1277 ok、10 預期錯誤|502|954|922|32|',
'','舊 1277 ok 包含 1247 完整星盤及 30 個 helper；10 個預期錯誤是 8 UserError、1 AmbiguousTimeError、1 ValueError。不能稱為 1287 張星盤。兩種模式均沒有新增拒絕。',
'','以上天體點包含五顆小行星。若僅計日月、水金火木土、天海冥，完全資料為 **463 點**、舊資料 **357 點**；其餘為小行星。ASC、MC、交點及幸運點沒有宮號變更。本批零黃緯模式沒有 Koch 未定義點；這不是修改 Koch 或承諾其他條件都可計算。',
'','[可搜尋逐筆清單](index.html) · [完整 CSV（2351 列）](affected-planets.csv) · [逐星盤統計](cases.csv)。每列包括案例、時間、時區、地理座標、天體、真實黃經／黃緯、開關兩模式的宮號與有效連續宮位座標。空白宮號代表未定義，`kind` 明確分類，不以宮頭角度門檻豁免差異。',
'','## 不變條件','',
'- 開啟相對前輪 Azimuth 補丁捕捉，3303 例原始結果在扣除新增 `input.house_latitude=true` 後逐值精確相同。此比較對象是修補後的前輪資料；不是聲稱與未修正原版 v0.6.5 全相同。',
'- 開關兩模式共 **64680 點真實黃經／黃緯、速度與逆行資訊** 精確不變；全部十二宮頭、ASC／MC 座標、時標、UTC、日夜判定與相位資料不變。座標最大差 **0 度／0 角秒**。',
'- **6468 個 ASC／MC 宮號配對全部相同**（完全 3974、舊 2494）。不是硬設 ASC=1 或 MC=10；兩模式保留既有正式計算結果。',
'- 所有原始零黃緯點的宮號不變。關閉後歸宮 audit 保留所用零黃緯，原始天體座標另存，沒有互相覆寫。',
'','## 按宮位制分類','',
'下表是變更點數，包含未定義變可定義；0 表示這兩批沒有觀察到宮號變更，並非對所有可能出生條件的定理。',
'','|宮位制|完全資料|舊資料|','|---|---:|---:|']
systems={'P':'Placidus','K':'Koch','C':'Campanus','R':'Regiomontanus','E':'Equal','V':'Vehlow','X':'Meridian','O':'Porphyry','B':'Alcabitius','U':'Krusinski','H':'Azimuth','M':'Morinus','T':'Polich–Page','W':'Whole Sign'}
for code,name in systems.items():report.append(f"|{name} ({code})|{summary['suites']['complete']['by_system'].get(code,0)}|{summary['suites']['legacy']['by_system'].get(code,0)}|")
report+=['','## 按天體分類','','|天體|完全資料|舊資料|','|---|---:|---:|']
for body in ('太陽','月亮','水星','金星','火星','木星','土星','天王星','海王星','冥王星','凱龍星','婚神星','智神星','灶神星','穀神星'):
    report.append(f"|{body}|{summary['suites']['complete']['by_body'].get(body,0)}|{summary['suites']['legacy']['by_body'].get(body,0)}|")
report+=['','## 圖面與匯出驗證','',
'逐張呼叫正式 `paint_wheel`，觀察 QPainter 實際畫出的宮頭線與定位小點，套用繪圖轉換後由座標反推扇區。兩模式共 **6468 張圖／129350 個可見定位點，0 個不一致**。未定義點確認只在外緣、沒有內圈宮位。舊資料有一張隱藏五顆小行星，兩模式共少 10 個可見點；數值比對仍涵蓋所有隱藏天體。',
'','宮頭附近以 1e-9 度的繪圖座標還原容差核對端點身分；這是渲染浮點還原，不是調整 house_pos 或角度驗收門檻。完整 traces 保留於 `paint-traces.jsonl.gz`。此步驗證呈現一致性，不能把使用歸宮結果畫圖，當成歸宮算法已獲獨立天文證明。先前 H 的獨立空間驗證仍保留。',
'','- 118 項桌面測試與 10 項正式歸宮測試通過；最後繪圖／列印微調後重驗黃緯、報表及相關說明測試。',
'- 8 類代表盤 × 兩模式 × 中英文，共 32 組；含 H 正／反向、C／R 反向、T ASC 邊界、Koch 未定義、Whole Sign、Placidus。桌面使用隔離資料庫；表格值與正式數值吻合，開關與過期結果處理通過。',
f"- Edge 離線 128 組寬度檢查（1400／800／480／320 px），無頁面錯誤、外部請求及橫向溢出。32 份 A4 橫向 PDF 共 **{sum(p['pages'] for p in pdf)} 頁**，逐頁檢查頁碼及表格完整性，提示均留在星盤頁。一般盤 5 頁，H 另含說明附錄。",
'- 實際目視檢查全部 32 份 PDF 的星盤頁，以及代表性的完整文件／未定義盤／反向盤／表格／窄桌面。最終轉圖位於 `exports/pdf-pages-final/`；早期 `pdf-pages/` 不是最終驗收版。',
'','## 原始耗時','',
'下列為工具記錄的每輪 wall time，含程序池計算、寫出及結尾環境驗證；每例原始秒數在各 `results.jsonl.gz`。不把此值換算成未量測的速度或成本。',
'','|樣本|模式|程序|秒|','|---|---|---:|---:|']
for suite in ('complete','legacy'):
    for mode in ('on','off'):
        s=read(OUT/'final'/f'{suite}-{mode}/summary.json');report.append(f"|{suite}|{mode}|12|{s['elapsed_seconds']}|")
report+=['','## 保存、執行與限制','',
f'- {len(protected)} 個受保護檔案的 SHA-256 完全未變，包含原基準、Swiss 對照、LibEphemeris 來源／安裝檔、固定測試資料及封裝保留項。`preservation.json` 列出核對結果。',
'- `final/complete-on`、`final/complete-off`、`final/legacy-on`、`final/legacy-off` 是本次有效捕捉；不是新正式基準。`source-before/` 保存修改前應用檔，`source-final/` 保存最後繪圖與匯出來源。數值捕捉之後只調整呈現、說明及驗收工具，數值核心未再更改。',
'- 根目錄的早期 `complete-off/` 是試跑；早期 `legacy-off/` 因來源指紋變更被防護拒絕，沒有成功 summary，均不列入驗收。所有正式捕捉的前後核心／依賴指紋一致，guard events 為空。',
'- 驗證限目前來源、Qt offscreen、Edge headless。既有 EXE／ZIP 未重新封裝；從來源啟動請用 `launch-desktop.ps1`。APP_VERSION 仍為 0.6.5。沒有修改個人資料庫，也沒有修改 T 鄰域多解或 Koch 算法。',
'- 重跑腳本：`scripts/latitude_mode_audit.py`（固定輸入、12 程序；拒絕覆寫已有捕捉）、`scripts/audit_latitude_results.py`（逐點及實際繪圖核對）、`scripts/check_latitude_exports.py`、`scripts/check_latitude_browser.cjs`、`scripts/check_latitude_pdf.py`。再次捕捉應先指定新的輸出目錄，不能刪掉舊結果或覆寫原基準。',
'']
(OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')

esc=lambda v:html.escape(str(v),quote=True)
parts=['<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>黃緯歸宮：逐筆差異</title>',
'<style>body{font-family:system-ui,sans-serif;margin:24px;color:#342c27;background:#faf7f1}h1{font-size:25px}input,select{font:inherit;padding:8px;margin:4px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #ddd;padding:9px;text-align:left}thead{position:sticky;top:0;background:#eee5d7}.scroll{overflow:auto}a{color:#864c2e}</style>',
'<h1>歸宮納入天體黃緯：逐筆差異</h1><p>完全資料 714 張／1397 點；舊資料 502 張／954 點。包含小行星及 Koch 未定義轉可定義。黃經、宮頭、ASC／MC 宮號均不變。</p>',
'<p><a href="REPORT.md">完整報告</a> · <a href="affected-planets.csv">下載完整 CSV</a></p><label>樣本 <select id="suite"><option value="">全部</option><option>complete</option><option>legacy</option></select></label><label>搜尋 <input id="search" placeholder="案例、天體、宮位制或日期"></label><p id="count"></p>',
'<div class="scroll"><table id="changes"><thead><tr><th>樣本／案例</th><th>宮制</th><th>當地時間</th><th>天體</th><th>真實黃緯</th><th>開啟：宮號</th><th>關閉：宮號</th></tr></thead><tbody>']
representatives={r['case'] for r in exports}
for r in changes:
    case=esc(r['case']);detail=(f'<a href="exports/{case}-on-zh-TW.html">{case}</a>' if r['case'] in representatives else case)
    parts.append(f'<tr data-suite="{r["suite"]}"><td>{r["suite"]}<br>{detail}</td><td>{esc(systems[r["system"]])}</td><td>{esc(r["local_time"])}</td><td>{esc(r["body"])}</td><td>{float(r["latitude"]):.8f}°</td><td>{esc(r["house_on"] or "未定義")}</td><td>{esc(r["house_off"] or "未定義")}</td></tr>')
parts+=['</tbody></table></div><script>const rows=[...document.querySelectorAll("tbody tr")],s=document.querySelector("#suite"),q=document.querySelector("#search");function filter(){let n=0;for(const r of rows){r.hidden=!!((s.value&&r.dataset.suite!==s.value)||!r.textContent.toLowerCase().includes(q.value.toLowerCase()));if(!r.hidden)n++}document.querySelector("#count").textContent=`顯示 ${n} / ${rows.length} 筆`}s.onchange=filter;q.oninput=filter;filter();</script></html>']
(OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8')

for top in ('desktop','scripts','translations','templates/report','docs','tests'):
    for p in (ROOT/top).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            dest=OUT/'source-final'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
write(OUT/'EVIDENCE-SHA256.json',{p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*'))
    if p.is_file() and p.name!='EVIDENCE-SHA256.json' and '__pycache__' not in p.parts})
print('Report, searchable differences, source snapshot and evidence hashes written.')
