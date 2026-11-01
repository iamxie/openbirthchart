# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""UTC -> TT and UTC -> UT1 from pinned independent time data.

IERS UT1-TAI is interpolated on a continuous TAI axis, so a UTC leap second
is not smeared into the Earth's rotation. Outside IERS coverage, the optional
Skyfield model is explicitly labelled as a scenario, never as an observation.
"""
from bisect import bisect_right
from datetime import datetime
import math
import re
import warnings
import erfa
import numpy as np
from skyfield.api import load
from common import ROOT, read, sha

DAY=86400.0
MJD0=2400000.5

def seconds_between(a,b):
    return math.fsum([a[0]-b[0],a[1]-b[1]])*DAY

class TimeAuthority:
    def __init__(self):
        self.manifest=read(ROOT/'time-data-sources.lock.json')
        for item in self.manifest['files']:
            if sha(ROOT/item['path'])!=item['sha256']: raise ValueError('Time data hash mismatch')
        text=(ROOT/'data/time/Leap_Second.dat').read_text(encoding='ascii')
        expiry=re.search(r'File expires on (.+)',text).group(1).strip()
        self.leap_expiry=datetime.strptime(expiry,'%d %B %Y').date().isoformat()
        leaps=[]
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith('#'): continue
            mjd,day,month,year,offset=map(float,line.split())
            if day!=1: raise ValueError('Unexpected leap effective date')
            leaps.append((int(year),int(month),offset))
        erfa.leap_seconds.update(np.array(leaps,dtype=erfa.leap_seconds.get().dtype))
        self.leaps=leaps
        self.eop=[]
        for line in (ROOT/'data/time/finals2000A.all').read_text(encoding='ascii').splitlines():
            if not line[58:68].strip(): continue
            mjd=float(line[7:15]); year=int(line[:2])+(1900 if mjd<=51543 else 2000)
            month=int(line[2:4]); day=int(line[4:6])
            flag=line[57]; dut_a=float(line[58:68]); error=float(line[68:78])
            final=line[154:165].strip()
            if final:
                dut=float(final); status='final_B'
            else:
                dut=dut_a; status={'I':'rapid_A','P':'prediction_A'}[flag]
            dat=self.offset(year,month,day)
            self.eop.append(dict(mjd=mjd,tai_mjd=mjd+dat/DAY,ut1_tai=dut-dat,
                dut1=dut,status=status,a_sigma_seconds=error))
        self.mjds=[row['mjd'] for row in self.eop]
        if any(b-a!=1 for a,b in zip(self.mjds,self.mjds[1:])): raise ValueError('EOP dates not contiguous')
        self.ts=load.timescale(builtin=True)

    def offset(self,year,month,day):
        eligible=[x for x in self.leaps if (x[0],x[1])<=(year,month)]
        if not eligible: raise ValueError('This experiment supports UTC from 1972 onward')
        return eligible[-1][2]

    def convert(self,iso,allow_model=False):
        match=re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)(?:Z|\+00:00)',iso)
        if not match: raise ValueError('Require explicit UTC (Z or +00:00)')
        y,mo,d,h,mi=map(int,match.groups()[:5]); sec=float(match.group(6))
        dat=self.offset(y,mo,d)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',erfa.ErfaWarning)
            utc=tuple(map(float,erfa.dtf2d('UTC',y,mo,d,h,mi,sec)))
            tai=tuple(map(float,erfa.utctai(*utc)))
            tt=tuple(map(float,erfa.taitt(*tai)))
            if abs(seconds_between(tt,tai)-32.184)>1e-7: raise AssertionError('TT-TAI invariant')
            mjd=(utc[0]-MJD0)+utc[1]
            index=bisect_right(self.mjds,mjd)-1
            eop_info=None
            if 0<=index<len(self.eop)-1:
                a,b=self.eop[index:index+2]
                tai_mjd=(tai[0]-MJD0)+tai[1]
                fraction=(tai_mjd-a['tai_mjd'])/(b['tai_mjd']-a['tai_mjd'])
                ut1_tai=a['ut1_tai']+fraction*(b['ut1_tai']-a['ut1_tai'])
                dut1=ut1_tai+dat
                statuses={a['status'],b['status']}
                source='prediction_A' if 'prediction_A' in statuses else ('rapid_A' if 'rapid_A' in statuses else 'final_B')
                eop_info=dict(left=a,right=b,fraction=fraction,method='linear UT1-TAI on TAI axis')
            else:
                if not allow_model: raise ValueError('UTC outside pinned EOP coverage')
                sf=self.ts.tt_jd(tt[0],tt[1])
                dut1=dat+32.184-float(sf.delta_t)
                source='model_outside_eop'
            ut1=tuple(map(float,erfa.utcut1(*utc,dut1)))
            dpsi,deps=erfa.nut06a(*tt)
            eps=math.degrees(float(erfa.obl06(*tt)+deps))
            gast=math.degrees(float(erfa.gst06a(*ut1,*tt)))%360
            sf=self.ts.utc(y,mo,d,h,mi,sec)
            sf_tt=(float(sf.whole),float(sf.tt_fraction))
        warning_text=sorted(set(str(w.message) for w in caught))
        # Invalid leap seconds are errors, not accepted 'warnings'. Dubious years
        # remain labelled model scenarios and are outside observed-data acceptance.
        if any('after end of day' in w or 'bad' in w for w in warning_text): raise ValueError(warning_text)
        future_leaps=iso[:10]>=self.leap_expiry
        return dict(utc=iso,calendar=[y,mo,d,h,mi,sec],utc_parts=utc,tai_parts=tai,
            tt_parts=tt,ut1_parts=ut1,tt_jd=sum(tt),ut1_jd=sum(ut1),tai_minus_utc=dat,
            dut1_seconds=dut1,delta_t_seconds=seconds_between(tt,ut1),ut1_source=source,
            leap_table_assumption=future_leaps,leap_table_expiry=self.leap_expiry,
            measured_time=source in ('final_B','rapid_A') and not future_leaps,
            erfa_gast_deg=gast,erfa_true_obliquity_deg=eps,
            independent_skyfield_tt_difference_seconds=seconds_between(tt,sf_tt),
            erfa_warnings=warning_text,eop=eop_info)
