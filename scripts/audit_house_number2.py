# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Recalculate 1200 fixed charts with house_number2; never write a baseline.

Run: .venv-desktop/Scripts/python.exe scripts/audit_house_number2.py --output NEW_DIRECTORY
Verify saved output: add --verify-only (does not rerun astronomy).
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import platform
import sys
import time
import warnings

import numerical_regression as nr

ROOT = nr.ROOT
VERSIONS = ('0.6.0', '0.6.1', '0.6.2')
SOURCES = ('desktop/house_positions.py', 'scripts/audit_house_number2.py', 'tests/test_house_number2.py')


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def protect():
    paths = {p for tree in ('desktop', 'regression', 'requirements', 'vendor/libephemeris')
             for p in (ROOT / tree).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    paths.update((ROOT / 'dist').glob('*.zip'))
    paths.update(ROOT / p for p in nr.CORE + nr.LOCKS + list(SOURCES))
    return {p.relative_to(ROOT).as_posix(): nr.sha(p) for p in sorted(paths)}


def without_houses(chart):
    values = nr.numeric_projection(chart)
    for point in values['all_points'].values():
        point.pop('house')
    return nr.exact(values)


def scope(point_id):
    if 0 <= point_id < 10:
        return 'major10'
    if point_id in (11, 15, 17, 18, 19, 20):
        return 'other_direct6'
    return 'axes2' if point_id in (-2, -3) else 'other_derived2'


def load_baselines():
    baselines = {}
    for version in VERSIONS:
        folder = ROOT / 'regression/baselines' / version
        nr.verify_seal(folder)
        baselines[version] = nr.load_run(folder)
    suite = nr.read(ROOT / 'regression/baselines/0.6.2/cases.json')
    cases = [c for c in suite['cases'] if c['group'] == 'balanced']
    assert len(cases) == 1200
    for version in VERSIONS:
        other = nr.read(ROOT / 'regression/baselines' / version / 'cases.json')
        assert [c for c in other['cases'] if c['group'] == 'balanced'] == cases
    return suite, cases, baselines


def stats(points):
    charts = {p['case'] for p in points}
    differences = [p for p in points if p['different']]
    undefined = [p for p in points if p['status'] == 'undefined']
    corrections = [p for p in points if p['correction']]
    return dict(charts=len(charts), points=len(points),
                changed_charts=len({p['case'] for p in differences}),
                unchanged_charts=len(charts - {p['case'] for p in differences}),
                changed_points=len(differences),
                assigned_to_different_house=sum(p['new_house'] is not None and p['old_house'] is not None for p in differences),
                became_unassigned=sum(p['new_house'] is None and p['old_house'] is not None for p in differences),
                became_assigned=sum(p['new_house'] is not None and p['old_house'] is None for p in differences),
                undefined_points=len(undefined), undefined_charts=len({p['case'] for p in undefined}),
                patched_points=len(corrections), patched_charts=len({p['case'] for p in corrections}))


def summarize(points, systems, cities):
    result = dict(total=stats(points))
    for field, keys in [('system', systems), ('hemisphere', ['north', 'south']),
                        ('band', ['北高', '北中', '北低', '南高', '南中', '南低']),
                        ('city', list(cities)), ('scope', ['major10', 'other_direct6', 'axes2', 'other_derived2'])]:
        result['by_' + field] = {key: stats([p for p in points if p[field] == key]) for key in keys}
    result['direct16'] = stats([p for p in points if p['scope'] in ('major10', 'other_direct6')])
    result['non_axes18'] = stats([p for p in points if p['scope'] != 'axes2'])
    result['by_point'] = {str(key): dict(name=next(p['name'] for p in points if p['point_id'] == key),
                                       **stats([p for p in points if p['point_id'] == key]))
                          for key in dict.fromkeys(p['point_id'] for p in points)}
    return result


def analyze(output, suite, cases, baselines, records):
    cities = {c['id']: c for c in suite['cities']}
    by_case = {r['id']: r for r in records}
    assert len(by_case) == len(records) == 1200
    summaries = {}; all_comparisons = {}
    for version in ('0.6.0', '0.6.2'):
        comparisons = []
        baseline = baselines[version][2]
        for case in cases:
            ident = case['id']; row = by_case[ident]; original = baseline[ident]['raw']
            candidate = row['raw']; city = cities[case['city']]
            # Verify every numerical field other than house membership, bit for bit.
            assert without_houses(original) == without_houses(candidate), ident
            old_points = {p['id']: p for p in original['all_points']}
            for point, audit in zip(candidate['all_points'], row['house_position_audit'], strict=True):
                assert point['id'] == audit['point_id']
                old = old_points[point['id']]
                comparisons.append(dict(case=ident, local_iso=case['input']['local_iso'],
                    zone=case['input']['zone'], utc=candidate['utc'], city=case['city'], city_name=city['name'],
                    geographic_longitude=city['longitude'], geographic_latitude=city['latitude'],
                    hemisphere='north' if city['latitude'] > 0 else 'south', band=city['band'],
                    system=case['input']['system'], point_id=point['id'], name=point['name'],
                    scope=scope(point['id']), longitude=point['lon'], latitude=point['lat'],
                    old_house=old['house'], new_house=point['house'], different=old['house'] != point['house'],
                    **{k: audit[k] for k in ('raw_position', 'position', 'correction', 'status', 'warnings')}))
        assert len(comparisons) == 24000
        summaries[version] = summarize(comparisons, suite['house_systems'], cities)
        summaries[version]['non_house_numerical_differences'] = 0
        all_comparisons[version] = comparisons
        nr.write(output / f'differences-vs-{version}.json', [p for p in comparisons if p['different']])
    latest = all_comparisons['0.6.2']
    nr.write(output / 'patches.json', [p for p in latest if p['correction']])
    nr.write(output / 'undefined.json', [p for p in latest if p['status'] == 'undefined'])
    nr.write(output / 'summary.json', summaries)
    build_report(output, suite, cases, summaries, all_comparisons)
    return summaries


def build_report(output, suite, cases, summaries, comparisons):
    from desktop.model import HOUSE_SYSTEMS
    current = summaries['0.6.2']; original = summaries['0.6.0']; total = current['total']
    lines = ['# house_number2：1200 張固定星盤重算與基準比較', '',
        '比較目的：確認改用 LibEphemeris 的實際黃緯空間歸宮後，哪些既有星盤資料會改變。本報告不是新基準，也不是天文正確性認證。', '',
        '## 方法與範圍', '',
        '- 從封存案例的出生時間、時區、經緯度及顯示選項出發，用現有 ChartEngine 重新計算 1200 張完整星盤。先逐值核對重算結果與 0.6.2 一致，再以 house_number2 重新歸宮。不是直接複製舊 API 結果。',
        '- 每張 20 點，共 24000 次新的 LibEphemeris 3.2.2 house_pos 呼叫。傳入同次重算所得 ARMC、地理緯度、真黃赤交角、天體實際黃經／黃緯及原宮制。',
        '- 唯一修正：精確回傳 13.0 → 1.0，再向下取整取得宮號。沒有容差、四捨五入、宮頭吸附，也沒有把天體黃緯歸零。12.999… 與 9.999… 保留原回傳及其宮號。',
        '- Koch 回傳 0 保留為 undefined，宮號記為 null；不改成第 0 宮、不換宮制、不退回舊算法。',
        '- 保留每次原始回傳、修正後回傳、修正原因與完整候選星盤。正式桌面仍使用原 house_number／axis_house_number；本次沒有切換正式排盤、更新依賴或重建封裝。',
        '- 只包含原 1200 筆 balanced 主案例；87 筆邊界案例（含另存的 16 張反向 Azimuth）不在本次範圍。', '',
        '## 整體差異', '',
        '| 比較基準 | 有變化的星盤 | 完全相同的星盤 | 不同宮號（雙方都有宮號） | 原有宮號變成未定義 | 原本空值取得宮號 | 所有變動點 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for version in ('0.6.0', '0.6.2'):
        s = summaries[version]['total']
        lines.append(f"| {version} | {s['changed_charts']}／1200 | {s['unchanged_charts']} | {s['assigned_to_different_house']} | {s['became_unassigned']} | {s['became_assigned']} | {s['changed_points']}／24000 |")
    lines += ['', '兩版基準皆完整保留。所有變動只在歸宮欄位；時間換算、宮頭、黃經／黃緯、速度、逆行、日夜判斷、幸運點位置與相位等數值逐位一致。', '',
        '以下詳細統計主要對照目前 0.6.2；原始 0.6.0 的逐點差異另存 differences-vs-0.6.0.json。', '',
        '## 各宮制（對照 0.6.2）', '',
        '| 宮制 | 星盤數 | 有變化的星盤 | 變化比例 | 有效宮號改變的點 | 未定義的點 | 修正 13→1 的點 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for code in suite['house_systems']:
        s = current['by_system'][code]
        lines.append(f"| {code} {HOUSE_SYSTEMS[code]} | {s['charts']} | {s['changed_charts']} | {s['changed_charts']/s['charts']:.1%} | {s['assigned_to_different_house']} | {s['undefined_points']} | {s['patched_points']} |")
    lines += ['', '## 天體與軸點分開看', '',
        '| 分組 | 點數 | 有變化的星盤 | 變動點數 | 未定義點數 |', '|---|---:|---:|---:|---:|']
    for label, s in [('十顆主要天體', current['by_scope']['major10']),
                      ('直接計算 16 點（含真北交點、五顆小行星）', current['direct16']),
                      ('南交點、幸運點', current['by_scope']['other_derived2']),
                      ('ASC、MC', current['by_scope']['axes2'])]:
        lines.append(f"| {label} | {s['points']} | {s['changed_charts']} | {s['changed_points']} | {s['undefined_points']} |")
    lines += ['', '16 點包含上述十顆主要天體，不能把這兩列相加。不同分組的星盤數也可能重疊。歸宮定義改變所造成的差異，不直接稱為錯誤率；ASC／MC 邊界問題與 Azimuth 已知差異也保留在結果中。', '',
        '## 南北半球與緯度分布', '',
        '| 分組 | 星盤數 | 有變化的星盤 | 變化比例 | 變動點數 | 未定義點數 |', '|---|---:|---:|---:|---:|---:|']
    for key, label in [('north', '北半球'), ('south', '南半球')]:
        s = current['by_hemisphere'][key]
        lines.append(f"| {label} | {s['charts']} | {s['changed_charts']} | {s['changed_charts']/s['charts']:.1%} | {s['changed_points']} | {s['undefined_points']} |")
    for key, s in current['by_band'].items():
        lines.append(f"| {key} | {s['charts']} | {s['changed_charts']} | {s['changed_charts']/s['charts']:.1%} | {s['changed_points']} | {s['undefined_points']} |")
    lines += ['', '緯度分組沿用固定案例：低緯 |lat|<23.5°；中緯 23.5°≤|lat|<50°；高緯 50°≤|lat|<66.5°。', '',
        '## 第十三宮修正與未定義結果', '',
        f"- 共 {total['patched_points']} 個原始 13.0 改為 1.0；原始值、修正原因及案例在 patches.json。",
        f"- 共 {total['undefined_points']} 個點、{total['undefined_charts']} 張盤沒有有效 house_pos，完整清單在 undefined.json。這些未定義結果計入變動，不從分母移除。",
        '- 不把本次補正解讀成已處理所有宮界問題；Placidus 的 12.999…／9.999… 等結果仍會造成相鄰宮分歧。', '',
        '## 全部有變化的星盤（對照 0.6.2）', '',
        '宮號以「舊→新」表示，未定義寫成「未定義」。完整小數、實際黃緯、UTC 與經緯度見 JSON。', '',
        '| 案例 | 當地時間 | 城市 | 宮制 | 變動點 |', '|---|---|---|---|---|']
    by_case = {}
    for p in comparisons['0.6.2']:
        if p['different']:
            by_case.setdefault(p['case'], []).append(p)
    for case in cases:
        changed = by_case.get(case['id'])
        if not changed:
            continue
        r = changed[0]
        detail = '；'.join(f"{p['name']} {p['old_house'] if p['old_house'] is not None else '空值'}→{p['new_house'] if p['new_house'] is not None else '未定義'}" for p in changed)
        lines.append(f"| {r['case']} | {r['local_iso']} | {r['city_name']} | {r['system']} | {detail} |")
    lines += ['', '## 證據與重跑', '',
        '- results.jsonl.gz：1200 張完整候選星盤、每個點的 API 原值／修正值、逐值數值投影與實際耗時。',
        '- summary.json：兩個基準的各宮制／半球／緯度／城市／天體分組統計。',
        '- differences-vs-0.6.0.json、differences-vs-0.6.2.json：全部差異點及原始輸入。',
        '- manifest.json、verification.json、protected-before.json：執行完整性、雜湊與基準／依賴保護核對。',
        '- verification.json 的 passed 只表示稽核完整且資料保護通過，不表示候選結果與基準相同，也不表示已適合切換正式排盤。', '',
        '```powershell', '.venv-desktop/Scripts/python.exe scripts/audit_house_number2.py --output results/numerical/NEW-DIRECTORY',
        f'.venv-desktop/Scripts/python.exe scripts/audit_house_number2.py --output {output.relative_to(ROOT).as_posix()} --verify-only', '```', '']
    (output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')


def verify(output):
    manifest = nr.read(output / 'manifest.json')
    assert manifest['complete']
    for name, digest in manifest['artifacts_sha256'].items():
        assert nr.sha(output / name) == digest, name
    for name, digest in nr.read(output / 'protected-before.json').items():
        assert nr.sha(ROOT / name) == digest, name
    for version in VERSIONS:
        nr.verify_seal(ROOT / 'regression/baselines' / version)
    env = nr.read(output / 'environment.json')
    count = 0
    for package in env['dependencies'].values():
        for name, digest in package['files'].items():
            assert nr.sha(ROOT / '.venv-desktop/Lib/site-packages' / name) == digest, name
            count += 1
    suite, cases, baselines = load_baselines()
    records = rows(output / 'results.jsonl.gz')
    assert len(records) == 1200 and {r['id'] for r in records} == {c['id'] for c in cases}
    counts = Counter(); changed = {v: set() for v in ('0.6.0', '0.6.2')}; points_changed = Counter()
    for r in records:
        chart = r['raw']; current = baselines['0.6.2'][2][r['id']]['raw']
        assert r['numeric'] == nr.exact(nr.numeric_projection(chart))
        assert without_houses(current) == without_houses(chart)
        b = chart['input']; t = chart['times']
        for p, audit in zip(chart['all_points'], r['house_position_audit'], strict=True):
            assert audit['point_id'] == p['id'] and audit['house'] == p['house']
            expected_args = [(t['erfa_gast_deg'] + b['longitude']) % 360, b['latitude'],
                             t['erfa_true_obliquity_deg'], p['lon'], p['lat'], b['system']]
            assert nr.exact(audit['arguments']) == nr.exact(expected_args)
            counts['points'] += 1; counts['nonzero_latitudes'] += p['lat'] != 0
            raw = audit['raw_position']
            assert audit['position'] == (1.0 if raw == 13.0 else raw)
            assert audit['correction'] == ('exact_13_to_1' if raw == 13 else None)
            if raw == 13:
                counts['patched'] += 1
            if raw == 0:
                assert b['system'] == 'K' and p['house'] is None and audit['status'] == 'undefined'
                counts['undefined'] += 1
            else:
                assert p['house'] == math.floor(audit['position']) and 1 <= p['house'] <= 12
            for version in changed:
                old = next(x for x in baselines[version][2][r['id']]['raw']['all_points'] if x['id'] == p['id'])
                if old['house'] != p['house']:
                    changed[version].add(r['id']); points_changed[version] += 1
        assert {p['id']: p for p in chart['points']} == {p['id']: p for p in chart['all_points']}
    assert counts['points'] == 24000
    summary = nr.read(output / 'summary.json')
    for version in changed:
        assert len(changed[version]) == summary[version]['total']['changed_charts']
        assert points_changed[version] == summary[version]['total']['changed_points']
    assert counts['patched'] == summary['0.6.2']['total']['patched_points']
    assert counts['undefined'] == summary['0.6.2']['total']['undefined_points']
    assert not manifest['guard_events']
    report = dict(passed=True, charts=1200, counts=dict(counts), baseline_seals=list(VERSIONS),
                  unchanged_dependency_files=count, protected_files=len(nr.read(output / 'protected-before.json')),
                  changed_charts={v: len(ids) for v, ids in changed.items()}, changed_points=dict(points_changed),
                  numerical_fields_except_house_exact=True, inputs_and_actual_latitudes_preserved=True)
    nr.write(output / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    suite, cases, baselines = load_baselines()
    platform.platform(); platform.machine()
    from guard import RuntimeGuard
    guard = RuntimeGuard(); guard.install()
    from desktop.model import ChartEngine, BirthInput
    from desktop.house_positions import house_number2, HOUSE_NUMBER2_POLICY
    before = nr.provenance()
    for key in ('dependencies', 'data', 'locks', 'core_sources', 'harness_sources'):
        assert before[key] == baselines['0.6.2'][1][key], key
    protected = protect()
    nr.write(output / 'protected-before.json', protected)
    nr.write(output / 'environment.json', before)
    nr.write(output / 'cases.json', dict(cities=suite['cities'], house_systems=suite['house_systems'], cases=cases))
    engine = ChartEngine(); records = []; patched = undefined = 0
    with gzip.open(output / 'results.jsonl.gz', 'xt', encoding='utf-8', newline='\n') as stream:
        for index, case in enumerate(cases, 1):
            tick = time.perf_counter()
            chart = engine.calculate(BirthInput(**case['input']), {int(k): v for k, v in case['orbs'].items()})
            reference = baselines['0.6.2'][2][case['id']]
            assert nr.exact(nr.numeric_projection(chart)) == reference['result']['values'], case['id']
            assert nr.exact(chart) == nr.exact(reference['raw']), case['id']
            candidate = copy.deepcopy(chart); audit_rows = []
            b = chart['input']; t = chart['times']
            with engine.lock:
                for p in candidate['all_points']:
                    args = [(t['erfa_gast_deg'] + b['longitude']) % 360, b['latitude'],
                            t['erfa_true_obliquity_deg'], p['lon'], p['lat'], b['system']]
                    audit = dict(point_id=p['id'], arguments=args)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        p['house'] = house_number2(*args, audit=audit)
                    audit['warnings'] = [str(w.message) for w in caught]
                    audit_rows.append(audit)
                    patched += bool(audit['correction']); undefined += audit['status'] == 'undefined'
            placed = {p['id']: p['house'] for p in candidate['all_points']}
            for p in candidate['points']:
                p['house'] = placed[p['id']]
            record = dict(id=case['id'], raw=candidate, numeric=nr.exact(nr.numeric_projection(candidate)),
                          house_position_audit=audit_rows, current_engine_exact_match=True,
                          elapsed_seconds=time.perf_counter() - tick)
            records.append(record); stream.write(nr.dumps(record) + '\n'); stream.flush()
            if index % 50 == 0:
                print(f'{index}/1200; {time.perf_counter()-started:.3f}s; patched={patched}; undefined={undefined}', flush=True)
    assert nr.provenance() == before
    assert protect() == protected
    assert not guard.events and 'swisseph' not in sys.modules
    summaries = analyze(output, suite, cases, baselines, records)
    artifacts = {p.name: nr.sha(p) for p in output.iterdir() if p.is_file()}
    nr.write(output / 'manifest.json', dict(complete=True, created_utc=datetime.now(timezone.utc).isoformat(),
        policy=HOUSE_NUMBER2_POLICY, charts=1200, api_calls=24000, baseline_versions=list(VERSIONS),
        current_engine_exact_matches=1200, guard_events=guard.events, artifacts_sha256=artifacts,
        sources_sha256={p: nr.sha(ROOT / p) for p in SOURCES}, elapsed_seconds=time.perf_counter() - started))
    verify(output)
    print('COMPARISON', json.dumps({v: s['total'] for v, s in summaries.items()}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    options = parser.parse_args(); output_path = options.output.resolve()
    if not output_path.is_relative_to(ROOT / 'results/numerical'):
        parser.error('Output must be a new directory under results/numerical, never a baseline directory.')
    verify(output_path) if options.verify_only else run(output_path)
