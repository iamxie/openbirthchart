# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Protect scientific units, angle wrap, source parsing, and sample selection."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import ROOT
from observation_data import parse_line, selected_records
from observation_compare import separation, residual, legacy_place

class ObservationTests(unittest.TestCase):
    def test_wrap_and_submilliarcsecond_separation(self):
        self.assertAlmostEqual(separation([359.999,0],[0.001,0]),7.2,places=7)
        self.assertAlmostEqual(separation([30,0],[30+1e-8,0]),.000036,places=9)
        self.assertAlmostEqual(separation([0,90],[180,90]),0,places=8)

    def test_ra_cosdec_and_sign(self):
        dra,dd,sep=residual([0.001,60],[359.999,60])
        self.assertAlmostEqual(dra,3.6,places=7)
        self.assertEqual(dd,0)
        self.assertAlmostEqual(sep,3.6,places=7)
        self.assertAlmostEqual(residual([10,-20],[10,-20+1/3600])[1],-1,places=7)

    def test_catalogue_sexagesimal_and_missing_magnitude(self):
        line=(ROOT/'data/observations/planet.dat').read_text().splitlines()[0]
        r=parse_line(line,1)
        self.assertEqual(r['cmc'],9000053)
        self.assertEqual(r['tt_jd'],2448647.663371)
        self.assertAlmostEqual(r['ra_deg'],15*(11+1/60+36.045/3600))
        self.assertAlmostEqual(r['dec_deg'],7+37/60+21.13/3600)
        self.assertEqual(parse_line(line[:76],1),r)
        blank=line[:50]+' '*12+line[62:]
        self.assertIsNone(parse_line(blank,1)['ra_deg'])
        with self.assertRaises(ValueError): parse_line(line[:50]+'  '+line[52:],1)
        with self.assertRaises(ValueError): parse_line(line[:46]+'?'+line[47:],1)

    def test_selection_quality_not_residual_clipping(self):
        r=selected_records()
        self.assertEqual(len(r),283)
        self.assertEqual(len({x['id'] for x in r}),283)
        self.assertEqual(sum(bool(x['flag']) for x in r),4)
        self.assertEqual({b:sum(x['body']==b for x in r) for b in ('Uranus','Neptune','Pluto')},
                         dict(Uranus=119,Neptune=122,Pluto=42))
        self.assertTrue(all(2448257.5<=x['tt_jd']<2448622.5 for x in r))

    def test_frame_rotation_preserves_angular_distance(self):
        a,b=[359.999,23],[0.001,23.0001]
        self.assertAlmostEqual(separation(a,b),separation(legacy_place(2448450,a),legacy_place(2448450,b)),places=7)
        self.assertTrue(math.isfinite(separation(a,legacy_place(2448450,a))))

if __name__=='__main__': unittest.main()
