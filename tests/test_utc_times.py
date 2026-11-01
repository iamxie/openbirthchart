# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Independent UTC conversion contracts, especially the discontinuous UTC leap."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from utc_times import TimeAuthority, seconds_between
from compare_utc import coverage

class UTCTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.authority=TimeAuthority()

    def test_1999_known_atomic_offset(self):
        row=self.authority.convert('1999-04-25T13:25:31Z')
        self.assertEqual(row['tai_minus_utc'],32)
        self.assertAlmostEqual(seconds_between(row['tt_parts'],row['utc_parts']),64.184,places=6)
        self.assertTrue(row['measured_time'])
        self.assertLess(abs(row['independent_skyfield_tt_difference_seconds']),1e-5)

    def test_leap_second_advances_tt_and_ut1_by_one_second(self):
        rows=[self.authority.convert(iso) for iso in ('2016-12-31T23:59:59Z',
              '2016-12-31T23:59:60Z','2017-01-01T00:00:00Z')]
        for before,after in zip(rows,rows[1:]):
            self.assertAlmostEqual(seconds_between(after['tt_parts'],before['tt_parts']),1,places=6)
            self.assertAlmostEqual(seconds_between(after['ut1_parts'],before['ut1_parts']),1,places=5)
        self.assertAlmostEqual(rows[-1]['dut1_seconds']-rows[1]['dut1_seconds'],1,places=5)

    def test_rejects_invalid_leap_second(self):
        with self.assertRaises(ValueError): self.authority.convert('2016-12-30T23:59:60Z')

    def test_no_silent_model_extrapolation(self):
        with self.assertRaises(ValueError): self.authority.convert('2149-12-31T12:00:00Z')
        row=self.authority.convert('2149-12-31T12:00:00Z',allow_model=True)
        self.assertFalse(row['measured_time'])
        self.assertTrue(row['leap_table_assumption'])
        self.assertEqual(row['ut1_source'],'model_outside_eop')

    def test_eop_sample_reproduces_published_value(self):
        row=self.authority.convert('1999-04-25T00:00:00Z')
        self.assertAlmostEqual(row['dut1_seconds'],row['eop']['left']['dut1'],places=10)

    def test_offset_or_pre_utc_input_rejected(self):
        for iso in ('1999-04-25T13:25:31+08:00','1850-01-01T00:00:00Z'):
            with self.assertRaises(ValueError): self.authority.convert(iso,allow_model=True)

    def test_missing_or_unexpected_results_cannot_pass(self):
        for rows in ([],[{'id':'wrong'}],[{'id':'a'},{'id':'extra'}]):
            with self.assertRaises(ValueError): coverage(rows,{'a'})

if __name__=='__main__':unittest.main()
