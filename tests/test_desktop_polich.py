# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Expected Polich rejection is explained in both languages, without fallback."""
import json
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
from desktop.errors import UserError
from desktop.i18n import install_language,error_text
from desktop.storage import ProfileStore
from desktop.window import MainWindow
from PySide6.QtWidgets import QApplication,QMessageBox


class PolichRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.engine=ChartEngine()
        cls.policy=json.loads((ROOT/'tests/fixtures/polich-rejection-policy.json').read_text(encoding='utf-8'))
        cls.cases={c['id']:c for c in json.loads((ROOT/cls.policy['suite']).read_text(encoding='utf-8'))['cases']}

    def tearDown(self):install_language(self.app,'zh-TW')

    def test_five_expected_rejections_explain_geometry_and_action_in_both_languages(self):
        self.assertEqual(len(set(self.policy['cases'])),5)
        self.assertEqual(self.policy['expected_status'],'UserError')
        for ident in self.policy['cases']:
            with self.subTest(case=ident),self.assertRaises(UserError) as caught:
                self.engine.calculate(BirthInput(**self.cases[ident]['input']))
            for lang,reason,action in [('zh-TW','宮頭順序交錯或重疊','請改選其他宮位制'),
                                       ('en-US','out of order or coincide','Choose another house system')]:
                install_language(self.app,lang);text=error_text(caught.exception)
                self.assertIn('Polich',text);self.assertIn(reason,text);self.assertIn(action,text)
                self.assertIn('Equal',text);self.assertIn('Whole Sign',text)
                with tempfile.TemporaryDirectory() as tmp:
                    window=MainWindow(auto_start=False,store=ProfileStore(Path(tmp)/'test.sqlite'),prompt_unsaved=False)
                    try:
                        window.export_button.setEnabled(True)
                        with patch.object(QMessageBox,'warning') as warning:window.error(text)
                        self.assertEqual(warning.call_args.args[2],text)
                        self.assertIn(text,window.status.text())
                        self.assertFalse(window.export_button.isEnabled())
                    finally:window.close()

    def test_valid_polich_chart_is_still_accepted(self):
        chart=self.engine.calculate(BirthInput(**self.cases['complete-1904-01-T']['input']))
        self.assertEqual(chart['input']['system'],'T')
        self.assertEqual(len(chart['cusps']),12)


if __name__=='__main__':unittest.main()
