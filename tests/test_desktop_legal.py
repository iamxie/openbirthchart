# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""The packaged license is reachable offline from either UI language."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from PySide6.QtWidgets import QApplication,QDialog,QTabWidget,QTextBrowser
from desktop.i18n import install_language
from desktop.window import MainWindow
from desktop.storage import ProfileStore
from desktop.model import APP_VERSION

class LegalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def tearDown(self):install_language(self.app,'zh-TW')
    def test_notice_and_full_license_are_accessible_offline(self):
        for locale,title in [('zh-TW','關於與授權'),('en-US','About and License')]:
            install_language(self.app,locale)
            with tempfile.TemporaryDirectory() as temp:
                window=MainWindow(auto_start=False,store=ProfileStore(Path(temp)/'unused.sqlite'),prompt_unsaved=False)
                try:
                    seen=[]
                    def inspect(dialog):
                        tabs=dialog.findChild(QTabWidget);self.assertEqual(tabs.count(),3)
                        self.assertIn(APP_VERSION,dialog.windowTitle())
                        notices=tabs.widget(0).toPlainText();license=tabs.widget(1).toPlainText()
                        self.assertIn('OpenBirthChart contributors',notices);self.assertIn('WITHOUT ANY WARRANTY',notices)
                        self.assertIn('https://github.com/iamxie/openbirthchart',notices)
                        self.assertIn('13. Remote Network Interaction',license)
                        self.assertEqual(license,(ROOT/'LICENSE').read_text(encoding='utf-8'))
                        seen.append(True);return 0
                    self.assertEqual(window.legal_action.text(),title)
                    with patch.object(QDialog,'exec',inspect):window.legal_action.trigger()
                    self.assertEqual(seen,[True]);self.assertFalse((Path(temp)/'unused.sqlite').exists())
                finally:window.close()
    def test_versioned_source_archives_and_required_notices_exist(self):
        import json
        manifest=json.loads((ROOT/'third-party-sources.lock.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['application'],APP_VERSION)
        self.assertTrue(any(x['name']=='libephemeris' and x['version']=='3.2.2' for x in manifest['archives']))
        self.assertTrue(any(x['name']=='qtbase' for x in manifest['archives']))
        for name in ('NOTICE.md','LICENSE','THIRD_PARTY_DESKTOP.md','docs/BUILDING.md','docs/DEPENDENCY_UPGRADES.md'):
            self.assertTrue((ROOT/name).is_file())

if __name__=='__main__':unittest.main()
