# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Guard the original 1200-case scope, frozen times, and latitude mode routing."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch

class MainSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=ROOT/'regression/main-v2/product'
        if folder.exists():cls.suites={m:batch.read(folder/m/'cases.json') for m in ('actual','zero')}
        else:
            folder=ROOT/'results/numerical/main-dual-20261031/inputs'
            if not folder.exists():raise unittest.SkipTest('Author the fixed dual-mode inputs first')
            cls.suites={m:batch.read(folder/f'{m}.json') for m in ('actual','zero')}

    def test_both_modes_have_original_1200_and_no_boundaries(self):
        for mode,suite in self.suites.items():
            counts=batch.validate_suite(suite)
            self.assertEqual(counts['cases'],1200);self.assertEqual(counts['boundary'],0)
            self.assertEqual(batch.house_latitude_mode(suite),mode)

    def test_boundary_case_cannot_enter_main_suite(self):
        suite=copy.deepcopy(self.suites['actual'])
        original=batch.read(ROOT/'regression/cases-v2.json')
        suite['cases'].append(next(c for c in original['cases'] if c['group']=='boundary'))
        with self.assertRaises(ValueError):batch.validate_suite(suite)

    def test_balanced_but_resampled_time_is_rejected(self):
        suite=copy.deepcopy(self.suites['actual'])
        case=suite['cases'][0]
        case['input']['local_iso']=case['input']['local_iso'][:-2]+'01'
        with self.assertRaises(ValueError):batch.validate_suite(suite)

    def test_frozen_physical_time_is_not_substitutable(self):
        suite=copy.deepcopy(self.suites['actual']);suite['groups'][0]['tt_jd']+=.001
        with self.assertRaises(ValueError):batch.validate_suite(suite)

    def test_complete_2016_coverage_remains_separate(self):
        suite=batch.read(ROOT/'regression/complete-v2/product/actual/cases.json')
        self.assertEqual(batch.validate_suite(suite)['cases'],2016)

if __name__=='__main__':unittest.main()
