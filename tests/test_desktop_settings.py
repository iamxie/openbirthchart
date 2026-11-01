# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Persist only the API key, preserve profiles, and start exports in Documents."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys,tempfile,unittest,json
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'scripts')]
from desktop.storage import ProfileStore
from desktop.model import BirthInput,ASPECTS
from desktop.geocoding import GeocodeDialog
from desktop.window import MainWindow
from PySide6.QtWidgets import QApplication,QDialog

class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'data.sqlite';self.store=ProfileStore(self.path)
    def tearDown(self):self.app.processEvents();self.tmp.cleanup()

    def test_key_reopen_update_delete_and_profile_isolation(self):
        self.assertEqual(self.store.load_geocode_key(),'');self.assertFalse(self.path.exists())
        payload=dict(schema=1,input=asdict(BirthInput(name='範例')),custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS})
        ident=self.store.save(payload);before=self.store.load(ident)
        self.store.save_geocode_key('\u200b test-only-key \ufeff')
        reopened=ProfileStore(self.path);self.assertEqual(reopened.load_geocode_key(),'test-only-key')
        self.assertEqual(reopened.load(ident),before);self.assertNotIn('test-only-key',json.dumps(reopened.list()))
        reopened.save_geocode_key('replacement-test-key');self.assertEqual(self.store.load_geocode_key(),'replacement-test-key')
        reopened.save_geocode_key('\u200b \ufeff');self.assertEqual(self.store.load_geocode_key(),'')
        self.assertEqual(reopened.load(ident),before)

    def test_global_orbs_reopen_legacy_profile_and_busy_guard(self):
        from desktop.settings import default_orbs
        from desktop.timeline import TimelineInput,TimelineResult
        from desktop.errors import UserError
        values={**default_orbs(),0:6.,72:2.5}
        w=MainWindow(auto_start=False,store=self.store,prompt_unsaved=False)
        try:
            w.mode_tabs.setCurrentIndex(1);page=w.timeline_page
            request=page.request();start,end,_=request.resolve()
            page.apply_result(TimelineResult(request,start.timestamp(),end.timestamp(),2,[],1,[]))
            snapshot=w.form_snapshot()
            w.apply_orbs(values)
            self.assertEqual(w.form_snapshot(),snapshot)
            self.assertIsNone(page.result)
            self.assertEqual(page.request().orbs,(6.,3.,3.,3.))
            self.assertEqual(ProfileStore(self.path).load_orbs(),values)
            legacy=dict(schema=1,input=asdict(BirthInput(name='legacy')),custom_orbs=True,
                        orb_values={str(a):15 for a in values})
            w.restore_profile(legacy)
            self.assertEqual(w.orbs(),values)
            saved=w.store.load(w.store.save(w.profile_payload()))
            self.assertNotIn('orb_values',saved);self.assertNotIn('custom_orbs',saved)
            page.worker=object()
            with self.assertRaises(UserError):w.apply_orbs(default_orbs())
            self.assertEqual(self.store.load_orbs(),values)
            page.worker=None
            with patch.object(self.store,'save_orbs',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):w.apply_orbs(default_orbs())
            self.assertEqual(w.orbs(),values)
        finally:
            page.worker=None;w.close();w.deleteLater();self.app.processEvents()
        reopened=MainWindow(auto_start=False,store=ProfileStore(self.path),prompt_unsaved=False)
        self.assertEqual(reopened.orbs(),values)
        reopened.close();reopened.deleteLater();self.app.processEvents()

    def test_invalid_global_orbs_do_not_replace_saved_settings(self):
        from desktop.settings import default_orbs
        from desktop.errors import UserError
        self.store.save_orbs(default_orbs())
        for value in (float('nan'),float('inf'),-1,16,.15,True):
            with self.subTest(value=value),self.assertRaises(UserError):
                self.store.save_orbs({**default_orbs(),0:value})
        self.assertEqual(self.store.load_orbs(),default_orbs())

    def test_dialog_close_saves_and_next_window_prefills(self):
        seen=[];replacement=['test-only-key','']
        class Dialog(GeocodeDialog):
            def exec(inner):
                seen.append(inner.key.text());inner.key.setText(replacement.pop(0))
                inner.address.setText('transient address must not be saved')
                return QDialog.DialogCode.Rejected
        with patch('desktop.window.GeocodeDialog',Dialog):
            for _ in range(2):
                w=MainWindow(store=ProfileStore(self.path),prompt_unsaved=False)
                w.lookup_coordinates();w.close();w.deleteLater();self.app.processEvents()
        self.assertEqual(seen,['','test-only-key']);self.assertEqual(self.store.load_geocode_key(),'')
        self.assertNotIn(b'transient address must not be saved',self.path.read_bytes())

    def test_export_dialog_starts_in_documents_folder(self):
        target=Path(self.tmp.name)/'Documents/openbirthchart'
        w=MainWindow(store=self.store,prompt_unsaved=False)
        w.chart={'input':{'name':'郭淮安','local_iso':'1978-04-20T08:23:00'}}
        try:
            with patch.object(w,'export_ready',return_value=True),patch('desktop.window.default_database_path',return_value=target/'data.sqlite'),patch('desktop.window.QDialog.exec',return_value=QDialog.DialogCode.Accepted),patch('desktop.window.QFileDialog.getSaveFileName',return_value=('','')) as chooser:
                w.export()
            initial=Path(chooser.call_args.args[2]);self.assertEqual(initial.parent,target)
            self.assertEqual(initial.name,'郭淮安-19780420.html');self.assertTrue(target.is_dir())
        finally:w.close();w.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()
