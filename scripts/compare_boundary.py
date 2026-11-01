# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Compare boundary charts, independent time conversions, and explicit API exclusions."""
import argparse
from collections import Counter
import gzip
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch
from complete_latitude_baselines import csv_write
from compare_reference import angular_comparison,point_comparison,stats,FLAGS,DIRECT_IDS

def compare(product,reference,output):
    pm,ps,pr=batch.load_run(product);sm,ss,sr=batch.load_run(reference)
    if pm['engine']!='product' or sm['engine']!='swiss' or ps!=ss or ps['baseline_suite']!='boundary-v2':raise ValueError('Wrong pair')
    if any(m['guard_events'] or m['unexpected_errors'] or m['cases']!=87 for m in (pm,sm)):raise ValueError('Invalid captures')
    mode=batch.house_latitude_mode(ps);rows=[];outcomes=[];times=[];cities={c['id']:c for c in ps['cities']}
    for case,p,r in zip(ps['cases'],pr,sr,strict=True):
        if case['id']!=p['id'] or p['id']!=r['id'] or case.get('input')!=p['input'] or p['input']!=r['input']:raise ValueError('Case/input mismatch')
        context=dict(case=case['id'],case_kind=case['kind'],house_latitude_mode=mode)
        if case['kind']=='chart':
            b=case['input'];city=cities.get(case.get('city'),{})
            context.update(local_iso=b['local_iso'],zone=b['zone'],system=b['system'],city_name=city.get('name','合成地點'),
                geographic_latitude=b['latitude'],geographic_longitude=b['longitude'])
        elif case['kind']=='time':context['utc']=case['utc']
        both=p['status']==r['status']=='ok'
        category=('chart_compared' if both else 'no_unique_instant' if r['status']=='not_comparable' else
            'product_only_rejection' if r['status']=='ok' else 'both_rejected' if p['status']!='ok' else 'reference_only_rejection') if case['kind']=='chart' else (
            'time_compared' if both and case['kind']=='time' else 'product_helper_no_native_equivalent' if r['status']=='not_comparable' else 'unexpected_helper_outcome')
        outcomes.append(dict(context,category=category,product_status=p['status'],reference_status=r['status'],
            product_outcome=p['outcome_kind'],reference_outcome=r['outcome_kind'],reference_method=r['reference_method'],
            reason=r['reference_reason'] or (r['raw'].get('reason') if isinstance(r['raw'],dict) else None),
            product_error=None if p['status']=='ok' else batch.dumps(p['raw']),
            reference_error=None if r['status']=='ok' else batch.dumps(r['raw'])))
        if not both:continue
        a,b=p['raw'],r['raw']
        if case['kind']=='time':
            times.append(dict(context,product_tt_jd=a['tt_jd'],reference_tt_jd=b['tt_jd'],
                product_ut1_jd=a['ut1_jd'],reference_ut1_jd=b['ut1_jd'],
                tt_delta_seconds=math.fsum([b['tt_jd'],-a['tt_jd']])*86400.,ut1_delta_seconds=math.fsum([b['ut1_jd'],-a['ut1_jd']])*86400.,
                product_ut1_source=a['ut1_source'],product_measured_time=a['measured_time'],
                product_leap_table_assumption=a['leap_table_assumption'],reference_function=b['function']))
            continue
        if case['kind']!='chart':raise ValueError('Unexpected directly comparable helper')
        if batch.exact(p['time_context'])!=batch.exact(r['time_context']):raise ValueError('Chart physical times differ')
        if len(a['cusps'])!=12 or len(b['cusps'])!=12:raise ValueError('Cusp count')
        for i,(x,y) in enumerate(zip(a['cusps'],b['cusps'],strict=True),1):
            rows.append(dict(context,kind='cusp',name=f'宮頭 {i}',point_id=i,product_longitude=x,reference_longitude=y,**angular_comparison(x,y)))
        other={point['id']:point for point in b['all_points']}
        if len(a['all_points'])!=20 or len(other)!=20:raise ValueError('Point count')
        for point in a['all_points']:
            q=other[point['id']];key=str(point['id']);pa=a['house_positions'][key];pb=b['house_positions'][key]
            if pa['house']!=point['house'] or pb['house']!=q['house']:raise ValueError('House audit mismatch')
            for pt,audit in ((point,pa),(q,pb)):
                expected=[pt['lon'],pt['lat'] if mode=='actual' else 0.,case['input']['system']]
                if batch.exact(audit['arguments'][3:])!=batch.exact(expected):raise ValueError('Latitude argument mismatch')
            row=dict(context,kind='point',name=point['name'],point_id=point['id'],product_longitude=point['lon'],reference_longitude=q['lon'],
                product_latitude=point['lat'],reference_latitude=q['lat'],scope='direct16' if point['id'] in DIRECT_IDS else 'axes2' if point['id'] in (-2,-3) else 'derived2',
                **point_comparison(point,q,pa,pb))
            row['day_chart_mismatch']=point['id']==-1 and a['day_chart']!=b['day_chart'];rows.append(row)
    for row in rows:row['angular_exceeded']=not row['angular_within_tolerance']
    points=[r for r in rows if r['kind']=='point'];cusps=[r for r in rows if r['kind']=='cusp']
    exceptions=[r for r in rows if any(r.get(f) for f in FLAGS)];different=[r for r in points if r['house_crossing']]
    maxima={}
    for label,selected in [('sun_through_pluto',[r for r in points if 0<=r['point_id']<=9]),('direct16',[r for r in points if r['scope']=='direct16']),
        ('all20',points),('cusps',cusps),('azimuth_cusps',[r for r in cusps if r['system']=='H'])]:
        maxima[label]={f:max(selected,key=lambda r:r[f]) for f in ('longitude_delta_arcsec','latitude_delta_arcsec','separation_arcsec')}
    summary=dict(cases=87,house_latitude_mode=mode,outcomes=dict(Counter(o['category'] for o in outcomes)),
        product_statuses=dict(Counter(r['status'] for r in pr)),reference_statuses=dict(Counter(r['status'] for r in sr)),
        total=stats(rows),points=stats(points),cusps=stats(cusps),angular_maxima=maxima,
        by_system={s:stats([r for r in rows if r.get('system')==s]) for s in sorted({r['system'] for r in rows})},
        house_difference_systems=dict(Counter(r['system'] for r in different)),asc_differences=sum(r['point_id']==-2 for r in different),mc_differences=sum(r['point_id']==-3 for r in different),
        time_comparison=dict(cases=len(times),max_abs_tt_seconds=max(abs(r['tt_delta_seconds']) for r in times),
            max_abs_ut1_seconds=max(abs(r['ut1_delta_seconds']) for r in times),
            worst_tt=max(times,key=lambda r:abs(r['tt_delta_seconds'])),worst_ut1=max(times,key=lambda r:abs(r['ut1_delta_seconds'])),
            interpretation='Independent time models; differences are in seconds, not angular arcseconds. No shared time inputs for these 19 tests. No accuracy pass/fail threshold is assigned.'),
        threshold_arcsec=30.,threshold_operator='<',review_required=True,
        product_manifest_sha256=batch.sha(Path(product)/'manifest.json'),reference_manifest_sha256=batch.sha(Path(reference)/'manifest.json'),source_sha256=batch.sha(__file__))
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    batch.write(output/'summary.json',summary)
    for name,items in [('all-comparisons',rows),('exceptions',exceptions),('house-differences',different),('outcomes',outcomes),('time-comparisons',times),
        ('not-comparable',[o for o in outcomes if o['reference_status']=='not_comparable']),('rejections',[o for o in outcomes if o['product_status']!='ok' or o['reference_status'] not in ('ok','not_comparable')])]:
        csv_write(output/f'{name}.csv',items)
        with gzip.open(output/f'{name}.jsonl.gz','xt',encoding='utf-8',newline='\n') as stream:
            for item in items:stream.write(batch.dumps(item)+'\n')
    lines=['# 87 邊界案例：產品與 Swiss 比較','',f"模式：{mode}；完整保留 87 筆輸入／狀態，分類為 {batch.dumps(summary['outcomes'])}。",'',
        f"- 可比星盤 {summary['points']['charts']} 張；宮號差異 {summary['points']['house_crossing']['charts']} 張／{len(different)} 點；ASC {summary['asc_differences']}、MC {summary['mc_differences']}。",
        f"- 可比較角度 ≥30 角秒：{summary['total']['angular_exceeded']['measurements']}；天體最大黃經差 {summary['points']['max_longitude_delta_arcsec']!r} 角秒，宮頭 {summary['cusps']['max_longitude_delta_arcsec']!r} 角秒。",
        f"- 時標獨立對照 {len(times)} 例；TT 最大絕對差 {summary['time_comparison']['max_abs_tt_seconds']!r} 秒；UT1 {summary['time_comparison']['max_abs_ut1_seconds']!r} 秒。這不是角度誤差，也未用 30 角秒門檻判定時間正確。",'',
        '- all-comparisons.csv 保存所有星盤點與宮頭；house-differences.csv 是宮號差異。time-comparisons.csv 分開保存每例時標結果與來源。',
        '- outcomes.csv 包含全部 87 例；not-comparable.csv 列明未指定唯一物理時間及沒有原生 Swiss 對應 API 的測試；rejections.csv 保留預期拒絕及錯誤。',
        '- 共用 TT／UT1 的星盤比較不獨立驗證時區。UTC 閏秒排盤的 Swiss 輸出使用其原生 utc_to_jd，產品拒絕該輸入，沒有假造可比產品星盤。',
        '- 未定義、預期拒絕、未能對照皆不當成成功同宮。Swiss 沒有模仿產品任意宮頭陣列或相位容許度規則。',
        '- 兩模式只改歸宮時傳入的黃緯；真實座標、獨立時標測試及不適用項目的原始輸入都保留。','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    batch.write(output/'manifest.json',dict(complete=True,review_required=True,artifacts_sha256={p.name:batch.sha(p) for p in output.iterdir() if p.is_file()}))
    print(batch.dumps({k:summary[k] for k in ('cases','house_latitude_mode','outcomes','time_comparison')}),flush=True)
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('product','reference','output'):parser.add_argument('--'+arg,type=Path,required=True)
    a=parser.parse_args();compare(a.product,a.reference,a.output)
