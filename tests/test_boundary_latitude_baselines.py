# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Keep 87 cases, invalid inputs and independent Swiss time coverage explicit."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch
import boundary_latitude_baselines as boundary

class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/'regression/boundary-v2/product/actual/cases.json'
        if not path.exists():path=ROOT/'results/numerical/boundary-dual-20261101/inputs/actual.json'
        if not path.exists():raise unittest.SkipTest('Author the fixed boundary mode inputs first')
        cls.suite=batch.read(path)

    def test_all_87_cases_are_preserved_with_distinct_native_coverage(self):
        result=batch.validate_suite(self.suite)
        self.assertEqual(result['cases'],87);self.assertEqual(result['kinds'],boundary.KINDS)
        self.assertEqual(result['reference_routes'],{'shared_chart':53,'native_leap_chart':1,'native_time':19,'not_comparable':14})

    def test_omitting_unsupported_case_cannot_pass_coverage(self):
        suite=copy.deepcopy(self.suite);suite['cases']=[c for c in suite['cases'] if c['id']!='edge-cusp-0.0']
        with self.assertRaises(ValueError):batch.validate_suite(suite)

    def test_cannot_resolve_ambiguous_time_by_silently_picking_fold(self):
        suite=copy.deepcopy(self.suite)
        next(c for c in suite['cases'] if c['id']=='edge-fold-None')['input']['fold']=0
        with self.assertRaises(ValueError):batch.validate_suite(suite)

    def test_cannot_substitute_frozen_time(self):
        suite=copy.deepcopy(self.suite);suite['groups'][0]['reference']['time_context']['tt_jd']+=.1
        with self.assertRaises(ValueError):batch.validate_suite(suite)

    def test_mode_only_applies_to_chart_cases(self):
        suite=copy.deepcopy(self.suite);suite['house_latitude_mode']='zero'
        for case in suite['cases']:
            if case['kind']=='chart':case['input']['house_latitude']=False
        self.assertEqual(batch.house_latitude_mode(suite),'zero');self.assertEqual(batch.validate_suite(suite)['cases'],87)

    def test_native_utc_conversion_preserves_a_leap_second(self):
        self.assertEqual(boundary.utc_calendar('2016-12-31T23:59:60Z'),[2016,12,31,23,59,60.])
        class Spy:
            GREG_CAL=1
            def utc_to_jd(self,*args):self.arguments=args;return 2457754.500789167,2457754.500006844
        case=next(c for c in self.suite['cases'] if c['kind']=='time' and ':60Z' in c['utc'])
        group=next(g for g in self.suite['groups'] if g['id']==case['group_id']);spy=Spy()
        row=boundary.calculate_case(spy,'swiss',case,group)
        self.assertEqual(spy.arguments,(2016,12,31,23,59,60.,1))
        self.assertEqual(row['status'],'ok');self.assertEqual(row['raw']['function'],'swisseph.utc_to_jd')
        self.assertIsNone(row['time_context'])

    def test_product_specific_helper_is_preserved_as_not_comparable(self):
        case=next(c for c in self.suite['cases'] if c['kind']=='aspect')
        group=next(g for g in self.suite['groups'] if g['id']==case['group_id'])
        row=boundary.calculate_case(object(),'swiss',case,group)
        self.assertEqual(row['status'],'not_comparable');self.assertIn('orb',row['raw']['reason'])

    def test_time_case_ids_are_kept_but_checkpoint_names_are_windows_safe(self):
        case=next(c for c in self.suite['cases'] if c['kind']=='time')
        self.assertIn(':',case['id']);self.assertNotIn(':',case['group_id'])
        self.assertEqual(len({c['group_id'] for c in self.suite['cases']}),87)

if __name__=='__main__':unittest.main()
