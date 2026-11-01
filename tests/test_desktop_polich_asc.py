# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Unique T geometry, exact cusp identity, and whole-chart refusal contracts."""
import gzip
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.model import BirthInput,ChartEngine
from desktop.house_positions import house_number2
from desktop.polich import prepare_polich,PolichGeometryError,_segment_roots
from desktop.errors import UserError


class PolichAscTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=ChartEngine()
        cls.cases=json.loads((ROOT/'tests/fixtures/polich-asc-cusps.json').read_text(encoding='utf-8'))
        with gzip.open(ROOT/'regression/complete-v2/product/actual/results.jsonl.gz','rt',encoding='utf-8') as f:
            cls.rows={r['id']:r for r in map(json.loads,f) if r['input']['system']=='T'}

    def test_unique_residual_preserves_raw_and_angles(self):
        c=self.cases[0];chart=self.engine.calculate(BirthInput(**c['input']))
        self.assertEqual(chart['cusps'],c['cusps'])
        a=chart['house_positions']['-2']
        self.assertEqual(a['raw_position'],12.999998569488525)
        self.assertEqual(a['house'],1)
        self.assertEqual(a['correction'],'polich_unique_cusp_roundoff')
        self.assertEqual(len(a['polich_geometry']['roots']),1)

    def test_folded_families_refuse_both_modes_preserve_every_raw(self):
        for c in self.cases[1:]:
            for mode in (True,False):
                with self.subTest(case=c['case'],mode=mode),self.assertRaises(UserError) as caught:
                    self.engine.calculate(BirthInput(**dict(c['input'],house_latitude=mode)))
                d=caught.exception.diagnostics
                self.assertEqual(d['frame']['reason'],'folded_or_degenerate_family')
                self.assertEqual(len(d['house_positions']),20)
                self.assertEqual(d['house_positions']['-2']['raw_position'],next(p['raw_position'] for p in c['probes'] if p['delta_degrees']==0))
                self.assertTrue(all(a['house'] is None for a in d['house_positions'].values()))

    def test_normal_family_three_actual_latitude_bodies_refuse_chart(self):
        r=self.rows['complete-1914-06-T']
        for small in (True,False):
            with self.assertRaises(UserError) as caught:
                self.engine.calculate(BirthInput(**dict(r['input'],small_bodies=small)))
            d=caught.exception.diagnostics
            self.assertEqual(d['frame']['status'],'ok')
            self.assertEqual({p['point_id'] for p in d['failures']},{1,2,3})
            for p in d['failures']:self.assertEqual(p['reason'],'multiple_roots')
            for key,a in d['house_positions'].items():
                self.assertEqual(a['raw_position'],r['raw']['house_positions'][key]['raw_position'])
        chart=self.engine.calculate(BirthInput(**dict(r['input'],house_latitude=False)))
        self.assertTrue(all(p['house'] for p in chart['all_points']))

    def test_nearby_points_are_not_snapped_and_axis_name_is_not_authority(self):
        c=self.cases[0]
        for delta in (-1e-6,-1e-8,1e-8,1e-6):
            a={}
            house_number2(c['armc'],c['input']['latitude'],c['obliquity'],c['asc']+delta,0.,'T',axis='asc',cusps=c['cusps'],audit=a)
            self.assertIsNone(a['correction']);self.assertEqual(a['position'],a['raw_position'])
        c=self.cases[1]
        for axis in (None,'asc'):
            a={}
            with self.assertRaises(PolichGeometryError):
                house_number2(c['armc'],c['input']['latitude'],c['obliquity'],c['asc'],0.,'T',axis=axis,cusps=c['cusps'],audit=a)
            self.assertEqual(a['status'],'rejected');self.assertIsNone(a['house'])

    def test_unconverged_invalid_library_and_wrong_frame(self):
        c=self.cases[0];args=(c['armc'],c['input']['latitude'],c['obliquity'],c['asc'],0.,'T')
        for raw in (0.,12.5,math.nan,math.inf):
            with patch.object(self.engine.e,'house_pos',return_value=raw),self.assertRaises(PolichGeometryError):
                house_number2(*args,cusps=c['cusps'])
        frame=prepare_polich(*args[:3],c['cusps'])
        with self.assertRaises(PolichGeometryError):
            house_number2(args[0]+1,*args[1:],cusps=c['cusps'],polich_frame=frame)

    def test_unique_near_cusp_wrong_side_is_refused_not_corrected(self):
        c=self.cases[0];a={};args=(c['armc'],c['input']['latitude'],c['obliquity'],c['cusps'][1]-1e-6,0.,'T')
        raw=self.engine.e.house_pos(*args[:3],args[3:5],b'T')
        with self.assertRaises(PolichGeometryError) as caught:
            house_number2(*args,cusps=c['cusps'],audit=a)
        self.assertEqual(caught.exception.reason,'library_house_disagrees_with_unique_root')
        self.assertEqual(a['raw_position'],raw);self.assertIsNone(a['house']);self.assertIsNone(a['correction'])
        self.assertEqual(len(a['polich_geometry']['roots']),1)
        with self.assertRaises(PolichGeometryError) as caught:
            house_number2(*args[:3],math.nextafter(c['cusps'][1],0),0.,'T',cusps=c['cusps'])
        self.assertEqual(caught.exception.reason,'numerically_indeterminate_boundary')

    def test_all_cusps_and_southern_mirror(self):
        a=213.56849978362274;e=23.449096214738837
        for phi in (0.,25.,-25.,64.13548):
            cusps=self.engine.e.houses_armc(a,phi,e,b'T')[0]
            frame=prepare_polich(a,phi,e,cusps)
            self.assertEqual(frame.geometry['status'],'ok')
            for i,lon in enumerate(cusps):
                self.assertEqual(house_number2(a,phi,e,lon,0.,'T',cusps=cusps,polich_frame=frame),i+1)
        c=self.cases[1];a=(c['armc']+180)%360;phi=-c['input']['latitude'];e=c['obliquity']
        cusps=self.engine.e.houses_armc(a,phi,e,b'T')[0]
        with self.assertRaises(PolichGeometryError):house_number2(a,phi,e,cusps[0],0.,'T',cusps=cusps)

    def test_tangent_and_equatorial_pole_refused(self):
        q=60.;u=-math.degrees(math.atan(math.radians(q)));h=q+u;b=90/q*math.sin(math.radians(u))
        with self.assertRaises(PolichGeometryError):_segment_roots(b,1.,h,0.,90.,1/90,0.)
        a=0.;phi=25.;e=23.4;cusps=self.engine.e.houses_armc(a,phi,e,b'T')[0]
        with self.assertRaises(PolichGeometryError):house_number2(a,phi,e,90.,90-e,'T',cusps=cusps)

    def test_ordinary_boundary_precision_refusal_has_distinct_chart_message(self):
        from PySide6.QtWidgets import QApplication
        from desktop.i18n import install_language,error_text
        app=QApplication.instance() or QApplication([])
        c=self.cases[0];original=self.engine.e.calc
        def near_cusp(jd,body,flags):
            values,returned=original(jd,body,flags)
            if body==0 and not flags & self.engine.e.FLG_EQUATORIAL:
                values=list(values);values[0]=c['cusps'][1]-1e-6;values[1]=0.
            return values,returned
        with patch.object(self.engine.e,'calc',side_effect=near_cusp),self.assertRaises(UserError) as caught:
            self.engine.calculate(BirthInput(**c['input']))
        self.assertEqual(caught.exception.diagnostics['failures'],[dict(point_id=0,reason='library_house_disagrees_with_unique_root')])
        try:
            for lang,fragment in [('zh-TW','精度不足'),('en-US','numerical precision')]:
                install_language(app,lang);message=error_text(caught.exception)
                self.assertIn(fragment,message);self.assertNotIn('multiple solutions',message)
        finally:install_language(app,'zh-TW')

    def test_translated_worker_refusal_clears_stale_export(self):
        from PySide6.QtWidgets import QApplication,QMessageBox
        from desktop.i18n import install_language
        from desktop.window import MainWindow,Calculation
        from desktop.storage import ProfileStore
        app=QApplication.instance() or QApplication([])
        try:
            for lang,fragment in [('zh-TW','幾何多解'),('en-US','multiple solutions')]:
                install_language(app,lang)
                with tempfile.TemporaryDirectory() as tmp:
                    window=MainWindow(auto_start=False,store=ProfileStore(Path(tmp)/'test.sqlite'),prompt_unsaved=False)
                    try:
                        window.chart=self.engine.calculate(BirthInput(**self.cases[0]['input']))
                        window.export_button.setEnabled(True)
                        worker=Calculation(BirthInput(**self.rows['complete-1914-06-T']['input']),None,self.engine,window)
                        success=[];fail=[];worker.succeeded.connect(success.append);worker.failed.connect(fail.append);worker.run()
                        self.assertFalse(success);self.assertEqual(len(fail),1);self.assertIn(fragment,fail[0])
                        with patch.object(QMessageBox,'warning'):window.error(fail[0])
                        self.assertIsNone(window.chart);self.assertFalse(window.export_ready())
                        self.assertFalse(window.export_button.isEnabled());self.assertEqual(window.positions.rowCount(),0)
                    finally:window.close()
        finally:install_language(app,'zh-TW')


if __name__=='__main__':unittest.main()
