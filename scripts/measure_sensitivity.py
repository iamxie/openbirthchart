# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Measure house response to actual UTC time shifts. No Swiss engine is used."""
from datetime import datetime,timedelta,timezone
import csv
import importlib.metadata as md
import json
from pathlib import Path
import sys
import time
from common import ROOT,configure_core,dump,read,sha,finite_vector,angular_delta
from sensitivity_math import find_crossing

OFFSETS=[-300,-180,-60,-30,-1,1,30,60,180,300]
LOCATIONS=[dict(name='Taipei',region='Taiwan',lat=25.0330,lon=121.5654),
    dict(name='Tainan',region='Taiwan',lat=22.9999,lon=120.2269),
    dict(name='Kaohsiung',region='Taiwan',lat=22.6273,lon=120.3014),
    dict(name='Equator',region='Comparison',lat=0.0,lon=0.0),
    dict(name='Greenwich',region='Comparison',lat=51.4779,lon=0.0),
    dict(name='NearPolarN',region='HighLatitude',lat=65.5,lon=25.0),
    dict(name='NearPolarS',region='HighLatitude',lat=-65.5,lon=-70.0)]
SYSTEMS=['P','K','O','E','W']
FIELDS=[f'cusp_{i}' for i in range(1,13)]+['asc','mc']

def main():
    started=time.perf_counter()
    configuration=configure_core()
    from guard import RuntimeGuard
    guard=RuntimeGuard();guard.install();self_test=guard.self_test()
    from utc_times import TimeAuthority,seconds_between
    import libephemeris as engine
    assert engine.get_calc_mode()=='skyfield'
    authority=TimeAuthority()
    epochs=[datetime(y,m,d,h,17,23,tzinfo=timezone.utc)
        for y in (1991,1999,2024) for m,d in ((3,20),(6,21),(9,22),(12,21)) for h in range(24)]
    config=dict(years=[1991,1999,2024],sample_dates=[[3,20],[6,21],[9,22],[12,21]],
        hours_utc=list(range(24)),minute=17,second=23,offset_seconds=OFFSETS,
        locations=LOCATIONS,systems=SYSTEMS,fields=FIELDS,
        method='UTC to TT/UT1 from pinned ERFA/IERS, ERFA GAST/obliquity, LibEphemeris houses_armc',
        scope='Sensitivity of one fixed engine to changed birth time, not ephemeris error or population probability')
    dump(ROOT/'sensitivity-cases.json',config)
    out=ROOT/'results/sensitivity';out.mkdir(parents=True,exist_ok=True)
    cache={}
    def instant(dt,allow_model=False):
        iso=dt.isoformat()
        if iso not in cache: cache[iso]=authority.convert(iso,allow_model=allow_model)
        row=cache[iso]
        if not allow_model and not row['measured_time']: raise ValueError('Sensitivity grid requires measured EOP')
        return row
    def positions(dt,location,system,allow_model=False,native=False):
        t=instant(dt,allow_model)
        if native:
            engine.set_delta_t_userdef(t['delta_t_seconds']/86400)
            try: cusps,angles=engine.houses(t['ut1_jd'],location['lat'],location['lon'],system.encode())
            finally: engine.set_delta_t_userdef(engine.DELTAT_AUTOMATIC)
        else:
            cusps,angles=engine.houses_armc((t['erfa_gast_deg']+location['lon'])%360,
                location['lat'],t['erfa_true_obliquity_deg'],system.encode())
        return finite_vector(cusps,12)+finite_vector(angles,8)[:2]
    headers=['id','epoch','utc','location','region','lat','lon','system','offset_seconds']
    headers += [f'{field}_arcsec' for field in FIELDS]+[f'{field}_after_deg' for field in FIELDS]
    chart_count=0;row_count=0;max_time_error=0.0
    with (out/'measurements.csv').open('w',encoding='utf-8',newline='') as measurements, (out/'baselines.jsonl').open('w',encoding='utf-8') as baselines:
        writer=csv.DictWriter(measurements,fieldnames=headers);writer.writeheader()
        for ei,dt in enumerate(epochs):
            base_time=instant(dt)
            for offset in OFFSETS:
                shifted_time=instant(dt+timedelta(seconds=offset))
                error=abs(seconds_between(shifted_time['tt_parts'],base_time['tt_parts'])-offset)
                max_time_error=max(max_time_error,error)
                if error>1e-6: raise AssertionError('Time shift is not the requested SI seconds')
            for location in LOCATIONS:
                for system in SYSTEMS:
                    cid=f'e{ei:03d}:{location["name"]}:{system}'
                    base=positions(dt,location,system)
                    baselines.write(json.dumps(dict(id=cid,utc=dt.isoformat(),values=base),allow_nan=False)+'\n')
                    chart_count+=1
                    for offset in OFFSETS:
                        shifted=positions(dt+timedelta(seconds=offset),location,system)
                        deltas=[angular_delta(a,b)*3600 for a,b in zip(shifted,base,strict=True)]
                        if system=='W' and any(abs(d/108000-round(d/108000))>1e-8 for d in deltas[:12]):
                            raise AssertionError('Whole-sign cusp is not an exact 30-degree step')
                        row=dict(id=cid,epoch=ei,utc=dt.isoformat(),location=location['name'],region=location['region'],
                            lat=location['lat'],lon=location['lon'],system=system,offset_seconds=offset)
                        row.update({f'{field}_arcsec':delta for field,delta in zip(FIELDS,deltas,strict=True)})
                        row.update({f'{field}_after_deg':value for field,value in zip(FIELDS,shifted,strict=True)})
                        writer.writerow(row);row_count+=1
            if (ei+1)%24==0:print('sensitivity epochs',ei+1,'/',len(epochs),flush=True)
    if chart_count!=len(epochs)*len(LOCATIONS)*len(SYSTEMS) or row_count!=chart_count*len(OFFSETS):
        raise AssertionError('Missing sensitivity cases')
    # Explicit worked example: location is illustrative, not the user's birthplace.
    example_dt=datetime(1999,4,25,13,25,31,tzinfo=timezone.utc)
    location=next(p for p in LOCATIONS if p['name']=='Tainan')
    example={}
    for system in SYSTEMS:
        base=positions(example_dt,location,system)
        example[system]=dict(base=base,offsets={str(offset):dict(values=(shifted:=positions(example_dt+timedelta(seconds=offset),location,system)),
            delta_arcsec=[angular_delta(a,b)*3600 for a,b in zip(shifted,base,strict=True)]) for offset in OFFSETS})
    dump(out/'example.json',dict(utc=example_dt.isoformat(),location=location,results=example,
        caveat='Tainan is a demonstration coordinate, not an asserted birthplace.'))
    # Intentionally find Whole Sign discontinuities; never mix with the grid's frequencies.
    events=[]
    start=datetime(1999,4,25,tzinfo=timezone.utc)
    for location in [p for p in LOCATIONS if p['region']=='Taiwan']:
        def asc_at(seconds):return positions(start+timedelta(seconds=seconds),location,'E')[12]
        before=asc_at(0)
        for seconds in range(60,86401,60):
            after=asc_at(seconds)
            if int(before//30)!=int(after//30):
                if (int(after//30)-int(before//30))%12!=1:raise AssertionError('Skipped sign in event search')
                boundary=(int(after//30)*30)%360
                root=find_crossing(asc_at,boundary,seconds-60,seconds)
                t0=start+timedelta(seconds=root)
                earlier=positions(t0-timedelta(seconds=.5),location,'W')
                later=positions(t0+timedelta(seconds=.5),location,'W')
                cusp_jumps=[angular_delta(a,b)*3600 for a,b in zip(later[:12],earlier[:12],strict=True)]
                if not all(abs(v-108000)<1e-5 for v in cusp_jumps):raise AssertionError('Expected 30-degree Whole Sign jump')
                events.append(dict(location=location['name'],transition_utc=t0.isoformat(),boundary_deg=boundary,
                    bracket_tolerance_seconds=.001,elapsed_seconds=1,
                    whole_sign_cusp_displacement_arcsec=cusp_jumps,
                    asc_displacement_arcsec=angular_delta(later[12],earlier[12])*3600))
            before=after
        print('whole sign boundaries found:',location['name'],sum(e['location']==location['name'] for e in events),flush=True)
    dump(out/'whole-sign-events.json',events)
    # Relate the earlier worst comparison to its own local response, not an average Earth rate.
    prior=read(ROOT/'results/utc/summary.json')['worst_split_houses'][0]
    special_dt=datetime.fromisoformat(prior['utc'])
    location=next(p for p in LOCATIONS if p['name']==prior['location'])
    base=positions(special_dt,location,prior['system'],allow_model=True,native=True)
    previous=next(r for r in read(ROOT/'results/utc/core.json')['houses'] if r['case']==prior['case'] and r['stage']=='split')
    if max(abs(angular_delta(a,b))*3600 for a,b in zip(base[:12],previous['cusps'],strict=True))>1e-5:
        raise AssertionError('Prior native core position not reproduced')
    special=dict(previous_comparison=prior,location=location,base=base,
        source=instant(special_dt,allow_model=True)['ut1_source'],
        caveat='Extrapolated future scenario and original native setter behaviour; kept separate from measured-EOP grid.')
    special['offsets']={}
    for offset in OFFSETS:
        shifted=positions(special_dt+timedelta(seconds=offset),location,prior['system'],allow_model=True,native=True)
        special['offsets'][str(offset)]=dict(values=shifted,delta_arcsec=[angular_delta(a,b)*3600 for a,b in zip(shifted,base,strict=True)])
    dump(out/'prior-worst-case.json',special)
    # Store independent time inputs, retaining EOP status and two-part dates.
    keys=['utc','tt_parts','ut1_parts','dut1_seconds','delta_t_seconds','ut1_source','measured_time',
          'erfa_gast_deg','erfa_true_obliquity_deg','leap_table_assumption']
    dump(out/'times.json',[{k:row[k] for k in keys} for row in cache.values()])
    installed={d.metadata['Name']:d.version for d in md.distributions()}
    loaded=[name for name in sys.modules if name.split('.')[0] in ('swisseph','pyswisseph','pysweph')]
    unexpected=[e for e in guard.events if e['phase']=='calculation']
    if loaded or unexpected or any('swiss' in name.lower() or 'pysweph' in name.lower() for name in installed):
        raise RuntimeError('Forbidden dependency')
    inputs={'sensitivity-cases.json':sha(ROOT/'sensitivity-cases.json'),'time-data-sources.lock.json':sha(ROOT/'time-data-sources.lock.json')}
    outputs={path.name:sha(path) for path in sorted(out.iterdir()) if path.is_file() and path.name in
        ('measurements.csv','baselines.jsonl','times.json','example.json','whole-sign-events.json','prior-worst-case.json')}
    dump(out/'run.json',dict(completed_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-started,
        configuration=configuration,packages=installed,epochs=len(epochs),baseline_charts=chart_count,
        shifted_charts=row_count,whole_sign_event_count=len(events),guard_self_test=self_test,guard_events=guard.events,
        unexpected_guard_events=unexpected,loaded_swiss=loaded,input_hashes=inputs,output_hashes=outputs,
        max_requested_time_shift_error_seconds=max_time_error))
    print('Sensitivity complete:',row_count,'shifted charts;',round(time.perf_counter()-started,3),'seconds',flush=True)

if __name__=='__main__':main()
