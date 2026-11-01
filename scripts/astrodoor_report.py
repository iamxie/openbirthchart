# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Generate a numeric-only comparison report after all 100 public cases exist."""
import collections, csv, datetime as dt, hashlib, json, math, statistics
from astrodoor_compare import ROOT, OUT, MAJOR, MINOR, save, analyze

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def delta(a,b):return ((a-b+180)%360-180)*3600
def stats(v):
    return dict(n=len(v),mean=statistics.mean(v),median=statistics.median(v),std_population=statistics.pstdev(v),max=max(v))

def main():
    analyze(); summary=read(OUT/'summary.json');cases=read(OUT/'cases.json')
    if summary['completed_cases']!=100: raise RuntimeError('Final report requires all 100 cases')
    assert len({c['local'] for c in cases})==100
    assert all(1950<=int(c['local'][:4])<=2020 and dt.datetime.fromisoformat(c['local']).second==0 for c in cases)
    for name, expected in read(OUT/'source-hashes.json').items():
        path=(OUT/'cases.json') if name=='cases.json' else ROOT/name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected, f'Changed input: {name}'
    geometries=[]; sign_mismatches=[]; requests=[]; audits=[]
    for case in cases:
        ident=case['id']; site=read(OUT/'parsed'/f'{ident}.json'); geo=read(OUT/'geometric'/f'{ident}.json')
        local=read(OUT/'local'/f'{ident}.json'); own={p['name']:p for p in local['points']}
        raw=OUT/'raw'/f'{ident}.html';meta=read(raw.with_suffix('.json'))
        assert meta['status']==200 and meta['curl_returncode']==0
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==meta['sha256']
        requests.append(meta)
        for point in geo['points']:
            name=point['name']
            if name not in MAJOR+MINOR:continue
            d=delta(point['lon'],site['points'][name]['lon'])
            geometries.append(dict(case_id=ident,local=case['local'],name=name,group='major' if name in MAJOR else 'minor',
                signed_arcsec=d,abs_arcsec=abs(d),floor_match=0<=d<60,interval_excess_arcsec=max(0,-d,d-60)))
            if int(own[name]['lon']//30)!=int(site['points'][name]['lon']//30):
                sign_mismatches.append(dict(case_id=ident,name=name,desktop_deg=own[name]['lon'],website=site['points'][name]['displayed']))
        for n,lon in enumerate(geo['clock_as_ut1_cusps'],1):
            d=delta(lon,site['cusps'][str(n)]['lon'])
            geometries.append(dict(case_id=ident,local=case['local'],name=f'第{n}宮',group='cusp',signed_arcsec=d,
                abs_arcsec=abs(d),floor_match=0<=d<60,interval_excess_arcsec=max(0,-d,d-60)))
        audits.append(dict(case_id=ident,local=case['local'],utc=case['utc'],dst_minutes=case['dst_minutes'],
            raw_sha256=meta['sha256'],local_sha256=hashlib.sha256((OUT/'local'/f'{ident}.json').read_bytes()).hexdigest()))
    gaps=[(dt.datetime.fromisoformat(b['started_utc'])-dt.datetime.fromisoformat(a['completed_utc'])).total_seconds() for a,b in zip(requests,requests[1:])]
    assert min(gaps)>=11.95
    controls={g:dict(n=len([r for r in geometries if r['group']==g]),
        floor_matches=sum(r['floor_match'] for r in geometries if r['group']==g),
        max_interval_excess_arcsec=max(r['interval_excess_arcsec'] for r in geometries if r['group']==g)) for g in ('major','minor','cusp')}
    outliers=[r for r in geometries if not r['floor_match']]
    duration=(dt.datetime.fromisoformat(requests[-1]['completed_utc'])-dt.datetime.fromisoformat(requests[0]['started_utc'])).total_seconds()
    runtime=read(OUT/'runtime.json');assert not runtime['swisseph_loaded'] and not runtime['events']
    geometric_runtime=read(OUT/'geometry-runtime.json');assert not geometric_runtime['swisseph_loaded'] and not geometric_runtime['events']
    save(OUT/'audit.json',dict(cases=audits,min_gap_seconds=min(gaps),max_gap_seconds=max(gaps),elapsed_seconds=duration,
        submitted_chart_requests=len(requests),raw_hashes_verified=True,source_hashes_verified=True,
        source_changes='Product source and packaged application unchanged'))
    save(OUT/'control-summary.json',dict(groups=controls,rows=geometries,outside_intervals=outliers,sign_mismatches=sign_mismatches))
    with (OUT/'controls.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(geometries[0]));w.writeheader();w.writerows(geometries)
    names={'major':'十個主要天體','minor':'五個小行星／凱龍星','cusp':'十二宮宮頭','derived':'南北交點與幸運點'}
    table=['| 比較項目 | 筆數 | 平均絕對差 | 中位數 | 標準差 | 最大絕對差 |','|---|---:|---:|---:|---:|---:|']
    for g in names:
        s=summary['groups'][g];table.append(f"| {names[g]} | {s['n']} | {s['mean']:.3f}″ | {s['median']:.3f}″ | {s['std_population']:.3f}″ | {s['max']:.3f}″ |")
    controls_table=['| 離線診斷 | 相同角分顯示 | 超出角分區間的最大距離 |','|---|---:|---:|']
    for g in controls:
        s=controls[g];controls_table.append(f"| {names[g]} | {s['floor_matches']} / {s['n']} | {s['max_interval_excess_arcsec']:.3f}″ |")
    point_table=['| 天體 | 平均絕對差 | 中位數 | 標準差 | 最大絕對差 |','|---|---:|---:|---:|---:|']
    for name in MAJOR+MINOR:
        s=summary['by_point'][name];point_table.append(f"| {name} | {s['mean']:.3f}″ | {s['median']:.3f}″ | {s['std_population']:.3f}″ | {s['max']:.3f}″ |")
    maxes=[]
    with (OUT/'differences.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    for g in names:
        r=max((r for r in rows if r['group']==g),key=lambda r:float(r['abs_arcsec']))
        maxes.append(f"- {names[g]}：{r['local'].replace('T',' ')}，{r['name']}。網站 {r['website_display']}；本程式黃經 {float(r['desktop_deg']):.9f}°；絕對差 {float(r['abs_arcsec']):.3f}″。")
    house_physical=sum(summary['groups'][g]['house_mismatches'] for g in ('major','minor'))
    retro=sum(summary['groups'][g]['retrograde_mismatches'] for g in ('major','minor'))
    retro_lines=[]
    for r in summary['retrograde_mismatches']:
        chart=read(OUT/'local'/(r['case_id']+'.json'))
        point=next(p for p in chart['points'] if p['name']==r['name'])
        retro_lines.append(f"- {r['local'].replace('T',' ')}（台灣時間），{r['name']}：網站 {'逆行' if r['website_retrograde'] else '順行'}；本程式 {'逆行' if r['desktop_retrograde'] else '順行'}；本程式瞬時黃經速度 {point['speed']*3600:+.6f}″／日，位置絕對差 {r['abs_arcsec']:.3f}″。")
    if any(r['case_id']=='061' for r in summary['retrograde_mismatches']):
        station=read(OUT/'station-diagnostic.json');now=next(r for r in station['rows'] if r['offset_days']==0)
        fd=read(OUT/'station-finite-difference.json')
        retro_lines += ['',
            f"這筆冥王星正接近由逆轉順的『留』。獨立 Swiss 參考計算也得到正速度：視位置 {now['apparent']['speed_arcsec_day']:+.6f}″／日、幾何位置 {now['geometric']['speed_arcsec_day']:+.6f}″／日；LibEphemeris 前後各一小時位置差分為 {fd['speed_deg_day']*3600:+.6f}″／日，都支持順行。前一天仍是逆行。",
            '',
            '這個網站標記差異不能單靠「截去角秒」解釋。網站如何判定接近留的順逆行，現有公開輸出不足以確定，因此列為真正的相容性差異；沒有為了配合網站而修改本程式的瞬時速度判定。詳細數值見 `station-diagnostic.json`、`station-finite-difference.json`。']
    lines=[
        '# Astrodoor 與桌面版 0.1.0：100 筆相容性比較',
        '',
        f"實測 100 組出生時間、1,500 個實體天體位置、1,200 個宮頭。天體落宮不一致 {house_physical} / 1500；天體星座不一致 {len(sign_mismatches)} / 1500；順逆行不一致 {retro} / 1500。",
        '',
        '## 直接拿網站顯示值和目前程式相比',
        '',
        '以下都是「絕對值差異」，單位為角秒；標準差採母體標準差。公式是最短圓周角差的絕對值，跨越 0° 時不會錯算成近 360°。網站只列到角分，1′ = 60″，因此這張表包含網站省略秒數的效果，不能當作對真實天空的誤差。',
        '',*table,'',
        '## 差異從哪裡來',
        '',
        '1. **行星位置的定義不同。** 原版採地心視位置，包含光行時、光行差等修正。離線把 LibEphemeris 設為 `FLG_TRUEPOS`（幾何位置）後，與網站的角分顯示高度吻合。這是數值實驗支持的推論，沒有取得網站後端程式或版本，不能宣稱已證明它的內部實作。',
        '2. **網站顯示看起來是截去秒數。** 例如 12°34′59″ 顯示成 12°34′，單靠顯示就會相差 59″。因此「平均差約半個角分」不等於計算平均錯了半個角分。此規則由幾何位置與宮頭的多筆匹配推得。',
        '3. **宮頭的時間慣例不同。** 原版保留 UTC → UT1 的修正。診斷時只把換算後的 UTC/GMT 鐘點當成 UT1，保持地點、宮制與 TT 不變，宮頭與網站更吻合。這同樣是實驗推論；不能據此判定哪一方網站內部採何種時間資料。',
        '',
        '下表使用同一套 LibEphemeris 做上述離線控制。這不是改過的產品，也沒有對網站多發查詢。假設網站截去秒數，顯示 X′ 代表的完整值可能在 [X′, X′+60″) 內；「超出區間距離」是無法由截位解釋的最小差距，不是完整誤差的估計。',
        '',*controls_table,'',
        f"角分邊界外的診斷列共 {len(outliers)} 筆，逐筆資料見 `results/astrodoor/control-summary.json` 的 `outside_intervals`。",
        '',
        '## 順逆行標記差異','',*(retro_lines or ['本次沒有順逆行標記差異。']),'',
        '## 最大差值的具體案例','',*maxes,'',
        '## 各天體原版差值','',*point_table,'',
        '## 測試範圍與取得方式','',
        '- 對照來源：[占星之門公開排盤表單](https://astrodoor.cc/horoscope.jsp)。只提交正常公開表單；沒有登入、繞過驗證或存取私人資料。',
        '- 固定亂數種子 20261026，在 1950-01-01 至 2020-12-31 的所有當地分鐘均勻抽樣 100 筆、不重複；抽樣在送出第一筆前完成，所有秒數皆為 00。沒有按結果挑選或剔除樣本。',
        f"- 實際抽到的最早與最晚時間：{cases[0]['local']}、{cases[-1]['local']}。本次沒有要求每年必有樣本。",
        '- 固定台南東經 120°12′、北緯 23°00′、Placidus。這是固定地點的年代抽樣，不代表已驗證全球緯度、所有時區或其他宮制。',
        f"- 網站填標準 GMT+8，依程式綁定的 tzdata 歷史規則勾選夏令時間；100 筆中 {sum(c['dst_minutes']>0 for c in cases)} 筆使用 GMT+9。每筆核對網站回傳的日期、時間、經緯度、時區、夏令勾選、宮制及小行星開關。",
        '- 包含太陽、月亮、水星至冥王星，加凱龍星、婚神星、智神星、灶神星、穀神星；另列南北交點、幸運點。ASC、DES、MC、IC 與第 1、7、10、4 宮頭交叉檢查。未比較解讀文、相位容許度、法達或網站其他附加功能。',
        f"- 完成 100 次星盤提交，串行、沒有重試；每次回應後至少休息 12 秒。紀錄中的最短間隔 {min(gaps):.3f} 秒，第一筆到最後一筆共 {duration/60:.2f} 分鐘（包括中途離線檢查）。沒有下載圖檔、廣告或額外解讀頁面。",
        '- 保存原始 HTML、提交欄位、HTTP 回應、時間戳、SHA-256；所有 100 個原始回應雜湊已複核。原始頁面只供本機稽核，報告僅摘出數值。',
        '- 原版及幾何控制計算均在阻擋 Swiss 載入與 Python 網路連線的 guard 下執行；兩者無違規事件。Swiss 只在另一個 `.venv-reference` 程序做原因診斷，不是產品或資料收集的依賴。',
        '- 沒有修改桌面程式計算預設、沒有替換原先的 0.1.0 執行檔。與網站相同不等於已證明絕對天文精度；網站也不是實測觀測資料。',
        '',
        '## 如何重跑','',
        '在專案根目錄執行（既有網站回應會重用，不重複提交）：','',
        '```powershell',
        '.\\.venv-desktop\\Scripts\\python.exe scripts\\astrodoor_compare.py prepare',
        '.\\.venv-desktop\\Scripts\\python.exe scripts\\astrodoor_compare.py local',
        '.\\.venv-desktop\\Scripts\\python.exe scripts\\astrodoor_compare.py collect --limit 100',
        '.\\.venv-desktop\\Scripts\\python.exe scripts\\astrodoor_geometry.py',
        '.\\.venv-desktop\\Scripts\\python.exe scripts\\astrodoor_motion.py',
        '.\\.venv-reference\\Scripts\\python.exe scripts\\astrodoor_diagnose.py',
        '.\\.venv-desktop\\Scripts\\python.exe scripts\\astrodoor_report.py',
        '.\\.venv-desktop\\Scripts\\python.exe -m unittest discover -s tests -p test_astrodoor.py -v',
        '```','',
        '網站失敗、限流、驗證頁、缺欄位或回傳設定不符時停止；不自動重試。每筆數值與差異見 `results/astrodoor/differences.csv`，控制比較見 `controls.csv`，完整摘要見 `summary.json`。',
    ]
    (ROOT/'ASTRODOOR_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(controls=controls,sign_mismatches=sign_mismatches,min_gap_seconds=min(gaps),elapsed_minutes=duration/60),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
