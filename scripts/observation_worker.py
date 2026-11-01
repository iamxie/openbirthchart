# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Independent offline workers: compute native and mean-J2000 apparent RA/Dec."""
import argparse
from datetime import datetime, timezone
import importlib.metadata as md
import sys
import time
from common import ROOT, read, sha, dump, configure_core, finite_vector
from observation_data import selected_records

def main():
    p=argparse.ArgumentParser(); p.add_argument('engine',choices=['core','reference'])
    engine=p.parse_args().engine; start=time.perf_counter()
    observations=selected_records()
    for f in read(ROOT/'data-sources.lock.json')['files']:
        if f'data/{engine}/' in f['path'] and sha(ROOT/f['path']) != f['sha256']:
            raise ValueError('Ephemeris hash mismatch')
    result=dict(engine=engine, source_sha256=sha(ROOT/'data/observations/planet.dat'),
                packages={d.metadata['Name']:d.version for d in md.distributions()}, rows=[])
    guard=None
    if engine=='core':
        result['configuration']=configure_core()
        from guard import RuntimeGuard
        guard=RuntimeGuard(); guard.install(); result['guard_self_test']=guard.self_test()
        import libephemeris as e
        assert e.get_calc_mode()=='skyfield'
        from libephemeris.state import get_planets
        from libephemeris.planets import get_planet_target
        result['resolved_targets']={name:dict(naif_id=get_planet_target(get_planets(),name).target,
                                              implementation=type(get_planet_target(get_planets(),name)).__name__)
                                    for name in ('uranus','neptune','pluto')}
    else:
        import swisseph as e
        e.set_ephe_path(str(ROOT/'data/reference'))
    flags=e.FLG_SWIEPH | e.FLG_EQUATORIAL
    for obs in observations:
        row=dict(id=obs['id'])
        for label, extra in [('native',0), ('j2000',e.FLG_J2000 | e.FLG_NONUT)]:
            values, returned=e.calc(obs['tt_jd'], obs['body_id'], flags | extra)
            if engine=='reference' and returned & 7 != e.FLG_SWIEPH:
                raise RuntimeError('Swiss ephemeris fallback')
            row[label]=finite_vector(values,6)
            row[label+'_flags']=returned
        result['rows'].append(row)
    if guard:
        result['guard_events']=guard.events
        result['unexpected_guard_events']=[x for x in guard.events if x['phase']=='calculation']
        result['loaded_swiss']=[n for n in sys.modules if n.split('.')[0] in ('swisseph','pysweph','pyswisseph')]
        result['installed_swiss']=[n for n in result['packages'] if 'swiss' in n.lower() or 'pysweph' in n.lower()]
        result['input_data']=[dict(path=p,sha256=sha(p)) for p in sorted(guard.data_reads)]
        if result['unexpected_guard_events'] or result['loaded_swiss'] or result['installed_swiss']:
            raise RuntimeError('Forbidden core dependency')
    else:
        result['swiss_files']=[e.get_current_file_data(0)]
    result['elapsed_seconds']=time.perf_counter()-start
    result['completed_utc']=datetime.now(timezone.utc).isoformat()
    dump(ROOT/f'results/observations/{engine}.json',result)
    print(engine,len(result['rows']),'observations',round(result['elapsed_seconds'],3),'seconds')

if __name__=='__main__': main()
