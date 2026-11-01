# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Fail-closed validation of the Polich–Page circle family, independent of Qt.

This validates the existing library; it does not replace its house_pos result.
For eastern meridian distance H, a position belongs to a circle q when
sin(dec)*tan(phi)*k(q) - cos(dec)*sin(H-q) = 0. The pole ratio k is q/90
on [0,90] and (180-q)/90 on [90,180]. Western positions are mirrored.
Both quadrants must be searched: a horizon-based restriction can hide roots.
"""
from dataclasses import dataclass
import math

POLICY = 'lib-house-pos-polich-unique-v5'
R = math.radians
D = math.degrees
ROUNDING = 2e-14                 # normalized plane residual, binary64 guard
SLOPE_GUARD = 1e-12             # normalized residual per parameter degree
GEOMETRY_GUARD = 1e-12          # forward derivative numerator / norm
CUSP_MATCH = 1e-10              # degrees, independent reconstruction only
RAW_FRAME_RESIDUAL = 1.1e-6     # degrees; library stops at 1e-6 degrees
CUSP_POSITION_RESIDUAL = 1e-5   # house coordinate; never a longitude snap band


class PolichGeometryError(ValueError):
    def __init__(self, reason, evidence):
        self.reason, self.evidence = reason, evidence
        super().__init__(reason)


def equatorial(lon, lat, eps):
    x = math.cos(R(lat))*math.cos(R(lon))
    y = math.cos(R(lat))*math.sin(R(lon))*math.cos(R(eps))-math.sin(R(lat))*math.sin(R(eps))
    z = math.cos(R(lat))*math.sin(R(lon))*math.sin(R(eps))+math.sin(R(lat))*math.cos(R(eps))
    return D(math.atan2(y,x)) % 360, D(math.atan2(z,math.hypot(x,y))), math.hypot(x,y)


def _bisect(f, lo, hi):
    flo = f(lo)
    for _ in range(64):
        mid = (lo+hi)/2
        if mid == lo or mid == hi:
            break
        fm = f(mid)
        if fm == 0:
            return mid
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo+hi)/2


def _segment_roots(b, c, h, lo, hi, slope, intercept):
    f = lambda q: b*(slope*q+intercept)-c*math.sin(R(h-q))
    df = lambda q: b*slope+c*R(1)*math.cos(R(h-q))
    bounds = [lo, hi]
    ratio = -b*slope/(c*R(1))
    if abs(ratio) <= 1:
        angle = D(math.acos(ratio))
        for sign in (-1,1):
            for turn in (-1,0,1):
                q = h-sign*angle+360*turn
                if lo < q < hi:
                    bounds.append(q)
    bounds = sorted(set(bounds))
    roots = []
    for q in bounds:
        if abs(f(q)) <= ROUNDING:
            if abs(df(q)) <= SLOPE_GUARD:
                raise PolichGeometryError('tangent_or_indeterminate_root',dict(q=q,residual=f(q),slope=df(q)))
            roots.append(q)
    for left,right in zip(bounds,bounds[1:]):
        if f(left)*f(right) < 0 and abs(f(left)) > ROUNDING and abs(f(right)) > ROUNDING:
            q = _bisect(f,left,right)
            if abs(df(q)) <= SLOPE_GUARD:
                raise PolichGeometryError('ill_conditioned_root',dict(q=q,residual=f(q),slope=df(q)))
            roots.append(q)
    return roots


@dataclass(frozen=True)
class PolichFrame:
    armc: float
    geographic_latitude: float
    obliquity: float
    cusps: tuple
    geometry: dict

    def audit(self):
        return self.geometry

    def check_point(self, longitude, latitude, raw):
        if self.geometry['status'] != 'ok':
            raise PolichGeometryError(self.geometry['reason'],dict(frame=self.geometry))
        if not math.isfinite(raw) or not 1 <= raw <= 13:
            raise PolichGeometryError('invalid_library_position',dict(raw_position=raw))
        ra,dec,xy = equatorial(longitude,latitude,self.obliquity)
        if xy <= GEOMETRY_GUARD:
            raise PolichGeometryError('equatorial_pole',dict(ra=ra,declination=dec))
        signed_h = math.remainder(ra-self.armc,360)
        h = abs(signed_h)
        b = math.sin(R(dec))*math.tan(R(self.geographic_latitude))
        c = math.cos(R(dec))
        scale = max(1.,abs(b),abs(c))
        b, c = b/scale, c/scale
        if c <= GEOMETRY_GUARD:
            raise PolichGeometryError('ill_conditioned_coordinates',dict(declination=dec))
        candidates = (_segment_roots(b,c,h,0.,90.,1/90,0.) +
                      _segment_roots(b,c,h,90.,180.,-1/90,2.))
        # At a meridian, q=0 and q=180 describe the same full plane.
        # Keep the appropriate oriented half, rather than counting its antipode.
        candidates = [q for q in candidates if not(q == 0 and h > 90) and not(q == 180 and h < 90)]
        qs = []
        for q in sorted(candidates):
            # Only the shared endpoint is duplicated by the two closed intervals.
            if not qs or q != qs[-1]:
                qs.append(q)
        def position(q):
            return ((q if signed_h >= 0 else -q)-90)%360/30+1
        proof = dict(ra=ra,declination=dec,meridian_distance=signed_h,
                     roots=[dict(q=q,position=position(q)) for q in qs],
                     residual_guard=ROUNDING,slope_guard=SLOPE_GUARD)
        if len(qs) != 1:
            raise PolichGeometryError('multiple_roots' if qs else 'no_root',proof)
        q = qs[0]
        # A piecewise join must be locally one-to-one on both sides.
        if q == 90:
            slopes = [b/90+c*R(1)*math.cos(R(h-q)), -b/90+c*R(1)*math.cos(R(h-q))]
            if min(abs(s) for s in slopes) <= SLOPE_GUARD or slopes[0]*slopes[1] <= 0:
                raise PolichGeometryError('noncontinuous_join',dict(**proof,slopes=slopes))
        raw_q = ((raw-1)*30+90)%360
        if signed_h < 0:
            raw_q = (-raw_q)%360
        if raw_q > 180 and 360-raw_q <= 1e-5:
            raw_q -= 360  # numerical residual immediately across the MC
        if raw_q < -1e-5 or raw_q > 180+1e-5:
            raise PolichGeometryError('library_wrong_half',dict(**proof,raw_q=raw_q))
        k = raw_q/90 if raw_q <= 90 else (180-raw_q)/90
        pole = math.atan(k*math.tan(R(self.geographic_latitude)))
        residual = D(math.asin(max(-1.,min(1.,math.sin(R(dec))*math.sin(pole)-
                                      math.cos(R(dec))*math.sin(R(h-raw_q))*math.cos(pole)))))
        proof.update(unique_position=position(q),raw_frame_residual_degrees=residual,
                     raw_frame_residual_limit=RAW_FRAME_RESIDUAL)
        if abs(residual) > RAW_FRAME_RESIDUAL:
            raise PolichGeometryError('library_not_converged',proof)
        value = 1. if raw == 13 else raw
        correction = 'exact_13_to_1' if raw == 13 else None
        # Identity is exact modulo a full turn, not merely proximity. A genuine
        # nearby body, however close, is never pulled across the boundary.
        target = next((i+1 for i,lon in enumerate(self.cusps)
                       if latitude == 0. and math.remainder(longitude-lon,360) == 0.),None)
        if target is not None:
            delta = abs(math.remainder(raw-target,12))
            root_delta = abs(math.remainder(position(q)-target,12))
            if delta > CUSP_POSITION_RESIDUAL or root_delta > CUSP_MATCH:
                raise PolichGeometryError('cusp_identity_not_a_small_residual',dict(**proof,target=target,raw_delta=delta))
            if value != target:
                value, correction = float(target), 'polich_unique_cusp_roundoff'
            proof['cusp_identity'] = dict(target_house=target,longitude=self.cusps[target-1],
                                         raw_position_delta=delta,position_limit=CUSP_POSITION_RESIDUAL,
                                         longitude_delta_degrees=0.)
        else:
            # A small solver residual can put an ordinary near-cusp point on
            # the wrong side. It has no endpoint identity, so never snap it.
            # Check the nearest numbered circle independently; if binary64
            # cannot separate it from the boundary, fail rather than guess.
            boundary_q=round(q/30)*30
            boundary_k=boundary_q/90 if boundary_q<=90 else (180-boundary_q)/90
            boundary_residual=b*boundary_k-c*math.sin(R(h-boundary_q))
            proof['nearest_boundary_residual']=boundary_residual
            if abs(boundary_residual)<=ROUNDING:
                raise PolichGeometryError('numerically_indeterminate_boundary',proof)
            if math.floor(value)!=math.floor(position(q)):
                raise PolichGeometryError('library_house_disagrees_with_unique_root',proof)
        return value, correction, proof


def prepare_polich(armc, geographic_latitude, obliquity, cusps):
    """Certify the whole continuous ecliptic family, not only 12 samples.

    Forward longitude is atan2(y,x), y=sin(a+q),
    x=cos(a+q)*cos(eps)-k(q)*tan(phi)*sin(eps).
    Its derivative numerator N has derivative proportional to k*sin(a+q).
    Thus segment endpoints and sin(a+q)=0 include all extrema of N.
    Strict N>0 also excludes a zero (x,y), folded branches and stationary cusps.
    Opposite circles repeat the same derivative, so [0,180] covers the full ring.
    """
    if (cusps is None or len(cusps)!=12 or
        not all(math.isfinite(v) for v in (armc,geographic_latitude,obliquity,*cusps)) or
        not -90 < geographic_latitude < 90):
        raise PolichGeometryError('invalid_frame',{})
    a = armc%360
    ce,se,tp = math.cos(R(obliquity)),math.sin(R(obliquity)),math.tan(R(geographic_latitude))
    checkpoints=[]
    for lo,hi,slope,intercept in [(0.,90.,1/90,0.),(90.,180.,-1/90,2.)]:
        qs=[lo,hi]+[n*180-a for n in range(4) if lo < n*180-a < hi]
        for q in qs:
            k=slope*q+intercept;t=R(a+q)
            x,y=math.cos(t)*ce-k*tp*se,math.sin(t)
            numerator=R(1)*ce+tp*se*(slope*math.sin(t)-k*R(1)*math.cos(t))
            # Scale prevents a near-polar large tangent from hiding cancellation.
            normalized=numerator/max(1.,abs(tp*se))
            checkpoints.append(dict(q=q,segment_start=lo,numerator=normalized,norm_squared=x*x+y*y))
    geometry=dict(status='ok',reason=None,checkpoints=checkpoints,derivative_guard=GEOMETRY_GUARD)
    if any(p['numerator'] <= GEOMETRY_GUARD or p['norm_squared'] <= GEOMETRY_GUARD**2 for p in checkpoints):
        geometry.update(status='rejected',reason='folded_or_degenerate_family')
    errors=[]
    for i,cusp in enumerate(cusps):
        q=((i-9)*30)%360
        opposite=q>=180
        q=q%180
        k=q/90 if q<=90 else (180-q)/90
        lon=D(math.atan2(math.sin(R(a+q)),math.cos(R(a+q))*ce-k*tp*se))%360
        if opposite:lon=(lon+180)%360
        errors.append(abs(math.remainder(lon-cusp,360)))
    geometry['cusp_reconstruction_errors_degrees']=errors
    if max(errors)>CUSP_MATCH:
        geometry.update(status='rejected',reason='cusp_family_mismatch')
    return PolichFrame(armc,geographic_latitude,obliquity,tuple(cusps),geometry)
