# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Directed cusp topology, boundary ownership and real reversed Azimuth cases."""
import json
import math
from pathlib import Path
import sys
import unittest
from dataclasses import replace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.model import BirthInput,ChartEngine,house_direction,house_number,house_midpoints
from desktop.errors import UserError

class DirectedHouseTests(unittest.TestCase):
    def test_reverse_house_labels_do_not_overlap_or_change_cusps(self):
        from desktop.chart import house_label_longitudes
        rows=json.loads((ROOT/'tests/fixtures/azimuth-original-cusps.json').read_text(encoding='utf-8'))
        for row in rows:
            cusps=row['cusps'];original=cusps.copy()
            for gap in (7.,9.):
                labels=sorted(house_label_longitudes(cusps,gap))
                self.assertTrue(all((labels[(i+1)%12]-v)%360>=gap-1e-10 for i,v in enumerate(labels)))
                self.assertEqual(cusps,original)
        forward=[float(i*30) for i in range(12)]
        self.assertEqual(house_label_longitudes(forward),house_midpoints(forward))

    def test_each_cusp_and_both_sides_including_zero_wrap(self):
        for direction in (1,-1):
            for origin in (0.,17.25,350.):
                cusps=[(origin+direction*i*30)%360 for i in range(12)]
                self.assertEqual(house_direction(cusps),direction)
                for i,cusp in enumerate(cusps):
                    with self.subTest(direction=direction,origin=origin,cusp=i+1):
                        self.assertEqual(house_number(cusp,cusps),i+1)
                        self.assertEqual(house_number((cusp+direction*1e-7)%360,cusps),i+1)
                        self.assertEqual(house_number((cusp-direction*1e-7)%360,cusps),(i-1)%12+1)

    def test_unequal_arcs_form_unique_partition_and_correct_labels(self):
        widths=[2.,3.,5.,10.,20.,30.,40.,50.,60.,70.,30.,40.]
        self.assertEqual(sum(widths),360)
        for direction in (1,-1):
            offsets=[sum(widths[:i]) for i in range(12)]
            cusps=[(359.5+direction*x)%360 for x in offsets]
            mids=house_midpoints(cusps)
            for i,(start,width) in enumerate(zip(offsets,widths)):
                expected_mid=(359.5+direction*(start+width/2))%360
                self.assertEqual(mids[i],expected_mid)
                for fraction in (.00001,.25,.5,.75,.99999):
                    lon=(359.5+direction*(start+width*fraction))%360
                    self.assertEqual(house_number(lon,cusps),i+1)

    def test_invalid_rings_are_not_mistaken_for_reverse(self):
        valid=[float(i*30) for i in range(12)]
        crossed=valid.copy();crossed[2],crossed[8]=crossed[8],crossed[2]
        too_narrow=valid.copy();too_narrow[1]=1e-9
        for cusps in [valid[:-1],[0.]*12,valid[:11]+[math.nan],valid[:11]+[math.inf],
                      valid[:11]+[valid[0]],crossed,too_narrow]:
            with self.subTest(cusps=cusps),self.assertRaises(ValueError):house_direction(cusps)

    def test_midpoint_on_the_actual_short_reverse_sector(self):
        # Original 0.6.0 Lima H cusps, independently archived before this fix.
        row=json.loads((ROOT/'tests/fixtures/azimuth-original-cusps.json').read_text(encoding='utf-8'))[0]
        cusps=row['cusps'];mids=house_midpoints(cusps)
        self.assertAlmostEqual(mids[0],145.9197024399826)
        old_mid=(cusps[0]+(cusps[1]-cusps[0])%360/2)%360
        self.assertAlmostEqual(abs(math.remainder(mids[0]-old_mid,360)),180.)
        self.assertEqual([house_number(m,cusps) for m in mids],list(range(1,13)))

class RealAzimuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=ChartEngine()
        suite=json.loads((ROOT/'regression/cases-v1.json').read_text(encoding='utf-8'))
        cls.cases=[c for c in suite['cases'] if c['id'].startswith('edge-azimuth-')]
        cls.original={c['id']:c for c in json.loads((ROOT/'tests/fixtures/azimuth-original-cusps.json').read_text(encoding='utf-8'))}

    def test_all_16_now_succeed_without_moving_cusps_or_physical_positions(self):
        self.assertEqual(len(self.cases),16)
        for case in self.cases:
            with self.subTest(case=case['id']):
                birth=BirthInput(**case['input']);chart=self.engine.calculate(birth)
                self.assertEqual(chart['cusps'],self.original[case['id']]['cusps'])
                self.assertEqual(house_direction(chart['cusps']),-1)
                self.assertEqual(chart['asc'],self.original[case['id']]['angles'][0])
                self.assertEqual(chart['mc'],self.original[case['id']]['angles'][1])
                self.assertGreater(abs(math.remainder(chart['asc']-chart['cusps'][0],360)),1.)
                same_instant=self.engine.calculate(replace(birth,system='W'))
                self.assertEqual(chart['times'],same_instant['times'])
                for a,b in zip(chart['all_points'],same_instant['all_points']):
                    self.assertEqual({k:v for k,v in a.items() if k!='house'},{k:v for k,v in b.items() if k!='house'})
                    self.assertIn(a['house'],range(1,13))
                self.assertEqual([house_number(m,chart['cusps']) for m in house_midpoints(chart['cusps'])],list(range(1,13)))
                for i,c in enumerate(chart['cusps']):self.assertEqual(house_number(c,chart['cusps']),i+1)

    def test_lima_planets_use_actual_latitude_spatial_placement(self):
        birth=BirthInput(local_iso='1936-03-02T05:58:00',zone='America/Lima',
                         latitude=-12.05,longitude=-(77+2/60),system='H')
        chart=self.engine.calculate(birth)
        expected=[]
        for p in chart['all_points'][:10]:
            raw=self.engine.e.house_pos((chart['times']['erfa_gast_deg']+birth.longitude)%360,
                birth.latitude,chart['times']['erfa_true_obliquity_deg'],(p['lon'],p['lat']),b'H')
            self.assertEqual(chart['house_positions'][str(p['id'])]['raw_position'],raw)
            # This Lima chart has western origin and reversed spatial numbering.
            expected.append(math.floor(1+((180-(raw-1)*30)%360)/30))
        self.assertEqual([p['house'] for p in chart['all_points'][:10]],expected)
        self.assertEqual(expected,[7,1,7,7,7,8,7,6,1,1])
        # Integer houses can coincide with the wheel while latitude still
        # changes the continuous spatial coordinate.
        p=chart['all_points'][1];a=chart['house_positions'][str(p['id'])]
        zero=self.engine.e.house_pos(*a['arguments'][:3],(p['lon'],0.),b'H')
        self.assertGreater(abs(a['raw_position']-zero),.001)

    def test_unapproved_system_reverse_acceptance_policy_is_unchanged(self):
        row=next(iter(self.original.values()))
        with patch.object(self.engine.e,'houses_armc',return_value=(row['cusps'],row['angles'])):
            with self.assertRaises(UserError):self.engine.calculate(BirthInput(system='T'))

    def test_both_report_templates_retain_cusps_asc_and_new_house_numbers(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFontDatabase
        from desktop.report import render_html,TEMPLATES
        app=QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
        chart=self.engine.calculate(BirthInput(**self.cases[0]['input']))
        from html.parser import HTMLParser
        class Cells(HTMLParser):
            def __init__(self):super().__init__();self.rows=[];self.row=[];self.cell=None
            def handle_starttag(self,tag,attrs):
                if tag=='tr':self.row=[]
                elif tag=='td':self.cell=''
            def handle_data(self,data):
                if self.cell is not None:self.cell+=data
            def handle_endtag(self,tag):
                if tag=='td' and self.cell is not None:self.row.append(self.cell);self.cell=None
                elif tag=='tr':self.rows.append(self.row)
        for lang,jupiter in [('zh-TW','木星'),('en-US','Jupiter')]:
            text=render_html(chart,template_dir=TEMPLATES/lang)
            parser=Cells();parser.feed(text)
            row=next(r for r in parser.rows if r and r[0]==jupiter)
            self.assertEqual(row[2],str(next(p['house'] for p in chart['points'] if p['id']==5)))
            self.assertIn('<svg',text)
        self.assertIsNotNone(app)

if __name__=='__main__':unittest.main()
