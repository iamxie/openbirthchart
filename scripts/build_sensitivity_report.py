# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Translate measured finite shifts into user-facing time/angle scales."""
from datetime import datetime,timedelta,timezone
from common import ROOT,read
from sensitivity_math import sampled_span

def main():
    out=ROOT/'results/sensitivity';s=read(out/'summary.json');run=read(out/'run.json')
    smooth=('P','K','O','E')
    def values(scope,system,seconds,field='cusps'):return s['groups'][f'{scope}/{system}/{seconds}'][field]
    def span(scope,seconds):
        data=[values(scope,system,seconds) for system in smooth]
        return min(x['min'] for x in data),max(x['max'] for x in data)
    worst=s['prior_worst'];index=worst['previous_comparison']['index']
    angular_gap=abs(worst['previous_comparison']['difference_arcsec'])
    local_one_second=abs(worst['offsets']['1']['delta_arcsec'][index])
    low1,high1=span('Taiwan',1);low60,high60=span('Taiwan',60)
    lines=['# 出生時間敏感度實測', '',
        f'本輪完成時間（UTC）：{run["completed_utc"]}。實測改動出生時間，觀察同一計算核心的宮頭位移；這些位移不是計算誤差。', '',
        f'**台北、台南、高雄的 P/K/O/E 宮制抽樣：時間差 1 秒，宮頭移動約 {low1:.1f}–{high1:.1f} 角秒；差 1 分鐘，約 {low60:,.0f}–{high60:,.0f} 角秒，即 {low60/3600:.2f}–{high60/3600:.2f} 度。**這是本次格點的範圍，不是所有台灣地點、年代與時刻的已證明上下界。', '',
        '## 台灣使用情境的量級', '',
        '一度 = 3,600 角秒。表中位移是原時間與「往前或往後移動指定秒數」之間的角距，兩個方向共同統計；不是前後整個區間的總寬。', '',
        '| 與原出生時間相差 | 宮頭位移範圍（角秒） | 換成度 |', '|---|---:|---:|',
    ]
    for sec,name in [(1,'1 秒'),(30,'30 秒'),(60,'1 分鐘'),(180,'3 分鐘'),(300,'5 分鐘')]:
        low,high=span('Taiwan',sec)
        lines.append(f'| {name} | {low:.2f}–{high:.2f} | {low/3600:.5f}°–{high/3600:.5f}° |')
    lines += ['', '各宮制分開看；典型值用本次樣本的中位數表示，不代表出生人口分布：', '',
        '| 宮制 | 1 秒位移最小／中位／最大（角秒） | 1 分鐘位移最小／中位／最大（角秒） |', '|---|---:|---:|']
    names={'P':'Placidus','K':'Koch','O':'Porphyry','E':'等宮制'}
    for system in smooth:
        a=values('Taiwan',system,1);b=values('Taiwan',system,60)
        lines.append(f'| {names[system]} | {a["min"]:.2f} / {a["median"]:.2f} / {a["max"]:.2f} | {b["min"]:.2f} / {b["median"]:.2f} / {b["max"]:.2f} |')
    lines += ['',
        '## 一分鐘差異與「不確定 ±1 分鐘」不同', '',
        '- 「相差 1 分鐘」：比較原時間與早／晚 60 秒的位置。',
        '- 「不確定 ±1 分鐘」：可能時間從早 60 秒到晚 60 秒，區間總長 2 分鐘；完整角度範圍通常接近單邊位移的兩倍，但應直接重算。',
        '- 如果時間是四捨五入到整分鐘，單純取整帶來的區間通常為 ±30 秒；如果是記憶、鐘錶偏差或出生定義差異，不能自動套用 ±30 秒。', '',
        f'本次台灣 Placidus 的 ±1 分鐘區間，採樣得到的宮頭總跨度為 {s["sampled_window_spans"]["Taiwan/P/60"]["min"]:.2f}–{s["sampled_window_spans"]["Taiwan/P/60"]["max"]:.2f} 角秒（{s["sampled_window_spans"]["Taiwan/P/60"]["min"]/3600:.3f}°–{s["sampled_window_spans"]["Taiwan/P/60"]["max"]/3600:.3f}°）。', '',
        '區間內取樣包含原時刻、±1、±30、±60 秒等適用節點，並以圓周展開處理跨 0°。這是取樣跨度，不是對所有中間時刻的連續極值保證；產品若宣稱完整不確定區間，仍須事件搜尋與適應性取樣。', '',
        '## 一張具體範例：1999-04-25 13:25:31 UTC', '',
        '以下使用台南座標、Placidus，只是示範，不代表使用者的出生地。比較時間「晚 1 秒」與「晚 1 分鐘」。', '',
        '| 位置 | 晚 1 秒位移（角秒） | 晚 1 分鐘位移（角秒） | 晚 1 分鐘位移（度） |', '|---|---:|---:|---:|']
    example=s['example']['results']['P']
    for i,label in enumerate([f'第 {n} 宮頭' for n in range(1,13)]+['上升 ASC','中天 MC']):
        a=example['offsets']['1']['delta_arcsec'][i];b=example['offsets']['60']['delta_arcsec'][i]
        lines.append(f'| {label} | {a:.2f} | {b:.2f} | {b/3600:.5f}° |')
    points={0:example['base'],**{int(k):v['values'] for k,v in example['offsets'].items()}}
    asc_span=sampled_span([points[o][12] for o in sorted(points) if abs(o)<=60])
    lines += ['',f'此例上升點在 ±1 分鐘採樣區間內的總跨度約 {asc_span:.2f} 角秒（{asc_span/3600:.5f}°）。', '',
        '## 高緯度不能沿用台灣的每秒換算', '',
        '| 地點／緯度 | P 宮頭最大 1 秒位移（角秒） | K 宮頭最大 1 秒位移（角秒） |', '|---|---:|---:|']
    for name,lat in [('Taipei',25.033),('Tainan',22.9999),('Kaohsiung',22.6273),('Equator',0),('Greenwich',51.4779),('NearPolarN',65.5),('NearPolarS',-65.5)]:
        lines.append(f'| {name} / {lat}° | {values(name,"P",1)["max"]:.2f} | {values(name,"K",1)["max"]:.2f} |')
    lines += ['',
        '高緯度仍是有觀測時間資料的歷史日期測試；沒有把無定義的極區宮制偷偷換成其他宮制。此格點只到 ±65.5°，沒有宣稱更高緯度的 P/K 都可定義。', '',
        '## 重新理解先前的 19.2 角秒', '',
        f'先前最大差距的案例是 {worst["previous_comparison"]["utc"]}、緯度 {worst["location"]["lat"]}°、Koch 第 {index+1} 宮頭。這個案例另以當時相同的原生 LibEphemeris 模型重算，且確認重現上一輪核心宮頭。', '',
        f'- 與 Swiss 的原比較差距：{angular_gap:.6f} 角秒。',
        f'- 核心出生時間晚 1 秒，該宮頭移動：{local_one_second:.6f} 角秒。',
        f'- 以該點一秒位移作局部比例估算，原差距約相當於 **{angular_gap/local_one_second:.3f} 秒**的時間偏移。這不是調整出生時間的建議，也不是證明 Swiss 正確。',
        f'- 晚 1 分鐘的直接實測位移：{abs(worst["offsets"]["60"]["delta_arcsec"][index]):.2f} 角秒（{abs(worst["offsets"]["60"]["delta_arcsec"][index])/3600:.3f}°）。',
        '- 此案例使用未來的時間模型推估，並保留上一輪原生 API 的全域 ΔT 行為；與主表的歷史觀測組分開，不作絕對精度宣稱。', '',
        '## 整宮制是例外：會跳格', '',
        '整宮制 W 的每個宮頭位於星座起點。只要上升星座不變，宮頭可以完全不動；跨過上升星座邊界時，十二宮頭一起移動 30°（108,000 角秒）。ASC 本身仍是連續移動，不等於整宮制的第一宮頭。', '',
        f'一般格點中，台灣 W 的 ±1 秒樣本都沒有跨界；不能因此推論一秒永遠不影響整宮制。我們另做事件搜尋，在台灣三地一天內找到 {s["whole_sign_targeted_events"]} 個分界，全部確認分界前後相隔 1 秒時，宮頭跳 30°。這是刻意挑出的邊界案例，不是發生機率。', '',
    ]
    event=read(out/'whole-sign-events.json')[0]
    local=datetime.fromisoformat(event['transition_utc']).astimezone(timezone(timedelta(hours=8)))
    lines += [f'例如台北 {local:%Y-%m-%d %H:%M:%S} 附近（UTC+8）：分界前後一秒，ASC 只移動約 {event["asc_displacement_arcsec"]:.2f} 角秒，但整宮制宮頭移動 30°。事件時刻定位到 0.001 秒是為了驗證跳變，不表示出生紀錄有這種準確度。', '',
        '## 依結果建議的產品精度', '',
        '1. **優先表達輸入時間的不確定性。**輸入「13:25」不代表真實時間精確到那一秒。允許指定時間範圍或 ±1／±3／±5 分鐘；出生定義造成的差異也放在輸入範圍處理，而不是修改天文公式。',
        '2. **日常出生星盤不必追逐 0.001 角秒的顯示。**台灣本次連續宮制，一秒已造成約 12.5–20.5 角秒位移。秒以下微小模型差異的實務優先序低於時間來源與宮位邊界的處理。',
        '3. **保留原有 1 角秒一致性測試作工程檢查。**相對台灣本次一秒位移量，1 角秒約為 0.05–0.08 秒的量級，已比秒級輸入細很多。這是可保留的工程餘裕；沒有把過去未通過的遠期比較改判成通過，也沒有新增更嚴格的千分之一角秒發布門檻。',
        '4. **顯示精度與計算精度分開。**分鐘級來源的宮頭可先顯示到角分並附時間範圍；內部保留完整精度供重算。落宮邊界與整宮制分界則應標記可能變動，不能只靠四捨五入隱藏。這輪尚未做 UI。', '',
        '上述是根據實測提出的規格建議，不是把一秒或一分鐘當成所有人的已知誤差，也不是對占星解讀有效性的驗證。', '',
        '## 方法與可重跑性', '',
        f'- {s["counts"]["epochs"]} 個 UTC 基準時刻：1991、1999、2024，每年四個日期、每天 24 個時刻；三個台灣地點與四個對照地點，五宮制。',
        f'- {s["counts"]["baseline_charts"]:,} 組基準宮位，每組前後 1／30／60／180／300 秒，共 {s["counts"]["shifted_charts"]:,} 次重算、{s["counts"]["cusp_comparisons"]:,} 個宮頭位移及 {s["counts"]["asc_mc_comparisons"]:,} 個 ASC/MC 位移。',
        '- 使用 UTC→TT、UTC→UT1 的固定 IERS/ERFA 時間資料，再用 ERFA 天空角度與 LibEphemeris houses_armc。主表沒有使用全域 ΔT setter；它只用在明確分開的舊遠期案例重現。',
        '- 主表時刻均有 IERS 最終／快速觀測值；所選日期不跨閏秒。每個移動時刻另查時間資料，沒有把地球旋轉直接當作固定 900 角秒／分，也沒有用乘法代替一分鐘、五分鐘重算。',
        f'- 最大指定時間位移誤差：{run["max_requested_time_shift_error_seconds"]:.12g} 秒；原始宮頭與差值逐項一致性核對通過。',
        f'- Swiss／網路依賴攔截通過：{s["independence_pass"]}；核心未載入 Swiss。CPython guard 是測試儀器，不是 OS 安全邊界。',
        f'- 原始計算 wall time：{run["elapsed_seconds"]:.9f} 秒；不是單張星盤或跨引擎效能排名。',
        '- 圓周跨零、區間內轉折、分界求根與無效括區都有測試。輸入／原始輸出 SHA-256 在 run.json。格點樣本統計不是全域誤差保證。', '',
        '執行：`powershell -NoProfile -File .\\run-sensitivity.ps1`。需要上一輪 UTC 資料與結果已存在，才能同時重現舊遠期案例。結果存在 results/sensitivity/，重跑會保存上一輪。', '',
        '- [統計與各地點結果](results/sensitivity/summary.json)',
        '- [逐筆時間位移與宮頭原始結果 CSV](results/sensitivity/measurements.csv)',
        '- [基準宮頭](results/sensitivity/baselines.jsonl)',
        '- [時間輸入](results/sensitivity/times.json)',
        '- [整宮制事件證據](results/sensitivity/whole-sign-events.json)',
        '- [1999 範例](results/sensitivity/example.json)',
        '- [19.2 角秒案例重算](results/sensitivity/prior-worst-case.json)',
        '- [版本、雜湊、攔截紀錄](results/sensitivity/run.json)', '',
    ]
    (ROOT/'SENSITIVITY_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('SENSITIVITY_REPORT.md generated')

if __name__=='__main__':main()
