# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Exact release check against explicitly selected reviewed source captures.

Does not replace a baseline. The sole permitted difference is raw chart version;
elapsed time is excluded by the existing capture semantic comparison.
"""
import argparse
import copy
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from complete_regression import environment,exact,load_run,read,run,semantic,sha,write
from desktop.model import APP_VERSION


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=(1,4,8,12),default=12)
    parser.add_argument('--resume',action='store_true',help='Reverify completed captures; never reuse an incomplete capture')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=args.resume)
    start=time.perf_counter();summaries=[]
    for suite,count in (('main',1200),('complete',2016),('boundary',87)):
        for mode in ('actual','zero'):
            before=args.reference/suite/('run-'+mode)
            ma,sa,old=load_run(before)
            assert ma['engine']=='product' and len(old)==count
            assert not ma['unexpected_errors'] and not ma['guard_events']
            after=args.output/(suite+'-'+mode)
            if not (args.resume and after.exists()):
                run(before/'cases.json',after,'product',args.workers)
            mb,sb,new=load_run(after)
            assert sa==sb and len(new)==count
            assert not mb['unexpected_errors'] and not mb['guard_events']
            ea=read(before/'environment.json');eb=read(after/'environment.json')
            assert eb==environment('product'),'Captured source or environment changed'
            for key in ('dependencies','data','locks','python'):assert ea[key]==eb[key],key
            assert eb['app_version']==APP_VERSION
            changed_versions=0;failures=[]
            for a,b in zip(old,new,strict=True):
                assert a['id']==b['id']
                a=copy.deepcopy(semantic(a));b=semantic(b)
                if a['status']=='ok' and isinstance(a['raw'],dict) and 'version' in a['raw']:
                    assert a['raw']['version']==ea['app_version']
                    assert b['raw']['version']==APP_VERSION
                    if a['raw']['version']!=b['raw']['version']:changed_versions+=1
                    a['raw']['version']=b['raw']['version']
                if exact(a)!=exact(b):failures.append(a['id'])
            pids=sorted({read(p)['payload']['pid'] for p in (after/'checkpoints').glob('*.json')})
            summary=dict(suite=suite,mode=mode,cases=count,version_only_changes=changed_versions,
                exact_except_version=not failures,unexpected_case_ids=failures,workers=args.workers,worker_pids=pids,
                reference=str(before.resolve()),reference_manifest_sha256=sha(before/'manifest.json'),
                candidate=str(after.resolve()),candidate_manifest_sha256=sha(after/'manifest.json'),
                pool_wall_seconds=mb['pool_wall_seconds'],capture_wall_seconds=mb['wall_seconds'])
            write(args.output/(suite+'-'+mode+'-comparison.json'),summary);summaries.append(summary)
            print(summary,flush=True)
            assert not failures,summary
    write(args.output/'verification.json',dict(version=APP_VERSION,status='passed',
        cases=sum(x['cases'] for x in summaries),allowed_difference='raw/version only; execution timing excluded',
        baseline_replaced=False,suites=summaries,wall_seconds=time.perf_counter()-start))


if __name__=='__main__':main()
