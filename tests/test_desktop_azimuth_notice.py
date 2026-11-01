# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Known H conditions must remain visible and portable in both UI languages."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import copy, json, re, sys, tempfile, unittest, html
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from PySide6.QtWidgets import QApplication
from desktop.model import BirthInput, ChartEngine
from desktop.house_positions import azimuth_notices
from desktop.report import render_html, TEMPLATES
from desktop.i18n import install_language
from desktop.help import has_azimuth_notice, article_html


class AzimuthNoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.engine=ChartEngine()
        cls.affected=cls.engine.calculate(BirthInput(local_iso='1947-04-06T09:46:45',zone='America/Lima',longitude=-77.02824,latitude=-12.04318,system='H'))
        cls.unaffected=cls.engine.calculate(BirthInput(system='H'))

    def test_geometric_detection_in_both_hemispheres_and_reversed_rings(self):
        import numerical_regression as nr
        from desktop.model import house_direction
        _,_,rows=nr.load_run(ROOT/'regression/baselines/0.6.3')
        counts={'main':0,'boundary':0}
        for ident,r in rows.items():
            c=r['raw']
            if not isinstance(c,dict) or 'house_positions' not in c:continue
            notices=azimuth_notices(c['input']['system'],house_direction(c['cusps']),c['mc'],c['cusps'],c['house_positions']['-3']['raw_position'])
            if notices:counts['main' if ident.startswith('main-') else 'boundary']+=1
        self.assertEqual(counts,{'main':42,'boundary':16})

    def test_affected_exports_are_self_contained_and_language_independent(self):
        self.assertTrue(has_azimuth_notice(self.affected))
        before=copy.deepcopy(self.affected)
        for ui in ('zh-TW','en-US'):
            install_language(self.app,ui)
            for report_language in ('zh-TW','en-US'):
                labels=json.loads((TEMPLATES/report_language/'labels.json').read_text(encoding='utf-8'))
                content=render_html(self.affected,template_dir=TEMPLATES/report_language)
                self.assertIn(html.escape(labels['azimuth_aligned_notice'],quote=True),content)
                self.assertEqual(content.count('role="note"'),2)
                self.assertIn('href="#azimuth-help"',content);self.assertIn('id="azimuth-help"',content)
                self.assertIn(article_html(report_language),content)
                self.assertNotIn('<script',content);self.assertNotIn('file:',content)
                mc_name=labels['bodies']['天頂']
                # The zodiac cell now contains decorative SVG and named spans.
                from test_desktop_reverse_cr import Cells
                parsed=Cells();parsed.feed(content)
                row=next(r for r in parsed.rows if len(r)==4 and r[0]==mc_name)
                self.assertEqual(row[2],'10')
                audit=self.affected['house_positions']['-3']
                self.assertEqual(audit['raw_position'],3.9999999999999756)
                self.assertEqual(audit['correction'],'azimuth_numbering')
                self.assertIn('3.999',article_html(report_language))
        self.assertEqual(before,self.affected)
        install_language(self.app,'zh-TW')

    def test_unaffected_chart_has_no_notice_or_help_appendix(self):
        self.assertFalse(has_azimuth_notice(self.unaffected))
        report=render_html(self.unaffected)
        self.assertNotIn('role="note"',report);self.assertNotIn('id="azimuth-help"',report)

    def test_historical_notice_is_not_relabelled_as_aligned(self):
        older=copy.deepcopy(self.affected)
        older['house_notices']=[dict(code='azimuth_house_numbering',reasons=['mc_cusp_numbering'])]
        for locale in ('zh-TW','en-US'):
            labels=json.loads((TEMPLATES/locale/'labels.json').read_text(encoding='utf-8'))
            content=render_html(older,template_dir=TEMPLATES/locale)
            self.assertIn(html.escape(labels['azimuth_notice'],quote=True),content)
            self.assertNotIn(html.escape(labels['azimuth_aligned_notice'],quote=True),content)

    def test_desktop_notice_survives_tab_changes_and_clears_on_new_chart(self):
        from desktop.window import MainWindow
        from desktop.storage import ProfileStore
        with tempfile.TemporaryDirectory() as temp:
            for locale in ('zh-TW','en-US'):
                install_language(self.app,locale)
                w=MainWindow(store=ProfileStore(Path(temp)/(locale+'.sqlite')),prompt_unsaved=False)
                w.show();w.apply_chart(self.affected);self.app.processEvents()
                from desktop.help import azimuth_notice_text
                self.assertEqual(w.house_notice_label.text(),azimuth_notice_text(self.affected))
                for tab in range(w.tabs.count()):
                    w.tabs.setCurrentIndex(tab);self.app.processEvents();self.assertTrue(w.house_notice.isVisible())
                with patch('desktop.window.show_azimuth_help') as help_dialog:
                    w.house_notice_help.click();help_dialog.assert_called_once_with(w)
                w.apply_chart(self.unaffected);self.assertTrue(w.house_notice.isHidden())
                w.apply_chart(self.affected);w.new_record();self.assertTrue(w.house_notice.isHidden())
                w.close();w.deleteLater();self.app.processEvents()
        install_language(self.app,'zh-TW')


if __name__=='__main__':unittest.main()
