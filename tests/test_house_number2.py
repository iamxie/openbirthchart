# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Candidate house-position contracts and actual archived regression examples."""
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from common import configure_core
configure_core()
import libephemeris
from desktop.house_positions import house_number2, azimuth_notices, AXIS_POSITION_TOLERANCE


class HouseNumber2Tests(unittest.TestCase):
    args = (120.0, 25.0, 23.4393, 225.0, 3.0, 'P')

    def test_passes_actual_latitude_and_preserves_fractional_result(self):
        audit = {}
        with patch.object(libephemeris, 'house_pos', return_value=7.625) as api:
            self.assertEqual(house_number2(*self.args, audit=audit), 7)
        api.assert_called_once_with(120.0, 25.0, 23.4393, (225.0, 3.0), b'P')
        self.assertEqual(audit['raw_position'], 7.625)
        self.assertEqual(audit['position'], 7.625)
        self.assertIsNone(audit['correction'])

    def test_wraps_exact_thirteen_only(self):
        for raw, expected in [(13.0, 1), (math.nextafter(13.0, 0), 12),
                              (math.nextafter(10.0, 0), 9), (10.0, 10), (1.0, 1)]:
            with self.subTest(raw=raw), patch.object(libephemeris, 'house_pos', return_value=raw):
                audit = {}
                self.assertEqual(house_number2(*self.args, audit=audit), expected)
                self.assertEqual(audit['raw_position'], raw)
                self.assertEqual(audit['correction'], 'exact_13_to_1' if raw == 13 else None)

    def test_koch_zero_remains_undefined(self):
        audit = {}
        with patch.object(libephemeris, 'house_pos', return_value=0.0):
            self.assertIsNone(house_number2(*self.args[:-1], 'K', audit=audit))
        self.assertEqual(audit['status'], 'undefined')
        self.assertEqual(audit['raw_position'], 0.0)
        self.assertIsNone(audit['correction'])

    def test_other_invalid_values_are_not_normalized(self):
        for raw in [0.0, -1.0, 14.0, math.nextafter(13.0, math.inf), math.nan, math.inf]:
            with self.subTest(raw=raw), patch.object(libephemeris, 'house_pos', return_value=raw):
                with self.assertRaises(ValueError):
                    house_number2(*self.args)

    def test_excludes_36_sector_system_and_invalid_inputs_before_api(self):
        with patch.object(libephemeris, 'house_pos') as api:
            for code in ['G', 'g', '', 'PP', 'Z']:
                with self.subTest(system=code), self.assertRaises(ValueError):
                    house_number2(*self.args[:-1], code)
            with self.assertRaises(ValueError):
                house_number2(math.nan, *self.args[1:])
            api.assert_not_called()

    def test_archived_thirteen_cases_call_real_unmodified_library(self):
        path = ROOT / 'tests/fixtures/house-pos-exact-thirteen.json'
        examples = [r for r in json.loads(path.read_text(encoding='utf-8')) if r['lib']['value'] == 13.0]
        self.assertEqual(len(examples), 43)
        for r in examples:
            with self.subTest(case=r['case']):
                audit = {}
                result = house_number2(r['armc'], r['geographic_latitude'], r['obliquity'],
                                       r['longitude'], r['latitude'], r['system'], audit=audit)
                self.assertEqual(result, 1)
                self.assertEqual(audit['raw_position'], 13.0)
                self.assertEqual(audit['correction'], 'exact_13_to_1')

    def test_actual_latitude_affects_real_spatial_placement(self):
        actual = {}; zero = {}
        house_number2(*self.args, audit=actual)
        house_number2(*self.args[:4], 0.0, 'P', audit=zero)
        self.assertGreater(abs(actual['raw_position'] - zero['raw_position']), 0.001)

    def test_axis_identity_and_numeric_guard_are_both_required(self):
        cusps=[float(i*30) for i in range(12)]
        for axis,lon,raw,target in [('asc',0.,13.-1.79e-7,1),('mc',270.,10.-1e-8,10)]:
            args=(120.,25.,23.4393,lon,0.,'P')
            with self.subTest(axis=axis),patch.object(libephemeris,'house_pos',return_value=raw):
                audit={}
                self.assertEqual(house_number2(*args,axis=axis,cusps=cusps,audit=audit),target)
                self.assertEqual(audit['raw_position'],raw)
                self.assertEqual(audit['correction'],'axis_cusp_roundoff')
                self.assertEqual(house_number2(*args),math.floor(raw))
                self.assertEqual(house_number2(*args[:3],lon-1e-8,0.,'P',axis=axis,cusps=cusps),math.floor(raw))
                self.assertEqual(house_number2(*args[:4],1e-8,'P',axis=axis,cusps=cusps),math.floor(raw))
        with patch.object(libephemeris,'house_pos',return_value=9.99999):
            self.assertEqual(house_number2(120.,25.,23.4393,270.,0.,'P',axis='mc',cusps=cusps),9)
        for system,axis,lon,raw in [('W','asc',0.,12.99999999),('E','mc',270.,9.99999999),('M','mc',270.,9.99999999)]:
            with patch.object(libephemeris,'house_pos',return_value=raw):
                self.assertEqual(house_number2(120.,25.,23.4393,lon,0.,system,axis=axis,cusps=cusps),math.floor(raw))

    def test_exact_zero_degree_wrap_and_historical_azimuth_notices(self):
        cusps=[float(i*30) for i in range(12)]
        with patch.object(libephemeris,'house_pos',return_value=12.999999999999998):
            self.assertEqual(house_number2(120.,25.,23.4393,360.-5e-11,0.,'P',axis='asc',cusps=cusps),1)
        self.assertTrue(azimuth_notices('H',1,270.,cusps,4.))
        self.assertTrue(azimuth_notices('H',-1,270.,cusps,10.))
        self.assertFalse(azimuth_notices('H',1,270.,cusps,9.999999999999998))
        self.assertFalse(azimuth_notices('P',1,270.,cusps,4.))

    def test_all_223_archived_boundaries_and_three_exceptions_with_real_api(self):
        pairs=json.loads((ROOT/'tests/fixtures/axis-cusp-0.6.3.json').read_text(encoding='utf-8'))['cases']
        corrected=0;azimuth_corrected=0
        for pair in pairs:
            key=str(pair['point_id']);audit={}
            with self.subTest(case=pair['case'],point=key):
                value=house_number2(*pair['arguments'],axis='asc' if key=='-2' else 'mc',cusps=pair['cusps'],audit=audit)
                self.assertEqual(audit['raw_position'],pair['raw_position'])
                if pair['arguments'][-1]=='H':
                    self.assertEqual(value,10)
                    self.assertIn(audit['correction'],('azimuth_cusp_roundoff','azimuth_numbering'))
                    azimuth_corrected+=1
                else:
                    self.assertEqual(value,pair['expected_house']);self.assertEqual(audit['correction'],'polich_unique_cusp_roundoff' if pair['arguments'][-1]=='T' else 'axis_cusp_roundoff');corrected+=1
        self.assertEqual(corrected+azimuth_corrected,226)
        self.assertGreater(azimuth_corrected,3)



if __name__ == '__main__':
    unittest.main()
