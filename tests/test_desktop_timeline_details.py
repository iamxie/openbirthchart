# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.timeline import (TimelineInput,TimelineResult,SkyEvent,ZodiacSegment,
    EventCollector,_refine_bundle,_assemble_sign_segments,DEFAULT_ORBS)
from desktop.timeline_details import sign_at,event_spans,sign_path,overlapping_events
from desktop.timeline_report import render_timeline_html,labels_for,sign_description


def fixture():
    e=SkyEvent('aspect',2,4,180,0,600,exact=[300])
    other=SkyEvent('retro',4,None,None,100,450)
    r=TimelineResult(TimelineInput('2027-01-01T00:00','2027-01-01T01:00'),0,600,2,[e,other],1,[],[],[
        ZodiacSegment(2,0,200,7),ZodiacSegment(2,200,400,8),ZodiacSegment(2,400,600,7),
        ZodiacSegment(4,0,300,1),ZodiacSegment(4,300,600,2)])
    return r,e,other


class DetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_scope_palette_and_chart_first_report(self):
        from desktop.timeline import PAIRS,RETRO_IDS,_sample_chunk
        from desktop.timeline_palette import COLORS
        from desktop.timeline_ui import COLORS as UI_COLORS
        from desktop.timeline_report import COLORS as REPORT_COLORS
        self.assertEqual(len(PAIRS),28)
        self.assertIs(UI_COLORS,REPORT_COLORS)
        self.assertEqual(len(set(COLORS.values())),5)
        calls=[]
        def positions(stamp,bodies):
            calls.append(bodies);return np.zeros((len(bodies),2)),[]
        with patch('desktop.timeline._positions',positions):_sample_chunk((0,600,0,2,600))
        self.assertEqual(calls,[RETRO_IDS,RETRO_IDS])
        r,e,_=fixture()
        for locale in ('zh-TW','en-US'):
            doc=render_timeline_html(r,ROOT/'templates/report'/locale)
            self.assertLess(doc.index('id="timeline"'),doc.index('id="overview"'))
            for color in COLORS.values():self.assertIn(color,doc)

    def test_english_zodiac_icons_in_reports_details_and_qt_images(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument
        from PySide6.QtWidgets import QTextBrowser
        from desktop.timeline_report import sign_markup,event_html,overlaps_html
        from desktop.timeline_zodiac import qt_sign_image
        en=labels_for(ROOT/'templates/report/en-US');zh=labels_for(ROOT/'templates/report/zh-TW')
        browser=QTextBrowser()
        for sign in range(12):
            markup=sign_markup(sign,en)
            self.assertIn('<path',markup);self.assertIn(en['signs'][sign],markup)
            self.assertIn('aria-hidden="true"',markup)
            self.assertNotIn('<svg',sign_markup(sign,zh))
            browser.setHtml(sign_markup(sign,en,'qt'))
            loaded=browser.document().resource(QTextDocument.ResourceType.ImageResource,QUrl(qt_sign_image(sign)))
            self.assertIsNotNone(loaded);self.assertFalse(loaded.isNull())
        r,e,_=fixture()
        self.assertIn('zodiac-icon',event_html(r,e,en))
        self.assertIn('zodiac-icon',overlaps_html(r,e,en))
        self.assertIn('data:image/png',event_html(r,e,en,icon_mode='qt'))
        doc=render_timeline_html(r,ROOT/'templates/report/en-US')
        self.assertIn('<svg x=',doc);self.assertIn('class="zodiac-position"',doc)
        self.assertNotIn('data:image/png',doc)
        browser.deleteLater()

    def curve_segments(self,fn,times):
        def positions(t,bodies):
            p=np.zeros((10,2));p[:,0]=np.arange(10)*29+1;p[:,1]=1
            p[2]=fn(t)
            return p[list(bodies)],[]
        c=EventCollector(times[0],times[-1],DEFAULT_ORBS)
        for t in times:c.consume(t,positions(t,tuple(range(10)))[0])
        with patch('desktop.timeline._positions',positions):
            c.apply_refinements([_refine_bundle(jobs) for jobs,key in c.jobs])
            return _assemble_sign_segments(list(c.zodiac_jobs())[0])

    def test_wrap_and_retrograde_sign_crossing(self):
        for direction,expected in ((1,[11,0]),(-1,[0,11])):
            segments=self.curve_segments(lambda t:(((direction*(t-300)/600)%360),direction),[0,600])
            self.assertEqual([s.sign for s in segments],expected)
            self.assertAlmostEqual(segments[1].start,300,delta=.125)

    def test_reentry_between_equal_endpoint_signs_and_tangent(self):
        segments=self.curve_segments(lambda t:(30.1-(t-300)**2/600000,-2*(t-300)/600000),[0,600])
        self.assertEqual([s.sign for s in segments],[0,1,0])
        self.assertLess(segments[1].start,300);self.assertGreater(segments[1].end,300)
        tangent=self.curve_segments(lambda t:(30-(t-300)**2/600000,-2*(t-300)/600000),[0,600])
        self.assertEqual([s.sign for s in tangent],[0])

    def test_combined_history_half_open_boundary_and_reentry(self):
        r,e,_=fixture()
        self.assertEqual(sign_path(r,e,2),[7,8,7])
        self.assertEqual([v[2] for v in event_spans(r,e)],[(7,1),(8,1),(8,2),(7,2)])
        self.assertEqual(sign_at(r,4,300),2)
        point=SkyEvent('aspect',2,4,180,300,300)
        self.assertEqual(event_spans(r,point),[(300,300,(8,2))])
        self.assertEqual(sign_at(r,2,600),7)

    def test_ingress_near_query_end_keeps_complete_coverage(self):
        with patch('desktop.timeline._positions',lambda t,b:(np.array([[29.9 if t<599.95 else 30.1,1]]),[])):
            segments=_assemble_sign_segments((2,0,600,[599.95]))
        self.assertEqual(segments[-1].end,600)
        self.assertEqual([s.sign for s in segments],[0,1])

    def test_overlap_scope_and_shared_instant(self):
        r,e,other=fixture()
        r.events.append(SkyEvent('retro',5,None,None,600,900))
        found=overlapping_events(r,e)
        self.assertEqual([(v[2],v[3]) for v in found],[(100,450),(600,600)])
        self.assertEqual([v[1] for v in overlapping_events(r,e,300)],[other])
        self.assertFalse(overlapping_events(r,e,0))

    def test_offline_multilingual_report_and_selected_scope(self):
        r,e,_=fixture()
        for locale,word in (('zh-TW','天象時間軸'),('en-US','Sky Timeline')):
            folder=ROOT/'templates/report'/locale
            markup=render_timeline_html(r,folder)
            self.assertIn(word,markup);self.assertIn('<svg',markup)
            self.assertIn('A4 landscape',markup);self.assertIn('counter(pages)',markup)
            self.assertIn('id="event-1"',markup)
            self.assertNotIn('<script',markup);self.assertNotIn('<link',markup)
            self.assertIn(sign_description(r,e,labels_for(folder)),markup)
            selected=render_timeline_html(r,folder,e)
            self.assertNotIn('id="event-1"',selected)
            self.assertNotIn('href="#event-1"',selected)
            self.assertIn(labels_for(folder)['concurrent'],selected)

    def test_report_escapes_notes_and_supports_empty_result(self):
        r,e,_=fixture();r.notes=['<script>alert("x")</script>']
        self.assertIn('&lt;script&gt;',render_timeline_html(r))
        r.events=[]
        self.assertIn('此範圍沒有事件',render_timeline_html(r))


class DetailsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_detail_navigation_scope_and_invalidated_export(self):
        from desktop.timeline_ui import TimelinePage
        from PySide6.QtCore import QUrl
        p=TimelinePage();r,e,other=fixture();p.apply_result(r);p.show_event(e)
        self.assertEqual(p.export_button.text(),'匯出文件')
        self.assertEqual([p.body_filter.itemData(i) for i in range(p.body_filter.count())],[None,*range(2,10)])
        d=p.detail_dialog
        self.assertTrue(p.export_button.isEnabled());self.assertEqual(d.scope.count(),4)
        d.scope.setCurrentIndex(2)
        self.assertIn('火星',d.overlaps.toPlainText())
        d.navigate(QUrl('event:1'));self.assertIs(d.current_event,other)
        d.go_back();self.assertIs(d.current_event,e)
        p.conditions_changed();self.assertFalse(p.export_button.isEnabled());self.assertFalse(d.isVisible())
        p.close();p.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
