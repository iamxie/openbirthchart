# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""UI-independent birth time, chart, and aspect calculations. No Swiss imports."""
from .errors import UserError, AmbiguousTimeError
from .house_positions import (house_number2, house_policy_for, azimuth_notices,
    InvalidHousePosition, validate_house_number, validate_chart_houses, invalid_house_error)
from .azimuth import prepare_azimuth, AzimuthGeometryError
from .polich import prepare_polich, PolichGeometryError
from .leap_seconds import reject_leap_second
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import math
import threading
import warnings
from zoneinfo import ZoneInfo, available_timezones, reset_tzpath
import erfa
import tzdata
from common import ROOT, configure_core, finite_vector, read, sha, angular_delta
from utc_times import TimeAuthority

# Always use the shipped IANA snapshot, including on Linux/macOS.
reset_tzpath(())
HOUSE_SYSTEMS={'P':'Placidus','K':'Koch','C':'Campanus','R':'Regiomontanus','E':'Equal',
               'V':'Vehlow','X':'Meridian','O':'Porphyry','B':'Alcabitius','U':'Krusinski',
               'H':'Azimuth','M':'Morinus','T':'Polich-Page','W':'Whole Sign（整宮制）'}
SIGNS=['牡羊','金牛','雙子','巨蟹','獅子','處女','天秤','天蠍','射手','摩羯','水瓶','雙魚']
BODIES=[(0,'太陽','日','#df484c'),(1,'月亮','月','#e45e82'),(2,'水星','水','#22875e'),
        (3,'金星','金','#ce447e'),(4,'火星','火','#bc542e'),(5,'木星','木','#d85e2a'),
        (6,'土星','土','#88633d'),(7,'天王星','天','#387b59'),(8,'海王星','海','#4e65bb'),
        (9,'冥王星','冥','#474359'),(11,'北交點','北','#777c3c')]
MINORS=[(15,'凱龍星','凱','#3d8068'),(19,'婚神星','婚','#44866e'),(18,'智神星','智','#44866e'),
        (20,'灶神星','灶','#44866e'),(17,'穀神星','穀','#44866e')]
APP_VERSION='0.7.0-dev'
ASPECT_IDS=tuple(range(10))+(-2,-3)
DETAIL_BODY_ORDER=('太陽','月亮','水星','金星','火星','木星','土星','上升點','冥王星','天王星','海王星','天頂')
DETAIL_ANGLE_ORDER=(0,120,180,90,60,30,45,72,135,150)

def sorted_aspect_details(aspects):
    """Presentation order only; never change calculation or matrix ordering."""
    rank={name:i for i,name in enumerate(DETAIL_BODY_ORDER)}
    ordered=[]
    for original in aspects:
        a=dict(original)
        if rank[a['a']]>rank[a['b']]:
            a['a'],a['b']=a['b'],a['a']
            a['a_lon'],a['b_lon']=a['b_lon'],a['a_lon']
        ordered.append(a)
    def key(a):
        important_body=min(rank[a['a']],rank[a['b']])<7
        important_angle=a['angle'] in (0,120,180,90)
        group=(0 if important_angle else 2)+(0 if important_body else 1)
        return group,rank[a['a']],rank[a['b']],DETAIL_ANGLE_ORDER.index(a['angle'])
    return sorted(ordered,key=key)
ASPECTS=[(0,'合相',4.,'#dfb900',False),(90,'四分',3.,'#ed3030',False),
         (120,'三分',3.,'#3434ed',False),(180,'對分',3.,'#ed3030',False),
         (60,'六合',2.,'#3434ed',False),(30,'半六合',1.,'#69a9a9',True),
         (45,'半四分',1.,'#b57ac6',True),(72,'五分相',1.5,'#92934b',True),
         (135,'補八分',1.5,'#42b84b',True),(150,'梅花相',1.5,'#655e58',True)]

@dataclass(frozen=True)
class BirthInput:
    local_iso: str='1978-04-20T08:23:00'
    zone: str='Asia/Taipei'
    longitude: float=120.2
    latitude: float=23.0
    system: str='P'
    small_bodies: bool=True
    minor_aspects: bool=True
    fold: int | None=None
    manual_dst: bool=False
    dst_enabled: bool=False
    dst_minutes: int=60
    name: str=''
    gender: str='男'
    notes: str=''
    house_latitude: bool=True

def calculation_key(birth):
    """Identity and display preferences never change the astronomical instant."""
    return tuple(getattr(birth,k) for k in ('local_iso','zone','longitude','latitude',
        'system','fold','manual_dst','dst_enabled','dst_minutes','house_latitude'))

def display_chart(chart,birth,orbs=None):
    validate_chart_houses(chart)
    if calculation_key(BirthInput(**chart['input']))!=calculation_key(birth):
        raise UserError('出生條件已變更，請重新排盤。')
    points=[p for p in chart['all_points'] if birth.small_bodies or p['id'] not in {b[0] for b in MINORS}]
    orbs=orbs or {a:o for a,_,o,_,_ in ASPECTS}
    return dict(chart,input=asdict(birth),points=points,orbs=dict(orbs),
                aspects=find_aspects([p for p in points if p['id'] in ASPECT_IDS],birth.minor_aspects,orbs))

def utc_label(offset):
    seconds=int(offset.total_seconds());sign='+' if seconds>=0 else '-';seconds=abs(seconds)
    h,remainder=divmod(seconds,3600);m,s=divmod(remainder,60)
    return f'UTC{sign}{h:02}:{m:02}'+(f':{s:02}' if s else '')

def local_datetime(birth):
    """Validate unsupported leap input before datetime's generic rejection."""
    reject_leap_second(birth,_resolve_wall)
    return datetime.fromisoformat(birth.local_iso)


def resolve_local(birth):
    return _resolve_wall(birth,local_datetime(birth))


def _resolve_wall(birth,wall):
    if wall.tzinfo is not None: raise UserError('請輸入當地鐘錶時間，時區另外選擇。')
    zone=ZoneInfo(birth.zone); candidates={}
    for fold in (0,1):
        aware=wall.replace(tzinfo=zone,fold=fold);utc=aware.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None)==wall: candidates[utc]=aware
    if not candidates: raise UserError('這個當地時間因夏令時間切換而不存在，請核對出生時間。')
    choices=[v for _,v in sorted(candidates.items())]
    if len(choices)>1 and birth.fold is None:
        raise AmbiguousTimeError()
    if birth.fold not in (None,0,1): raise UserError('無效的重複時間選項。')
    chosen=choices[birth.fold or 0] if len(choices)>1 else choices[0]
    dst=chosen.dst() or timedelta();offset=chosen.utcoffset()
    if birth.manual_dst:
        if not -120<=birth.dst_minutes<=180: raise UserError('夏令調整需在 -120～180 分鐘內。')
        offset=offset-dst+(timedelta(minutes=birth.dst_minutes) if birth.dst_enabled else timedelta())
        dst=timedelta(minutes=birth.dst_minutes) if birth.dst_enabled else timedelta()
    fixed=wall.replace(tzinfo=timezone(offset));utc=fixed.astimezone(timezone.utc)
    return dict(utc=utc,offset=offset,dst=dst,local=fixed,ambiguous=len(choices)>1,
                offset_label=utc_label(offset),mode='手動夏令修正' if birth.manual_dst else '地區歷史時區')

def zodiac_text(lon):
    total=int(round((lon%360)*3600))%(360*3600)
    sign,inside=divmod(total,30*3600);degrees,rest=divmod(inside,3600);minutes,seconds=divmod(rest,60)
    return f'{SIGNS[sign]} {degrees:02}°{minutes:02}′{seconds:02}″'

def house_direction(cusps):
    """Validate twelve distinct, ordered cusps making exactly one directed turn.

    Never sort cusps: their sequence defines their house identities. Azimuth
    can run towards decreasing longitude. Degenerate/self-crossing rings must
    still fail; increasing a numerical tolerance is not a direction fix.
    """
    if len(cusps)!=12 or not all(math.isfinite(c) for c in cusps):
        raise ValueError('Expected twelve finite house cusps')
    for direction in (1,-1):
        widths=[(direction*(cusps[(i+1)%12]-start))%360 for i,start in enumerate(cusps)]
        if min(widths)>=1e-7 and abs(sum(widths)-360)<=1e-5:
            return direction
    raise ValueError('House cusps do not form one non-degenerate directed turn')

def house_number(lon,cusps,direction=None):
    """Ecliptic-longitude interval placement; each cusp belongs to its own house.

    Historical helper retained for archived regression cases. Production chart
    placement uses house_number2 with the actual ecliptic latitude.
    """
    direction=house_direction(cusps) if direction is None else direction
    if direction not in (1,-1):raise ValueError('Invalid house direction')
    for i,start in enumerate(cusps):
        if (direction*(lon-start))%360 < (direction*(cusps[(i+1)%12]-start))%360: return i+1
    return None

def house_midpoints(cusps):
    """Label anchors on the ecliptic wheel, independent of spatial placement."""
    direction=house_direction(cusps)
    return [(start+direction*((direction*(cusps[(i+1)%12]-start))%360)/2)%360
            for i,start in enumerate(cusps)]

def axis_house_number(lon,cusps,system,axis):
    """Resolve ASC/MC cusp identity without altering any physical longitude.

    Only systems that define that axis as that cusp may use this roundoff
    allowance (1e-10 degree = 0.00000036 arcsecond). It is not a general planet
    snapping tolerance and does not relax numerical regression comparisons.
    Azimuth retains its existing placement policy pending separate research.
    """
    if axis not in ('asc','mc'):raise ValueError('Expected ASC or MC')
    if system=='H':return house_number(lon,cusps)
    target=(1 if axis=='asc' and system in 'PKCREOBUT' else
            10 if axis=='mc' and system in 'PKCROBUTX' else None)
    if target is not None and abs(math.remainder(lon-cusps[target-1],360))<=1e-10:
        return target
    result=house_number(lon,cusps)
    if result is not None:return result
    # Subtraction/modulo can round a just-below-cusp angle into neither sector.
    # Ordered endpoints give even this residual case a house, without snapping.
    direction=house_direction(cusps);lon=lon%360
    for i,start in enumerate(cusps):
        start=start%360;end= cusps[(i+1)%12]%360
        if direction==1:
            inside=start<=lon<end if start<end else lon>=start or lon<end
        else:
            inside=end<lon<=start if start>end else lon<=start or lon>end
        if inside:return i+1
    raise ValueError('Axis longitude is not in a valid house interval')

def find_aspects(points,include_minor=True,orbs=None):
    orbs=orbs or {angle:orb for angle,_,orb,_,_ in ASPECTS};results=[]
    for i,a in enumerate(points):
        for b in points[i+1:]:
            if {a['name'],b['name']}=={'北交點','南交點'}: continue
            separation=abs(angular_delta(a['lon'],b['lon']));choices=[]
            for angle,name,default,color,minor in ASPECTS:
                orb=float(orbs[angle])
                if not math.isfinite(orb) or not 0<=orb<=15: raise UserError('相位容許度需在 0～15 度內。')
                if minor and not include_minor: continue
                error=abs(separation-angle)
                if error<=orb: choices.append((error,angle,name,color,minor,orb))
            if choices:
                error,angle,name,color,minor,orb=min(choices)
                results.append(dict(a=a['name'],b=b['name'],a_lon=a['lon'],b_lon=b['lon'],
                                    angle=angle,name=name,orb=error,limit=orb,color=color,minor=minor))
    return sorted(results,key=lambda r:r['orb'])

class ChartEngine:
    def __init__(self):
        configure_core()
        for manifest,needle in [('data-sources.lock.json','data/core/'),('desktop-data-sources.lock.json','')]:
            for item in read(ROOT/manifest)['files']:
                if needle in item['path'] and sha(ROOT/item['path'])!=item['sha256']:
                    raise UserError('星曆資料損壞，請重新安裝：{path}',path=item['path'])
        import libephemeris as e
        self.e=e;self.authority=TimeAuthority();self.lock=threading.Lock()
        e.set_leb_file(str(ROOT/'data/desktop/base_core.leb2'));e.set_strict_precision(True)

    def times(self,dt):
        if dt.year>=1972:
            t=self.authority.convert(dt.isoformat(),allow_model=True);notes=[]
            if t['ut1_source']=='model_outside_eop': notes.append('此日期的地球自轉時間採模型估計。')
            elif t['ut1_source']=='prediction_A': notes.append('此日期的地球自轉時間採預測值。')
            if t['leap_table_assumption']: notes.append('未來閏秒尚未確定，日期接近時請更新資料。')
            return t,notes
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',erfa.ErfaWarning)
            if dt.year>=1960:
                utc=erfa.dtf2d('UTC',dt.year,dt.month,dt.day,dt.hour,dt.minute,dt.second)
                tt=erfa.taitt(*erfa.utctai(*utc));sf=self.authority.ts.tt_jd(*tt)
                ut1=(float(sf.whole),float(sf.ut1_fraction));note='1960～1971 年：採歷史 UTC 換算，地球自轉時間以模型估計。'
            else:
                jd0,jdf=erfa.cal2jd(dt.year,dt.month,dt.day)
                ut1=(float(jd0),float(jdf)+(dt.hour*3600+dt.minute*60+dt.second)/86400)
                sf=self.authority.ts.ut1_jd(sum(ut1));tt=(float(sf.whole),float(sf.tt_fraction))
                note='1960 年以前：以歷史時區換算的格林威治時間近似地球自轉時間。'
            dpsi,deps=erfa.nut06a(*tt)
            return dict(tt_jd=sum(tt),ut1_jd=sum(ut1),ut1_source='historical_model',
                erfa_gast_deg=math.degrees(erfa.gst06a(*ut1,*tt))%360,
                erfa_true_obliquity_deg=math.degrees(erfa.obl06(*tt)+deps)),[note]

    def calculate(self,birth,orbs=None):
        if type(birth.house_latitude) is not bool:raise UserError('設定值需為勾選狀態。')
        if not math.isfinite(birth.latitude) or not -90<birth.latitude<90: raise UserError('緯度需小於 90°。')
        if not math.isfinite(birth.longitude) or not -180<=birth.longitude<=180: raise UserError('經度需在 0～180°。')
        if birth.system not in HOUSE_SYSTEMS: raise UserError('不支援的分宮制。')
        resolved=resolve_local(birth)
        if not datetime(1850,1,2,tzinfo=timezone.utc)<=resolved['utc']<datetime(2149,12,31,tzinfo=timezone.utc):
            raise UserError('本版可計算 UTC 1850/01/02～2149/12/30；邊界預留給光行時與速度計算。')
        with self.lock:
            t,notes=self.times(resolved['utc']);e=self.e
            try:
                e.set_calc_mode('skyfield')
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    cusps,angles=e.houses_armc((t['erfa_gast_deg']+birth.longitude)%360,birth.latitude,
                                              t['erfa_true_obliquity_deg'],birth.system.encode())
                if caught: raise UserError('此地點的分宮計算出現警示；請改選 Equal 或 Whole Sign。')
                cusps=finite_vector(cusps,12);angles=finite_vector(angles,8)
                direction=None
                try:
                    direction=house_direction(cusps)
                    # These systems can form a valid reversed ring at high latitudes.
                    # Keep Lib's numbered cusp order; shared renderers use its direction.
                    if direction==-1 and birth.system not in ('H','C','R'):
                        raise ValueError('Unsupported reverse system')
                except ValueError as exc:
                    if birth.system=='T' and direction is None:
                        raise UserError('此時間／地點的 Polich–Page 宮頭順序交錯或重疊，無法形成連續、不重疊的十二宮，因此停止排盤。請改選其他宮位制（例如 Equal 或 Whole Sign）後重新排盤。') from exc
                    raise UserError('此時間／地點的宮位無法形成有效十二宮，請改選 Equal 或 Whole Sign。') from exc
                points=[];flags=e.FLG_SWIEPH|e.FLG_SPEED
                def append(body):
                    ident,name,short,color=body
                    values,rf=e.calc(t['tt_jd'],ident,flags);v=finite_vector(values,6)
                    points.append(dict(id=ident,name=name,short=short,color=color,lon=v[0],lat=v[1],speed=v[3],
                                       retrograde=v[3]<0,house=None,source=e.get_calc_mode()))
                for body in BODIES: append(body)
                # Cache all physical positions so visibility changes are immediate.
                e.set_calc_mode('leb')
                for body in MINORS: append(body)
                e.set_calc_mode('skyfield')
                node=next(p for p in points if p['name']=='北交點')
                south=dict(node,id=-11,name='南交點',short='南',lon=(node['lon']+180)%360)
                points.append(south)
                sun=points[0]['lon'];moon=points[1]['lon'];asc,mc=angles[:2]
                eq,_=e.calc(t['tt_jd'],0,e.FLG_SWIEPH|e.FLG_EQUATORIAL)
                h=math.radians((t['erfa_gast_deg']+birth.longitude-eq[0])%360)
                phi,dec=math.radians(birth.latitude),math.radians(eq[1])
                day=math.sin(phi)*math.sin(dec)+math.cos(phi)*math.cos(dec)*math.cos(h)>=0
                fortune=(asc+moon-sun if day else asc+sun-moon)%360
                for ident,name,short,lon,color in [(-1,'幸運點','幸',fortune,'#688966'),(-2,'上升點','升',asc,'#447d67'),(-3,'天頂','頂',mc,'#447d67')]:
                    points.append(dict(id=ident,name=name,short=short,color=color,lon=lon,lat=0,speed=None,
                                       retrograde=False,house=None,source='derived'))
                azimuth_frame=(prepare_azimuth((t['erfa_gast_deg']+birth.longitude)%360,
                    birth.latitude,t['erfa_true_obliquity_deg'],cusps) if birth.system=='H' else None)
                house_positions={}
                polich_frame=(prepare_polich((t['erfa_gast_deg']+birth.longitude)%360,
                    birth.latitude,t['erfa_true_obliquity_deg'],cusps) if birth.system=='T' else None)
                polich_failures=[];invalid_houses=[]
                for point in points:
                    arguments=[(t['erfa_gast_deg']+birth.longitude)%360,birth.latitude,
                               t['erfa_true_obliquity_deg'],point['lon'],
                               point['lat'] if birth.house_latitude else 0.0,birth.system]
                    audit=dict(arguments=arguments)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        axis={-2:'asc',-3:'mc'}.get(point['id'])
                        try:
                            point['house']=house_number2(*arguments,audit=audit,axis=axis,
                                cusps=cusps if axis else None,azimuth_frame=azimuth_frame,
                                polich_frame=polich_frame)
                            validate_house_number(point['house'],birth.system,audit)
                        except InvalidHousePosition:
                            invalid_houses.append(dict(point_id=point['id'],house=point['house']))
                        except PolichGeometryError as exc:
                            polich_failures.append(dict(point_id=point['id'],reason=exc.reason))
                    audit['warnings']=[str(w.message) for w in caught]
                    house_positions[str(point['id'])]=audit
                if invalid_houses:
                    raise invalid_house_error(dict(failures=invalid_houses,house_positions=house_positions,
                        points=points,cusps=cusps,times=t,input=asdict(birth)))
                if polich_failures:
                    error=UserError('此時間／地點的 Polich–Page 宮位制因幾何多解、折返或退化，無法取得唯一且連續的歸宮結果，因此停止整張排盤。即使只有個別天體無法唯一歸宮，也不輸出星盤。請改選其他宮位制後重新排盤。')
                    if all(f['reason'] in {'numerically_indeterminate_boundary',
                        'library_house_disagrees_with_unique_root','invalid_library_position',
                        'library_wrong_half','library_not_converged','cusp_identity_not_a_small_residual'}
                        for f in polich_failures):
                        error=UserError('Polich–Page 個別點的原始求解值與已驗證的宮位邊界不一致，或精度不足以判定邊界哪一側，因此無法確認歸宮結果，停止整張排盤。請改選其他宮位制後重新排盤。')
                    error.diagnostics=dict(policy=house_policy_for('T'),frame=polich_frame.audit(),
                        failures=polich_failures,house_positions=house_positions,cusps=cusps,
                        points=points,times=t,input=asdict(birth))
                    raise error
                house_notices=azimuth_notices(birth.system,direction,mc,cusps,
                                               house_positions['-3']['raw_position'],frame=azimuth_frame)
                if any(p['house'] is None for p in points):
                    notes.append('部分天體在 Koch 宮制下無法定義宮位。')
            except AzimuthGeometryError as exc:
                raise UserError('此時間／地點的 Azimuth 空間方向無法確定，或宮頭與歸宮座標無法對齊，因此停止排盤。請改選其他宮位制（例如 Equal 或 Whole Sign）後重新排盤。') from exc
            except e.PolarCircleError as exc:
                raise UserError('此緯度無法使用 {system}，請改選 Equal 或 Whole Sign。',system=HOUSE_SYSTEMS[birth.system]) from exc
            finally: e.set_calc_mode('skyfield')
        if abs(birth.latitude)>65: notes.append('高緯度的宮頭對出生時間很敏感。')
        chart=dict(input=asdict(birth),utc=resolved['utc'].isoformat(),local=resolved['local'].isoformat(),
                    utc_offset=resolved['offset_label'],dst_minutes=resolved['dst'].total_seconds()/60,
                    timezone_mode=resolved['mode'],tzdata_version=tzdata.__version__,times=t,
                    cusps=cusps,asc=asc,mc=mc,all_points=points,
                    house_policy=house_policy_for(birth.system),house_positions=house_positions,
                    house_notices=house_notices,
                    notes=notes,day_chart=day,version=APP_VERSION)
        return display_chart(chart,birth,orbs)
