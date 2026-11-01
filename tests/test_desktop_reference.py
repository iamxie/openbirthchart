# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Numerical tolerance, circular boundaries and production spatial integration."""
from pathlib import Path
import gzip
import json
import math
import os
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from compare_reference import angular_comparison, point_comparison
from desktop.model import BirthInput, ChartEngine


class ReferenceToleranceTests(unittest.TestCase):
    def test_strict_thirty_arcsecond_threshold(self):
        boundary=30/3600
        self.assertTrue(angular_comparison(0.,math.nextafter(boundary,0.))['angular_within_tolerance'])
        self.assertFalse(angular_comparison(0.,boundary)['angular_within_tolerance'])
        self.assertFalse(angular_comparison(0.,math.nextafter(boundary,math.inf))['angular_within_tolerance'])

    def test_small_circular_error_still_records_zodiac_crossing(self):
        result=angular_comparison(359.999,0.001)
        self.assertAlmostEqual(result['longitude_delta_arcsec'],7.2)
        self.assertTrue(result['angular_within_tolerance'])
        self.assertTrue(result['zodiac_crossing'])

    def test_display_rounding_boundary_is_recorded_separately(self):
        result=angular_comparison(30.-0.6/3600,30.-0.4/3600)
        self.assertFalse(result['zodiac_crossing'])
        self.assertTrue(result['display_zodiac_crossing'])

    def test_latitude_and_combined_separation_cannot_hide(self):
        self.assertFalse(angular_comparison(0.,0.,0.,0.01)['angular_within_tolerance'])
        r=angular_comparison(0.,25/3600,0.,25/3600)
        self.assertLess(r['longitude_delta_arcsec'],30)
        self.assertLess(r['latitude_delta_arcsec'],30)
        self.assertGreater(r['separation_arcsec'],30)
        self.assertFalse(r['angular_within_tolerance'])

    def test_tiny_error_does_not_hide_house_crossing_or_undefined(self):
        p=dict(lon=12.,lat=1.,house=9,retrograde=False)
        a=dict(raw_position=math.nextafter(10.,0.),position=math.nextafter(10.,0.),correction=None)
        b=dict(raw_position=10.,position=10.,correction=None)
        r=point_comparison(p,dict(p,house=10),a,b)
        self.assertTrue(r['angular_within_tolerance']);self.assertTrue(r['house_crossing'])
        r=point_comparison(dict(p,house=None),p,dict(a,position=0.,raw_position=0.),b)
        self.assertTrue(r['undefined_mismatch']);self.assertFalse(r['house_crossing'])
        r=point_comparison(dict(p,house=None),dict(p,house=None),a,b)
        self.assertTrue(r['undefined_both']);self.assertFalse(r['undefined_mismatch'])


class ProductionSpatialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=ChartEngine()
        suite=json.loads((ROOT/'regression/cases-v2.json').read_text(encoding='utf-8'))
        cls.cases={c['id']:c for c in suite['cases']}

    def test_formal_engine_matches_archived_candidate_without_legacy_calls(self):
        from desktop.house_positions import HOUSE_NUMBER2_POLICY
        import copy
        fixes=json.loads((ROOT/'tests/fixtures/axis-cusp-0.6.3.json').read_text(encoding='utf-8'))['cases']
        fixes={(f['case'],f['point_id']):f for f in fixes if f['expected_correction']}
        path=ROOT/'tests/fixtures/spatial-candidate-examples.json'
        rows=json.loads(path.read_text(encoding='utf-8'))['records']
        selected=[]
        for predicate in (lambda r:any(a['correction'] for a in r['house_position_audit']),
                          lambda r:any(a['status']=='undefined' for a in r['house_position_audit']),
                          lambda r:r['raw']['input']['system']=='H'):
            selected.append(next(r for r in rows if predicate(r)))
        with patch('desktop.model.house_number',side_effect=AssertionError('Legacy placement called')), \
             patch('desktop.model.axis_house_number',side_effect=AssertionError('Legacy axis placement called')):
            for row in selected:
                case=self.cases[row['id']]
                actual=self.engine.calculate(BirthInput(**case['input']),{int(k):v for k,v in case['orbs'].items()})
                expected_points=copy.deepcopy(row['raw']['all_points'])
                for point in expected_points:
                    if (row['id'],point['id']) in fixes:point['house']=fixes[row['id'],point['id']]['expected_house']
                if case['input']['system']=='H':
                    # Historical raw values/coordinates remain exact; aligned
                    # houses are covered by the independent geometry tests.
                    for old,new in zip(expected_points,actual['all_points']):
                        self.assertEqual({k:v for k,v in old.items() if k!='house'}, {k:v for k,v in new.items() if k!='house'})
                    for original in row['house_position_audit']:
                        self.assertEqual(actual['house_positions'][str(original['point_id'])]['raw_position'],original['raw_position'])
                    self.assertEqual(actual['house_positions']['-3']['house'],10)
                    continue
                self.assertEqual(actual['all_points'],expected_points)
                for original in row['house_position_audit']:
                    audit=actual['house_positions'][str(original['point_id'])]
                    expected={k:v for k,v in original.items() if k!='point_id'}
                    expected['policy']=HOUSE_NUMBER2_POLICY
                    fix=fixes.get((row['id'],original['point_id']))
                    if fix:
                        expected.update(house=fix['expected_house'],position=float(fix['expected_house']),correction='axis_cusp_roundoff')
                        self.assertEqual(audit['boundary_correction']['target_house'],fix['expected_house'])
                    self.assertEqual({k:v for k,v in audit.items() if k!='boundary_correction'},expected)

    def test_koch_undefined_is_localized_in_ui_and_both_exports(self):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        import tempfile
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QCoreApplication,QEvent
        from desktop.i18n import install_language
        from desktop.window import MainWindow
        from desktop.storage import ProfileStore
        from desktop.report import render_html,TEMPLATES
        examples=json.loads((ROOT/'tests/fixtures/spatial-candidate-examples.json').read_text(encoding='utf-8'))['records']
        example=next(r for r in examples if any(a['status']=='undefined' for a in r['house_position_audit']))
        case=self.cases[example['id']]
        chart=self.engine.calculate(BirthInput(**case['input']))
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            for lang,label in [('zh-TW','未定義'),('en-US','Undefined')]:
                install_language(app,lang)
                w=MainWindow(auto_start=False,store=ProfileStore(Path(tmp)/'profiles.sqlite'),prompt_unsaved=False)
                w.apply_chart(chart)
                for index,p in enumerate(chart['points']):
                    if p['house'] is None:self.assertEqual(w.positions.item(index,2).text(),label)
                html=render_html(chart,template_dir=TEMPLATES/lang)
                self.assertIn('<td>'+label+'</td>',html);self.assertNotIn('<td>None</td>',html)
                w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
        install_language(app,'zh-TW')


if __name__=='__main__':unittest.main()
