# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Offline checks for interpreting external displayed angles and input echoes."""
from pathlib import Path
import sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from astrodoor_compare import make_row, parse_site, position, MAJOR, MINOR

class ComparisonTests(unittest.TestCase):
    def test_display_parser_and_invalid_minutes(self):
        self.assertAlmostEqual(position("魔羯座 29° 6'"),299.1)
        self.assertEqual(position("牡羊座 0° 0'"),0)
        self.assertIsNone(position('合相 (0°)'))
        with self.assertRaises(ValueError): position("牡羊座 30° 0'")
        with self.assertRaises(ValueError): position("牡羊座 0°60'")

    def test_shortest_angle_across_zero(self):
        case=dict(id='x',local='x',utc='x',dst_minutes=0)
        point=dict(lon=0,displayed="牡羊座 0° 0'",house=1,retrograde=False)
        row=make_row(case,'太陽','major',point,359.999,1,False)
        self.assertAlmostEqual(row['signed_arcsec'],-3.6)
        self.assertAlmostEqual(row['abs_arcsec'],3.6)

    def test_complete_tables_and_echo_fail_closed(self):
        case=dict(id='x',form={'year':'2000','houseSystem':'P','showAsteroids':'Y'},dst_minutes=0)
        raw=''.join(f'<input type="hidden" name="{k}" value="{v}">' for k,v in (case['form']|{'daylight':'no'}).items())
        raw+='<table>'+''.join(f'<tr><td>{n}</td><td>牡羊座 0° 0\x27</td><td>第1宮(命宮)</td></tr>' for n in MAJOR+MINOR+['北交點','南交點','幸運點','宿命點'])+'</table>'
        raw+='<table>'+''.join(f'<tr><td>第{i}宮</td><td>牡羊座 0° 0\x27</td></tr>' for i in range(1,13))+'</table>'
        raw+='<table>'+''.join(f'<tr><td>尖軸 ({a})</td><td>牡羊座 0° 0\x27</td></tr>' for a in ['ASC','DES','MC','IC'])+'</table>'
        self.assertEqual(len(parse_site(raw,case)['points']),19)
        with self.assertRaisesRegex(ValueError,'echoed'): parse_site(raw.replace('value="P"','value="K"'),case)
        with self.assertRaisesRegex(ValueError,'Missing'): parse_site(raw.replace('凱龍星','不明星'),case)
        with self.assertRaisesRegex(ValueError,'Duplicate'): parse_site(raw+raw,case)

if __name__=='__main__':unittest.main()
