# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Separate, immutable-input captures for both house-latitude modes."""
from __future__ import annotations
import argparse, copy, gzip, hashlib, json, os, platform, shutil, sys, time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
OUT=ROOT/'results/numerical/latitude-mode-20261031'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def protect():
    OUT.mkdir(exist_ok=False)
    old=read(ROOT/'results/numerical/azimuth-self-consistency-20261031/protected-before.json')
    editable=('desktop/','scripts/','translations/','templates/','docs/')
    paths={p for p in old if not p.startswith(editable) and p not in ('HANDOFF.md','TODO.md','DESKTOP_README.md')}
    for folder in ('regression','tests/fixtures'):
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob('*') if p.is_file())
    write(OUT/'protected-before.json',{p:sha(ROOT/p) for p in sorted(paths)})
    for folder in ('desktop','scripts','translations','templates/report'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                dest=OUT/'source-before'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    print('Protected files:',len(paths),flush=True)

ENGINE=None;GUARD=None
def init():
    global ENGINE,GUARD
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    platform.platform();platform.machine()
    from guard import RuntimeGuard
    GUARD=RuntimeGuard();GUARD.install()
    from desktop.model import ChartEngine
    ENGINE=ChartEngine()
def task(cases):
    from numerical_regression import execute_case
    rows=[]
    for case in cases:
        tick=time.perf_counter();row=execute_case(ENGINE,case)
        row['elapsed_seconds']=time.perf_counter()-tick;rows.append(row)
    assert not GUARD.events,GUARD.events
    return rows
def capture(suite,mode):
    path=ROOT/('regression/complete-v1/cases.json' if suite=='complete' else 'regression/cases-v2.json')
    original=read(path);cases=copy.deepcopy(original['cases']);enabled=mode=='on'
    for c in cases:
        if c['kind']=='chart':c['input']['house_latitude']=enabled
    folder=OUT/'final'/(suite+'-'+mode);folder.mkdir(parents=True,exist_ok=False)
    write(folder/'cases.json',dict(original,cases=cases))
    from numerical_regression import provenance
    before=provenance();write(folder/'environment.json',before)
    sources={p.relative_to(ROOT).as_posix():sha(p) for top in ('desktop','templates/report','translations')
             for p in (ROOT/top).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    sources['scripts/latitude_mode_audit.py']=sha(Path(__file__))
    write(folder/'application-sources.json',sources)
    for name in sources:
        dest=folder/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    start=time.perf_counter();collected={}
    with ProcessPoolExecutor(max_workers=12,initializer=init) as pool:
        futures=[pool.submit(task,cases[i:i+28]) for i in range(0,len(cases),28)]
        for f in as_completed(futures):
            for r in f.result():collected[r['id']]=r
    rows=[collected[c['id']] for c in cases]
    with gzip.open(folder/'results.jsonl.gz','wt',encoding='utf-8',newline='\n') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    assert before==provenance(),'Environment changed during capture'
    assert all(sha(ROOT/p)==h for p,h in sources.items()),'Application changed during capture'
    summary=dict(cases=len(rows),workers=12,elapsed_seconds=time.perf_counter()-start,
                 outcomes=dict(Counter(r['result']['status'] for r in rows)),
                 guard_events=[],input_sha256=sha(path),house_latitude=enabled)
    write(folder/'summary.json',summary);print(summary,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['protect','capture','all'])
    p.add_argument('--suite',choices=['complete','legacy']);p.add_argument('--mode',choices=['on','off'])
    p.add_argument('--output',type=Path,default=OUT);a=p.parse_args();OUT=a.output.resolve()
    if a.action=='capture' and (a.suite is None or a.mode is None):p.error('capture requires --suite and --mode')
    if a.action=='protect':protect()
    elif a.action=='capture':capture(a.suite,a.mode)
    else:
        for suite in ('complete','legacy'):
            for mode in ('on','off'):capture(suite,mode)
