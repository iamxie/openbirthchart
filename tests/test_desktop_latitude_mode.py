# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""House-latitude selection: calculation, persistence, stale results and painting."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import copy,json,math,sys,tempfile,unittest
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.model import BirthInput,ChartEngine,ASPECTS,calculation_key,display_chart
from desktop.storage import ProfileStore,validate_profile
from desktop.errors import UserError
from desktop.wheel_geometry import wheel_points
from desktop.report import render_html,TEMPLATES,svg_image
from desktop.chart import paint_wheel
from desktop.i18n import install_language
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication


class LatitudeModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.engine=ChartEngine()
        suite=json.loads((ROOT/'regression/complete-v1/cases.json').read_text(encoding='utf-8'))
        cls.birth=replace(BirthInput(**next(c['input'] for c in suite['cases'] if c['id']=='complete-1904-01-H')),fold=None)
        cls.on=cls.engine.calculate(cls.birth);cls.off=cls.engine.calculate(replace(cls.birth,house_latitude=False))

    def tearDown(self):install_language(self.app,'zh-TW')

    def test_only_effective_latitude_and_house_results_change(self):
        a,b=self.on,self.off
        for key in ('cusps','asc','mc','times','aspects','utc','day_chart'):self.assertEqual(a[key],b[key])
        changed=[]
        for p,q in zip(a['all_points'],b['all_points']):
            self.assertEqual({k:v for k,v in p.items() if k!='house'},{k:v for k,v in q.items() if k!='house'})
            pa=a['house_positions'][str(p['id'])];pb=b['house_positions'][str(p['id'])]
            self.assertEqual(pa['arguments'][4],p['lat']);self.assertEqual(pb['arguments'][4],0)
            if p['house']!=q['house']:changed.append(p['id'])
            if p['lat']==0:self.assertEqual(pa,pb)
        self.assertIn(9,changed);self.assertNotIn(-2,changed);self.assertNotIn(-3,changed)

    def test_false_is_passed_to_library_not_only_display(self):
        import libephemeris
        original=libephemeris.house_pos;inputs=[]
        def spy(*args,**kw):inputs.append(args[3]);return original(*args,**kw)
        with patch.object(libephemeris,'house_pos',side_effect=spy):
            chart=self.engine.calculate(replace(self.birth,house_latitude=False))
        self.assertEqual(len(inputs),20);self.assertTrue(all(p[1]==0 for p in inputs))
        self.assertTrue(any(p['lat']!=0 for p in chart['all_points']))

    def test_cannot_relabel_cached_chart_as_other_mode(self):
        off=replace(self.birth,house_latitude=False)
        self.assertNotEqual(calculation_key(self.birth),calculation_key(off))
        with self.assertRaises(UserError):display_chart(self.on,off)
        with self.assertRaises(UserError):self.engine.calculate(replace(self.birth,house_latitude='false'))

    def test_defaults_old_profiles_and_saved_false(self):
        self.assertTrue(BirthInput().house_latitude)
        values=asdict(self.birth);values.pop('house_latitude');values['name']='Latitude test'
        payload=dict(schema=1,input=values,custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS})
        self.assertTrue(validate_profile(payload)['input']['house_latitude'])
        payload['input']['house_latitude']=False
        with tempfile.TemporaryDirectory() as tmp:
            store=ProfileStore(Path(tmp)/'profiles.sqlite');ident=store.save(payload)
            self.assertFalse(ProfileStore(store.path).load(ident)['input']['house_latitude'])
        payload['input']['house_latitude']=0
        with self.assertRaises(UserError):validate_profile(payload)

    def test_actual_painter_uses_house_projection_not_longitude(self):
        class Trace:
            def __init__(self,p):self.p=p;self.dots=[]
            def __getattr__(self,k):return getattr(self.p,k)
            def drawEllipse(self,*args):
                if len(args)==3 and isinstance(args[0],QPointF) and args[1:]==(2.5,2.5):self.dots.append(self.p.transform().map(args[0]))
                return self.p.drawEllipse(*args)
        for chart in (self.on,self.off):
            snapshot=copy.deepcopy(chart);traces=[]
            def draw(p):
                t=Trace(p);traces.append(t);paint_wheel(t,chart)
            svg_image(1000,1000,draw)
            self.assertEqual(chart,snapshot)
            self.assertEqual(len(traces[0].dots),20)
            for body,xy in zip(wheel_points(chart),traces[0].dots):
                angle=(math.degrees(math.atan2(500-xy.y(),xy.x()-500))-180+chart['asc'])%360
                self.assertLess(abs(math.remainder(angle-body['plot_lon'],360)),1e-10)
        pluto=next(p for p in wheel_points(self.on) if p['id']==9)
        self.assertNotEqual(pluto['plot_lon'],pluto['lon'])
        self.assertTrue(all(p['plot_lon']==p['lon'] for p in wheel_points(self.off)))

    def test_undefined_has_no_fabricated_house_anchor(self):
        c=self.engine.calculate(BirthInput(local_iso='1935-12-20T12:00:00',zone='UTC',latitude=-53.1638,longitude=-70.9171,system='K'))
        # A fixed presentation fixture tests undefined rendering independent of
        # whether this extra date happens to have a Koch sentinel.
        c=copy.deepcopy(c);c['points'][0]['house']=None
        c['house_positions'][str(c['points'][0]['id'])].update(
            raw_position=0.0,position=None,house=None,status='undefined')
        p=wheel_points(c)[0];self.assertEqual(p['plot_radius'],365);self.assertIsNone(p['house_position'])
        svg=svg_image(1000,1000,lambda painter:paint_wheel(painter,c))
        self.assertIn('>?</text>',svg)
        self.assertIn('？表示宮位未定義',render_html(c))

    def test_report_language_independent_of_ui(self):
        for ui in ('en-US','zh-TW'):
            install_language(self.app,ui)
            for lang in ('en-US','zh-TW'):
                for c in (self.on,self.off):
                    html=render_html(c,template_dir=TEMPLATES/lang)
                    if lang=='en-US':
                        self.assertNotRegex(html,r'[\u3400-\u9fff]')
                        self.assertIn('Use ecliptic latitude for houses',html)
                        self.assertIn('House-position view' if c['input']['house_latitude'] else 'Longitude wheel',html)
                    else:self.assertIn('歸宮納入天體黃緯',html)

    def test_ui_marks_changed_mode_stale_and_restores_selection(self):
        from desktop.window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            w=MainWindow(store=ProfileStore(Path(tmp)/'p.sqlite'),prompt_unsaved=False)
            payload=dict(schema=1,input=asdict(self.birth),custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS})
            try:
                w.restore_profile(payload);w.apply_chart(self.on)
                self.assertTrue(w.export_ready());self.assertTrue(w.house_latitude.isChecked())
                w.house_latitude.setChecked(False)
                self.assertFalse(w.export_ready());self.assertFalse(w.export_button.isEnabled());self.assertTrue(w.is_dirty())
                saved=w.profile_payload();w.apply_chart(self.off)
                self.assertTrue(w.export_ready());self.assertEqual(w.wheel.chart['input']['house_latitude'],False)
                w.restore_profile(saved);self.assertFalse(w.house_latitude.isChecked())
                w.new_record();self.assertTrue(w.house_latitude.isChecked())
            finally:w.close();w.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
