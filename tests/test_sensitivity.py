# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sensitivity_math import sampled_span,find_crossing

class SensitivityTests(unittest.TestCase):
    def test_uncertainty_window_wrap_and_interior_extremum(self):
        self.assertAlmostEqual(sampled_span([359.9,0,.1]),720,places=6)
        self.assertAlmostEqual(sampled_span([10,11,10]),3600,places=6)

    def test_find_sign_crossing_through_zero(self):
        root=find_crossing(lambda t:(359.9+.2*t)%360,0,0,1,.00001)
        self.assertAlmostEqual(root,.5,places=4)

    def test_invalid_root_bracket_is_rejected(self):
        with self.assertRaises(ValueError):find_crossing(lambda t:10+t,30,0,1)

if __name__=='__main__':unittest.main()
