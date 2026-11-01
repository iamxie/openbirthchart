# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Legacy 1287-case exact regression against historical releases.

Current dual-mode 1200-case regression is routed by verify-numerics.ps1.
No automatic baseline updates or tolerance passes.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata as metadata
import json
import math
from pathlib import Path
import platform
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
CASES = ROOT / 'regression/cases-v1.json'
BASELINE = ROOT / 'regression/baselines/0.6.0'
# Legacy constants above remain available to the original diagnostic scripts.
# This historical CLI retains its 1287-case reference; the current 1200-case
# baseline is selected separately through regression/main-current.json.
CURRENT_CASES = ROOT / 'regression/cases-v2.json'
CURRENT_BASELINE = ROOT / 'regression/baselines/0.6.5'
CORE = ['desktop/model.py','desktop/house_positions.py','desktop/azimuth.py','desktop/polich.py','desktop/leap_seconds.py','desktop/errors.py','scripts/common.py','scripts/utc_times.py','config/isolated.toml']
LOCKS = ['requirements/desktop.lock','requirements/core.lock','data-sources.lock.json',
         'desktop-data-sources.lock.json','time-data-sources.lock.json']
PACKAGES = ['libephemeris','skyfield','skyfield-data','jplephem','numpy','pyerfa','tzdata']

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def dumps(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def exact(value):
    if isinstance(value,float):
        if not math.isfinite(value): raise ValueError('Non-finite calculation output')
        return {'$float':value.hex()}
    if isinstance(value,dict): return {str(k):exact(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [exact(v) for v in value]
    return value

def numeric_projection(chart):
    """Keep computation/state; omit presentation and version labels. Raw output is also saved."""
    result = {k:v for k,v in chart.items() if k not in
              {'version','tzdata_version','notes','timezone_mode','all_points','points','aspects'}}
    result['times'] = {k:v for k,v in chart['times'].items() if k!='erfa_warnings'}
    result['all_points'] = {str(p['id']):{k:v for k,v in p.items() if k not in {'name','short','color'}}
                            for p in chart['all_points']}
    result['visible_point_ids'] = [p['id'] for p in chart['points']]
    ids = {p['name']:p['id'] for p in chart['all_points']}
    result['aspects'] = {f"{ids[a['a']]}:{ids[a['b']]}:{a['angle']}":
                         {k:v for k,v in a.items() if k not in {'a','b','name','color'}} for a in chart['aspects']}
    return result

def coverage(suite):
    cases = suite['cases']; ids = [c['id'] for c in cases]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate case IDs')
    main = [c for c in cases if c['group']=='balanced']
    city_ids = [c['id'] for c in suite['cities']]
    systems = suite['house_systems']
    cities = Counter(c['city'] for c in main)
    houses = Counter(c['input']['system'] for c in main)
    pairs = Counter((c['city'],c['input']['system']) for c in main)
    months = Counter(c['input']['local_iso'][:7] for c in main)
    city_months = Counter((c['city'],c['input']['local_iso'][5:7]) for c in main)
    if len(main)!=1200 or len(city_ids)!=12 or len(systems)!=14: raise ValueError('Incomplete suite')
    if set(cities)!=set(city_ids) or set(cities.values())!={100}: raise ValueError('City imbalance')
    if set(houses)!=set(systems) or not set(houses.values())<={85,86}: raise ValueError('House imbalance')
    if len(pairs)!=168 or not set(pairs.values())<={7,8}: raise ValueError('City/house imbalance')
    if len(city_months)!=144 or not set(city_months.values())<={8,9}: raise ValueError('City/month imbalance')
    if set(months)!={f'{y}-{m:02}' for y in range(1927,2027) for m in range(1,13)} or set(months.values())!={1}:
        raise ValueError('Missing year/month')
    # Inputs must remain tied to the documented representative city point.
    for case in main:
        city = next(c for c in suite['cities'] if c['id']==case['city'])
        if any(case['input'][k]!=city[k] for k in ('latitude','longitude','zone')):
            raise ValueError('City coordinates/timezone mismatch: '+case['id'])
        if case['expected']!='ok': raise ValueError('Balanced cases must be successful charts')
    return dict(total=len(cases),balanced=1200,boundary=len(cases)-1200,city_counts=dict(cities),
                house_counts=dict(houses),city_house_counts={c:{h:pairs[c,h] for h in systems} for c in city_ids},
                city_month_counts={c:{str(m):city_months[c,f'{m:02}'] for m in range(1,13)} for c in city_ids})

def provenance():
    from desktop.model import APP_VERSION
    packages = {}
    for name in PACKAGES:
        try: dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            if name=='skyfield-data': continue
            raise
        files = {}
        for item in dist.files or []:
            if '__pycache__' in item.parts or item.suffix=='.pyc' or item.name=='RECORD': continue
            path = Path(dist.locate_file(item))
            if path.is_file(): files[item.as_posix()] = sha(path)
        packages[name] = dict(version=dist.version,files=files)
    data = {}
    for manifest in LOCKS[2:]:
        for item in read(ROOT/manifest)['files']:
            if item['path'].startswith('data/reference/'): continue
            digest = sha(ROOT/item['path'])
            if digest!=item['sha256']: raise ValueError('Data integrity failure: '+item['path'])
            data[item['path']] = digest
    return dict(app_version=APP_VERSION,python=sys.version,platform=platform.platform(),machine=platform.machine(),
                core_sources={p:sha(ROOT/p) for p in CORE},locks={p:sha(ROOT/p) for p in LOCKS},
                harness_sources={p:sha(ROOT/p) for p in ['scripts/numerical_regression.py','scripts/generate_numerical_cases.py']},
                data=data,dependencies=packages)

def execute_case(engine,case):
    from desktop.model import BirthInput,house_number,find_aspects
    try:
        if case['kind']=='chart':
            raw=engine.calculate(BirthInput(**case['input']),{int(k):v for k,v in case['orbs'].items()})
            values=numeric_projection(raw)
        elif case['kind']=='house':
            raw=values=house_number(case['longitude'],case['cusps'])
        elif case['kind']=='aspect':
            raw=find_aspects(case['points'],orbs={int(k):v for k,v in case['orbs'].items()})
            values=[{k:v for k,v in a.items() if k not in {'color','name'}} for a in raw]
        elif case['kind']=='time':
            raw=engine.authority.convert(case['utc'],allow_model=True)
            values={k:v for k,v in raw.items() if k!='erfa_warnings'}
        else: raise ValueError('Unknown case kind: '+case['kind'])
        result=dict(status='ok',values=exact(values))
    except Exception as exc:
        raw=dict(type=type(exc).__name__,source=getattr(exc,'source',str(exc)),values=getattr(exc,'values',{}))
        if hasattr(exc,'diagnostics'):raw['diagnostics']=exc.diagnostics
        result=dict(status=type(exc).__name__,error=exact(raw))
    return dict(id=case['id'],result=result,raw=raw,expected_outcome_met=result['status']==case['expected'])

def run(output,cases_path=CASES,reverse=False):
    # Freeze the exact bytes used for calculation before any lengthy setup.
    # A concurrent edit must not make the archived inputs differ from those run.
    case_bytes=Path(cases_path).read_bytes()
    suite=json.loads(case_bytes); counts=coverage(suite)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    # Windows platform discovery may invoke a system helper; cache it before
    # installing the calculation guard (which must precede engine imports).
    platform.platform(); platform.machine()
    from guard import RuntimeGuard
    guard=RuntimeGuard();guard.install()
    from desktop.model import ChartEngine,HOUSE_SYSTEMS,ASPECTS
    if set(HOUSE_SYSTEMS)!=set(suite['house_systems']): raise ValueError('House system coverage needs review')
    before=provenance()
    write(output/'environment.json',before)
    (output/'cases.json').write_bytes(case_bytes)
    engine=ChartEngine()
    outcomes=Counter(); failures=[]
    cases=list(reversed(suite['cases'])) if reverse else suite['cases']
    with gzip.open(output/'results.jsonl.gz','wt',encoding='utf-8',newline='\n') as stream:
        for i,case in enumerate(cases,1):
            tick=time.perf_counter();record=execute_case(engine,case)
            record['elapsed_seconds']=time.perf_counter()-tick
            outcomes[record['result']['status']]+=1
            if not record['expected_outcome_met']: failures.append(case['id'])
            stream.write(dumps(record)+'\n');stream.flush()
            if i%50==0 or i==len(cases):
                print(f'{i}/{len(cases)} cases; {time.perf_counter()-started:.3f}s; unexpected={len(failures)}',flush=True)
    # Recheck source/dependency/data files to reject a mixed-environment run.
    after=provenance()
    if after!=before: raise ValueError('Environment changed during calculation; run is incomplete')
    contracts=exact(dict(default_orbs={str(a):o for a,_,o,_,_ in ASPECTS},house_systems=sorted(HOUSE_SYSTEMS)))
    manifest=dict(schema=1,complete=True,created_utc=datetime.now(timezone.utc).isoformat(),
                  cases_sha256=sha(output/'cases.json'),results_sha256=sha(output/'results.jsonl.gz'),
                  environment_sha256=sha(output/'environment.json'),coverage=counts,outcomes=dict(outcomes),
                  unexpected_outcomes=failures,guard_events=guard.events,contracts=contracts,
                  data_reads=sorted(str(Path(p).relative_to(ROOT)) if Path(p).is_relative_to(ROOT) else p for p in guard.data_reads),
                  elapsed_seconds=time.perf_counter()-started,order='reverse' if reverse else 'forward')
    write(output/'manifest.json',manifest)
    return manifest

def load_run(folder):
    folder=Path(folder); manifest=read(folder/'manifest.json')
    if manifest.get('schema')!=1 or not manifest.get('complete'): raise ValueError('Incomplete/unsupported run')
    for filename,key in [('cases.json','cases_sha256'),('results.jsonl.gz','results_sha256'),('environment.json','environment_sha256')]:
        if sha(folder/filename)!=manifest[key]: raise ValueError('Run integrity mismatch: '+str(folder/filename))
    suite=read(folder/'cases.json')
    if coverage(suite)!=manifest['coverage']: raise ValueError('Coverage manifest mismatch')
    with gzip.open(folder/'results.jsonl.gz','rt',encoding='utf-8') as stream:
        rows=[json.loads(line) for line in stream]
    records={r['id']:r for r in rows}
    if len(records)!=len(rows) or set(records)!={c['id'] for c in suite['cases']}: raise ValueError('Missing/duplicate/extra result IDs')
    for case in suite['cases']:
        record=records[case['id']]
        if record['expected_outcome_met']!=(record['result']['status']==case['expected']):
            raise ValueError('Outcome manifest mismatch')
    actual_failures=sorted(r['id'] for r in rows if not r['expected_outcome_met'])
    if actual_failures!=sorted(manifest['unexpected_outcomes']): raise ValueError('Failure inventory mismatch')
    if dict(Counter(r['result']['status'] for r in rows))!=manifest['outcomes']: raise ValueError('Outcome counts mismatch')
    return manifest,read(folder/'environment.json'),records

def float_node(value):
    return isinstance(value,dict) and set(value)=={'$float'}

def differences(old,new,path='$'):
    if type(old) is not type(new):
        yield dict(path=path,before=old,after=new,kind='type');return
    if float_node(old) and float_node(new):
        if old==new: return
        a,b=float.fromhex(old['$float']),float.fromhex(new['$float'])
        entry=dict(path=path,before=a,after=b,before_hex=old['$float'],after_hex=new['$float'],
                   kind='float',absolute_delta=abs(b-a))
        # Diagnostic units only: never use these differences to decide pass/fail.
        key=path.rsplit('/',1)[-1]
        if key in {'lon','a_lon','b_lon','asc','mc','erfa_gast_deg'} or '/cusps/' in path:
            delta=math.remainder(b-a,360.)
            entry.update(signed_angular_delta_degrees=delta,absolute_delta_arcseconds=abs(delta)*3600)
        if key in {'tt_jd','ut1_jd'}: entry['absolute_delta_seconds']=abs(b-a)*86400
        yield entry;return
    if isinstance(old,dict):
        for key in sorted(set(old)|set(new)):
            child=path+'/'+str(key).replace('~','~0').replace('/','~1')
            if key not in old or key not in new:
                yield dict(path=child,kind='added' if key not in old else 'removed',before=old.get(key),after=new.get(key))
            else: yield from differences(old[key],new[key],child)
    elif isinstance(old,list):
        if len(old)!=len(new): yield dict(path=path+'/length',before=len(old),after=len(new),kind='length')
        for i,(a,b) in enumerate(zip(old,new)): yield from differences(a,b,f'{path}/{i}')
        for i in range(min(len(old),len(new)),max(len(old),len(new))):
            yield dict(path=f'{path}/{i}',kind='added' if i>=len(old) else 'removed',
                       before=old[i] if i<len(old) else None,after=new[i] if i<len(new) else None)
    elif old!=new: yield dict(path=path,before=old,after=new,kind='value')

def compare(baseline,candidate,report):
    bm,be,br=load_run(baseline);cm,ce,cr=load_run(candidate)
    report=Path(report);report.mkdir(parents=True,exist_ok=False)
    problems=[]
    if bm['cases_sha256']!=cm['cases_sha256']: problems.append('Fixed inputs changed; comparisons are not valid')
    if bm['unexpected_outcomes'] or cm['unexpected_outcomes']: problems.append('Unexpected calculation outcomes')
    if bm['guard_events'] or cm['guard_events']: problems.append('Runtime guard violation')
    deltas=[];changed=[];raw_changed=[]
    if bm['cases_sha256']==cm['cases_sha256']:
        for ident in sorted(br):
            diff=list(differences(br[ident]['result'],cr[ident]['result']))
            if diff: changed.append(ident)
            deltas.extend(dict(case_id=ident,**d) for d in diff)
            if exact(br[ident]['raw'])!=exact(cr[ident]['raw']): raw_changed.append(ident)
        deltas.extend(dict(case_id='configuration',**d) for d in differences(bm['contracts'],cm['contracts']))
    env_diff=list(differences(be,ce))
    summary=dict(schema=1,passed=not problems and not deltas,baseline_version=be['app_version'],
                 candidate_version=ce['app_version'],cases=cm['coverage']['total'],
                 changed_cases=len(changed),changed_case_ids=changed,changed_fields=len(deltas),problems=problems,
                 environment_changed=bool(env_diff),environment_changed_fields=len(env_diff),
                 raw_changed_cases=len(raw_changed),raw_only_changed_cases=len(set(raw_changed)-set(changed)),
                 max_angular_delta_arcseconds=max((d.get('absolute_delta_arcseconds',0) for d in deltas),default=0),
                 candidate_elapsed_seconds=cm['elapsed_seconds'],baseline_cases_sha256=bm['cases_sha256'],
                 candidate_cases_sha256=cm['cases_sha256'])
    write(report/'summary.json',summary);write(report/'differences.json',deltas);write(report/'environment-differences.json',env_diff)
    with (report/'differences.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=['case_id','path','kind','before','after','before_hex','after_hex','absolute_delta',
                'signed_angular_delta_degrees','absolute_delta_arcseconds','absolute_delta_seconds']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in deltas:
            writer.writerow({k:dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    lines=['# 數值一致性比對', '',f"結果：{'通過' if summary['passed'] else '未通過'}（完整精度逐值比對，無自動容差放行）",'',
           f"基準 {be['app_version']} → 本次 {ce['app_version']}；{summary['cases']} 筆案例；{len(changed)} 筆計算結果改變；{len(deltas)} 個欄位差異。",
           f"本次執行時間：{cm['elapsed_seconds']:.6f} 秒；環境差異：{len(env_diff)} 個欄位。",'',
           '環境版本變更本身不代表數值漂移；請同時檢閱 environment-differences.json。',
           '完整原始輸出留在各次 results.jsonl.gz；顏色、文案、版本標籤不列入數值成敗。',
           '本檢查只證明這批案例與指定版本一致，不能證明天文正確性，也不涵蓋所有輸入。','']
    lines+=problems
    for d in deltas[:30]: lines.append(f"- {d['case_id']} {d['path']}: {d.get('before')} → {d.get('after')}")
    if len(deltas)>30: lines.append(f'其餘 {len(deltas)-30} 個差異見 differences.csv / differences.json。')
    (report/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(dumps(summary),flush=True)
    return 0 if summary['passed'] else 1

def seal(run_folder,destination,version,package=None):
    manifest,environment,_=load_run(run_folder)
    if manifest['unexpected_outcomes'] or manifest['guard_events']: raise ValueError('Cannot seal a failed run')
    if environment['app_version']!=version: raise ValueError('Baseline version does not match calculated version')
    evidence={}
    if version=='0.6.0':
        if package is None: raise ValueError('0.6.0 baseline requires original package source verification')
        package=Path(package)
        inventory=read(package/'package-manifest.json')
        expected={i['path']:i['sha256'] for i in inventory['files']}
        pinned=dict(re.findall(r'^([\w-]+)==([^\s]+)',(package/'source/requirements/desktop.lock').read_text(encoding='utf-8'),re.M))
        for name,info in environment['dependencies'].items():
            if pinned.get(name)!=info['version']: raise ValueError('Baseline dependency does not match original lock: '+name)
        for p,h in environment['core_sources'].items():
            if sha(package/'source'/p)!=h or expected['source/'+p]!=h: raise ValueError('Original package source differs: '+p)
        for p,h in environment['locks'].items():
            if sha(package/'source'/p)!=h or expected['source/'+p]!=h: raise ValueError('Original package lock differs: '+p)
        for p,h in environment['data'].items():
            if sha(package/'_internal'/p)!=h or expected['_internal/'+p]!=h: raise ValueError('Original package data differs: '+p)
        # Version evidence from the original wheel metadata in the package.
        for name,info in environment['dependencies'].items():
            matches=list((package/'_internal').glob(name.replace('-','_')+'-*.dist-info/METADATA'))
            if matches:
                text=matches[0].read_text(encoding='utf-8')
                if '\nVersion: '+info['version']+'\n' not in text: raise ValueError('Packaged dependency version differs: '+name)
        evidence=dict(package_manifest_sha256=sha(package/'package-manifest.json'),
                      executable_sha256=sha(package/'OpenBirthChart.exe'),
                      verified='Core source, requirement locks and shipped data match the original 0.6.0 package. Source runner, not frozen-executable numerical replay.')
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)  # NEVER overwrite an existing baseline.
    for name in ('manifest.json','environment.json','cases.json','results.jsonl.gz'):
        shutil.copyfile(Path(run_folder)/name,destination/name)
    write(destination/'origin.json',dict(version=version,evidence=evidence,
          policy='Frozen reference. Never regenerate to make a failing comparison pass. Keep old baselines after an approved change.'))
    write(destination/'SHA256SUMS.json',{p.name:sha(p) for p in destination.iterdir() if p.is_file()})
    print('Sealed baseline: '+str(destination))

def verify_seal(folder):
    sums=read(Path(folder)/'SHA256SUMS.json')
    required={'manifest.json','environment.json','cases.json','results.jsonl.gz','origin.json'}
    if set(sums)!=required: raise ValueError('Incomplete baseline seal')
    for name,digest in sums.items():
        if sha(Path(folder)/name)!=digest: raise ValueError('Baseline integrity failure: '+name)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ('run','check'):
        p=sub.add_parser(command);p.add_argument('--output',type=Path,required=True)
        p.add_argument('--cases',type=Path,default=CURRENT_CASES);p.add_argument('--reverse',action='store_true')
        if command=='check': p.add_argument('--baseline',type=Path,default=CURRENT_BASELINE)
    p=sub.add_parser('compare');p.add_argument('--baseline',type=Path,default=CURRENT_BASELINE)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p=sub.add_parser('seal');p.add_argument('--run',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True);p.add_argument('--version',required=True)
    p.add_argument('--original-package',type=Path)
    args=parser.parse_args()
    if args.command=='seal': seal(args.run,args.destination,args.version,args.original_package);return 0
    if args.command=='compare':
        verify_seal(args.baseline)
        return compare(args.baseline,args.run,args.report)
    if args.command=='check':
        verify_seal(args.baseline)
        if sha(args.cases)!=read(args.baseline/'manifest.json')['cases_sha256']:
            raise ValueError('Fixed inputs differ from baseline; refusing to run a substituted suite')
    manifest=run(args.output,args.cases,args.reverse)
    if args.command=='check': return compare(args.baseline,args.output,args.output/'comparison')
    return 1 if manifest['unexpected_outcomes'] or manifest['guard_events'] else 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print(f'REGRESSION ERROR: {type(exc).__name__}: {exc}',file=sys.stderr)
        raise SystemExit(2)
