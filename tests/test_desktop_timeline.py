# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Timeline contracts: DST, circular roots, seams, cancellation and isolated UI."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.timeline import (TimelineInput, SkyEvent, EventCollector, TimelineResult,
    worker_count, RETRO_IDS, PAIRS, DEFAULT_ORBS, _refine)
from desktop.errors import AmbiguousTimeError, UserError


class TimelineNumericalTests(unittest.TestCase):
    def test_sampling_range_and_core_boundary(self):
        r=TimelineInput('2027-01-02T00:00','2027-06-30T23:59')
        self.assertEqual(r.resolve()[2],259200)
        self.assertEqual([worker_count(n) for n in (1,3,4,5,8,12)],[1,1,1,1,4,8])
        self.assertEqual(RETRO_IDS,tuple(range(2,10)))
        self.assertEqual(len(PAIRS),45)
        self.assertEqual(TimelineInput('2027-01-02T00:00','2027-01-02T00:00').resolve()[2],1)

    def test_dst_real_elapsed_and_endpoint_fold(self):
        self.assertEqual(TimelineInput('2027-03-14T00:00','2027-03-14T04:00','America/New_York').resolve()[2],181)
        self.assertEqual(TimelineInput('2027-11-07T00:00','2027-11-07T04:00','America/New_York').resolve()[2],301)
        with self.assertRaises(AmbiguousTimeError):
            TimelineInput('2027-11-07T01:30','2027-11-07T02:30','America/New_York').resolve()
        early=TimelineInput('2027-11-07T01:30','2027-11-07T02:30','America/New_York',start_fold=0).resolve()
        late=TimelineInput('2027-11-07T01:30','2027-11-07T02:30','America/New_York',start_fold=1).resolve()
        self.assertEqual((late[0]-early[0]).total_seconds(),3600)
        with self.assertRaisesRegex(UserError,'不存在'):
            TimelineInput('2027-03-14T02:30','2027-03-14T04:00','America/New_York').resolve()

    def test_invalid_conditions_rejected(self):
        for r in [TimelineInput('2027-01-02T00:00:01','2027-01-03T00:00'),
                  TimelineInput('2027-01-03T00:00','2027-01-02T00:00'),
                  TimelineInput('2027-01-02T00:00','2027-01-03T00:00','invalid'),
                  TimelineInput('2027-01-02T00:00','2027-01-03T00:00',orbs=(float('nan'),3,3,3))]:
            with self.subTest(r=r),self.assertRaises(UserError):r.resolve()

    def test_retrograde_spans_chunk_seam_and_no_sun_or_moon(self):
        c=EventCollector(0,180,DEFAULT_ORBS)
        for i,speed in enumerate((1,-1,-1,1)):
            p=np.zeros((10,2));p[:,0]=np.arange(10)*21;p[:,1]=1
            p[:3,1]=speed
            c.consume(i*60,p)
        c.finish()
        r=[e for e in c.events if e.kind=='retro']
        self.assertEqual(len(r),1);self.assertEqual(r[0].a,2)
        self.assertEqual([(j[0][-2],j[0][-1]) for j in c.jobs if j[0][0]=='retro'],[(0,60),(120,180)])
        self.assertFalse(r[0].clipped_start or r[0].clipped_end)

    def test_clipped_events_and_multiple_exact_hits(self):
        c=EventCollector(0,180,DEFAULT_ORBS)
        for i,lon in enumerate((89,91,89,91)):
            p=np.zeros((10,2));p[:,0]=np.arange(10)*25;p[:,1]=1
            p[4,0]=0;p[6,0]=lon;p[4,1]=-1
            c.consume(i*60,p)
        c.finish()
        e=next(e for e in c.events if e.key==('aspect',4,6,90))
        self.assertTrue(e.clipped_start and e.clipped_end)
        jobs=[j for j,target,attr in c.jobs if target==('aspect',4,6,90) and attr=='exact']
        self.assertEqual(len(jobs),3)

    def test_circular_exact_conjunction_and_no_opposite_false_root(self):
        def positions(t,bodies):
            return np.array([[0.,0.],[(359+t/30)%360,1.]]),[]
        with patch('desktop.timeline._positions',positions):
            roots=_refine(('exact',0,1,0,0,0,60))
            self.assertEqual(roots,[30.])
            self.assertEqual(_refine(('exact',0,1,180,0,0,60)),[])

    def test_exact_twice_between_samples_and_tangent(self):
        def positions(t,bodies):
            return np.array([[0.,0.],[90+((t-30)**2-100)*1e-5,(t-30)*2e-5]]),[]
        with patch('desktop.timeline._positions',positions):
            roots=_refine(('exact',0,1,90,0,0,60))
            self.assertEqual(len(roots),2)
            self.assertAlmostEqual(roots[0],20,delta=.125)
            self.assertAlmostEqual(roots[1],40,delta=.125)
        def tangent(t,bodies):
            return np.array([[0.,0.],[90+(t-30)**2*1e-5,(t-30)*2e-5]]),[]
        with patch('desktop.timeline._positions',tangent):
            self.assertEqual(_refine(('exact',0,1,90,0,0,60)),[30.,30.])
        def near_miss(t,bodies):
            values,notes=tangent(t,bodies)
            values[1,0]+=.0001
            return values,notes
        with patch('desktop.timeline._positions',near_miss):
            self.assertEqual(_refine(('exact',0,1,90,0,0,60)),[])

    def test_zero_orb_exact_marker_and_duplicate_boundary(self):
        c=EventCollector(0,120,(0,0,0,0))
        key=('aspect',0,1,90)
        c.jobs=[(('exact',0,1,90,0,0,60),key,'exact'),(('exact',0,1,90,0,60,120),key,'exact')]
        c.apply_refinements([[60],[60]])
        self.assertEqual(len(c.events),1);self.assertEqual(c.events[0].exact,[60])


class TimelineUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        from desktop.timeline_ui import TimelinePage
        self.page=TimelinePage()

    def tearDown(self):
        self.page.close();self.page.deleteLater();self.app.processEvents()

    def test_no_hardware_fields_and_eight_retrograde_rows(self):
        from PySide6.QtWidgets import QLabel
        text=' '.join(w.text() for w in self.page.findChildren(QLabel))
        self.assertNotIn('核心',text);self.assertNotIn('程序',text)
        self.assertIn('共八顆',text)
        r=TimelineInput('2027-01-02T00:00','2027-01-02T01:00')
        start,end,n=r.resolve()
        result=TimelineResult(r,start.timestamp(),end.timestamp(),n,[],1,[])
        self.page.apply_result(result)
        names=[label for kind,label,events in self.page.canvas.rows if kind=='lane']
        self.assertEqual(len(names),8);self.assertNotIn('月亮',names)

    def test_settings_clear_previous_result_and_progress_uses_real_count(self):
        from PySide6.QtCore import QDate
        r=TimelineInput('2027-01-02T00:00','2027-01-02T01:00')
        start,end,n=r.resolve()
        self.page.apply_result(TimelineResult(r,start.timestamp(),end.timestamp(),n,[],1,[]))
        self.page.start_date.setDate(QDate(2027,2,1))
        self.assertIsNone(self.page.result)
        self.page.on_progress(dict(stage='sample',done=120,total=259200,elapsed=13,stage_elapsed=12))
        self.assertEqual(self.page.progress_bar.value(),120)
        self.assertEqual(self.page.progress_bar.maximum(),259200)
        self.assertIn('259,200',self.page.status.text())

    def test_mode_switch_does_not_change_birth_profile(self):
        from desktop.window import MainWindow
        from desktop.storage import ProfileStore
        with tempfile.TemporaryDirectory() as tmp:
            w=MainWindow(auto_start=False,store=ProfileStore(Path(tmp)/'unused.sqlite'),prompt_unsaved=False)
            before=w.form_snapshot()
            w.mode_tabs.setCurrentIndex(1)
            self.assertIsNotNone(w.timeline_page)
            w.mode_tabs.setCurrentIndex(0)
            self.assertEqual(w.form_snapshot(),before)
            self.assertFalse((Path(tmp)/'unused.sqlite').exists())
            w.close();w.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
