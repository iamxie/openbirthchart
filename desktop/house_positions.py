# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Production spatial house placement, shared by desktop and report output."""
from __future__ import annotations

import math
from numbers import Real
from typing import MutableMapping, Sequence
from .errors import UserError
from .azimuth import POLICY as AZIMUTH_POLICY, AzimuthFrame, AzimuthGeometryError, prepare_azimuth
from .polich import POLICY as POLICH_POLICY, PolichFrame, PolichGeometryError, prepare_polich


HOUSE_NUMBER2_POLICY = 'lib-house-pos-polich-asc-cusp-v4'
TWELVE_HOUSE_SYSTEMS = frozenset('PKCREVXOBUHMTW')
# Both checks are required. The longitude guard establishes cusp identity;
# the house-coordinate guard covers the Topocentric iterative residual (up to
# 1.79e-7 in the archived cases) without accepting an unrelated house number.
AXIS_CUSP_DEGREES = 1e-10
AXIS_POSITION_TOLERANCE = 1e-6
AXIS_SYSTEMS = {'asc': frozenset('PKCREOBUT'), 'mc': frozenset('PKCROBUTXH')}


class InvalidHousePosition(ValueError):
    """Invalid API coordinate or final house number, separate from geometry."""


def validate_house_number(house, system, audit=None):
    if type(house) is int and 1 <= house <= 12:
        return
    audit = audit or {}
    raw = audit.get('raw_position')
    if (house is None and system in ('K', b'K') and audit.get('status') == 'undefined'
            and isinstance(raw, Real) and not isinstance(raw, bool) and raw == 0.0):
        return
    raise InvalidHousePosition(f'Invalid final house number: {house!r}')


def invalid_house_error(diagnostics):
    error = UserError('計算結果包含無效宮號，無法完成排盤或匯出。')
    error.diagnostics = diagnostics
    return error


def validate_chart_houses(chart):
    """Guard cached/derived charts at presentation and export boundaries."""
    system = chart['input']['system']
    audits = chart.get('house_positions', {})
    failures = []
    for point in [*chart.get('all_points', []), *chart.get('points', [])]:
        try:
            validate_house_number(point.get('house'), system, audits.get(str(point['id'])))
        except InvalidHousePosition:
            failures.append(dict(point_id=point['id'], house=point.get('house')))
    if failures:
        raise invalid_house_error(dict(failures=failures, house_positions=audits))


def house_policy_for(system):
    return (AZIMUTH_POLICY if system in ('H', b'H') else
            POLICH_POLICY if system in ('T', b'T') else HOUSE_NUMBER2_POLICY)


def house_number2(
    armc: float,
    geographic_latitude: float,
    obliquity: float,
    longitude: float,
    latitude: float,
    system: str | bytes,
    *,
    audit: MutableMapping | None = None,
    axis: str | None = None,
    cusps: Sequence[float] | None = None,
    azimuth_frame: AzimuthFrame | None = None,
    polich_frame: PolichFrame | None = None,
) -> int | None:
    """Call LibEphemeris with supplied coordinates and return an integer house.

    The caller configures the existing LibEphemeris runtime, just as ChartEngine
    does. ChartEngine selects actual or zero latitude via the explicit user
    option; this function never replaces or rounds its supplied coordinates.
    Exact 13.0 is wrapped to 1.0. With explicit ASC/MC context, a point on
    its defined cusp may be corrected from just below that cusp's integer.
    Azimuth uses a validated cusp frame to align the continuous raw coordinate
    before taking its integer house. Actual latitude and raw API values remain
    intact. Every Azimuth call requires cusps or a prepared chart frame.

    Polich-Page requires a continuous cusp family and a unique simple root for
    every point. Only exact cusp identity with a small proved residual permits
    correction; an ASC name never overrides ambiguous geometry.

    Koch's documented 0 sentinel returns None (undefined), never house zero or
    an alternative house system. Other invalid results raise ValueError.
    Gauquelin's 36 sectors and unsupported systems are excluded explicitly.
    Optional audit captures the unmodified API value and the correction used.
    """
    code = system.decode('ascii') if isinstance(system, bytes) else system
    if not isinstance(code, str) or code not in TWELVE_HOUSE_SYSTEMS:
        raise ValueError(f'Unsupported twelve-house system: {system!r}')
    values = (armc, geographic_latitude, obliquity, longitude, latitude)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('house_number2 requires finite angular inputs')
    if not -90 < geographic_latitude < 90 or not -90 <= latitude <= 90:
        raise ValueError('Invalid geographic or ecliptic latitude')
    if axis is not None and (axis not in AXIS_SYSTEMS or cusps is None or
                            len(cusps) != 12 or not all(math.isfinite(c) for c in cusps)):
        raise ValueError('Axis correction requires a known axis and twelve finite cusps')

    import libephemeris

    returned = libephemeris.house_pos(
        armc, geographic_latitude, obliquity, (longitude, latitude), code.encode('ascii')
    )
    if not isinstance(returned, Real) or isinstance(returned, bool):
        if audit is not None:
            audit.update(policy=house_policy_for(code), raw_position=returned,
                         position=None, house=None, correction=None, status='invalid')
        raise InvalidHousePosition(f'Invalid LibEphemeris house_pos result: {returned!r}')
    raw = float(returned)
    correction = 'exact_13_to_1' if raw == 13.0 else None
    position = 1.0 if correction else raw
    boundary = None
    if code == 'T':
        if audit is not None:
            audit.update(policy=POLICH_POLICY,raw_position=raw,position=None,house=None,
                         correction=None,status='rejected')
        try:
            if polich_frame is None:
                if cusps is None:
                    cusps=libephemeris.houses_armc(armc,geographic_latitude,obliquity,b'T')[0]
                polich_frame=prepare_polich(armc,geographic_latitude,obliquity,cusps)
            if ((polich_frame.armc,polich_frame.geographic_latitude,polich_frame.obliquity)!=values[:3] or
                (cusps is not None and tuple(cusps)!=polich_frame.cusps)):
                raise PolichGeometryError('frame_input_mismatch',{})
            position,correction,proof=polich_frame.check_point(longitude,latitude,raw)
            if audit is not None:audit['polich_geometry']=proof
        except PolichGeometryError as exc:
            if audit is not None:audit['polich_geometry']=dict(reason=exc.reason,**exc.evidence)
            raise
    elif code == 'H':
        frame = azimuth_frame or prepare_azimuth(armc, geographic_latitude, obliquity, cusps)
        if ((frame.armc, frame.geographic_latitude, frame.obliquity) != values[:3] or
                (cusps is not None and frame.cusps != tuple(cusps))):
            raise AzimuthGeometryError('Azimuth frame does not belong to these chart inputs')
        position, correction, boundary = frame.align(raw, longitude, latitude)
        if audit is not None:
            audit['azimuth_numbering'] = frame.audit()
    elif axis is not None and code in AXIS_SYSTEMS[axis] and latitude == 0.0 and 1.0 <= raw < 13.0:
        target = 1 if axis == 'asc' else 10
        delta = abs(math.remainder(longitude - cusps[target - 1], 360.0))
        upper = 13.0 if target == 1 else 10.0
        if delta <= AXIS_CUSP_DEGREES and 0.0 < upper - raw <= AXIS_POSITION_TOLERANCE:
            position = float(target)
            correction = 'axis_cusp_roundoff'
            boundary = dict(axis=axis, target_house=target, cusp_longitude=cusps[target-1],
                            longitude_delta_degrees=delta, position_delta=upper-raw,
                            longitude_tolerance_degrees=AXIS_CUSP_DEGREES,
                            position_tolerance=AXIS_POSITION_TOLERANCE)
    valid = math.isfinite(position) and 1.0 <= position < 13.0
    undefined = code == 'K' and raw == 0.0
    house = math.floor(position) if valid else None
    if audit is not None:
        audit.update(
            policy=house_policy_for(code),
            raw_position=raw,
            position=position,
            house=house,
            correction=correction,
            status='ok' if valid else 'undefined' if undefined else 'invalid',
        )
        if boundary is not None:
            audit['boundary_correction'] = boundary
    if not valid and not undefined:
        raise InvalidHousePosition(f'Invalid LibEphemeris house_pos result: {raw!r}')
    return house


def azimuth_notices(system, direction, mc, cusps, mc_raw_position, *, frame=None):
    """Identify the reproduced numbering conditions without changing placement.

    Reversed H rings have an independently established cusp/placement mismatch.
    For forward rings, test MC identity and its returned coordinate rather than
    assuming every chart in a geographic hemisphere is affected.
    """
    if system != 'H':
        return []
    if frame is not None:
        return [dict(code='azimuth_numbering_aligned', **frame.audit())] if frame.changed else []
    reasons = []
    if direction == -1:
        reasons.append('reversed_cusp_numbering')
    if (abs(math.remainder(mc-cusps[9], 360.0)) <= AXIS_CUSP_DEGREES and
            abs(math.remainder(mc_raw_position-10.0, 12.0)) > AXIS_POSITION_TOLERANCE):
        reasons.append('mc_cusp_numbering')
    return [dict(code='azimuth_house_numbering', reasons=reasons)] if reasons else []
