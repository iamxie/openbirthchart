# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Parse CDS I/256 planet.dat, retaining source line identity and quality flags."""
import math
from common import ROOT, read, sha

TARGETS = {9000070: ('Uranus', 7), 9000080: ('Neptune', 8), 9000090: ('Pluto', 9)}

def verify_sources():
    for item in read(ROOT/'observation-data-sources.lock.json')['files']:
        if sha(ROOT/item['path']) != item['sha256']:
            raise ValueError('Observation source hash mismatch: '+item['path'])

def parse_line(line, number):
    # Distributed file omits the trailing blank magnitude on 7096 records.
    if len(line) not in (76, 83):
        raise ValueError(f'CMC line {number}: expected 76/83 columns, got {len(line)}')
    line=line.ljust(83)
    flag = line[46]
    if flag not in (' ', '*'):
        raise ValueError(f'Unknown quality flag: {flag!r}')
    ra_fields = [line[50:52], line[53:55], line[56:62]]
    de_fields = [line[65:67], line[68:70], line[71:76]]
    def coordinate(fields, sign, ra=False):
        if not ''.join(fields).strip():
            return None
        if any(not field.strip() for field in fields):
            raise ValueError(f'Partial coordinate at CMC line {number}')
        a,b,c = map(float, fields)
        if not (0 <= a <= (23 if ra else 90) and 0 <= b < 60 and 0 <= c < 60):
            raise ValueError(f'Invalid sexagesimal coordinate at line {number}')
        if not ra and sign not in ('+', '-'):
            raise ValueError('Missing declination sign')
        value = a+b/60+c/3600
        return value*15 if ra else value*(-1 if sign == '-' else 1)
    jd = float(line[32:46])
    if not math.isfinite(jd):
        raise ValueError('Nonfinite TT')
    return dict(id=f'CMC-I256-L{number}', source_line=number, cmc=int(line[1:8]),
                name=line[18:30].strip(), tt_jd=jd, flag=flag.strip(),
                ra_deg=coordinate(ra_fields, '+', True),
                dec_deg=coordinate(de_fields, line[64]))

def load_records():
    verify_sources()
    lines=(ROOT/'data/observations/planet.dat').read_text(encoding='ascii').splitlines()
    if len(lines) != 25848:
        raise ValueError('Unexpected catalogue record count')
    return [parse_line(line,i) for i,line in enumerate(lines,1)]

def selected_records():
    # 1991-01-01 00:00:00 TT through, excluding, 1992-01-01 TT.
    return [dict(r, body=TARGETS[r['cmc']][0], body_id=TARGETS[r['cmc']][1])
            for r in load_records()
            if r['cmc'] in TARGETS and 2448257.5 <= r['tt_jd'] < 2448622.5]
