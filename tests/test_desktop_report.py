# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""User-defined sorting, portable reports, stale export, and matrix visibility."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json,tempfile,unittest,sys,copy
from pathlib import Path
from dataclasses import asdict,replace
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'scripts')]
from desktop.model import BirthInput,ChartEngine,ASPECTS,sorted_aspect_details,display_chart
from desktop.report import render_html,TEMPLATES,page_counter_content
from desktop.storage import ProfileStore
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtCore import QTime
from PySide6.QtTest import QTest

class DetailSortTests(unittest.TestCase):
    def test_groups_and_orientation_and_input_immutable(self):
        def a(x,y,angle):return dict(a=x,b=y,a_lon=1,b_lon=2,angle=angle)
        original=[a('冥王星','海王星',60),a('太陽','月亮',60),a('冥王星','上升點',90),
            a('冥王星','太陽',90),a('月亮','太陽',0),a('金星','水星',120)]
        snapshot=copy.deepcopy(original);result=sorted_aspect_details(original)
        self.assertEqual([(x['a'],x['b'],x['angle']) for x in result],[
            ('太陽','月亮',0),('太陽','冥王星',90),('水星','金星',120),('上升點','冥王星',90),('太陽','月亮',60),('冥王星','海王星',60)])
        self.assertEqual(original,snapshot);self.assertEqual(result[1]['a_lon'],2)
    def test_angle_priority_after_pair(self):
        rows=[dict(a='太陽',b='月亮',a_lon=0,b_lon=1,angle=a) for a in (150,90,180,120,0,135,72,45,30,60)]
        self.assertEqual([x['angle'] for x in sorted_aspect_details(rows)],[0,120,180,90,60,30,45,72,135,150])

class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        root=Path(__file__).resolve().parents[1]
        fid=QFontDatabase.addApplicationFont(str(root/'data/desktop/NotoSansTC.ttf'))
        cls.app.setFont(QFont(QFontDatabase.applicationFontFamilies(fid)[0],10))
        cls.chart=ChartEngine().calculate(BirthInput(name='測試 <script>alert(1)</script>',notes='PRIVATE & <note>'))
    def test_html_escaping_visibility_and_no_hidden_payload(self):
        chart=display_chart(self.chart,replace(BirthInput(**self.chart['input']),small_bodies=False,minor_aspects=False))
        report=render_html(chart)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',report)
        self.assertNotIn('<script>',report);self.assertNotIn('PRIVATE',report)
        self.assertNotIn('凱龍星',report);self.assertNotIn('半四分',report)
        self.assertNotIn('data:font',report);self.assertNotIn('@font-face',report)
        self.assertIn('Microsoft JhengHei',report);self.assertLess(len(report.encode('utf-8')),1_000_000)
        self.assertEqual(report.count('<section class="page"'),5)
        self.assertNotIn('api_key',report);self.assertNotIn('<img',report)
        self.assertIn('PRIVATE &amp; &lt;note&gt;',render_html(chart,True))
    def test_clean_metadata_and_translated_real_page_counters(self):
        report=render_html(self.chart)
        self.assertNotIn('Open BirthChart',report)
        self.assertNotIn('夏令判定方式',report)
        self.assertIn('<dt>夏令調整</dt><dd>未套用</dd>',report)
        self.assertIn('<dt>換算 UTC</dt><dd>1978-04-20 00:23:00</dd>',report)
        self.assertNotIn('1978-04-20T00:23:00+00:00',report)
        self.assertIn('"第 " counter(page) " 頁 / 共 " counter(pages) " 頁"',report)
        self.assertGreater(report.index('<footer'),report.index('</main>'))
        chart=copy.deepcopy(self.chart);chart['dst_minutes']=60
        self.assertIn('<dt>夏令調整</dt><dd>60 分鐘</dd>',render_html(chart))
        self.assertEqual(page_counter_content('Page {page} of {pages}'),'"Page " counter(page) " of " counter(pages)')
        self.assertNotIn('</style>',page_counter_content('</style>{page}{pages}'))
        with self.assertRaises(ValueError):page_counter_content('Page {page}')
    def test_copy_template_translates_svg_and_tables(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'language';shutil.copytree(TEMPLATES/'zh-TW',folder)
            p=folder/'labels.json';labels=json.loads(p.read_text(encoding='utf-8'))
            labels['bodies']['太陽']='SUN-TEST';labels['shorts']['0']='Sx';labels['signs'][0]='ARIES-TEST'
            labels['page_number']='Page {page} of {pages}'
            p.write_text(json.dumps(labels,ensure_ascii=False),encoding='utf-8')
            report=render_html(self.chart,template_dir=folder)
            self.assertIn('SUN-TEST',report);self.assertIn('>Sx</text>',report);self.assertIn('ARIES-TEST',report)
            self.assertIn('"Page " counter(page) " of " counter(pages)',report)
    def test_english_export_selection_and_content(self):
        from desktop.dialogs import ExportDialog
        from desktop.report import available_templates
        self.assertEqual(available_templates()[0][0].name,'zh-TW')
        dialog=ExportDialog()
        index=dialog.templates.findText('English')
        self.assertGreaterEqual(index,0)
        dialog.templates.setCurrentIndex(index)
        folder=Path(dialog.templates.currentData())
        chart=copy.deepcopy(self.chart)
        chart['input'].update(name='Alex Example',notes='PRIVATE & <note>',system='W')
        labels=json.loads((folder/'labels.json').read_text(encoding='utf-8'))
        chart['notes']=list(labels['warnings'])
        chart['dst_minutes']=60
        snapshot=copy.deepcopy(chart)
        report=render_html(chart,template_dir=folder)
        self.assertIn('<html lang="en-US">',report)
        self.assertIn('>Su</text>',report)
        for value in ['Aries','Whole Sign','60 minutes','North Node','Sesquiquadrate','Page ',*labels['warnings'].values()]:
            self.assertIn(value,report)
        self.assertNotRegex(report,r'[\u3400-\u9fff]')
        self.assertNotIn('PRIVATE',report)
        chart['input']['name']='王小明 <script>'
        chart['input']['notes']='私人備註 & <note>'
        translated=render_html(chart,True,folder)
        self.assertIn('王小明 &lt;script&gt;',translated)
        self.assertIn('私人備註 &amp; &lt;note&gt;',translated)
        restricted=display_chart(snapshot,replace(BirthInput(**snapshot['input']),small_bodies=False,minor_aspects=False))
        restricted_html=render_html(restricted,template_dir=folder)
        self.assertNotIn('Chiron',restricted_html)
        self.assertNotIn('Sesquiquadrate',restricted_html)
        self.assertEqual(snapshot['points'],chart['points'])
        self.assertEqual(snapshot['aspects'],chart['aspects'])
        dialog.close()
    def test_zodiac_outlines_match_desktop_and_both_reports(self):
        from unittest.mock import patch
        from desktop.chart import paint_wheel
        from desktop.zodiac import draw_zodiac,zodiac_paths
        from desktop.report import svg_image
        import xml.etree.ElementTree as ET
        paths=zodiac_paths()
        self.assertEqual(len(paths),12)
        self.assertEqual(len({str([(p.elementAt(i).x,p.elementAt(i).y) for i in range(p.elementCount())]) for p in paths}),12)
        for path in paths:
            bounds=path.boundingRect()
            self.assertAlmostEqual(max(bounds.width(),bounds.height()),1)
            self.assertAlmostEqual(bounds.center().x(),0)
            self.assertAlmostEqual(bounds.center().y(),0)
        snapshot=copy.deepcopy(self.chart);draws=[]
        def capture(p,index,center,size,color):
            draws.append((index,center.x(),center.y(),size,color))
            draw_zodiac(p,index,center,size,color)
        with patch('desktop.chart.draw_zodiac',side_effect=capture):
            desktop_svg=svg_image(1000,1000,lambda p:paint_wheel(p,self.chart))
            for language in ('zh-TW','en-US'):
                report=render_html(self.chart,template_dir=TEMPLATES/language)
                wheel=report.split('<div class="wheel">',1)[1].split('</svg>',1)[0]+'</svg>'
                root=ET.fromstring(wheel)
                visible_text=[node.text for node in root.iter('{http://www.w3.org/2000/svg}text')]
                labels=json.loads((TEMPLATES/language/'labels.json').read_text(encoding='utf-8'))
                self.assertFalse(set(labels['signs'])&set(visible_text))
                self.assertIn(labels['signs'][0],root.attrib['aria-label'])
                self.assertNotIn('Astronomicon',wheel) # Paths, not a viewer font dependency.
                self.assertNotIn('@font-face',report)
        self.assertEqual(len(draws),36)
        self.assertEqual(draws[:12],draws[12:24]);self.assertEqual(draws[:12],draws[24:])
        self.assertEqual(self.chart,snapshot)
    def test_matrix_fits_supported_sizes_and_export_guard(self):
        from desktop.window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            w=MainWindow(store=ProfileStore(Path(tmp)/'test.sqlite'),prompt_unsaved=False)
            w.show();self.assertFalse(w.export_ready())
            w.restore_profile(dict(schema=1,input=self.chart['input'],custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS}))
            w.apply_chart(self.chart);w.tabs.setCurrentIndex(3)
            for width,height in [(1440,900),(1280,720),(1024,650),(920,540)]:
                w.resize(width,height)
                for _ in range(4):self.app.processEvents();QTest.qWait(10)
                table=w.matrix.table
                self.assertEqual(table.verticalScrollBar().maximum(),0,(width,height,'vertical'))
                self.assertEqual(table.horizontalScrollBar().maximum(),0,(width,height,'horizontal'))
                self.assertLessEqual(table.geometry().bottom(),w.matrix.height())
            self.assertTrue(w.export_ready());w.time.setTime(QTime(9,12,34));self.assertFalse(w.export_ready())
            self.assertFalse(w.export_button.isEnabled());w.export();self.assertIn('排星盤',w.status.text())
            w.close();w.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()
