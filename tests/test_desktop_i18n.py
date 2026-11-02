# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Language changes must preserve profiles, calculation semantics and report choice."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import copy,json,sys,tempfile,unittest
from contextlib import closing
from pathlib import Path
from dataclasses import asdict,replace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from PySide6.QtWidgets import QApplication,QDialog,QLabel,QPushButton
from desktop.i18n import install_language,language,tr,error_text,short_name
from desktop.model import BirthInput,ChartEngine,ASPECTS,resolve_local,sorted_aspect_details
from desktop.errors import AmbiguousTimeError
from desktop.window import MainWindow
from desktop.storage import ProfileStore,DuplicateProfile
from desktop.report import render_html,TEMPLATES
from desktop.dialogs import LanguageDialog,ExportDialog


class I18nTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.chart=ChartEngine().calculate(BirthInput(name='User 姓名',notes='Personal 備註'))

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=ProfileStore(Path(self.tmp.name)/'data.sqlite')
        install_language(self.app,'zh-TW');self.windows=[]

    def tearDown(self):
        for w in self.windows:w.close();w.deleteLater()
        self.app.processEvents();install_language(self.app,'zh-TW');self.tmp.cleanup()

    def window(self,lang):
        install_language(self.app,lang)
        w=MainWindow(store=self.store,prompt_unsaved=False);self.windows.append(w)
        return w

    def payload(self):
        return dict(schema=1,input=copy.deepcopy(self.chart['input']),custom_orbs=False,
                    orb_values={str(a):o for a,_,o,_,_ in ASPECTS})

    def test_language_setting_is_lazy_validated_and_profile_independent(self):
        self.assertEqual(self.store.load_ui_language(),'zh-TW');self.assertFalse(self.store.path.exists())
        ident=self.store.save(self.payload());before=self.store.load(ident)
        self.store.save_geocode_key('test-only-key');self.store.save_ui_language('en-US')
        reopened=ProfileStore(self.store.path)
        self.assertEqual(reopened.load_ui_language(),'en-US');self.assertEqual(reopened.load(ident),before)
        self.assertEqual(reopened.load_geocode_key(),'test-only-key')
        with self.assertRaises(ValueError):self.store.save_ui_language('bad-locale')
        self.assertEqual(reopened.load_ui_language(),'en-US')
        with closing(self.store._connect()) as conn,conn:conn.execute("UPDATE app_settings SET value='unknown' WHERE name='ui_language'")
        self.assertEqual(reopened.load_ui_language(),'zh-TW')

    def test_select_language_affects_next_start_only_and_cancel_preserves(self):
        w=self.window('zh-TW');w.restore_profile(self.payload());w.apply_chart(copy.deepcopy(self.chart))
        w.notes.setPlainText('Unsaved draft 備註');snapshot=w.form_snapshot();chart=copy.deepcopy(w.chart)
        def accept(dialog):
            dialog.languages.setCurrentIndex(dialog.languages.findData('en-US'));return QDialog.DialogCode.Accepted
        with patch.object(LanguageDialog,'exec',accept),patch('desktop.window.QMessageBox.information'):
            w.choose_language()
        self.assertEqual(language(),'zh-TW');self.assertEqual(w.calculate_button.text(),'排星盤')
        self.assertEqual(w.form_snapshot(),snapshot);self.assertEqual(w.chart,chart);self.assertTrue(w.is_dirty())
        self.assertEqual(self.store.load_ui_language(),'en-US')
        with patch.object(LanguageDialog,'exec',return_value=QDialog.DialogCode.Rejected):w.choose_language()
        self.assertEqual(self.store.load_ui_language(),'en-US')
        english=self.window(self.store.load_ui_language());self.assertEqual(english.calculate_button.text(),'Calculate')
        self.store.save_ui_language('zh-TW')
        self.assertEqual(english.calculate_button.text(),'Calculate')

    def test_english_load_save_duplicate_and_display_keep_canonical_data(self):
        original=self.payload();ident=self.store.save(original);w=self.window('en-US')
        w.restore_profile(self.store.load(ident),ident);w.apply_chart(copy.deepcopy(self.chart))
        self.assertEqual(w.gender.currentText(),'Male');self.assertEqual(w.input().gender,'男')
        self.assertEqual(w.positions.item(0,0).text(),'Sun')
        self.assertIn('Aries',w.positions.item(0,1).text())
        self.assertEqual(w.matrix.table.horizontalHeaderItem(0).text(),'Su')
        self.assertEqual(w.matrix.table.horizontalHeaderItem(0).toolTip(),'Sun')
        self.assertIn('Separation',w.matrix.description(1,0))
        self.assertEqual(w.chart['all_points'],self.chart['all_points'])
        self.assertEqual(sorted_aspect_details(w.chart['aspects']),sorted_aspect_details(self.chart['aspects']))
        self.assertFalse(w.is_dirty());self.assertTrue(w.save_record());self.assertEqual(w.record_id,ident)
        self.assertEqual(self.store.load(ident)['input'],original['input'])
        with self.assertRaises(DuplicateProfile) as caught:self.store.save(original)
        self.assertIn('already exists',error_text(caught.exception))
        w.gender.setCurrentIndex(w.gender.findData('女'));self.assertEqual(w.input().gender,'女')

    def test_ambiguous_time_selection_is_not_based_on_translated_text(self):
        w=self.window('en-US');payload=self.payload()
        payload['input']=asdict(BirthInput(local_iso='2024-11-03T01:30:00',zone='America/New_York',fold=0))
        w.restore_profile(payload);w.fold.setCurrentIndex(0);w.refresh_time()
        self.assertFalse(w.fold.isHidden());self.assertIn('occurs twice',w.time_info.text())
        with self.assertRaises(AmbiguousTimeError):resolve_local(replace(BirthInput(**payload['input']),fold=None))
        w.fold.setCurrentIndex(w.fold.findData(1));w.refresh_time()
        self.assertIn('UTC',w.time_info.text());self.assertNotIn('兩次',w.time_info.text())

    def test_both_report_languages_are_independent_of_interface(self):
        baseline={lang:render_html(self.chart,True,TEMPLATES/lang) for lang in ('zh-TW','en-US')}
        w=self.window('en-US');snapshot=copy.deepcopy(self.chart)
        for lang in baseline:self.assertEqual(render_html(self.chart,True,TEMPLATES/lang),baseline[lang])
        self.assertEqual(self.chart,snapshot)
        dialog=ExportDialog(w)
        self.assertEqual(dialog.windowTitle(),'Export Report')
        self.assertEqual(Path(dialog.templates.currentData()).name,'zh-TW')
        self.assertGreaterEqual(dialog.templates.findText('English'),0)
        dialog.deleteLater()

    def test_language_save_error_keeps_current_ui_and_draft(self):
        w=self.window('en-US');w.name.setText('Draft');snapshot=w.form_snapshot()
        with patch.object(LanguageDialog,'exec',return_value=QDialog.DialogCode.Accepted),patch.object(self.store,'save_ui_language',side_effect=OSError('disk full')),patch('desktop.window.QMessageBox.warning') as warning:
            w.choose_language()
        self.assertTrue(warning.called);self.assertEqual(w.form_snapshot(),snapshot)
        self.assertEqual(language(),'en-US');self.assertEqual(self.store.load_ui_language(),'zh-TW')

    def test_domain_terms_agree_with_report_and_calculation_is_identical(self):
        from desktop.model import SIGNS,BODIES,MINORS
        self.window('en-US')
        labels=json.loads((TEMPLATES/'en-US/labels.json').read_text(encoding='utf-8'))
        for source,expected in labels['bodies'].items():self.assertEqual(tr(source),expected)
        for source,expected in labels['warnings'].items():self.assertEqual(tr(source),expected)
        for source,expected in zip(SIGNS,labels['signs']):self.assertEqual(tr(source),expected)
        for angle,name,*_ in ASPECTS:self.assertEqual(tr(name),labels['aspects'][str(angle)])
        for ident,name,short,color in BODIES+MINORS:
            self.assertEqual(short_name(dict(short=short)),labels['shorts'][str(ident)])
        english=ChartEngine().calculate(BirthInput(**self.chart['input']))
        self.assertEqual(english,self.chart)

if __name__=='__main__':unittest.main()
