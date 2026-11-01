# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Explicit 0.6.1 -> 0.6.2 audit; only 40 archived ASC/MC house changes allowed."""
import argparse,copy
from pathlib import Path
from numerical_regression import ROOT,load_run,read,write,differences,verify_seal,exact,sha

def audit(candidate,output):
    baseline=ROOT/'regression/baselines/0.6.1';verify_seal(baseline)
    bm,be,br=load_run(baseline);cm,ce,cr=load_run(candidate)
    assert cm['cases_sha256']==bm['cases_sha256'],'Case inputs or expected outcomes changed'
    assert not cm['unexpected_outcomes'] and not cm['guard_events']
    assert cm['contracts']==bm['contracts']
    assert ce['app_version']=='0.6.2'
    for key in ('dependencies','data','locks'):assert ce[key]==be[key],key
    fixtures=read(ROOT/'tests/fixtures/axis-boundary-original.json')
    approved={f['id']:f['changes'] for f in fixtures}
    assert len(approved)==39 and sum(map(len,approved.values()))==40
    unplanned=[];changed=[];unchanged=0;azimuth=0
    for ident,before in br.items():
        after=cr[ident];expected=copy.deepcopy(before['result']);raw=copy.deepcopy(before['raw'])
        if isinstance(raw,dict) and 'version' in raw:raw['version']='0.6.2'
        if ident in approved:
            assert raw['input']['system'] in ('U','X')
            for name,change in approved[ident].items():
                point=next(p for p in raw['all_points'] if p['name']==name)
                assert point['id'] in (-2,-3) and point['house']==change['before']
                assert change['after']==(1 if point['id']==-2 else 10)
                expected['values']['all_points'][str(point['id'])]['house']=change['after']
                for key in ('all_points','points'):
                    next(p for p in raw[key] if p['id']==point['id'])['house']=change['after']
                changed.append(dict(case_id=ident,point_id=point['id'],before=change['before'],after=change['after']))
        else:unchanged+=1
        for kind,a,b in [('numerical',expected,after['result']),('raw_except_version',exact(raw),exact(after['raw']))]:
            unplanned.extend(dict(case_id=ident,comparison=kind,**d) for d in differences(a,b))
        if isinstance(raw,dict) and raw.get('input',{}).get('system')=='H':
            assert before['result']==after['result'],'Azimuth calculation changed'
            azimuth+=1
    assert unchanged==1248 and azimuth==101 and len(changed)==40
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    summary=dict(passed=not unplanned,total=1287,changed_charts=39,changed_axis_houses=40,
        resolved_missing_houses=sum(x['before'] is None for x in changed),unchanged_charts=unchanged,
        azimuth_unchanged=azimuth,unplanned_fields=len(unplanned),cases_unchanged=True,
        ephemeris_and_dependencies_unchanged=True,changes=changed)
    write(output/'summary.json',summary);write(output/'unplanned-differences.json',unplanned)
    print('Axis migration audit:',summary['passed'],'39 charts / 40 axis houses; 1248 unchanged; 101 Azimuth unchanged')
    return 0 if summary['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(audit(a.run,a.output))
