# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Application-only alignment of spatial Azimuth coordinates to numbered cusps.

LibEphemeris remains the raw placement provider. Independent Cartesian geometry
checks the convention before a start/direction transform is applied to its value.
"""
from dataclasses import dataclass
import math

POLICY = 'lib-house-pos-azimuth-aligned-v5'
GEOMETRY_TOLERANCE = 1e-7  # degrees; validation only, never a boundary snap
CUSP_TOLERANCE = 1e-10  # degrees of ecliptic longitude
POSITION_TOLERANCE = 1e-9  # houses, requires independently identified cusp
HORIZONTAL_MINIMUM = 1e-12  # unit-vector projection; zenith/nadir are undefined


class AzimuthGeometryError(ValueError):
    """No trustworthy mapping exists for the supplied geometry/API convention."""


def spatial_angle(armc, geographic_latitude, obliquity, longitude, latitude):
    a, p, e, l, b = map(math.radians,
                        (armc, geographic_latitude, obliquity, longitude, latitude))
    x = math.cos(b) * math.cos(l)
    y = math.cos(b) * math.sin(l) * math.cos(e) - math.sin(b) * math.sin(e)
    z = math.cos(b) * math.sin(l) * math.sin(e) + math.sin(b) * math.cos(e)
    east = -math.sin(a) * x + math.cos(a) * y
    north = (-math.sin(p) * math.cos(a) * x - math.sin(p) * math.sin(a) * y
             + math.cos(p) * z)
    if math.hypot(east, north) <= HORIZONTAL_MINIMUM:
        raise AzimuthGeometryError('Azimuth is undefined at the zenith or nadir')
    return math.degrees(math.atan2(north, east)) % 360.0


@dataclass(frozen=True)
class AzimuthFrame:
    armc: float
    geographic_latitude: float
    obliquity: float
    cusps: tuple[float, ...]
    origin: float
    direction: int

    @property
    def changed(self):
        return self.origin != 0.0 or self.direction != 1

    def align(self, raw, longitude, latitude):
        if not math.isfinite(raw) or not 1.0 <= raw <= 13.0:
            raise AzimuthGeometryError(f'Invalid raw Azimuth house position: {raw!r}')
        angle = spatial_angle(self.armc, self.geographic_latitude, self.obliquity,
                              longitude, latitude)
        raw_angle = (raw - 1.0) * 30.0
        if abs(math.remainder(angle - raw_angle, 360.0)) > GEOMETRY_TOLERANCE:
            raise AzimuthGeometryError('Raw Azimuth coordinate convention does not match geometry')
        # Preserve identity-frame values exactly. Transform before taking floor.
        position = (1.0 + (self.direction * (raw_angle - self.origin) % 360.0) / 30.0
                    if self.changed else (1.0 if raw == 13.0 else raw))
        correction = 'azimuth_numbering' if self.changed else ('exact_13_to_1' if raw == 13.0 else None)
        boundary = None
        # A geometric cusp is owned by its numbered house. Do not round an
        # arbitrary .99999 or erase latitude to establish that identity.
        if latitude == 0.0:
            for i, cusp in enumerate(self.cusps):
                delta = abs(math.remainder(longitude - cusp, 360.0))
                residual = math.remainder(position - (i + 1.0), 12.0)
                if delta <= CUSP_TOLERANCE and abs(residual) <= POSITION_TOLERANCE:
                    if position != i + 1.0:
                        boundary = dict(target_house=i+1, cusp_longitude=cusp,
                                        longitude_delta_degrees=delta, position_delta=residual,
                                        longitude_tolerance_degrees=CUSP_TOLERANCE,
                                        position_tolerance=POSITION_TOLERANCE)
                        position = i + 1.0
                        if correction is None:
                            correction = 'azimuth_cusp_roundoff'
                    break
        if not 1.0 <= position < 13.0:
            raise AzimuthGeometryError('Aligned Azimuth position is outside the twelve houses')
        return position, correction, boundary

    def audit(self):
        return dict(origin_degrees=self.origin, direction=self.direction,
                    numbering_changed=self.changed, geometry_tolerance_degrees=GEOMETRY_TOLERANCE)


def prepare_azimuth(armc, geographic_latitude, obliquity, cusps):
    if (cusps is None or len(cusps) != 12 or
            not all(math.isfinite(v) for v in (armc, geographic_latitude, obliquity, *cusps)) or
            not -90 < geographic_latitude < 90):
        raise AzimuthGeometryError('Azimuth alignment requires twelve finite cusps and a valid location')
    angles = [spatial_angle(armc, geographic_latitude, obliquity, c, 0.0) for c in cusps]
    # Current cusp convention begins at the eastern or western horizon.
    # A future incompatible library convention must fail explicitly.
    origin = min((0.0, 180.0), key=lambda x: abs(math.remainder(angles[0]-x, 360.0)))
    step = math.remainder(angles[1] - angles[0], 360.0)
    direction = 1 if step > 0 else -1
    if any(abs(math.remainder(v - (origin + direction*i*30.0), 360.0)) > GEOMETRY_TOLERANCE
           for i, v in enumerate(angles)):
        raise AzimuthGeometryError('Numbered Azimuth cusps do not define twelve consistent spatial sectors')
    return AzimuthFrame(armc, geographic_latitude, obliquity, tuple(cusps), origin, direction)
