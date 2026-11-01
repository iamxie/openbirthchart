# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Reproducible, cached, strictly serial public-form compatibility check."""
from pathlib import Path
import argparse, csv, datetime as dt, hashlib, html, json, math, random, re, statistics, subprocess, sys, time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
OUT = ROOT / 'results/astrodoor'
URL = 'https://astrodoor.cc/horoscope_result.jsp'
UA = 'EphemerisCompatibilityCheck/0.1 (rate-limited personal validation)'
SIGNS = ['牡羊','金牛','雙子','巨蟹','獅子','處女','天秤','天蠍','射手','魔羯','水瓶','雙魚']
MAJOR = ['太陽','月亮','水星','金星','火星','木星','土星','天王星','海王星','冥王星']
MINOR = ['凱龍星','婚神星','智神星','灶神星','穀神星']

def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', value))).strip()

def position(value):
    m = re.fullmatch(r'([^\s]+)座\s*(\d+)°\s*(\d+)\x27', value)
    if not m: return None
    sign, deg, minute = m.groups()
    deg, minute = int(deg), int(minute)
    if not (0 <= deg < 30 and 0 <= minute < 60): raise ValueError('Invalid displayed position')
    return SIGNS.index(sign) * 30 + deg + minute / 60

def parse_site(raw, case):
    from html.parser import HTMLParser
    class Inputs(HTMLParser):
        def __init__(self): super().__init__(); self.values = {}
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'input' and attrs.get('type') == 'hidden':
                self.values[attrs.get('name')] = attrs.get('value')
    inputs = Inputs(); inputs.feed(raw)
    expected = {k:v for k,v in case['form'].items() if not k.startswith(('sun','moon','planet'))}
    expected['daylight'] = 'yes' if case['dst_minutes'] else 'no'
    for key, value in expected.items():
        if inputs.values.get(key) != value: raise ValueError(f'{case["id"]} echoed {key}: {inputs.values.get(key)!r} != {value!r}')
    points, cusps, angles = {}, {}, {}
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', raw, re.S | re.I):
        cells = [plain(c) for c in re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S | re.I)]
        if len(cells) < 2: continue
        lon = position(cells[1])
        if lon is None: continue
        name = cells[0].replace('℞', '').strip()
        h = re.match(r'第(\d+)宮', cells[2]) if len(cells)>2 else None
        item = dict(name=name, displayed=cells[1], lon=lon, house=int(h[1]) if h else None,
                    retrograde='℞' in cells[0])
        if name in MAJOR + MINOR + ['北交點','南交點','幸運點','宿命點']:
            if name in points: raise ValueError('Duplicate point '+name)
            if not h or not 1<=int(h[1])<=12: raise ValueError('Missing/invalid house for '+name)
            points[name] = item
        elif name.startswith('第'):
            number = int(re.match(r'第(\d+)宮',name)[1])
            if number in cusps: raise ValueError('Duplicate cusp')
            cusps[number] = item
        elif any(f'({a})' in name for a in ('ASC','DES','MC','IC')):
            axis=re.search(r'\((\w+)\)', name)[1]
            if axis in angles: raise ValueError('Duplicate axis')
            angles[axis] = item
    if set(points) != set(MAJOR+MINOR+['北交點','南交點','幸運點','宿命點']): raise ValueError('Missing/extra point rows')
    if set(cusps) != set(range(1,13)) or len(angles)!=4: raise ValueError('Missing cusp/angle rows')
    for axis, cusp in [('ASC',1),('DES',7),('MC',10),('IC',4)]:
        if angles[axis]['lon'] != cusps[cusp]['lon']: raise ValueError('Inconsistent axis and cusp')
    return dict(echo=inputs.values, points=points, cusps=cusps, angles=angles)

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def prepare():
    from desktop.model import BirthInput, resolve_local
    if (OUT / 'cases.json').exists():
        return json.loads((OUT / 'cases.json').read_text(encoding='utf-8'))
    rng = random.Random(20261026)
    start = dt.datetime(1950, 1, 1)
    span = int((dt.datetime(2021, 1, 1) - start).total_seconds() // 60)
    minutes = sorted(rng.sample(range(span), 100))
    cases = []
    for i, minute in enumerate(minutes, 1):
        local = start + dt.timedelta(minutes=minute)
        birth = BirthInput(local_iso=local.isoformat())
        resolved = resolve_local(birth)
        dst = int(resolved['dst'].total_seconds() / 60)
        assert dst in (0, 60)
        form = dict(year=str(local.year), month=str(local.month), day=str(local.day),
                    hour=str(local.hour), minute=str(local.minute),
                    longitude='E', longitudeDegree='120', longitudeMinute='12',
                    latitude='N', latitudeDegree='23', latitudeMinute='0', timezone='-480',
                    houseSystem='P', showAsteroids='Y', minorAspect='yes')
        if dst: form['daylight'] = 'yes'
        for body in ('sun', 'moon', 'planet'):
            for angle in (0, 180, 90, 120, 60, 'minor'):
                form[f'{body}{angle}'] = str(3 if angle == 'minor' else 6 if angle == 60 else 7 if body == 'planet' else 10)
        cases.append(dict(id=f'{i:03}', local=local.isoformat(), utc=resolved['utc'].isoformat(),
                          dst_minutes=dst, zone='Asia/Taipei', longitude=120.2, latitude=23., form=form))
    save(OUT / 'cases.json', cases)
    save(OUT / 'protocol.json', dict(seed=20261026, count=100, selection='uniform sample without replacement over all local minutes 1950-01-01 to 2020-12-31; sorted before requesting',
        endpoint=URL, min_interval_seconds=12, concurrency=1, automatic_retries=0,
        location='Tainan 120E12 23N00', house_system='Placidus', seconds=0,
        timezone='tzdata bundled by desktop.model; website standard GMT+8 with per-date DST checkbox',
        scope='10 physical major bodies, 5 small bodies, 12 cusps; additional chart points recorded separately',
        robots='robots.txt returned HTTP 404 during preliminary Windows Invoke-WebRequest check',
        terms='https://astrodoor.cc/tos.jsp read before testing; private numeric comparison only, no interpretation text republished'))
    return cases

def collect(limit):
    cases = prepare()
    fetched = 0
    for case in cases:
        dest = OUT / 'raw' / (case['id'] + '.html')
        meta = dest.with_suffix('.json')
        if meta.exists():
            old = json.loads(meta.read_text(encoding='utf-8'))
            if old['status'] != 200: raise RuntimeError(f"Stopped response for {case['id']}; inspect before proceeding")
            parse_site(dest.read_text(encoding='utf-8'), case)
            continue
        if dest.exists(): raise RuntimeError('Uncommitted response exists; inspect before retrying: ' + str(dest))
        last_path = OUT / 'last-request.json'
        if last_path.exists():
            last = json.loads(last_path.read_text(encoding='utf-8'))['finished_epoch']
            time.sleep(max(0, 12 - (time.time() - last)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = dest.with_suffix('.form')
        request.write_text(urlencode(case['form']), encoding='ascii')
        began = time.time()
        response = subprocess.run(['curl.exe', '--silent', '--show-error', '--max-time', '45',
            '--user-agent', UA, '--referer', 'https://astrodoor.cc/horoscope.jsp',
            '--data-binary', '@' + str(request), '--output', str(dest),
            '--dump-header', str(dest.with_suffix('.headers')), '--write-out', '%{http_code}', URL],
            capture_output=True, text=True)
        ended = time.time()
        save(last_path, dict(finished_epoch=ended))
        status = int(response.stdout or 0)
        save(meta, dict(case_id=case['id'], url=URL, status=status, curl_returncode=response.returncode,
            error=response.stderr, started_utc=dt.datetime.fromtimestamp(began, dt.timezone.utc).isoformat(),
            completed_utc=dt.datetime.fromtimestamp(ended, dt.timezone.utc).isoformat(),
            sha256=hashlib.sha256(dest.read_bytes()).hexdigest() if dest.exists() else None))
        print(f"{case['id']} {case['local']} HTTP {status}", flush=True)
        if response.returncode or status != 200:
            raise RuntimeError('Collection stopped; no automatic retries. Inspect saved response.')
        html = dest.read_text(encoding='utf-8', errors='replace')
        save(OUT / 'parsed' / (case['id'] + '.json'), parse_site(html, case))
        fetched += 1
        if fetched >= limit: break

def local_calculations():
    from guard import RuntimeGuard
    guard = RuntimeGuard(); guard.install()
    from desktop.model import ChartEngine, BirthInput
    engine = ChartEngine()
    for case in prepare():
        dest = OUT / 'local' / (case['id'] + '.json')
        if dest.exists(): continue
        chart = engine.calculate(BirthInput(local_iso=case['local']))
        assert chart['utc'] == case['utc']
        save(dest, chart)
        print('local', case['id'], flush=True)
    save(OUT / 'runtime.json', dict(swisseph_loaded='swisseph' in sys.modules,
         events=guard.events))

def analyze():
    rows=[]; completed=[]
    for case in prepare():
        raw=OUT/'raw'/(case['id']+'.html'); local=OUT/'local'/(case['id']+'.json')
        if not raw.exists() or not local.exists(): continue
        site=parse_site(raw.read_text(encoding='utf-8'),case)
        save(OUT/'parsed'/(case['id']+'.json'),site)
        chart=json.loads(local.read_text(encoding='utf-8'))
        completed.append(case['id'])
        values={p['name']:p for p in chart['points']}
        for name, point in site['points'].items():
            if name=='宿命點': continue # The desktop does not currently expose Vertex.
            own=values[name]
            group='major' if name in MAJOR else 'minor' if name in MINOR else 'derived'
            rows.append(make_row(case,name,group,point,own['lon'],own['house'],own['retrograde']))
        for n,point in site['cusps'].items():
            rows.append(make_row(case,f'第{n}宮','cusp',point,chart['cusps'][n-1],None,None))
    if not rows: raise RuntimeError('No complete pairs')
    with (OUT/'differences.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
    def stats(items):
        v=[r['abs_arcsec'] for r in items]
        return dict(n=len(v),mean=statistics.mean(v),median=statistics.median(v),std_population=statistics.pstdev(v),max=max(v),
            over_60=sum(x>60 for x in v),floor_minute_matches=sum(r['floor_minute_match'] for r in items),
            house_mismatches=sum(r['house_match'] is False for r in items),
            retrograde_mismatches=sum(r['retrograde_match'] is False for r in items))
    summary=dict(completed_cases=len(completed),completed_ids=completed,
        groups={g:stats([r for r in rows if r['group']==g]) for g in ['major','minor','cusp','derived']},
        by_point={n:stats([r for r in rows if r['name']==n]) for n in dict.fromkeys(r['name'] for r in rows)},
        largest=sorted(rows,key=lambda r:r['abs_arcsec'],reverse=True)[:30],
        house_mismatches=[r for r in rows if r['house_match'] is False],
        retrograde_mismatches=[r for r in rows if r['retrograde_match'] is False])
    save(OUT/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['completed_cases','groups']},ensure_ascii=False,indent=2))

def make_row(case,name,group,site,lon,house,retrograde):
    delta=((lon-site['lon']+180)%360-180)*3600
    floor=(math.floor((lon%360)*60)/60)
    return dict(case_id=case['id'],local=case['local'],utc=case['utc'],dst_minutes=case['dst_minutes'],name=name,group=group,
        website_display=site['displayed'],website_deg=site['lon'],desktop_deg=lon,signed_arcsec=delta,abs_arcsec=abs(delta),
        floor_minute_match=abs((floor-site['lon']+180)%360-180)<1e-8,
        website_house=site['house'] if group!='cusp' else None,desktop_house=house,
        house_match=site['house']==house if house is not None else None,
        website_retrograde=site['retrograde'] if group in ('major','minor') else None,
        desktop_retrograde=retrograde if group in ('major','minor') else None,
        retrograde_match=site['retrograde']==retrograde if group in ('major','minor') else None)

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=['prepare','collect','local','analyze'])
    p.add_argument('--limit', type=int, default=1); args = p.parse_args()
    if args.command == 'prepare': print(len(prepare()), 'cases fixed')
    elif args.command == 'collect': collect(args.limit)
    elif args.command == 'local': local_calculations()
    else: analyze()
