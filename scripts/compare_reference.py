# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Prepare and compare the fixed 1200 charts with a sealed Swiss reference.

This comparison's <30 arcsecond allowance never changes exact release regression.
"""
from pathlib import Path
import argparse
from collections import Counter
import csv
import gzip
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
import numerical_regression as nr

THRESHOLD_ARCSEC = 30.0
DEFAULT_PRODUCT = ROOT/'regression/baselines/0.6.5'
DEFAULT_REFERENCE = ROOT/'regression/references/swiss-2.10.03-0.6.3'
DIRECT_IDS = set(range(10)) | {11, 15, 17, 18, 19, 20}


def angular_comparison(a, b, latitude_a=0., latitude_b=0.):
    # remainder preserves tiny differences and treats 359.999 -> 0.001 correctly.
    lon = abs(math.remainder(b-a, 360.))*3600
    lat = abs(latitude_b-latitude_a)*3600
    dl = math.radians(math.remainder(b-a, 360.))
    dp = math.radians(latitude_b-latitude_a)
    hav = math.sin(dp/2)**2 + math.cos(math.radians(latitude_a))*math.cos(math.radians(latitude_b))*math.sin(dl/2)**2
    separation = math.degrees(2*math.asin(math.sqrt(max(0., min(1., hav)))))*3600
    sign = lambda x: int((x % 360)//30)
    display_sign = lambda x: (round((x % 360)*3600) % 1296000)//108000
    return dict(longitude_delta_arcsec=lon, latitude_delta_arcsec=lat,
                separation_arcsec=separation,
                angular_within_tolerance=max(lon, lat, separation) < THRESHOLD_ARCSEC,
                zodiac_crossing=sign(a) != sign(b),
                display_zodiac_crossing=display_sign(a) != display_sign(b),
                product_sign=sign(a), reference_sign=sign(b))


def point_comparison(a, b, pa, pb):
    result = angular_comparison(a['lon'], b['lon'], a['lat'], b['lat'])
    both_valid = a['house'] is not None and b['house'] is not None
    result.update(product_house=a['house'], reference_house=b['house'],
        house_crossing=both_valid and a['house'] != b['house'],
        undefined_mismatch=(a['house'] is None) != (b['house'] is None),
        undefined_both=a['house'] is None and b['house'] is None,
        retrograde_mismatch=a['retrograde'] != b['retrograde'],
        product_house_pos_raw=pa['raw_position'], reference_house_pos_raw=pb['raw_position'],
        product_house_pos=pa['position'], reference_house_pos=pb['position'],
        product_correction=pa['correction'],
        house_pos_delta_units=abs(math.remainder(pb['position']-pa['position'], 12.)) if both_valid else None)
    # house_pos is a dimensionless house coordinate, not ecliptic degrees.
    # Retain it as a diagnostic, never call it a planet's angular error.
    return result


def prepare(product, output):
    nr.verify_seal(product)
    _, _, records = nr.load_run(product)
    suite = nr.read(product/'cases.json')
    suite = dict(suite, cases=[c for c in suite['cases'] if c['group'] == 'balanced'])
    nr.coverage(suite)
    output.mkdir(parents=True, exist_ok=False)
    nr.write(output/'cases.json', suite)
    with gzip.open(output/'inputs.jsonl.gz', 'xt', encoding='utf-8', newline='\n') as stream:
        for case in suite['cases']:
            row = records[case['id']]
            if row['result']['status'] != 'ok': raise ValueError('Failed product chart')
            c = row['raw']
            item = dict(id=case['id'], city=case['city'], input=case['input'], orbs=case['orbs'],
                        utc=c['utc'], tt_jd=c['times']['tt_jd'], ut1_jd=c['times']['ut1_jd'])
            stream.write(nr.dumps(item)+'\n')
    nr.write(output/'input-manifest.json', dict(charts=1200,
        product_manifest_sha256=nr.sha(product/'manifest.json'),
        product_cases_sha256=nr.sha(product/'cases.json'),
        time_policy='Shared product civil-time to TT/UT1 conversion; independent time conversion is outside this comparison.',
        artifacts_sha256={p.name:nr.sha(p) for p in output.iterdir() if p.is_file()}))


def load_reference(folder):
    manifest = nr.read(folder/'manifest.json')
    if not manifest['complete'] or manifest['charts'] != 1200 or manifest['errors']:
        raise ValueError('Incomplete reference')
    required = {'cases.json','inputs.jsonl.gz','input-manifest.json','environment.json','worker-source.py','results.jsonl.gz'}
    if set(manifest['artifacts_sha256']) != required:
        raise ValueError('Reference seal inventory mismatch')
    for name, digest in manifest['artifacts_sha256'].items():
        if nr.sha(folder/name) != digest: raise ValueError('Reference hash mismatch: '+name)
    rows = [json.loads(line) for line in gzip.open(folder/'results.jsonl.gz','rt',encoding='utf-8')]
    if len(rows) != 1200 or len({r['id'] for r in rows}) != 1200 or any(r['status'] != 'ok' for r in rows):
        raise ValueError('Missing/duplicate/failed reference charts')
    return {r['id']:r for r in rows}


FLAGS = ('angular_exceeded','house_crossing','zodiac_crossing','display_zodiac_crossing',
         'undefined_mismatch','undefined_both','retrograde_mismatch','day_chart_mismatch')


def stats(rows):
    answer = dict(charts=len({r['case'] for r in rows}), measurements=len(rows))
    for flag in FLAGS:
        selected = [r for r in rows if r.get(flag)]
        answer[flag] = dict(measurements=len(selected), charts=len({r['case'] for r in selected}))
    answer['review_charts'] = len({r['case'] for r in rows if any(r.get(f) for f in FLAGS if f != 'undefined_both')})
    for key in ('longitude_delta_arcsec','latitude_delta_arcsec','separation_arcsec'):
        answer['max_'+key] = max((r[key] for r in rows), default=0.)
    return answer


def compare(product, reference, output):
    if (product/'SHA256SUMS.json').exists(): nr.verify_seal(product)
    manifest, environment, charts = nr.load_run(product)
    if manifest['unexpected_outcomes'] or manifest['guard_events']:
        raise ValueError('Failed product run')
    ref = load_reference(reference)
    suite = nr.read(product/'cases.json')
    cases = [c for c in suite['cases'] if c['group'] == 'balanced']
    reference_cases = nr.read(reference/'cases.json')['cases']
    if cases != reference_cases or {c['id'] for c in cases} != set(ref):
        raise ValueError('Fixed cases differ from the reference')
    cities = {c['id']:c for c in suite['cities']}
    rows = []
    for case in cases:
        ident = case['id']; a = charts[ident]['raw']; b = ref[ident]; city = cities[case['city']]
        if a['input'] != case['input'] or b['input'] != case['input']:
            raise ValueError('Chart input mismatch: '+ident)
        if any(a['times'][k] != b[k] for k in ('tt_jd','ut1_jd')) or a['utc'] != b['utc']:
            raise ValueError('Shared physical instant changed; review time conversion before comparison: '+ident)
        context = dict(case=ident, local_iso=case['input']['local_iso'], utc=a['utc'], zone=case['input']['zone'],
            city=case['city'], city_name=city['name'], hemisphere='north' if city['latitude'] >= 0 else 'south',
            band=city['band'], geographic_latitude=city['latitude'], geographic_longitude=city['longitude'],
            system=case['input']['system'])
        if len(a['cusps']) != 12 or len(b['cusps']) != 12: raise ValueError('Missing cusps')
        for index, (x,y) in enumerate(zip(a['cusps'], b['cusps'], strict=True), 1):
            rows.append(dict(context, kind='cusp', name=f'宮頭 {index}', point_id=index,
                             product_longitude=x, reference_longitude=y, **angular_comparison(x,y)))
        other = {p['id']:p for p in b['all_points']}
        if len(other) != 20 or len(a['all_points']) != 20 or {p['id'] for p in a['all_points']} != set(other):
            raise ValueError('Point inventory mismatch')
        for p in a['all_points']:
            q = other[p['id']]; key = str(p['id'])
            if a['house_positions'][key]['house'] != p['house'] or b['house_positions'][key]['house'] != q['house']:
                raise ValueError('House audit mismatch')
            row = dict(context, kind='point', point_id=p['id'], name=p['name'],
                product_longitude=p['lon'], reference_longitude=q['lon'],
                product_latitude=p['lat'], reference_latitude=q['lat'],
                scope='direct16' if p['id'] in DIRECT_IDS else 'axes2' if p['id'] in (-2,-3) else 'derived2',
                **point_comparison(p,q,a['house_positions'][key],b['house_positions'][key]))
            row['day_chart_mismatch'] = p['id'] == -1 and a['day_chart'] != b['day_chart']
            rows.append(row)
    for row in rows: row['angular_exceeded'] = not row['angular_within_tolerance']
    output.mkdir(parents=True, exist_ok=False)
    points = [r for r in rows if r['kind'] == 'point']; cusps = [r for r in rows if r['kind'] == 'cusp']
    exceptions = [r for r in rows if any(r.get(f) for f in FLAGS)]
    summary = dict(product_version=environment['app_version'], reference_version=nr.read(reference/'environment.json')['swiss_version'],
        threshold_arcsec=THRESHOLD_ARCSEC, threshold_operator='<', total=stats(rows), points=stats(points),
        direct16=stats([r for r in points if r['scope'] == 'direct16']), cusps=stats(cusps),
        by_system={s:stats([r for r in rows if r['system'] == s]) for s in suite['house_systems']},
        by_hemisphere={h:stats([r for r in rows if r['hemisphere'] == h]) for h in ('north','south')},
        by_band={h:stats([r for r in rows if r['band'] == h]) for h in dict.fromkeys(r['band'] for r in rows)},
        by_city={c:stats([r for r in rows if r['city'] == c]) for c in cities},
        product_manifest_sha256=nr.sha(product/'manifest.json'), reference_manifest_sha256=nr.sha(reference/'manifest.json'))
    summary['within_angular_tolerance'] = summary['total']['angular_exceeded']['measurements'] == 0
    summary['review_required'] = bool(exceptions)
    nr.write(output/'summary.json', summary)
    nr.write(output/'exceptions.json', exceptions)
    with gzip.open(output/'all-comparisons.jsonl.gz','xt',encoding='utf-8') as f:
        for row in rows: f.write(nr.dumps(row)+'\n')
    fields = list(dict.fromkeys(k for r in rows for k in r))
    for filename, data in (('all-comparisons.csv',rows),('exceptions.csv',exceptions)):
        with (output/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(data)
    build_report(output, summary)
    nr.write(output/'manifest.json', dict(complete=True, script_sha256=nr.sha(__file__),
        artifacts_sha256={p.name:nr.sha(p) for p in output.iterdir() if p.is_file()}))
    print(nr.dumps({k:summary[k] for k in ('product_version','within_angular_tolerance','review_required','total','points','direct16','cusps')}))
    return 1 if summary['total']['review_charts'] else 0


def build_report(output, s):
    from desktop.model import HOUSE_SYSTEMS
    total=s['total']; p=s['points']; c=s['cusps']
    lines=[f"# {s['product_version']} 與 Swiss 基準對照：原 1200 筆固定星盤",'',
        '主樣本為原 1200 筆 balanced 案例，輸入逐項相同；產品另外保留 87 筆邊界案例作版本回歸。',
        '本次採正式 ChartEngine 的 house_number2，與 Swiss 自算的天體、宮頭及實際黃緯 house_pos 比較。沒有以產品座標餵 Swiss，沒有零黃緯變體。','',
        '## 判讀規則','',
        '- 宮頭黃經、天體黃經／黃緯及球面角距全部必須小於 30 角秒；等於 30 不放行。黃經採圓周最短差。',
        '- 不同宮號、不同原始星座，以及顯示到整角秒後跨星座，無論角度差多少都保留。宮頭跨星座也另記。',
        '- house_pos 是無量綱的宮位座標；另存原始值及循環 12 宮的座標差，不將其誤當成黃經角秒。',
        '- 雙方未定義、單方未定義、順逆行或日夜判斷不同亦保留；雙方未定義不假稱為有效同宮。',
        '- Swiss 與產品共用出生條件轉換出的 TT／UT1。Swiss 自算黃赤交角、章動、恆星時、宮頭、天體與衍生點。本次不獨立驗證民用時間與時標換算。',
        '- LibEphemeris 3.2.2；Swiss 2.10.03／pyswisseph 2.10.3.2；固定資料檔與模組雜湊均封存。Swiss 回傳旗標必須為 SWIEPH，禁止 Moshier fallback。',
        '- 30 角秒只用於這份外部對照。未來版本對指定產品基準仍採完整精度逐值比對。','',
        '## 整體結果','',
        f"- 1200 張、24000 個天體／衍生點、14400 個宮頭，全數完成。",
        f"- 角度超標：{total['angular_exceeded']['measurements']} 筆。",
        f"- 天體／衍生點最大黃經差 {p['max_longitude_delta_arcsec']:.12g} 角秒；最大黃緯差 {p['max_latitude_delta_arcsec']:.12g} 角秒；最大球面角距 {p['max_separation_arcsec']:.12g} 角秒。",
        f"- 宮頭最大黃經差 {c['max_longitude_delta_arcsec']:.12g} 角秒。",
        f"- 不同宮號：{p['house_crossing']['charts']} 張、{p['house_crossing']['measurements']} 點。",
        f"- 天體原始星座不同：{p['zodiac_crossing']['measurements']} 點；宮頭原始星座不同：{c['zodiac_crossing']['measurements']} 筆。",
        f"- 天體顯示星座不同：{p['display_zodiac_crossing']['measurements']} 點；宮頭顯示星座不同：{c['display_zodiac_crossing']['measurements']} 筆。",
        f"- 雙方未定義：{p['undefined_both']['charts']} 張、{p['undefined_both']['measurements']} 點；僅一方未定義：{p['undefined_mismatch']['measurements']} 點。",
        f"- 直接計算的 16 個天體／北交點，共 19200 點：不同宮號 {s['direct16']['house_crossing']['measurements']} 點。",'',
        '不同分類可能發生在同一張盤，不可直接相加當作星盤總數。角度在容許範圍內，不代表跨宮位的差異已解決。','',
        '## 各宮制','',
        '| 宮制 | 星盤數 | 跨宮星盤 | 跨宮點 | 角度超標 | 天體／宮頭跨星座 | 雙方未定義點 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for code, v in s['by_system'].items():
        lines.append(f"| {HOUSE_SYSTEMS[code]} | {v['charts']} | {v['house_crossing']['charts']} | {v['house_crossing']['measurements']} | {v['angular_exceeded']['measurements']} | {v['zodiac_crossing']['measurements']} | {v['undefined_both']['measurements']} |")
    lines += ['', '## 半球與緯度','', '| 分組 | 星盤數 | 跨宮星盤 | 跨宮點 | 雙方未定義點 |','|---|---:|---:|---:|---:|']
    for key,v in list(s['by_hemisphere'].items())+list(s['by_band'].items()):
        lines.append(f"| {key} | {v['charts']} | {v['house_crossing']['charts']} | {v['house_crossing']['measurements']} | {v['undefined_both']['measurements']} |")
    lines += ['', '## 完整可追溯資料','',
        '- exceptions.csv / exceptions.json：所有例外，含出生年月日時分秒、UTC、IANA 時區、城市、經緯度、宮制、天體、雙方原值及差異。',
        '- all-comparisons.csv / all-comparisons.jsonl.gz：全部 38400 筆比較，包含可容忍的微小差異。',
        '- summary.json：各宮制、城市、半球、緯度分組統計；manifest.json：這份報告的完整性封存。',
        '- 產品執行紀錄保存完整原始結果、每點 Lib API 原始回傳及補正原因；外部對照仍使用未修改的 regression/references/swiss-2.10.03-0.6.3。','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    for command in ('prepare','compare'):
        p=sub.add_parser(command);p.add_argument('--product',type=Path,default=DEFAULT_PRODUCT)
        p.add_argument('--output',type=Path,required=True)
        if command=='compare': p.add_argument('--reference',type=Path,default=DEFAULT_REFERENCE)
    args=parser.parse_args()
    if args.command=='prepare': prepare(args.product,args.output);return 0
    return compare(args.product,args.reference,args.output)


if __name__=='__main__': raise SystemExit(main())
