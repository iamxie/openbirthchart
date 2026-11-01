# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Separate core/reference processes; both consume independently prepared UTC times."""
import argparse
from datetime import datetime, timezone
import importlib.metadata as md
import sys
import time
from common import ROOT, BODIES, read, dump, sha, finite_vector, configure_core

def main():
    parser=argparse.ArgumentParser();parser.add_argument('engine',choices=['core','reference']);args=parser.parse_args()
    tick=time.perf_counter()
    cases=read(ROOT/'utc-cases.json')
    for item in read(ROOT/'data-sources.lock.json')['files']:
        if f'data/{args.engine}/' in item['path'] and sha(ROOT/item['path'])!=item['sha256']:
            raise RuntimeError('Ephemeris data hash mismatch')
    guard=None
    result=dict(engine=args.engine,started_utc=datetime.now(timezone.utc).isoformat(),
        cases_sha256=sha(ROOT/'utc-cases.json'),packages={d.metadata['Name']:d.version for d in md.distributions()},
        planets=[],houses=[],time_checks=[],errors=[])
    if args.engine=='core':
        result['configuration']=configure_core()
        from guard import RuntimeGuard
        guard=RuntimeGuard();guard.install();result['guard_self_test']=guard.self_test()
        import libephemeris as e
        assert e.get_calc_mode()=='skyfield'
    else:
        import swisseph as e
        e.set_ephe_path(str(ROOT/'data/reference'))
    flags=e.FLG_SWIEPH|e.FLG_SPEED
    times={row['id']:row for row in cases['times']}
    try:
        for index,row in enumerate(cases['times']):
            e.set_delta_t_userdef(e.DELTAT_AUTOMATIC)
            for stage in ('native','split'):
                for body in range(10):
                    values,rf=(e.calc_ut(row['ut1_jd'],body,flags) if stage=='native' else e.calc(row['tt_jd'],body,flags))
                    if args.engine=='reference' and rf&7!=e.FLG_SWIEPH: raise AssertionError('Moshier fallback')
                    result['planets'].append(dict(id=f'{row["id"]}:{stage}:{body}',epoch=row['id'],stage=stage,
                        body=BODIES[body],values=finite_vector(values,6),returned_flags=rf))
            if index%50==0: print(args.engine,'UTC epochs',index+1,'/',len(times),flush=True)
        for case in cases['houses']:
            row=times[case['epoch']]; delta=row['delta_t_seconds']/86400
            for stage in ('native','split','standard'):
                e.set_delta_t_userdef(e.DELTAT_AUTOMATIC if stage=='native' else delta)
                if stage=='split':
                    effective=e.deltat(row['ut1_jd'])*86400
                    if abs(effective-row['delta_t_seconds'])>1e-8: raise AssertionError('Delta T override ignored')
                if stage=='standard':
                    values=e.houses_armc((row['erfa_gast_deg']+case['lon'])%360,case['lat'],
                        row['erfa_true_obliquity_deg'],case['system'].encode())
                else: values=e.houses(row['ut1_jd'],case['lat'],case['lon'],case['system'].encode())
                result['houses'].append(dict(id=f'{case["id"]}:{stage}',case=case['id'],epoch=case['epoch'],
                    stage=stage,system=case['system'],location=case['location'],
                    cusps=finite_vector(values[0],12),angles=finite_vector(values[1],8)))
            e.set_delta_t_userdef(e.DELTAT_AUTOMATIC)
        for row in cases['times']:
            e.set_delta_t_userdef(row['delta_t_seconds']/86400)
            result['time_checks'].append(dict(id=row['id'],requested_tt=row['tt_jd'],
                delta_t_seconds=e.deltat(row['ut1_jd'])*86400,sidtime_deg=e.sidtime(row['ut1_jd'])*15))
    finally:
        e.set_delta_t_userdef(e.DELTAT_AUTOMATIC)
    if guard:
        result['loaded_swiss']=[name for name in sys.modules if name.split('.')[0] in ('swisseph','pysweph','pyswisseph')]
        result['installed_swiss']=[name for name in result['packages'] if 'swiss' in name.lower() or 'pysweph' in name.lower()]
        result['guard_events']=guard.events
        result['unexpected_guard_events']=[event for event in guard.events if event['phase']=='calculation']
        result['data_reads']=[dict(path=path,sha256=sha(path)) for path in sorted(guard.data_reads)]
        if result['unexpected_guard_events'] or result['loaded_swiss'] or result['installed_swiss']:
            raise RuntimeError('Forbidden core dependency')
    else: result['swiss_files']=[e.get_current_file_data(i) for i in (0,1)]
    result['elapsed_seconds']=time.perf_counter()-tick
    dump(ROOT/f'results/utc/{args.engine}.json',result)
    print(args.engine,'UTC complete',round(result['elapsed_seconds'],3),'seconds',flush=True)

if __name__=='__main__': main()
