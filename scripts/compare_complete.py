# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Compare complete-v1 product and independent Swiss captures, retaining rejections."""
import argparse
from collections import Counter
import csv
import gzip
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch
from compare_reference import angular_comparison,point_comparison,stats,FLAGS,DIRECT_IDS

def compare(product,reference,output):
    pm,ps,prows=batch.load_run(product);sm,ss,srows=batch.load_run(reference)
    if pm['engine']!='product' or sm['engine']!='swiss':raise ValueError('Wrong engines')
    if ps!=ss or pm['subset']!='full' or sm['subset']!='full':raise ValueError('Suite mismatch')
    mode=batch.house_latitude_mode(ps)
    if any(m['guard_events'] or m['unexpected_errors'] for m in (pm,sm)):raise ValueError('Unexpected errors/guard events')
    if [r['id'] for r in prows]!=[r['id'] for r in srows]:raise ValueError('Case inventory mismatch')
    cities={c['id']:c for c in ps['cities']};cases={c['id']:c for c in ps['cases']}
    rows=[];outcomes=[]
    for pa,sb in zip(prows,srows,strict=True):
        case=cases[pa['id']];city=cities[case['city']]
        if pa['input']!=case['input'] or sb['input']!=case['input']:raise ValueError('Input mismatch')
        if batch.exact(pa['time_context'])!=batch.exact(sb['time_context']):raise ValueError('Time mismatch')
        context=dict(case=pa['id'],local_iso=case['input']['local_iso'],utc=pa['time_context']['utc'],
            zone=city['zone'],city=city['id'],city_name=city['name'],band=city['band'],
            hemisphere='north' if city['latitude']>0 else 'south',geographic_latitude=city['latitude'],
            geographic_longitude=city['longitude'],system=case['input']['system'],house_latitude_mode=mode)
        both=pa['status']=='ok' and sb['status']=='ok'
        outcome=dict(context,product_status=pa['status'],reference_status=sb['status'],
            product_outcome=pa['outcome_kind'],reference_outcome=sb['outcome_kind'],
            category='both_ok' if both else 'both_rejected' if pa['status']!='ok' and sb['status']!='ok' else 'one_sided_rejection',
            product_error=None if pa['status']=='ok' else pa['raw'],
            reference_error=None if sb['status']=='ok' else sb['raw'])
        outcomes.append(outcome)
        if not both:continue
        a,b=pa['raw'],sb['raw']
        if len(a['cusps'])!=12 or len(b['cusps'])!=12:raise ValueError('Cusp inventory')
        for i,(x,y) in enumerate(zip(a['cusps'],b['cusps'],strict=True),1):
            rows.append(dict(context,kind='cusp',name=f'宮頭 {i}',point_id=i,product_longitude=x,reference_longitude=y,**angular_comparison(x,y)))
        other={p['id']:p for p in b['all_points']}
        if len(a['all_points'])!=20 or len(other)!=20 or {p['id'] for p in a['all_points']}!=set(other):raise ValueError('Point inventory')
        for p in a['all_points']:
            q=other[p['id']];key=str(p['id'])
            if a['house_positions'][key]['house']!=p['house'] or b['house_positions'][key]['house']!=q['house']:raise ValueError('Audit mismatch')
            for chart,point in ((a,p),(b,q)):
                arguments=chart['house_positions'][key]['arguments']
                expected=[point['lon'],point['lat'] if mode=='actual' else 0.0,case['input']['system']]
                if batch.exact(arguments[3:])!=batch.exact(expected):raise ValueError('Placement argument/mode mismatch')
            r=dict(context,kind='point',point_id=p['id'],name=p['name'],product_longitude=p['lon'],reference_longitude=q['lon'],
                product_latitude=p['lat'],reference_latitude=q['lat'],scope='direct16' if p['id'] in DIRECT_IDS else 'axes2' if p['id'] in (-2,-3) else 'derived2',
                **point_comparison(p,q,a['house_positions'][key],b['house_positions'][key]))
            r['day_chart_mismatch']=p['id']==-1 and a['day_chart']!=b['day_chart'];rows.append(r)
    for r in rows:r['angular_exceeded']=not r['angular_within_tolerance']
    points=[r for r in rows if r['kind']=='point'];cusps=[r for r in rows if r['kind']=='cusp']
    exceptions=[r for r in rows if any(r.get(f) for f in FLAGS)]
    rejected=[r for r in outcomes if r['category']!='both_ok']
    summary=dict(cases=len(outcomes),house_latitude_mode=mode,outcomes=dict(Counter(r['category'] for r in outcomes)),
        total=stats(rows),points=stats(points),cusps=stats(cusps),direct16=stats([r for r in points if r['scope']=='direct16']),
        by_system={s:dict(statistics=stats([r for r in rows if r['system']==s]),outcomes=dict(Counter(r['category'] for r in outcomes if r['system']==s))) for s in ps['house_systems']},
        by_city={c:dict(statistics=stats([r for r in rows if r['city']==c]),outcomes=dict(Counter(r['category'] for r in outcomes if r['city']==c))) for c in cities},
        by_band={b:stats([r for r in rows if r['band']==b]) for b in sorted({c['band'] for c in cities.values()})},
        threshold_arcsec=30.,threshold_operator='<',review_required=bool(exceptions or rejected),
        product_manifest_sha256=batch.sha(Path(product)/'manifest.json'),reference_manifest_sha256=batch.sha(Path(reference)/'manifest.json'),
        source_sha256=batch.sha(__file__),time_policy=ps['time_policy'])
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    batch.write(output/'summary.json',summary);batch.write(output/'exceptions.json',exceptions);batch.write(output/'rejections.json',rejected)
    for name,items in [('all-comparisons',rows),('exceptions',exceptions),('outcomes',outcomes),('rejections',rejected)]:
        with gzip.open(output/(name+'.jsonl.gz'),'xt',encoding='utf-8',newline='\n') as f:
            for r in items:f.write(batch.dumps(r)+'\n')
        with (output/(name+'.csv')).open('x',encoding='utf-8-sig',newline='') as f:
            fields=list(dict.fromkeys(k for r in items for k in r))
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            writer.writerows({k:batch.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in items)
    title='1200 例基準資料與 Swiss 基準對照資料' if ps.get('baseline_suite')=='main-v2' else '完全基準資料與 Swiss 完全基準對照資料'
    lines=['# '+title,'',
        '歸宮黃緯模式：'+('實際黃緯' if mode=='actual' else '零黃緯')+'。實際天體座標不歸零；只有 house_pos 輸入依此模式切換。','',
        '產品版本 0.6.5；LibEphemeris 3.2.2；Swiss 2.10.03／pyswisseph 2.10.3.2。',
        '這是指定產品捕捉與封存 Swiss 參考的比較；產品的歸宮政策以捕捉資料為準。兩套引擎一致不等於宮頭編號自洽，宮號與角度差分開列出。','',
        f"- 總案例：{len(outcomes)}；結果分類：{batch.dumps(summary['outcomes'])}。",
        f"- 雙方可比較星盤：{summary['total']['charts']}；天體／衍生點：{len(points)}；宮頭：{len(cusps)}。",
        f"- 角度超標（≥30 角秒）：{summary['total']['angular_exceeded']['measurements']}。",
        f"- 天體最大黃經差：{summary['points']['max_longitude_delta_arcsec']!r} 角秒；宮頭最大差：{summary['cusps']['max_longitude_delta_arcsec']!r} 角秒。",
        f"- 跨宮：{summary['points']['house_crossing']['charts']} 張／{summary['points']['house_crossing']['measurements']} 點。",
        f"- 雙方未定義：{summary['points']['undefined_both']['charts']} 張／{summary['points']['undefined_both']['measurements']} 點；單方未定義：{summary['points']['undefined_mismatch']['measurements']} 點。",
        f"- 原始星座不同：{summary['total']['zodiac_crossing']['measurements']}；顯示進位後星座不同：{summary['total']['display_zodiac_crossing']['measurements']}。",'',
        '## 各宮制','', '| 代碼 | 雙方成功 | 雙方拒絕 | 單方拒絕 | 跨宮點 | 雙方未定義點 | 角度超標 |', '|---|---:|---:|---:|---:|---:|---:|']
    for code,v in summary['by_system'].items():
        o=v['outcomes'];s=v['statistics']
        lines.append(f"| {code} | {o.get('both_ok',0)} | {o.get('both_rejected',0)} | {o.get('one_sided_rejection',0)} | {s['house_crossing']['measurements']} | {s['undefined_both']['measurements']} | {s['angular_exceeded']['measurements']} |")
    lines+=['','## 範圍與判讀','',
        f'- 兩份資料都保留全部 {len(outcomes)} 個輸入；幾何拒絕不刪除、不換時間、不換宮制。拒絕的案例沒有完整星盤可作數值比較；若僅一方成功，其完整輸出仍在原始資料中。',
        '- 原始 house_pos、實際黃經／黃緯及產品補正原因皆保留。house_pos 的小數是宮位座標，不是角秒。',
        '- 每次產品精確回歸與程序數一致性核對都使用完整浮點精度；30 角秒僅用於 Swiss 外部角度比較，跨宮、跨星座、未定義另列。',
        '- Swiss 獨立計算天體、宮頭、恆星時、黃赤交角、日夜及衍生點，使用與產品相同的 TT／UT1；沒有借用產品位置，也未獨立驗證民用時區或時標換算。',
        '- Swiss 旗標要求 SWIEPH，不允許 Moshier fallback。沒有升級依賴或資料。',
        '- all-comparisons.csv 保存全部可比較數值；exceptions.csv 保存跨界／超標／未定義；outcomes.csv 保存所有案例結果；rejections.csv 保存雙方及單方拒絕與原始錯誤。',
        '- 有拒絕、跨宮、未定義或其他例外時為 review-required；資料捕捉完整與外部結果全面一致是不同判定。','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    batch.write(output/'manifest.json',dict(complete=True,review_required=summary['review_required'],
        artifacts_sha256={p.name:batch.sha(p) for p in output.iterdir() if p.is_file()}))
    print(batch.dumps({k:summary[k] for k in ('cases','outcomes','review_required','points','cusps')}))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--product',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();s=compare(a.product,a.reference,a.output);raise SystemExit(1 if s['review_required'] else 0)
