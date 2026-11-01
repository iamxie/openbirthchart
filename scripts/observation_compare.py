# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Unfitted observed-minus-computed residuals; angles are arcseconds, not RA seconds."""
from collections import Counter
import csv
import math
import statistics
import erfa
import numpy as np
from common import ROOT, read, dump, sha, angular_delta
from observation_data import load_records, selected_records

def vector(ra, dec):
    a,d=math.radians(ra),math.radians(dec)
    return np.array([math.cos(d)*math.cos(a),math.cos(d)*math.sin(a),math.sin(d)])

def separation(a,b):
    u,v=vector(*a),vector(*b)
    return math.degrees(math.atan2(float(np.linalg.norm(np.cross(u,v))),float(np.dot(u,v))))*3600

def legacy_place(jd, position):
    # Mean dynamical J2000 -> true equator/equinox of date, IAU 1976/1980.
    # No fitted correction, aberration/light-time already included by each engine.
    v=erfa.pnm80(2451545.0,jd-2451545.0) @ vector(*position[:2])
    a,d=erfa.c2s(v)
    return [math.degrees(a)%360,math.degrees(d)]

def residual(observed,computed):
    return (angular_delta(observed[0],computed[0])*math.cos(math.radians(observed[1]))*3600,
            (observed[1]-computed[1])*3600, separation(observed,computed))

def stats(values):
    if not values: return None
    if not all(math.isfinite(v) for v in values): raise ValueError('Nonfinite residual')
    s=sorted(values)
    return dict(n=len(s),mean=statistics.mean(s),median=statistics.median(s),
                rms=math.sqrt(statistics.mean(v*v for v in s)),
                p95=s[math.ceil(len(s)*.95)-1],max=max(s),min=min(s))

def main():
    out=ROOT/'results/observations'; records=load_records(); observations=selected_records()
    engines={e:read(out/f'{e}.json') for e in ('core','reference')}
    expected={r['id'] for r in observations}
    keyed={}
    for e,result in engines.items():
        if result['source_sha256'] != sha(ROOT/'data/observations/planet.dat'): raise ValueError('Stale input')
        keyed[e]={r['id']:r for r in result['rows']}
        if len(keyed[e]) != len(result['rows']) or set(keyed[e]) != expected: raise ValueError('Missing/duplicate result')
    rows=[]
    for obs in observations:
        for mode in ('iau1976_1980','native'):
            positions={e:(legacy_place(obs['tt_jd'],keyed[e][obs['id']]['j2000'])
                          if mode=='iau1976_1980' else keyed[e][obs['id']]['native'][:2]) for e in engines}
            row=dict(obs,mode=mode,engine_separation_arcsec=separation(positions['core'],positions['reference']))
            y,m,d,_=erfa.d2dtf('TT',3,2451545.,obs['tt_jd']-2451545.)
            row['date_tt']=f'{y:04}-{m:02}-{d:02}'
            for e,pos in positions.items():
                row[e+'_ra_deg'],row[e+'_dec_deg']=pos
                row[e+'_frame_change_arcsec']=separation(legacy_place(obs['tt_jd'],keyed[e][obs['id']]['j2000']),keyed[e][obs['id']]['native'][:2])
                dra=ddec=sep=None
                if obs['ra_deg'] is not None:
                    # cos(dec) uses measured Dec if available, else calculated Dec.
                    dra=angular_delta(obs['ra_deg'],pos[0])*math.cos(math.radians(obs['dec_deg'] if obs['dec_deg'] is not None else pos[1]))*3600
                if obs['dec_deg'] is not None: ddec=(obs['dec_deg']-pos[1])*3600
                if obs['ra_deg'] is not None and obs['dec_deg'] is not None:
                    sep=separation([obs['ra_deg'],obs['dec_deg']],pos)
                row[e+'_oc_ra_cosdec_arcsec']=dra; row[e+'_oc_dec_arcsec']=ddec; row[e+'_separation_arcsec']=sep
            rows.append(row)
    with (out/'residuals.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    groups=[]
    for mode in ('iau1976_1980','native'):
        for body in ('Uranus','Neptune','Pluto'):
            for quality in ('all','unflagged','flagged'):
                rr=[r for r in rows if r['mode']==mode and r['body']==body and
                    (quality=='all' or (bool(r['flag']) == (quality=='flagged')))]
                group=dict(mode=mode,body=body,quality=quality,records=len(rr),
                           inter_engine=stats([r['engine_separation_arcsec'] for r in rr]))
                for e in engines:
                    group[e]={k:stats([r[e+'_'+k] for r in rr if r[e+'_'+k] is not None])
                              for k in ('oc_ra_cosdec_arcsec','oc_dec_arcsec','separation_arcsec','frame_change_arcsec')}
                groups.append(group)
    annual=[r for r in records if 2448257.5 <= r['tt_jd'] < 2448622.5]
    coverage={body:dict(first_tt=min(r['date_tt'] for r in rows if r['body']==body),
                        last_tt=max(r['date_tt'] for r in rows if r['body']==body),
                        monthly=dict(sorted(Counter(r['date_tt'][:7] for r in rows if r['body']==body and r['mode']=='iau1976_1980').items())))
              for body in ('Uranus','Neptune','Pluto')}
    summary=dict(catalogue_records=len(records),year=1991,all_objects_1991=len(annual),coverage=coverage,
                 object_counts_1991=dict(Counter(r['name'] for r in annual)),selected=len(observations),
                 selected_flagged=sum(bool(r['flag']) for r in observations),
                 selected_missing_ra=sum(r['ra_deg'] is None for r in observations),
                 selected_missing_dec=sum(r['dec_deg'] is None for r in observations),
                 erfa_version=erfa.__version__,groups=groups,
                 hashes={p.name:sha(p) for p in [out/'core.json',out/'reference.json',out/'residuals.csv']})
    dump(out/'summary.json',summary)
    for g in groups:
        if g['mode']=='iau1976_1980' and g['quality']=='unflagged': print(g['body'],g['records'],g['core']['separation_arcsec'],g['reference']['separation_arcsec'],'inter',g['inter_engine'])
    print('Selected',len(observations),'flagged',summary['selected_flagged'],'missing',summary['selected_missing_ra'],summary['selected_missing_dec'])

if __name__=='__main__': main()
