# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'scripts')]
import tempfile
from contextlib import closing
import unittest
from unittest.mock import patch
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtTest import QTest
from desktop.timeline import TimelineInput,TimelineResult
from desktop.sky_history import SkyHistory,FrameReader
from desktop.sky_player import SkyPlayer,active_aspects,point
from desktop.errors import UserError


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'skyhistory.sqlite'
        self.history=SkyHistory(self.path)
        self.request=TimelineInput('2026-11-01T00:00','2026-11-01T01:01')
        start,end,_=self.request.resolve();self.stamps=[min(end.timestamp(),start.timestamp()+i*600) for i in range(8)]
        self.data=np.zeros((8,10,2));self.data[:,:,0]=np.arange(10)*30;self.data[:,:,1]=1
        self.data[:,2,1]=-1;self.data[:,0,0]=np.arange(8)*.01
        self.run=self.history.begin(self.request,8)
        self.result=TimelineResult(self.request,self.stamps[0],self.stamps[-1],8,[],1,[])

    def tearDown(self):
        # These tests never enter app.exec(); explicitly release parentless Qt
        # dialogs before Python finalization can collect their signal cycles.
        for widget in self.app.topLevelWidgets():
            widget.close();widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.temp.cleanup()

    def finish(self):
        self.history.append(self.run,0,self.stamps,self.data);self.history.complete(self.run,self.result)
        return SkyHistory(self.path).load(self.run)

    def test_complete_only_atomic_append_and_restart(self):
        self.assertEqual(self.history.list_complete(),[])
        with self.assertRaises(ValueError):self.history.complete(self.run,self.result)
        with self.assertRaises(UserError):FrameReader(self.path,self.run)
        self.history.append(self.run,0,self.stamps[:3],self.data[:3])
        with self.assertRaises(ValueError):self.history.append(self.run,2,self.stamps[3:],self.data[3:])
        self.history.append(self.run,3,self.stamps[3:],self.data[3:]);self.history.complete(self.run,self.result)
        loaded=SkyHistory(self.path).load(self.run);self.assertEqual(loaded.request,self.request)
        reader=FrameReader(self.path,self.run,block_size=3)
        try:
            for i in (0,1,2,7,6,3,0):
                stamp,data=reader.frame(i);self.assertEqual(stamp,self.stamps[i]);np.testing.assert_array_equal(data,self.data[i])
            self.assertEqual(reader.reads,4)
            with self.assertRaises(IndexError):reader.frame(8)
        finally:reader.close()

    def test_cancelled_never_playable(self):
        self.history.append(self.run,0,self.stamps[:3],self.data[:3]);self.history.abort(self.run,'cancelled')
        self.assertEqual(self.history.list_complete(),[])
        with self.assertRaises(UserError):self.history.load(self.run)
        with self.assertRaises(ValueError):self.history.complete(self.run,self.result)
        with self.assertRaises(ValueError):self.history.append(self.run,3,self.stamps[3:],self.data[3:])

    def test_player_retains_items_never_calls_ephemeris_and_stops(self):
        result=self.finish()
        with patch('desktop.timeline._positions',side_effect=AssertionError('Playback computed ephemeris')),patch('desktop.model.ChartEngine.calculate',side_effect=AssertionError('Playback computed chart')):
            player=SkyPlayer(self.path,result);player.show();self.app.processEvents()
            try:
                ids=[id(i) for i in player.view.icons]
                self.assertEqual(len(ids),10);self.assertEqual(player.index,0)
                player.play(15);player.play(-30);self.assertEqual(player.rate,0)
                player.seek(7);self.assertIn('01:01',player.timestamp.text())
                self.assertEqual(ids,[id(i) for i in player.view.icons])
                self.assertTrue(player.view.retro[2].isVisible());self.assertFalse(player.view.retro[0].isVisible())
                player.play(-30);QTest.qWait(130);self.assertLess(player.index,7)
                player.pause();index=player.index;QTest.qWait(100);self.assertEqual(player.index,index)
                player.seek(0);player.play(15);QTest.qWait(550)
                self.assertEqual(player.index,7);self.assertEqual(player.rate,0)
                self.assertEqual(player.reader.reads,1)
            finally:player.close()
            self.assertTrue(player.closed);self.assertFalse(player.timer.isActive())

    def test_aspect_scope_and_wrap(self):
        data=self.data[0].copy();data[2,0]=359;data[3,0]=1
        aspects=list(active_aspects(data,self.request.orbs))
        self.assertIn((2,3,0),aspects)
        self.assertTrue(all(a>=2 and b>=2 for a,b,_ in aspects))
        self.assertAlmostEqual(point(0,280).x(),point(360,280).x())

    def test_incremental_speed_pause_reverse_and_endpoints(self):
        player=SkyPlayer(self.path,self.finish())
        try:
            self.assertEqual(player.forward_fps,15)
            for rate in range(30,121,15):
                player.buttons[4].click();self.assertEqual(player.rate,rate)
            self.assertFalse(player.buttons[4].isEnabled())
            player.accelerate();self.assertEqual(player.rate,120)
            player.buttons[3].click();self.assertEqual(player.rate,0)
            player.buttons[3].click();self.assertEqual(player.rate,120)
            player.seek(4);self.assertEqual(player.rate,0)
            player.buttons[1].click();self.assertEqual(player.rate,-30)
            self.assertTrue(player.buttons[4].isEnabled())
            player.buttons[4].click();self.assertEqual(player.rate,120)
            player.seek(7);player.buttons[4].click();self.assertEqual(player.rate,0)
            self.assertFalse(player.timer.isActive())
            player.seek(0);player.toggle();self.assertEqual(player.rate,120)
        finally:player.close()

    def test_retrograde_labels_follow_samples_in_both_directions(self):
        from desktop.sky_player import RETRO_TEXT
        from desktop.model import BODIES
        self.data[1,:,1]=1
        self.data[2,:,1]=-1  # Even corrupt luminary speeds must not add Sun/Moon R.
        player=SkyPlayer(self.path,self.finish());player.show();self.app.processEvents()
        try:
            items=player.view.icons;identities=[id(item) for item in items]
            bounds=[item.boundingRect() for item in items]
            positions=[item.pos() for item in items]
            for frame,active in ((0,(2,)),(1,()),(2,tuple(range(2,10))),(1,()),(0,(2,))):
                player.seek(frame)
                self.assertEqual(player.retrograde_summary.active,active)
                self.assertEqual(identities,[id(item) for item in items])
                for i,item in enumerate(items):
                    retro=i in active
                    self.assertEqual(item.retrograde,retro)
                    self.assertEqual(item.retro.isVisible(),retro)
                    self.assertEqual(item.text.font().bold(),retro)
                    self.assertEqual(item.text.brush().color().name(),RETRO_TEXT if retro else BODIES[i][3])
                    self.assertEqual(item.boundingRect(),bounds[i])
                    if i>0:self.assertEqual(item.pos(),positions[i])
            for width,height in ((600,540),(960,850)):
                player.resize(width,height);self.app.processEvents()
                rects,_=player.retrograde_summary.badge_rects(player.retrograde_summary.names)
                self.assertTrue(all(r.right()<=player.retrograde_summary.width() and r.bottom()<=player.retrograde_summary.height() for r in rects))
                for i,item in enumerate(items):
                    for other in items[i+1:]:self.assertFalse(item.sceneBoundingRect().intersects(other.sceneBoundingRect()))
        finally:player.close()

    def test_single_frame_and_missing_frame(self):
        request=TimelineInput('2026-11-01T00:00','2026-11-01T00:00')
        ident=self.history.begin(request,1)
        self.history.append(ident,0,self.stamps[:1],self.data[:1])
        result=TimelineResult(request,self.stamps[0],self.stamps[0],1,[],0,[]);self.history.complete(ident,result)
        player=SkyPlayer(self.path,self.history.load(ident))
        try:
            player.play(15);self.assertEqual(player.rate,0);self.assertEqual(player.index,0)
        finally:player.close()
        with closing(self.history.connect()) as db, db:db.execute('DELETE FROM frames WHERE run_id=?',(ident,))
        reader=FrameReader(self.path,ident)
        try:
            with self.assertRaises(UserError):reader.frame(0)
        finally:reader.close()

    def test_dst_repeated_hour_keeps_utc_order_and_offset(self):
        request=TimelineInput('2026-11-01T01:50','2026-11-01T01:10','America/New_York',start_fold=0,end_fold=1)
        start,end,_=request.resolve();stamps=[start.timestamp()+600*i for i in range(3)]
        ident=self.history.begin(request,3);self.history.append(ident,0,stamps,self.data[:3])
        self.history.complete(ident,TimelineResult(request,stamps[0],stamps[-1],3,[],0,[]))
        player=SkyPlayer(self.path,self.history.load(ident))
        try:
            self.assertIn('01:50 -0400',player.timestamp.text())
            player.seek(1);self.assertIn('01:00 -0500',player.timestamp.text())
            player.seek(2);self.assertIn('01:10 -0500',player.timestamp.text())
        finally:player.close()

    def test_worker_failure_and_cancellation_never_publish_partial_history(self):
        from PySide6.QtWidgets import QWidget
        from desktop.timeline import Cancelled
        from desktop.timeline_ui import TimelineWorker
        parent=QWidget();parent.history_path=self.path
        for exception,status in ((OSError('test failure'),'failed'),(Cancelled(),'cancelled')):
            worker=TimelineWorker(self.request,parent)
            def fail(*args,**kwargs):
                kwargs['samples_ready'](0,self.stamps[:2],self.data[:2])
                raise exception
            failures=[];success=[];cancellations=[]
            worker.failed.connect(failures.append);worker.succeeded.connect(success.append)
            worker.cancelled.connect(lambda:cancellations.append(True))
            with patch('desktop.timeline_ui.calculate_timeline',fail):worker.run()
            self.assertEqual(success,[])
            self.assertEqual(bool(failures),status=='failed')
            self.assertEqual(bool(cancellations),status=='cancelled')
            with closing(self.history.connect()) as db:
                self.assertEqual(db.execute('SELECT status,saved FROM runs ORDER BY id DESC LIMIT 1').fetchone(),(status,2))
        self.assertEqual(self.history.list_complete(),[])
        parent.deleteLater()

    def test_history_orbs_do_not_replace_shared_settings(self):
        from desktop.timeline_ui import TimelinePage
        result=self.finish();shared={0:7.,90:5.,120:4.,180:2.}
        page=TimelinePage(orb_provider=lambda:shared.copy(),history_path=self.path)
        try:
            page.load_history(result.history_id)
            self.assertEqual(page.result.request.orbs,(4.,3.,3.,3.))
            self.assertEqual(page.request().orbs,(7.,5.,4.,2.))
            page.show_player();player=page.player
            page.conditions_changed()
            self.assertTrue(player.closed);self.assertIsNone(page.result)
            self.assertFalse(page.player_button.isEnabled())
        finally:page.close_player();page.deleteLater()


if __name__=='__main__':unittest.main()
