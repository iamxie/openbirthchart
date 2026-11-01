# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
from common import ROOT, read, dump, angular_delta

def main():
    a=read(ROOT/'results/diagnostic-core.json'); b=read(ROOT/'results/diagnostic-reference.json')
    ref={r['id']:r for r in b['times']}
    times=[]
    for row in a['times']:
        r=ref[row['id']]
        times.append(dict(id=row['id'],calendar=row['calendar_label'],
            delta_t_diff_seconds=row['delta_t_seconds']-r['delta_t_seconds'],
            skyfield_delta_t_diff_seconds=row['skyfield_delta_t_seconds']-r['delta_t_seconds'],
            sidtime_diff_arcsec=angular_delta(row['sidtime_deg'],r['sidtime_deg'])*3600,
            core_erfa_sidtime_diff_arcsec=angular_delta(row['sidtime_deg'],row['erfa_gast_deg'])*3600,
            swiss_erfa_sidtime_diff_arcsec=angular_delta(r['sidtime_deg'],row['erfa_gast_deg'])*3600,
            obliquity_diff_arcsec=(row['eps_true_deg']-r['eps_true_deg'])*3600))
    geometry=[]
    rg={r['id']:r for r in b['geometry']}
    for row in a['geometry']:
        for field in ('cusps','angles'):
            geometry.extend(abs(angular_delta(x,y))*3600 for x,y in zip(row[field],rg[row['id']][field],strict=True))
    hr={r['id']:r for r in read(ROOT/'results/reference.json')['house_rows']}
    common=[]
    for row in a['houses']:
        for field in ('cusps','angles'):
            common.extend(abs(angular_delta(x,y))*3600 for x,y in zip(row['shared_input_'+field],hr[row['id']][field],strict=True))
    result={'max_geometry_arcsec':max(geometry),'geometry_comparisons':len(geometry),
        'max_house_with_shared_armc_obliquity_arcsec':max(common),
        'max_aligned_ut_planet_longitude_arcsec':max(abs(r['longitude_difference_arcsec']) for r in a['aligned_ut_planets']),
        'aligned_ut_planet_count':len(a['aligned_ut_planets']),
        'times':times,'largest_sidtime_differences':sorted(times,key=lambda r:abs(r['sidtime_diff_arcsec']),reverse=True)[:10],
        'largest_delta_t_differences':sorted(times,key=lambda r:abs(r['skyfield_delta_t_diff_seconds']),reverse=True)[:10]}
    dump(ROOT/'results/diagnostic-summary.json',result)
    print({key:value for key,value in result.items() if key not in ('times','largest_sidtime_differences','largest_delta_t_differences')})
    print('sidtime worst',result['largest_sidtime_differences'][:2])
    print('delta T worst',result['largest_delta_t_differences'][:2])

if __name__=='__main__':main()
