# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Regression cases for blank input, duplicate identity, migration and opt-in lookup."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json
import sqlite3
import tempfile
import unittest
from dataclasses import asdict
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'scripts')]
from desktop.model import BirthInput,ASPECTS,APP_VERSION,ASPECT_IDS,display_chart
from desktop.storage import ProfileStore,DuplicateProfile
from desktop.text import trim_text
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QObject,Signal,QByteArray,QTimer,Qt
from PySide6.QtNetwork import QNetworkRequest,QNetworkReply


def profile(**changes):
    return dict(schema=1,input=asdict(BirthInput(**dict({'name':'陳怡君'},**changes))),custom_orbs=False,
        orb_values={str(a):o for a,_,o,_,_ in ASPECTS},app_version=APP_VERSION)


class DuplicateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=ProfileStore(Path(self.tmp.name)/'data.sqlite')
    def tearDown(self):self.tmp.cleanup()

    def test_create_duplicate_update_self_and_original_without_notes(self):
        p=profile();a=self.store.save(p)
        self.store.save(p,a)
        with self.assertRaises(DuplicateProfile):self.store.save(p)
        q=profile(notes='同名的另一位')
        with self.assertRaises(DuplicateProfile):self.store.save(q)
        b=self.store.save(q,confirm_duplicate=True)
        self.assertNotEqual(a,b);self.store.save(p,a)
        self.assertEqual(self.store.load(a)['input']['notes'],'')
        q['input']['notes']='\u200b\ufeff\u3000'
        with self.assertRaisesRegex(ValueError,'不能清空'):self.store.save(q,b)
        self.assertEqual(len(self.store.list()),2)
        self.assertEqual(next(r for r in self.store.list() if r['id']==b)['notes'],'同名的另一位')

    def test_identity_changes_not_render_options_or_automatic_dst(self):
        a=self.store.save(profile());b=self.store.save(profile(name='另一人'))
        for field,value in [('system','W'),('small_bodies',False),('dst_enabled',True)]:
            p=profile();p['input'][field]=value
            with self.assertRaises(DuplicateProfile):self.store.save(p)
        with self.assertRaises(DuplicateProfile):self.store.save(profile(),b)
        self.assertEqual(self.store.load(b)['input']['name'],'另一人')
        self.store.save(profile(system='W'),a)

    def test_seconds_timezone_hemisphere_and_precision(self):
        self.store.save(profile(longitude=120.2))
        with self.assertRaises(DuplicateProfile):self.store.save(profile(longitude=120.20000001))
        for change in [dict(local_iso='1978-04-20T08:23:01'),dict(zone='Asia/Shanghai'),dict(longitude=-120.2),dict(latitude=-23),dict(longitude=120.20001)]:
            self.store.save(profile(**change))
        self.assertEqual(len(self.store.list()),6)

    def test_trim_preserves_internal_content_and_distinguishes_simplified(self):
        self.assertEqual(trim_text('\u200b\ufeff\u3000 陳\u200d怡 君 \u2060\ufe0f'),'陳\u200d怡 君')
        self.assertEqual(trim_text('\u200b\ufeff\u2800\u3164'),'')
        a=self.store.save(profile(name='\u200b陳怡君\ufeff',notes='\u3000說明\u200b'))
        self.assertEqual(self.store.load(a)['input']['notes'],'說明')
        with self.assertRaises(DuplicateProfile):self.store.save(profile())
        self.store.save(profile(name='陈怡君'))

    def test_v1_migration_preserves_id_payload_and_timestamps(self):
        p=profile();del p['input']['notes']
        with closing(sqlite3.connect(self.store.path)) as conn,conn:
            conn.execute('CREATE TABLE profiles (id TEXT PRIMARY KEY,name TEXT,gender TEXT,local_iso TEXT,payload TEXT,created_at TEXT,updated_at TEXT)')
            conn.execute('INSERT INTO profiles VALUES (?,?,?,?,?,?,?)',('old-id','陳怡君','男',p['input']['local_iso'],json.dumps(p),'original-created','original-updated'))
            conn.execute('PRAGMA user_version=1')
        self.assertEqual(self.store.load('old-id')['input']['notes'],'')
        with closing(sqlite3.connect(self.store.path)) as conn:
            row=conn.execute('SELECT id,payload,created_at,updated_at,notes_required FROM profiles').fetchone()
            self.assertEqual(row,('old-id',json.dumps(p),'original-created','original-updated',0))
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],2)


class FormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        from desktop.window import MainWindow
        self.tmp=tempfile.TemporaryDirectory();self.w=MainWindow(store=ProfileStore(Path(self.tmp.name)/'data.sqlite'),prompt_unsaved=False)
    def tearDown(self):
        self.w.close();self.w.deleteLater();self.app.processEvents();self.tmp.cleanup()

    def test_startup_and_new_are_empty_and_incomplete_never_saves(self):
        w=self.w
        self.assertIsNone(w.chart);self.assertIsNone(w.worker)
        for field in (w.name,w.date,w.time,w.lon,w.lat):self.assertEqual(field.text(),'')
        self.assertFalse(w.is_dirty());self.assertFalse(w.export_button.isEnabled())
        self.assertNotIn('UTC+08',w.time_info.text())
        w.name.setText('半筆資料')
        with patch('desktop.window.QMessageBox.warning'):
            self.assertFalse(w.save_record())
        self.assertFalse(w.store.path.exists())
        w.restore_profile(profile());self.assertTrue(w.save_record());w.new_record()
        self.assertIsNone(w.record_id);self.assertFalse(w.is_dirty());self.assertEqual(w.date.text(),'')
        self.assertIsNone(w.chart)

    def test_midnight_and_zero_are_explicit_valid_values(self):
        w=self.w;w.name.setText('零度');w.date.setText('2000/01/01');w.time.setText('00:00:00')
        w.lon.setText('0');w.lat.setText('0');self.assertTrue(w.save_record())
        self.assertEqual(w.store.load(w.record_id)['input']['longitude'],0)
        for field in (w.date,w.time,w.lon,w.lat):
            old=field.text();field.clear()
            with self.assertRaises(ValueError):w.input()
            field.setText(old)

    def test_duplicate_dialog_requires_notes_and_matches_show_notes(self):
        w=self.w;w.store.save(profile(notes='原檔案'));w.restore_profile(profile())
        def inspect_dialog():
            dialog=self.app.activeModalWidget()
            from PySide6.QtWidgets import QPushButton,QTableWidget
            proceed=next(b for b in dialog.findChildren(QPushButton) if b.text()=='依備註區分並儲存')
            self.assertFalse(proceed.isEnabled())
            self.assertEqual(dialog.findChild(QTableWidget).item(0,2).text(),'原檔案')
            dialog.reject()
        QTimer.singleShot(0,inspect_dialog);self.assertFalse(w.save_record());self.assertIsNone(w.record_id)
        w.notes.setPlainText('另一位')
        QTimer.singleShot(0,lambda:self.app.activeModalWidget().accept())
        self.assertTrue(w.save_record());self.assertEqual(len(w.store.list()),2)

    def test_all_aspect_outputs_exclude_small_points(self):
        source=json.loads((Path(__file__).resolve().parents[1]/'results/desktop/openbirthchart-0.2.0-final-source/chart.json').read_text(encoding='utf-8'))
        w=self.w;w.restore_profile(profile(**{k:v for k,v in source['input'].items() if k!='name'}))
        w.apply_chart(source)
        self.assertEqual([p['id'] for p in w.matrix.points],list(ASPECT_IDS))
        names={p['name'] for p in w.matrix.points}
        self.assertTrue(all(a['a'] in names and a['b'] in names for a in w.chart['aspects']))
        count=len(w.chart['aspects']);w.small.setChecked(False)
        self.assertEqual(len(w.chart['aspects']),count);self.assertEqual(w.matrix.table.rowCount(),12)
        self.assertEqual(w.positions.rowCount(),15)


class FakeReply(QObject):
    finished=Signal()
    def __init__(self,status=200,data=b'[]'):
        super().__init__();self.status=status;self.data=data;self.aborted=False
    def attribute(self,_):return self.status
    def error(self):return QNetworkReply.NetworkError.NoError
    def bytesAvailable(self):return len(self.data)
    def readAll(self):return QByteArray(self.data)
    def abort(self):self.aborted=True;self.finished.emit()


class FakeManager:
    def __init__(self,reply):self.reply=reply;self.calls=0
    def get(self,request):self.calls+=1;self.request=request;return self.reply


class GeocodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_request_privacy_and_google_order(self):
        from desktop.geocoding import search_request,maps_url
        request=search_request('\u200b Taipei Station \u3000',' temporary-test-key ')
        from PySide6.QtCore import QUrlQuery
        self.assertEqual(QUrlQuery(request.url()).queryItemValue('api_key'),'temporary-test-key')
        self.assertFalse(request.hasRawHeader('Authorization'))
        self.assertEqual(request.url().host(),'geocode.maps.co')
        self.assertIn('query=23.00000,120.20000',maps_url(23,120.2).toString())

    def test_candidates_adopt_only_coordinates_and_change_clears_results(self):
        from desktop.geocoding import GeocodeDialog
        reply=FakeReply(data=json.dumps([dict(lat='23',lon='120.2',display_name='公共地點')]).encode())
        manager=FakeManager(reply);d=GeocodeDialog(key='test-key',manager=manager)
        d.address.setText('公共地點');d.lookup();d.lookup();self.assertEqual(manager.calls,1)
        reply.finished.emit();self.assertEqual(d.list.count(),1);self.assertFalse(d.adopt.isEnabled())
        d.list.setCurrentRow(0);self.assertTrue(d.adopt.isEnabled())
        with patch('desktop.geocoding.QDesktopServices.openUrl',return_value=True) as opened:
            d.open_map();self.assertIn('23.00000,120.20000',opened.call_args.args[0].toString())
        d.use_selected();self.assertEqual(d.coordinates,(120.2,23))
        d.address.setText('不同地點');self.assertEqual(d.list.count(),0);self.assertFalse(d.map.isEnabled());d.deleteLater()

    def test_http_errors_timeout_cancel_and_bad_payload(self):
        from desktop.geocoding import GeocodeDialog,parse_results
        for status,expected in [(429,'限制'),(403,'key'),(503,'無法連線')]:
            reply=FakeReply(status);d=GeocodeDialog(key='key',manager=FakeManager(reply));d.address.setText('公共地點');d.lookup();reply.finished.emit()
            self.assertIn(expected,d.info.text());self.assertIsNone(d.coordinates);self.assertTrue(d.search.isEnabled());d.reject();d.deleteLater()
        reply=FakeReply();d=GeocodeDialog(key='key',manager=FakeManager(reply));d.address.setText('公共地點');d.lookup();d.timeout()
        self.assertTrue(reply.aborted);self.assertIn('逾時',d.info.text());d.deleteLater()
        reply=FakeReply();d=GeocodeDialog(key='key',manager=FakeManager(reply));d.address.setText('公共地點');d.lookup();d.reject()
        self.assertTrue(reply.aborted);self.assertIsNone(d.coordinates);d.deleteLater()
        for raw in [b'{}',b'not json',b'[{"lat":"nan","lon":"0","display_name":"x"}]']:
            with self.assertRaises(ValueError):parse_results(raw)

if __name__=='__main__':unittest.main()
