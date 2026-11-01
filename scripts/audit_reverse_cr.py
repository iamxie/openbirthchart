# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Audit the eight authorized C/R rejection-to-success changes without resealing."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from complete_regression import load_run,read,write,sha,exact,semantic


def audit(folder):
    folder=Path(folder)
    baseline=ROOT/'regression/complete-v1/product-0.6.5'
    bm,bs,old=load_run(baseline);cm,cs,new=load_run(folder/'product')
    originals={r['case']:r for r in read(ROOT/'tests/fixtures/reverse-cr-original-cusps.json')}
    assert len(originals)==8 and bs==cs
    assert not cm['unexpected_errors'] and not cm['guard_events']
    changes=[];unexpected=[];unchanged=0
    from desktop.model import house_direction
    for a,b in zip(old,new,strict=True):
        assert a['id']==b['id']
        if exact(semantic(a))==exact(semantic(b)):
            unchanged+=1;continue
        ident=a['id']
        if ident not in originals:
            unexpected.append(dict(id=ident,before=semantic(a),after=semantic(b)));continue
        assert a['status']=='UserError' and b['status']=='ok'
        assert a['input']==b['input'] and a['time_context']==b['time_context']
        chart=b['raw'];original=originals[ident]
        assert chart['cusps']==original['cusps'] and house_direction(chart['cusps'])==-1
        assert [chart['asc'],chart['mc']]==original['angles'][:2]
        changes.append(dict(id=ident,before=a['status'],after=b['status'],input=b['input'],
            direction=-1,original_cusps_and_axes_unchanged=True,
            houses={p['name']:p['house'] for p in chart['all_points']}))
    before=read(baseline/'environment.json');after=read(folder/'product/environment.json')
    changed_sources=[p for p,h in before['core_sources'].items() if after['core_sources'].get(p)!=h]
    assert changed_sources==['desktop/model.py']
    assert {k:v for k,v in before.items() if k!='core_sources'}=={k:v for k,v in after.items() if k!='core_sources'}
    protected=read(folder/'protected-before.json')
    altered=[p for p,h in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    write(folder/'preservation-check.json',dict(files=len(protected),changed=altered,passed=not altered))
    write(folder/'unexpected-differences.json',unexpected)
    result=dict(passed=not unexpected and unchanged==2008 and len(changes)==8 and not altered,
        total=2016,unchanged_exact=unchanged,changed_cases=changes,unexpected_cases=len(unexpected),
        unchanged_inputs_and_time_context=True,changed_core_sources=changed_sources,
        other_environment_fields_equal=True,baseline_statuses=bm['statuses'],candidate_statuses=cm['statuses'],
        baseline_manifest_sha256=sha(baseline/'manifest.json'),candidate_manifest_sha256=sha(folder/'product/manifest.json'))
    write(folder/'impact.json',result)
    print('Passed:',result['passed'],'unchanged:',unchanged,'authorized changes:',len(changes),'unexpected:',len(unexpected))
    assert result['passed']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path)
    audit(parser.parse_args().folder)
