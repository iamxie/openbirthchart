# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Real offline integration checks around dates, timezones and failure boundaries."""
from datetime import datetime, timezone
import os
import traceback
from common import ROOT, BODIES, dump, angular_delta, configure_core

def main():
    configure_core()
    from guard import RuntimeGuard
    guard=RuntimeGuard();guard.install()
    import libephemeris as le
    from kerykeion import AstrologicalSubjectFactory as F
    results=[]
    def check(name,fn):
        try:
            detail=fn()
            results.append({'name':name,'passed':True,'detail':detail})
        except Exception as exc:
            results.append({'name':name,'passed':False,'error':str(exc),'traceback':traceback.format_exc()})
    def expect_rejected(fn, exception_name, message_part):
        try: fn()
        except Exception as exc:
            assert type(exc).__name__ == exception_name, f'Wrong rejection: {type(exc).__name__}'
            assert message_part in str(exc), f'Wrong reason: {exc}'
            return {'exception':type(exc).__name__,'message':str(exc)}
        raise AssertionError('Invalid input accepted')
    def chart(**kw):
        return F.from_birth_data(name='contract',online=False,lat=22.9999,lng=120.2269,
                active_points=BODIES[:10],calculate_lunar_phase=False,suppress_geonames_warning=True,**kw)
    def timezone_pair():
        local=chart(year=2024,month=2,day=29,hour=20,minute=0,seconds=22,tz_str='Asia/Taipei')
        utc=chart(year=2024,month=2,day=29,hour=12,minute=0,seconds=22,tz_str='Etc/UTC')
        assert abs(local.julian_day-utc.julian_day)<1e-10
        assert abs(angular_delta(local.moon.abs_pos,utc.moon.abs_pos))<1e-10
        return {'local_utc':local.iso_formatted_utc_datetime,'jd':local.julian_day}
    def dst_pair():
        early=chart(year=2024,month=11,day=3,hour=1,minute=30,tz_str='America/New_York',is_dst=True)
        late=chart(year=2024,month=11,day=3,hour=1,minute=30,tz_str='America/New_York',is_dst=False)
        assert abs((late.julian_day-early.julian_day)*86400-3600)<1e-4
        return {'early':early.iso_formatted_utc_datetime,'late':late.iso_formatted_utc_datetime}
    def polar():
        subject=F.from_birth_data(name='polar',year=2024,month=1,day=1,hour=12,minute=0,tz_str='Etc/UTC',
            lat=69.65,lng=18.95,online=False,active_points=BODIES[:10],calculate_lunar_phase=False,
            houses_system_identifier='P',suppress_geonames_warning=True)
        data=subject.model_dump(mode='json')
        assert data['polar_house_fallbacks'], 'A silent fallback is unacceptable'
        assert abs(subject.lat-69.65)<1e-10
        return data['polar_house_fallbacks']
    check('same_instant_Taipei_UTC_leap_day_seconds',timezone_pair)
    check('DST_fold_two_distinct_instants',dst_pair)
    check('DST_fold_without_choice_rejected',lambda:expect_rejected(lambda:chart(year=2024,month=11,day=3,hour=1,minute=30,tz_str='America/New_York'),'KerykeionException','Ambiguous time'))
    check('DST_nonexistent_local_time_rejected',lambda:expect_rejected(lambda:chart(year=2024,month=3,day=10,hour=2,minute=30,tz_str='America/New_York'),'KerykeionException','Non-existent time'))
    for year in (1800,2200):
        check(f'kernel_range_{year}_rejected',lambda year=year:expect_rejected(lambda:le.calc(le.julday(year,1,1),0,258),'EphemerisRangeError','outside ephemeris range'))
    check('polar_fallback_is_explicit',polar)
    dump(ROOT/'results/core-contracts.json',{'checks':results,'guard_events':guard.events,
        'pass':all(r['passed'] for r in results) and not guard.events})
    print([(r['name'],r['passed']) for r in results])
    return 0 if all(r['passed'] for r in results) and not guard.events else 1

if __name__=='__main__':raise SystemExit(main())
