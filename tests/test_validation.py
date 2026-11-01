# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Checks for comparison-harness failure modes, not an engine substitute."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import angular_delta, finite_vector
from compare import keyed, stats

class ValidationTests(unittest.TestCase):
    def test_zero_crossing_uses_shortest_angle(self):
        self.assertAlmostEqual(angular_delta(.001,359.999)*3600,7.2,places=7)
        self.assertAlmostEqual(angular_delta(359.999,.001)*3600,-7.2,places=7)

    def test_rejects_nonfinite_and_missing_values(self):
        for values in ([0]*5,[0]*5+[math.nan],[0]*5+[math.inf]):
            with self.assertRaises(ValueError): finite_vector(values,6)

    def test_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError):keyed([{'id':'a'},{'id':'a'}])

    def test_no_empty_or_nonfinite_statistics(self):
        for values in ([],[math.nan],[math.inf]):
            with self.assertRaises(ValueError):stats(values)

    def test_errors_do_not_cancel_each_other(self):
        self.assertEqual(stats([-2,2])['max'],2)
        self.assertEqual(stats([-2,2])['median'],2)

if __name__=='__main__':unittest.main()
