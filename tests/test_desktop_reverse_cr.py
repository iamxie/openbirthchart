# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Real C/R polar rings retain Lib's numbered cusps across UI and exports."""
import copy
import json
import math
import os
from pathlib import Path
import sys
import unittest
from html.parser import HTMLParser

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.model import BirthInput,ChartEngine,house_direction,house_midpoints,house_number
from desktop.errors import UserError


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


class ReverseCRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
        cls.engine=ChartEngine()
        cls.original=json.loads((ROOT/'tests/fixtures/reverse-cr-original-cusps.json').read_text(encoding='utf-8'))
        cls.charts={r['case']:cls.engine.calculate(BirthInput(**r['input'])) for r in cls.original}

    def test_all_eight_keep_original_cusps_axes_and_reverse_sectors(self):
        self.assertEqual(len(self.charts),8)
        for r in self.original:
            with self.subTest(case=r['case']):
                chart=self.charts[r['case']];cusps=chart['cusps']
                self.assertEqual(cusps,r['cusps'])
                self.assertEqual((chart['asc'],chart['mc']),tuple(r['angles'][:2]))
                self.assertEqual(house_direction(cusps),-1)
                self.assertEqual([house_number(m,cusps) for m in house_midpoints(cusps)],list(range(1,13)))
                for i,cusp in enumerate(cusps):
                    self.assertEqual(house_number(cusp,cusps),i+1)
                    self.assertEqual(house_number(cusp-1e-7,cusps),i+1)
                    self.assertEqual(house_number(cusp+1e-7,cusps),(i-1)%12+1)
                self.assertTrue(all(p['house'] in range(1,13) for p in chart['all_points']))

    def test_labels_do_not_overlap_and_bilingual_export_keeps_numbered_rows(self):
        from desktop.chart import house_label_longitudes,WheelCanvas
        from desktop.report import render_html,TEMPLATES
        for ident,chart in self.charts.items():
            original=copy.deepcopy(chart)
            canvas=WheelCanvas();canvas.set_chart(chart)
            self.assertEqual(canvas.chart['cusps'],chart['cusps'])
            for gap in (7.,9.):
                labels=sorted(house_label_longitudes(chart['cusps'],gap))
                self.assertTrue(all((labels[(i+1)%12]-v)%360>=gap-1e-10 for i,v in enumerate(labels)))
            for lang in ('zh-TW','en-US'):
                with self.subTest(case=ident,lang=lang):
                    labels=json.loads((TEMPLATES/lang/'labels.json').read_text(encoding='utf-8'))
                    parsed=Cells();parsed.feed(render_html(chart,template_dir=TEMPLATES/lang))
                    for p in chart['points']:
                        row=next(r for r in parsed.rows if len(r)==4 and r[0]==labels['bodies'][p['name']])
                        self.assertEqual(row[2],str(p['house']))
                    for i,cusp in enumerate(chart['cusps']):
                        row=next(r for r in parsed.rows if len(r)==2 and r[0]==labels['house_number'].format(number=i+1))
                        total=round(cusp%360*3600)%(360*3600);sign,rest=divmod(total,108000)
                        d,rest=divmod(rest,3600);m,s=divmod(rest,60)
                        self.assertEqual(row[1],f'{labels["signs"][sign]} {d:02}°{m:02}′{s:02}″')
            self.assertEqual(chart,original)
            canvas.close()

    def test_five_nonmonotonic_polich_page_cases_still_rejected(self):
        suite=json.loads((ROOT/'regression/complete-v1/cases.json').read_text(encoding='utf-8'))
        ids={r['case'][:-1]+'T' for r in self.original}|{'complete-2000-06-T'}
        self.assertEqual(len(ids),5)
        for case in suite['cases']:
            if case['id'] in ids:
                with self.subTest(case=case['id']),self.assertRaises(UserError):
                    self.engine.calculate(BirthInput(**case['input']))


if __name__=='__main__':unittest.main()
