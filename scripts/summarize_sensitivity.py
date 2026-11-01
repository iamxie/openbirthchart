# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Summarize observed finite changes, keeping Whole Sign steps separate."""
from array import array
from collections import defaultdict,Counter
import csv
import json
import math
from common import ROOT,read,dump,sha,finite_vector,angular_delta
from sensitivity_math import describe,sampled_span

FIELDS=[f'cusp_{i}' for i in range(1,13)]+['asc','mc']

def bucket():return {key:array('d') for key in ('cusps','chart_max','asc','mc')}

def main():
    out=ROOT/'results/sensitivity';config=read(ROOT/'sensitivity-cases.json');run=read(out/'run.json')
    for name,digest in run['output_hashes'].items():
        if sha(out/name)!=digest:raise ValueError(f'Changed measurement artifact: {name}')
    for name,digest in run['input_hashes'].items():
        if sha(ROOT/name)!=digest:raise ValueError(f'Changed measurement input: {name}')
    bases={}
    for line in (out/'baselines.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['id'] in bases:raise ValueError('Duplicate baseline')
        finite_vector(row['values'],14);bases[row['id']]=row
    groups=defaultdict(bucket);windows=defaultdict(lambda:array('d'));seen=set();steps=defaultdict(Counter)
    chart_rows=defaultdict(dict)
    with (out/'measurements.csv').open(encoding='utf-8',newline='') as stream:
        for row in csv.DictReader(stream):
            offset=int(row['offset_seconds']);cid=row['id'];key=(cid,offset)
            if key in seen or cid not in bases or offset not in config['offset_seconds']:raise ValueError('Duplicate/unexpected row')
            seen.add(key)
            deltas=finite_vector([row[f'{f}_arcsec'] for f in FIELDS],14)
            after=finite_vector([row[f'{f}_after_deg'] for f in FIELDS],14)
            if max(abs(angular_delta(a,b)*3600-d) for a,b,d in zip(after,bases[cid]['values'],deltas,strict=True))>1e-6:
                raise ValueError('Raw position and stored displacement disagree')
            chart_rows[cid][offset]=after
            for scope in (row['region'],row['location']):
                name=f'{scope}/{row["system"]}/{abs(offset)}'
                group=groups[name]
                group['cusps'].extend(deltas[:12]);group['chart_max'].append(max(map(abs,deltas[:12])))
                group['asc'].append(deltas[12]);group['mc'].append(deltas[13])
                if row['system']=='W':steps[name]['changed' if any(abs(d)>1e-5 for d in deltas[:12]) else 'unchanged']+=1
    expected={(cid,offset) for cid in bases for offset in config['offset_seconds']}
    if seen!=expected or len(bases)!=run['baseline_charts']:raise ValueError('Missing measurement coverage')
    locations={r['name']:r for r in config['locations']}
    for cid,shifted in chart_rows.items():
        _,location,system=cid.split(':');points={0:bases[cid]['values'],**shifted}
        for halfwidth in (1,30,60,180,300):
            ordered=[points[o] for o in sorted(points) if abs(o)<=halfwidth]
            spans=[sampled_span([v[i] for v in ordered]) for i in range(12)]
            for scope in (location,locations[location]['region']):
                windows[f'{scope}/{system}/{halfwidth}'].extend(spans)
    events=read(out/'whole-sign-events.json')
    if not events or any(not all(abs(v-108000)<1e-5 for v in event['whole_sign_cusp_displacement_arcsec']) for event in events):
        raise ValueError('Whole Sign event evidence missing')
    summary=dict(groups={name:{key:describe(values) for key,values in group.items()} for name,group in groups.items()},
        sampled_window_spans={name:describe(values) for name,values in windows.items()},
        whole_sign_grid_steps={key:dict(value) for key,value in steps.items()},
        whole_sign_targeted_events=len(events),targeted_events_by_location=dict(Counter(e['location'] for e in events)),
        counts=dict(epochs=run['epochs'],baseline_charts=len(bases),shifted_charts=len(seen),
            cusp_comparisons=len(seen)*12,asc_mc_comparisons=len(seen)*2),
        independence_pass=not(run['unexpected_guard_events'] or run['loaded_swiss']) and all(run['guard_self_test'].values()),
        example=read(out/'example.json'),prior_worst=read(out/'prior-worst-case.json'),
        note='Finite signed UTC perturbations. Absolute statistics pool earlier/later shifts. Windows are sampled spans, not certified continuous bounds. Grid frequencies are not population probabilities. Whole Sign cusp steps are separate from continuous ASC/MC.')
    dump(out/'summary.json',summary)
    print('Taiwan continuous cusps: min / median / p95 / max arcsec')
    for system in config['systems']:
        for seconds in (1,60,300):
            v=summary['groups'][f'Taiwan/{system}/{seconds}']['cusps']
            print(system,seconds,{k:round(v[k],6) for k in ('min','median','p95','max')})
    print('High latitude 1s', {system:summary['groups'][f'HighLatitude/{system}/1']['cusps']['max'] for system in config['systems']})
    worst=summary['prior_worst'];index=worst['previous_comparison']['index']
    print('Prior 19.2 arcsec case movement:',{o:worst['offsets'][o]['delta_arcsec'][index] for o in ('1','60')})

if __name__=='__main__':main()
