# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Invalid placement must fail closed; English signs share wheel outlines."""
import copy,math,os,re,sys,tempfile,unittest
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from PySide6.QtWidgets import QApplication,QMessageBox
from desktop.errors import UserError
from desktop.house_positions import house_number2,InvalidHousePosition,validate_house_number,validate_chart_houses
from desktop.model import BirthInput,ChartEngine,ASPECTS,display_chart
from desktop.i18n import install_language,error_text,localized_zodiac
from desktop.zodiac import zodiac_index,zodiac_icon,zodiac_paths
from desktop.report import render_html,export_html,TEMPLATES
from desktop.chart import export_chart
from desktop.window import MainWindow
from desktop.storage import ProfileStore

class HouseGuardZodiacTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.engine=ChartEngine();cls.birth=BirthInput(name='Symbol QA')
        cls.chart=cls.engine.calculate(cls.birth)

    def tearDown(self):install_language(self.app,'zh-TW')

    def test_invalid_raw_coordinates_are_preserved_and_refused(self):
        import libephemeris
        for raw in (0,-1,13.01,14,math.nan,math.inf,-math.inf,None,True,'3',[]):
            audit={}
            with self.subTest(raw=raw),patch.object(libephemeris,'house_pos',return_value=raw):
                with self.assertRaises(InvalidHousePosition):house_number2(120,25,23.4,225,3,'P',audit=audit)
                self.assertEqual(audit['status'],'invalid')
                if isinstance(raw,float) and math.isnan(raw):self.assertTrue(math.isnan(audit['raw_position']))
                else:self.assertEqual(audit['raw_position'],raw)
        with patch.object(libephemeris,'house_pos',return_value=13):
            self.assertEqual(house_number2(120,25,23.4,225,3,'P'),1)

    def test_final_numbers_and_koch_sentinel_are_distinct(self):
        for v in (0,13,-1,2.5,3.0,None,True,math.nan,'3'):
            with self.subTest(value=v),self.assertRaises(InvalidHousePosition):validate_house_number(v,'P')
        for v in range(1,13):validate_house_number(v,'P')
        validate_house_number(None,'K',dict(status='undefined',raw_position=0.0))
        for audit in ({},dict(status='undefined',raw_position=False),dict(status='undefined',raw_position=1),dict(status='invalid',raw_position=0)):
            with self.assertRaises(InvalidHousePosition):validate_house_number(None,'K',audit)
        with patch.object(self.engine.e,'house_pos',return_value=0.0):
            chart=self.engine.calculate(replace(self.birth,system='K'))
        self.assertTrue(all(p['house'] is None for p in chart['all_points']))
        validate_chart_houses(chart)
        self.assertIn('Undefined',render_html(chart,template_dir=TEMPLATES/'en-US'))

    def test_raw_failure_is_a_clear_bilingual_error_with_all_point_audits(self):
        with patch.object(self.engine.e,'house_pos',return_value=-1.0),self.assertRaises(UserError) as caught:
            self.engine.calculate(self.birth)
        error=caught.exception;self.assertEqual(len(error.diagnostics['house_positions']),len(self.chart['all_points']))
        self.assertTrue(all(a['raw_position']==-1.0 for a in error.diagnostics['house_positions'].values()))
        for lang,word in [('zh-TW','無效宮號'),('en-US','invalid house number')]:
            install_language(self.app,lang);text=error_text(error);self.assertIn(word,text)
            self.assertNotIn('GitHub',text);self.assertNotIn('http',text)

    def test_one_hidden_body_or_invalid_final_return_refuses_the_whole_chart(self):
        from desktop import model
        original=model.house_number2
        hidden=next(p for p in self.chart['all_points'] if p['id']==model.MINORS[0][0])
        def bad(*args,**kwargs):
            value=original(*args,**kwargs)
            return 14 if args[3]==hidden['lon'] else value
        with patch.object(model,'house_number2',side_effect=bad),self.assertRaisesRegex(UserError,'無效宮號'):
            self.engine.calculate(replace(self.birth,small_bodies=False))
        for value in (None,True,3.0):
            with patch.object(model,'house_number2',return_value=value),self.assertRaisesRegex(UserError,'無效宮號'):
                self.engine.calculate(self.birth)

    def test_invalid_cached_chart_cannot_be_exported_or_reused(self):
        bad=copy.deepcopy(self.chart);bad['points'][0]['house']=0
        with self.assertRaisesRegex(UserError,'無效宮號'):display_chart(bad,self.birth)
        with tempfile.TemporaryDirectory() as tmp:
            for suffix,writer in [('html',export_html),('svg',lambda c,p:export_chart(c,p,'svg')),('png',export_chart)]:
                out=Path(tmp)/('bad.'+suffix)
                with self.assertRaisesRegex(UserError,'無效宮號'):writer(bad,out)
                self.assertFalse(out.exists())
            window=MainWindow(auto_start=False,store=ProfileStore(Path(tmp)/'unused.sqlite'),prompt_unsaved=False)
            try:
                window.apply_chart(self.chart)
                with patch.object(QMessageBox,'warning') as warning:window.apply_chart(bad)
                self.assertIn('無效宮號',warning.call_args.args[2]);self.assertIsNone(window.chart)
                self.assertFalse(window.export_ready());self.assertEqual(window.positions.rowCount(),0)
            finally:window.close()

    def test_rounding_and_all_twelve_shared_icons(self):
        install_language(self.app,'en-US')
        self.assertEqual(len(zodiac_paths()),12)
        for i in range(12):
            self.assertEqual(zodiac_index(i*30+1),i);self.assertFalse(zodiac_icon(i).isNull())
        for lon,index,name in [(29.999999999,1,'Taurus'),(359.999999999,0,'Aries'),(-0.000000001,0,'Aries')]:
            self.assertEqual(zodiac_index(lon),index);self.assertTrue(localized_zodiac(lon).startswith(name))

    def test_english_report_has_paths_and_keeps_readable_text_without_mutation(self):
        original=copy.deepcopy(self.chart)
        content=render_html(self.chart,template_dir=TEMPLATES/'en-US')
        self.assertEqual(content.count('class="zodiac-icon"'),len(self.chart['points'])+12)
        self.assertEqual(content.count('class="zodiac-text"'),len(self.chart['points'])+12)
        for svg in re.findall(r'<svg class="zodiac-icon".*?</svg>',content,re.S):
            self.assertIn('<path',svg);self.assertIn('aria-hidden="true"',svg)
            self.assertNotIn('<text',svg)
        self.assertNotIn('class="zodiac-icon"',render_html(self.chart,template_dir=TEMPLATES/'zh-TW'))
        self.assertEqual(original,self.chart)

    def test_desktop_english_positions_and_cusps_keep_icons_with_names(self):
        for lang in ('en-US','zh-TW'):
            install_language(self.app,lang)
            with tempfile.TemporaryDirectory() as tmp:
                window=MainWindow(auto_start=False,store=ProfileStore(Path(tmp)/'unused.sqlite'),prompt_unsaved=False)
                try:
                    window.apply_chart(self.chart)
                    for table,values in ((window.positions,[p['lon'] for p in self.chart['points']]),(window.houses,self.chart['cusps'])):
                        for row,lon in enumerate(values):
                            item=table.item(row,1)
                            self.assertEqual(item.text(),localized_zodiac(lon))
                            self.assertEqual(item.icon().isNull(),lang!='en-US')
                finally:window.close()

if __name__=='__main__':unittest.main()
