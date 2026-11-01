# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Independent geometry, cusp ownership, and application-only H alignment."""
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from common import configure_core
configure_core()
import libephemeris as lib
from desktop.azimuth import prepare_azimuth, AzimuthGeometryError
from desktop.house_positions import house_number2
from desktop.model import house_number, house_direction, ChartEngine, BirthInput
from desktop.errors import UserError


class AlignmentTests(unittest.TestCase):
    # Both hemispheres, both cusp directions, plus regular equatorial cases.
    frames = ((0.,30.), (0.,-30.), (90.,12.), (270.,-12.), (90.,0.), (45.,0.))

    def make_frame(self, armc, lat):
        cusps, _ = lib.houses_armc(armc,lat,23.4393,b'H')
        return prepare_azimuth(armc,lat,23.4393,cusps)

    def test_twelve_cusps_and_both_sides_match_directed_ecliptic_sectors(self):
        shapes=set()
        for armc,lat in self.frames:
            f=self.make_frame(armc,lat);direction=house_direction(f.cusps)
            shapes.add((f.origin,f.direction))
            for i,cusp in enumerate(f.cusps):
                for offset in (-1e-3,-1e-6,-1e-8,0.,1e-8,1e-6,1e-3):
                    lon=(cusp+offset)%360; audit={}
                    h=house_number2(armc,lat,23.4393,lon,0.,'H',azimuth_frame=f,audit=audit)
                    with self.subTest(armc=armc,lat=lat,cusp=i+1,offset=offset):
                        expected=i+1 if offset==0 else ((i if offset*direction>0 else i-1)%12+1)
                        self.assertEqual(h,expected)
                        self.assertEqual(audit['raw_position'],lib.house_pos(armc,lat,23.4393,(lon,0.),b'H'))
            for lon in (i*.7 for i in range(514)):
                self.assertEqual(house_number2(armc,lat,23.4393,lon,0.,'H',azimuth_frame=f),
                                 house_number(lon,f.cusps))
        self.assertEqual(shapes,{(0.,1),(0.,-1),(180.,1),(180.,-1)})

    def test_nonzero_latitude_matches_independent_equatorial_bearing(self):
        differences=0
        for armc,lat in self.frames:
            f=self.make_frame(armc,lat)
            for lon in (11.3,67.2,144.9,218.4,301.8):
                for beta in (-40.,-5.,5.,40.):
                    # Separate spherical path: ecliptic -> RA/declination ->
                    # local bearing. No production helper supplies expectations.
                    l,b,e=map(math.radians,(lon,beta,23.4393))
                    dec=math.asin(math.sin(b)*math.cos(e)+math.cos(b)*math.sin(e)*math.sin(l))
                    ra=math.atan2(math.sin(l)*math.cos(e)-math.tan(b)*math.sin(e),math.cos(l))
                    ha=math.radians(armc)-ra;p=math.radians(lat)
                    east=-math.cos(dec)*math.sin(ha)
                    north=math.sin(dec)*math.cos(p)-math.cos(dec)*math.cos(ha)*math.sin(p)
                    bearing=math.degrees(math.atan2(north,east))%360
                    expected=math.floor(1+(f.direction*(bearing-f.origin)%360)/30)
                    h=house_number2(armc,lat,23.4393,lon,beta,'H',azimuth_frame=f)
                    self.assertEqual(h,expected)
                    differences+=h!=house_number2(armc,lat,23.4393,lon,0.,'H',azimuth_frame=f)
        self.assertGreater(differences,10)

    def test_undefined_geometry_invalid_cusps_and_stale_frames_fail_explicitly(self):
        f=self.make_frame(0.,30.)
        for cusps in (None,f.cusps[:-1],(0.,)*12,tuple(reversed(f.cusps))):
            with self.assertRaises(AzimuthGeometryError):prepare_azimuth(0.,30.,23.4393,cusps)
        with self.assertRaises(AzimuthGeometryError):
            house_number2(1.,30.,23.4393,15.,1.,'H',azimuth_frame=f)
        # Equatorial zenith on the ecliptic: azimuth has no defined direction.
        with self.assertRaises(AzimuthGeometryError):self.make_frame(0.,0.)
        with self.assertRaises(AzimuthGeometryError):
            house_number2(90.,0.,23.4393,90.,-23.4393,'H',azimuth_frame=self.make_frame(90.,0.))

    def test_invalid_or_changed_library_convention_cannot_be_hidden_by_modulo(self):
        f=self.make_frame(0.,-30.)
        for raw in (0.,-1.,14.,math.nan,math.inf,7.):
            with patch.object(lib,'house_pos',return_value=raw),self.assertRaises(AzimuthGeometryError):
                house_number2(0.,-30.,23.4393,17.,5.,'H',azimuth_frame=f)

    def test_geometry_failure_becomes_explanatory_user_error(self):
        engine=ChartEngine()
        with patch('desktop.model.prepare_azimuth',side_effect=AzimuthGeometryError('degenerate')):
            with self.assertRaises(UserError) as caught:engine.calculate(BirthInput(system='H'))
        self.assertIn('Azimuth',str(caught.exception));self.assertIn('Equal',str(caught.exception))


if __name__=='__main__':unittest.main()
