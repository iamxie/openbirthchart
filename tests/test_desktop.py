# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Desktop scientific/input contracts and headless UI interactions."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from dataclasses import replace,asdict
from datetime import timedelta
from pathlib import Path
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'scripts')]
from desktop.model import BirthInput,ChartEngine,resolve_local,HOUSE_SYSTEMS,ASPECTS,find_aspects,zodiac_text
from common import ROOT,angular_delta

def fill_form(w):
    w.restore_profile(dict(schema=1,input=asdict(BirthInput()),custom_orbs=False,
        orb_values={str(a):o for a,_,o,_,_ in ASPECTS}))

class TimeInputTests(unittest.TestCase):
    def test_seconds_and_taipei(self):
        b=BirthInput(local_iso='1999-04-25T13:25:31')
        self.assertEqual(resolve_local(b)['utc'].isoformat(),'1999-04-25T05:25:31+00:00')

    def test_historical_taiwan_dst_and_manual_no_double_shift(self):
        b=BirthInput(local_iso='1979-07-01T12:00:00')
        r=resolve_local(b);self.assertEqual(r['offset'],timedelta(hours=9))
        self.assertEqual(r['utc'],resolve_local(replace(b,manual_dst=True,dst_enabled=True))['utc'])
        self.assertEqual(resolve_local(replace(b,manual_dst=True,dst_enabled=False))['offset'],timedelta(hours=8))

    def test_nonexistent_and_repeated_hours(self):
        with self.assertRaisesRegex(ValueError,'不存在'):
            resolve_local(BirthInput(local_iso='2024-03-10T02:30:00',zone='America/New_York'))
        b=BirthInput(local_iso='2024-11-03T01:30:00',zone='America/New_York')
        with self.assertRaisesRegex(ValueError,'兩次'):resolve_local(b)
        self.assertEqual(resolve_local(replace(b,fold=1))['utc']-resolve_local(replace(b,fold=0))['utc'],timedelta(hours=1))

    def test_fractional_offset_and_half_hour_dst(self):
        self.assertEqual(resolve_local(BirthInput(zone='Asia/Kathmandu',local_iso='2024-01-01T12:00:00'))['offset_label'],'UTC+05:45')
        self.assertEqual(resolve_local(BirthInput(zone='Australia/Lord_Howe',local_iso='2024-01-01T12:00:00'))['dst'],timedelta(minutes=30))

    def test_angle_wrap_and_rounding(self):
        self.assertEqual(zodiac_text(359.999999),'牡羊 00°00′00″')
        points=[dict(name='A',lon=359.5),dict(name='B',lon=.5)]
        self.assertEqual(find_aspects(points)[0]['angle'],0)
        self.assertEqual(find_aspects(points)[0]['orb'],1)

class AspectPresetTests(unittest.TestCase):
    expected={0:4.,60:2.,90:3.,120:3.,180:3.,30:1.,45:1.,72:1.5,135:1.5,150:1.5}

    def test_strict_boundaries_and_minor_visibility(self):
        self.assertEqual({a:o for a,_,o,_,_ in ASPECTS},self.expected)
        for angle,limit in self.expected.items():
            direction=-1 if angle==180 else 1
            for delta,included in [(0,True),(.001,False)]:
                with self.subTest(angle=angle,delta=delta):
                    points=[dict(name='A',lon=0),dict(name='B',lon=angle+direction*(limit+delta))]
                    self.assertEqual(bool(find_aspects(points)),included)
            if angle in (30,45,72,135,150):
                points=[dict(name='A',lon=0),dict(name='B',lon=angle)]
                self.assertEqual(find_aspects(points,include_minor=False),[])

    def test_custom_orb_changes_classification(self):
        points=[dict(name='A',lon=359),dict(name='B',lon=4)]
        self.assertEqual(find_aspects(points),[])
        custom={**self.expected,0:6.}
        result=find_aspects(points,orbs=custom)
        self.assertEqual(len(result),1)
        self.assertEqual((result[0]['angle'],result[0]['orb'],result[0]['limit']),(0,5,6))

class ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.engine=ChartEngine()

    def test_all_house_systems_and_permanent_outer_planets(self):
        for system in HOUSE_SYSTEMS:
            with self.subTest(system=system):
                c=self.engine.calculate(BirthInput(system=system,small_bodies=False))
                self.assertEqual(len(c['cusps']),12)
                self.assertEqual(len(c['points']),15)
                self.assertTrue({'天王星','海王星','冥王星'}<={p['name'] for p in c['points']})
                widths=[(c['cusps'][(i+1)%12]-v)%360 for i,v in enumerate(c['cusps'])]
                self.assertAlmostEqual(sum(widths),360)

    def test_small_bodies_and_one_second_change(self):
        c=self.engine.calculate(BirthInput());self.assertEqual(len(c['points']),20)
        minors=[p for p in c['points'] if p['id'] in (15,17,18,19,20)]
        self.assertEqual(len(minors),5);self.assertTrue(all(p['source']=='leb' for p in minors))
        d=self.engine.calculate(BirthInput(local_iso='1978-04-20T08:23:01'))
        movement=abs(angular_delta(d['asc'],c['asc']))*3600
        self.assertGreater(movement,10);self.assertLess(movement,25)
        self.assertEqual(c['utc'],'1978-04-20T00:23:00+00:00')

    def test_hemispheres_and_polar_failure(self):
        a=self.engine.calculate(BirthInput(longitude=-70,latitude=-33))
        b=self.engine.calculate(BirthInput(longitude=70,latitude=33))
        self.assertGreater(abs(angular_delta(a['asc'],b['asc'])),10)
        with self.assertRaisesRegex(ValueError,'無法使用'):
            self.engine.calculate(BirthInput(latitude=75,system='P'))
        self.assertEqual(len(self.engine.calculate(BirthInput(latitude=75,system='W'))['cusps']),12)

    def test_old_and_future_dates_are_labelled(self):
        for date in ['1900-04-20T08:23:00','1965-04-20T08:23:00','2082-04-20T08:23:00']:
            c=self.engine.calculate(BirthInput(local_iso=date))
            self.assertTrue(c['notes']);self.assertEqual(len(c['points']),20)

class UiTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        from PySide6.QtWidgets import QMainWindow
        from PySide6.QtCore import QCoreApplication,QEvent
        for window in cls.app.topLevelWidgets():
            if isinstance(window,QMainWindow):window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        cls.app.processEvents()

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFontDatabase,QFont
        cls.app=QApplication.instance() or QApplication([])
        font=QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
        assert font>=0
        cls.app.setFont(QFont(QFontDatabase.applicationFontFamilies(font)[0],10))
        cls.engine=ChartEngine()

    def test_strict_default_custom_edit_and_return_to_default(self):
        from desktop.window import MainWindow
        w=MainWindow(auto_start=False,prompt_unsaved=False);fill_form(w)
        try:
            self.assertEqual(w.orbs(),AspectPresetTests.expected)
            self.assertIn(72,w.orb_controls)
            w.orb_group.setChecked(True)
            w.orb_controls[0].setValue(6.)
            w.orb_controls[72].setValue(2.5)
            chart=self.engine.calculate(w.input(),w.orbs())
            self.assertEqual(chart['orbs'],{**AspectPresetTests.expected,0:6.,72:2.5})
            self.assertTrue(all(a['limit']==chart['orbs'][a['angle']] for a in chart['aspects']))
            w.orb_group.setChecked(False)
            self.assertEqual(w.orbs(),AspectPresetTests.expected)
        finally:
            w.close()

    def test_export_conditions_use_effective_dst_and_both_coordinate_formats(self):
        import tempfile
        import xml.etree.ElementTree as ET
        from desktop.chart import chart_conditions,coordinate_text,export_chart
        cases=[
            (BirthInput(local_iso='1979-05-17T08:30:00',longitude=120.22582,small_bodies=False),'未套用（0 分鐘）','UTC+08:00','1979/05/17 00:30:00'),
            (BirthInput(local_iso='2024-01-01T12:00:00',zone='Australia/Lord_Howe',longitude=159.08,latitude=-31.55,small_bodies=False),'已套用（+30 分鐘）','UTC+11:00','2024/01/01 01:00:00'),
            (BirthInput(local_iso='2024-07-01T12:00:00',zone='America/New_York',longitude=-74,latitude=40.7,small_bodies=False),'已套用（+60 分鐘）','UTC-04:00','2024/07/01 16:00:00'),
            (BirthInput(local_iso='2024-07-01T12:00:00',zone='America/New_York',longitude=-74,latitude=40.7,manual_dst=True,dst_enabled=False,small_bodies=False),'未套用（0 分鐘）','UTC-05:00','2024/07/01 17:00:00'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for i,(birth,dst,offset,utc) in enumerate(cases):
                with self.subTest(zone=birth.zone,manual=birth.manual_dst):
                    chart=self.engine.calculate(birth);lines=chart_conditions(chart)
                    self.assertIn(dst,lines[3]);self.assertIn(offset,lines[2]);self.assertIn(utc,lines[4])
                    self.assertIn('手動指定' if birth.manual_dst else '自動判斷',lines[3])
                    self.assertIn('西經' if birth.longitude<0 else '東經',lines[1])
                    self.assertIn('南緯' if birth.latitude<0 else '北緯',lines[1])
                    self.assertIn(f'{abs(birth.longitude):.5f}°',lines[1]);self.assertIn('′',lines[1]);self.assertIn('″',lines[1])
                    dest=Path(tmp)/f'{i}.svg';export_chart(chart,dest,'svg')
                    root=ET.parse(dest).getroot()
                    painted=''.join(''.join(node.itertext()) for node in root.iter() if node.tag.endswith('}text'))
                    from desktop.chart import metadata_lines
                    for line in metadata_lines(chart):self.assertIn(line,painted)
        self.assertIn('180°00′00.00″',coordinate_text(179.9999999))

    def test_input_directions_seconds_and_dirty_export(self):
        from desktop.window import MainWindow
        from PySide6.QtCore import QTime
        w=MainWindow(auto_start=False,prompt_unsaved=False);fill_form(w);w.time.setTime(QTime(13,25,31));w.ew.setCurrentIndex(1);w.ns.setCurrentIndex(1)
        b=w.input();self.assertTrue(b.local_iso.endswith('13:25:31'));self.assertLess(b.longitude,0);self.assertLess(b.latitude,0)
        c=self.engine.calculate(b);w.apply_chart(c);self.assertTrue(w.export_button.isEnabled())
        w.time.setTime(QTime(13,25,32));self.assertFalse(w.export_button.isEnabled());w.close()

    def test_manual_mode_initializes_half_hour_dst(self):
        from desktop.window import MainWindow
        from PySide6.QtCore import QDate
        w=MainWindow(auto_start=False,prompt_unsaved=False);fill_form(w);w.date.setDate(QDate(2024,1,1));w.zone.setCurrentText('Australia/Lord_Howe')
        self.assertTrue(w.dst.isChecked());w.dst_mode.setCurrentIndex(1)
        self.assertEqual(w.dst_amount.value(),30);w.close()

    def test_background_calculation_updates_chart_and_export(self):
        from desktop.window import MainWindow
        from PySide6.QtTest import QTest
        import time
        w=MainWindow(auto_start=False,prompt_unsaved=False);fill_form(w);w.engine=self.engine;w.calculate()
        deadline=time.monotonic()+30
        while w.worker is not None and time.monotonic()<deadline:
            self.app.processEvents();QTest.qWait(20)
        self.assertIsNone(w.worker);self.assertIsNotNone(w.chart)
        self.assertTrue(w.calculate_button.isEnabled());self.assertTrue(w.export_button.isEnabled());w.close()

if __name__=='__main__':unittest.main()
