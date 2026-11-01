# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Separate diagnostic experiment. Shared reference inputs are NOT a production workaround."""
import argparse
import importlib
import math
import os
from common import ROOT, read, dump, angular_delta, configure_core

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('engine',choices=['core','reference']); args=parser.parse_args()
    cases=read(ROOT/'cases.json')
    guard=None
    if args.engine=='core':
        configure_core()
        from guard import RuntimeGuard
        guard=RuntimeGuard(); guard.install()
        import libephemeris as e
        import erfa
        reference=read(ROOT/'results/diagnostic-reference.json')
        refs={r['id']:r for r in reference['times']}
    else:
        import swisseph as e
        e.set_ephe_path(str(ROOT/'data/reference'))
    result={'times':[],'geometry':[],'houses':[],'aligned_ut_planets':[]}
    for epoch in cases['epochs']:
        jd=epoch['jd']
        row=dict(epoch, delta_t_seconds=e.deltat(jd)*86400, sidtime_deg=e.sidtime(jd)*15)
        row['eps_true_deg']=e.calc(jd+e.deltat(jd),-1,2)[0][0]
        if args.engine=='core':
            row['skyfield_delta_t_seconds']=float(e.state.get_timescale().ut1_jd(jd).delta_t)
            row['erfa_gast_deg']=math.degrees(erfa.gst06a(jd,0,jd+e.deltat(jd),0))%360
        result['times'].append(row)
    # Same input geometry isolates house trigonometry from sidereal-time/obliquity conventions.
    for lat in (0,23,51.5,-33.8,65.5,-65.5):
        for armc in (0,45,90,123.456,180,270,359.99):
            for system in ('P','K','O','E','W'):
                cusps,angles=e.houses_armc(armc,lat,23.436,system.encode())
                result['geometry'].append({'id':f'{lat}:{armc}:{system}','cusps':list(cusps),'angles':list(angles)})
    for case in cases['houses']:
        row=dict(case)
        if args.engine=='core':
            module=importlib.import_module('libephemeris.houses')
            armc0,eps=module._house_armc_obliquity(case['jd'])
            row.update(armc0=armc0,eps=eps)
            ref=refs[case['epoch']]
            cusps,angles=e.houses_armc((ref['sidtime_deg']+case['lon'])%360,case['lat'],ref['eps_true_deg'],case['system'].encode())
            row.update(shared_input_cusps=list(cusps),shared_input_angles=list(angles))
        else:
            ref=next(r for r in result['times'] if r['id']==case['epoch'])
            row.update(armc0=ref['sidtime_deg'],eps=ref['eps_true_deg'])
        result['houses'].append(row)
    if args.engine=='core':
        summary=read(ROOT/'results/summary.json')
        ids={r['id'].split(':')[0] for r in summary['worst_planet_rows'][:15]}
        ids.update(c['id'] for c in cases['epochs'][::40])
        original={r['id']:r for r in read(ROOT/'results/reference.json')['planet_rows']}
        for epoch in cases['epochs']:
            if epoch['id'] not in ids: continue
            jd=epoch['jd']; dt=refs[epoch['id']]['delta_t_seconds']/86400
            for body in range(10):
                values,_=e.calc(jd+dt,body,258)
                ref=original[f'{epoch["id"]}:UT1:{body}']['values']
                result['aligned_ut_planets'].append({'id':f'{epoch["id"]}:{body}',
                    'values':list(values),'reference_values':ref,
                    'longitude_difference_arcsec':angular_delta(values[0],ref[0])*3600})
        result['guard_events']=guard.events
    dump(ROOT/f'results/diagnostic-{args.engine}.json',result)
    print(args.engine,'diagnostics done')

if __name__=='__main__':main()
