# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Persistence, display-only updates, and identity isolation contracts."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from dataclasses import asdict,replace
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'scripts')]
from desktop.model import APP_VERSION,ASPECTS,BirthInput,ChartEngine,display_chart
from desktop.storage import ProfileStore,default_database_path,validate_profile

def profile(**kwargs):
    return dict(schema=1,input=asdict(BirthInput(name='陳怡君',**kwargs)),custom_orbs=True,
                orb_values={str(a):o for a,_,o,_,_ in ASPECTS},app_version=APP_VERSION)

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=ProfileStore(Path(self.tmp.name)/'nested/data.sqlite')
    def tearDown(self):self.tmp.cleanup()

    def test_path_and_lazy_creation(self):
        self.assertEqual(default_database_path(),Path.home()/'Documents/openbirthchart/data.sqlite')
        self.assertFalse(self.store.path.exists())

    def test_same_name_distinct_ids_update_and_reopen(self):
        male=profile(gender='男');female=profile(gender='女')
        male['input']['name']="陳怡君'); DROP TABLE profiles; --"
        a=self.store.save(male);b=self.store.save(female);third=profile(gender='女',notes='另一位');c=self.store.save(third,confirm_duplicate=True)
        self.assertEqual(len({a,b,c}),3)
        male['orb_values']['72']=2.5;self.store.save(male,a)
        reopened=ProfileStore(self.store.path)
        self.assertEqual(reopened.load(a),validate_profile(male))
        self.assertEqual(reopened.load(b),validate_profile(female));self.assertEqual(len(reopened.list()),3)
        with self.assertRaisesRegex(ValueError,'不存在'):self.store.save(male,'missing-id')
        self.assertEqual(len(reopened.list()),3)

    def test_invalid_save_and_newer_schema_do_not_damage_data(self):
        good=profile();ident=self.store.save(good)
        bad=profile();bad['input']['longitude']=float('nan')
        with self.assertRaises(ValueError):self.store.save(bad,ident)
        self.assertEqual(self.store.load(ident),validate_profile(good))
        with closing(sqlite3.connect(self.store.path)) as conn:conn.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(ValueError,'較新版本'):self.store.list()
        with closing(sqlite3.connect(self.store.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM profiles').fetchone()[0],1)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],99)

class ProfileUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFontDatabase
        from common import ROOT
        cls.app=QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
        cls.engine=ChartEngine()
    def setUp(self):
        from desktop.window import MainWindow
        self.tmp=tempfile.TemporaryDirectory()
        self.w=MainWindow(auto_start=False,store=ProfileStore(Path(self.tmp.name)/'data.sqlite'),prompt_unsaved=False)
        self.w.engine=self.engine
        self.w.restore_profile(profile())
    def tearDown(self):
        from PySide6.QtCore import QCoreApplication,QEvent
        self.w.close();self.w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents();self.tmp.cleanup()

    def test_collapsed_order_and_display_without_recalculating(self):
        w=self.w
        self.assertTrue(w.advanced.isHidden())
        self.assertEqual(list(w.orbs()),[0,90,120,180,60,30,45,72,135,150])
        w.name.setText('陳怡君');w.gender.setCurrentText('女')
        w.apply_chart(self.engine.calculate(w.input(),w.orbs()))
        raw=w.chart['all_points'];cusps=w.chart['cusps']
        with patch.object(self.engine,'calculate',side_effect=AssertionError('Display should not calculate')):
            w.small.setChecked(False);w.minor.setChecked(False)
            self.assertEqual(len(w.chart['points']),15);self.assertEqual(w.matrix.table.rowCount(),12)
            self.assertTrue(all(not a['minor'] for a in w.chart['aspects']))
            w.apply_orbs({**w.orbs(),0:10})
            self.assertEqual(w.chart['orbs'][0],10)
            w.small.setChecked(True);self.assertEqual(len(w.chart['points']),20)
            w.gender.setCurrentText('男');self.assertEqual(w.chart['input']['gender'],'男')
            before=w.profile_payload();w.advanced_toggle.setChecked(True);w.advanced_toggle.setChecked(False)
            self.assertEqual(w.profile_payload(),before)
        self.assertIs(w.chart['all_points'],raw);self.assertIs(w.chart['cusps'],cusps)
        w.date.setDate(w.date.date().addDays(1));w.name.setText('另一人')
        self.assertFalse(w.export_button.isEnabled());self.assertEqual(w.chart['input']['name'],'陳怡君')

    def test_save_restore_manual_dst_hemispheres_and_custom_settings(self):
        w=self.w;p=profile(zone='America/New_York',local_iso='2024-11-03T01:30:00',fold=1,
            longitude=-74,latitude=40.7,manual_dst=True,dst_enabled=True,dst_minutes=30,gender='女',system='W')
        p['orb_values']['0']=7.5;p['custom_orbs']=False
        w.restore_profile(p);self.assertEqual(w.profile_payload(),validate_profile(p))
        self.assertTrue(w.save_record());ident=w.record_id
        w.name.setText('新名稱');self.assertTrue(w.is_dirty())
        w.restore_profile(w.store.load(ident),ident)
        self.assertFalse(w.is_dirty());self.assertEqual(w.profile_payload(),validate_profile(p))
        self.assertTrue(w.save_record());self.assertEqual(w.record_id,ident)
        self.assertEqual(len(w.store.list()),1)
        with patch.object(w,'confirm_discard',return_value=False):
            old=w.profile_payload();w.new_record();self.assertEqual(w.profile_payload(),old)
        with patch.object(w.store,'save',side_effect=OSError('disk full')),patch('desktop.window.QMessageBox.warning'):
            w.name.setText('未儲存');self.assertFalse(w.save_record());self.assertTrue(w.is_dirty())

    def test_matrix_agrees_with_aspect_list_and_identity_in_svg(self):
        from desktop.chart import export_chart
        import xml.etree.ElementTree as ET
        w=self.w;w.name.setText('陳怡君');w.gender.setCurrentText('男')
        w.apply_chart(self.engine.calculate(w.input(),w.orbs()))
        matrix=w.matrix;found=[]
        from PySide6.QtCore import Qt
        for i,a in enumerate(matrix.points):
            for j,b in enumerate(matrix.points):
                angle=matrix.table.item(i,j).data(Qt.ItemDataRole.UserRole)
                if i<=j:self.assertIsNone(angle)
                elif angle is not None:
                    found.append(frozenset((a['name'],b['name'])))
                    matrix.selected(i,j);self.assertIn('實際夾角',matrix.detail.text())
                    self.assertIn('容許',matrix.detail.text())
        self.assertEqual(set(found),set(matrix.lookup))
        self.assertEqual(len(found),len(w.chart['aspects']))
        dest=Path(self.tmp.name)/'identity.svg';export_chart(w.chart,dest,'svg')
        painted=''.join(''.join(n.itertext()) for n in ET.parse(dest).iter() if n.tag.endswith('}text'))
        self.assertIn('姓名：陳怡君',painted);self.assertIn('性別：男',painted)
        self.assertEqual({a:c for a,_,_,c,_ in ASPECTS if a in (60,90,120,180)},
                         {60:'#3434ed',90:'#ed3030',120:'#3434ed',180:'#ed3030'})

    def test_reload_current_record_after_saving_pending_edits(self):
        import time
        from PySide6.QtTest import QTest
        w=self.w;w.name.setText('原姓名');self.assertTrue(w.save_record());ident=w.record_id
        w.name.setText('修改後姓名');w.gender.setCurrentText('女')
        with patch.object(w,'confirm_discard',side_effect=w.save_record):
            self.assertTrue(w.load_record(ident))
        deadline=time.monotonic()+30
        while w.worker is not None and time.monotonic()<deadline:
            self.app.processEvents();QTest.qWait(20)
        self.assertIsNone(w.worker);self.assertFalse(w.is_dirty())
        self.assertEqual(w.chart['input']['name'],'修改後姓名')
        self.assertEqual(w.chart['input']['gender'],'女')
        self.assertEqual(w.store.load(ident)['input']['name'],'修改後姓名')

    def test_unsaved_dialog_cancel_discard_and_save(self):
        from PySide6.QtCore import QTimer
        w=self.w;w.prompt_unsaved=True;w.name.setText('未儲存姓名')
        def choose(label):
            def click():
                dialog=self.app.activeModalWidget()
                next(button for button in dialog.buttons() if button.text()==label).click()
            QTimer.singleShot(0,click)
        choose('取消');w.new_record();self.assertEqual(w.name.text(),'未儲存姓名')
        self.assertFalse(w.store.path.exists())
        choose('不儲存');w.new_record();self.assertEqual(w.name.text(),'');self.assertFalse(w.is_dirty())
        w.restore_profile(profile());w.name.setText('需要儲存');choose('儲存')
        self.assertTrue(w.confirm_discard());self.assertFalse(w.is_dirty())
        self.assertEqual(w.store.load(w.record_id)['input']['name'],'需要儲存')

if __name__=='__main__':unittest.main()
