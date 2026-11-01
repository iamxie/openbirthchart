# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Unsupported leap seconds retain input and never reach chart calculation."""
import copy
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.model import BirthInput,ChartEngine,resolve_local,ASPECTS
from desktop.errors import UserError,AmbiguousTimeError
from desktop.leap_seconds import leap_anchors
from desktop.storage import ProfileStore,validate_profile
from desktop.i18n import error_text,install_language
from desktop.window import MainWindow
from PySide6.QtWidgets import QApplication,QMessageBox


def payload(birth):
    return dict(schema=1,input=asdict(birth),custom_orbs=False,orb_values={str(a):v for a,_,v,_,_ in ASPECTS})


class LeapInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.engine=ChartEngine()
        cls.birth=BirthInput(local_iso='2016-12-31T23:59:60',zone='UTC')

    def tearDown(self):install_language(self.app,'zh-TW')

    def assert_unsupported(self,birth):
        original=asdict(birth)
        with self.assertRaises(UserError) as caught:resolve_local(birth)
        self.assertIn('目前不支援閏秒',caught.exception.source)
        self.assertEqual(asdict(birth),original)
        return caught.exception

    def test_all_27_known_insertions_in_six_zones(self):
        anchors=leap_anchors();self.assertEqual(len(anchors),27)
        self.assertNotIn(datetime(1971,12,31,23,59,59,tzinfo=timezone.utc),anchors)
        for instant in sorted(anchors):
            for zone in ('UTC','Asia/Taipei','America/New_York','Asia/Kolkata','Asia/Kathmandu','Pacific/Chatham'):
                local=instant.astimezone(ZoneInfo(zone))
                birth=replace(self.birth,local_iso=local.strftime('%Y-%m-%dT%H:%M:')+'60',zone=zone,fold=local.fold)
                with self.subTest(utc=str(instant),zone=zone):self.assert_unsupported(birth)

    def test_invalid_or_unannounced_sixty_is_not_called_valid(self):
        for iso,zone in [('2016-12-30T23:59:60','UTC'),('2016-12-31T23:58:60','UTC'),
            ('2016-12-31T23:59:60','Asia/Taipei'),('1971-12-31T23:59:60','UTC'),
            ('2027-12-31T23:59:60','UTC')]:
            birth=replace(self.birth,local_iso=iso,zone=zone)
            with self.subTest(iso=iso,zone=zone),self.assertRaises(UserError) as caught:resolve_local(birth)
            self.assertIn('無法依指定時區',caught.exception.source);self.assertEqual(birth.local_iso,iso)
        for iso in ('2016-12-31T24:59:60','2016-12-31T23:61:60','2016-02-30T23:59:60','2016-12-31T23:59:61'):
            with self.assertRaises(ValueError) as caught:resolve_local(replace(self.birth,local_iso=iso))
            self.assertNotIn('目前不支援閏秒',str(caught.exception))

    def test_fold_gaps_and_explicit_offset_keep_existing_rules(self):
        ambiguous=replace(self.birth,local_iso='2016-11-06T01:30:60',zone='America/New_York')
        with self.assertRaises(AmbiguousTimeError):resolve_local(ambiguous)
        for fold in (0,1):
            with self.assertRaisesRegex(UserError,'無法依指定時區'):resolve_local(replace(ambiguous,fold=fold))
        for iso,zone in [('2016-03-13T02:30:60','America/New_York'),('2011-12-30T12:00:60','Pacific/Apia')]:
            with self.assertRaisesRegex(UserError,'不存在'):resolve_local(replace(self.birth,local_iso=iso,zone=zone))
        with self.assertRaisesRegex(UserError,'時區另外選擇'):resolve_local(replace(self.birth,local_iso='2016-12-31T23:59:60Z'))

    def test_manual_dst_and_fractional_second_do_not_normalize_input(self):
        self.assert_unsupported(replace(self.birth,local_iso='2017-01-01T00:59:60',manual_dst=True,dst_enabled=True,dst_minutes=60))
        self.assert_unsupported(replace(self.birth,local_iso='2016-12-31T22:59:60',manual_dst=True,dst_enabled=True,dst_minutes=-60))
        self.assert_unsupported(replace(self.birth,manual_dst=True,dst_enabled=False))
        self.assert_unsupported(replace(self.birth,local_iso='2016-12-31T23:59:60.5'))
        with self.assertRaisesRegex(UserError,'無法依指定時區'):
            resolve_local(replace(self.birth,manual_dst=True,dst_enabled=True,dst_minutes=60))

    def test_neighboring_seconds_keep_normal_exact_utc(self):
        for iso,utc in [('2017-01-01T07:59:59','2016-12-31T23:59:59+00:00'),('2017-01-01T08:00:00','2017-01-01T00:00:00+00:00')]:
            birth=replace(self.birth,zone='Asia/Taipei',local_iso=iso)
            with patch('desktop.leap_seconds.leap_anchors',side_effect=AssertionError('ordinary input must not load table')):
                self.assertEqual(resolve_local(birth)['utc'].isoformat(),utc)

    def test_engine_worker_and_profile_refuse_before_computation_or_storage(self):
        from desktop.window import Calculation
        before=payload(self.birth);frozen=copy.deepcopy(before)
        with patch.object(self.engine,'times') as times,patch.object(self.engine.e,'houses_armc') as houses:
            with self.assertRaisesRegex(UserError,'目前不支援閏秒'):self.engine.calculate(self.birth)
            worker=Calculation(self.birth,None,self.engine);success=[];failure=[]
            worker.succeeded.connect(success.append);worker.failed.connect(failure.append);worker.run()
            self.assertFalse(success);self.assertEqual(len(failure),1);times.assert_not_called();houses.assert_not_called()
        with self.assertRaisesRegex(UserError,'目前不支援閏秒'):validate_profile(before)
        with tempfile.TemporaryDirectory() as tmp:
            store=ProfileStore(Path(tmp)/'unused.sqlite')
            with self.assertRaisesRegex(UserError,'目前不支援閏秒'):store.save(before)
            self.assertFalse(store.path.exists())
        self.assertEqual(before,frozen)

    def test_ui_both_languages_preserves_raw_fields_and_disables_export(self):
        for lang,valid,invalid in [('zh-TW','目前不支援閏秒','無法依指定時區'),
            ('en-US','Leap-second input is not currently supported','cannot be confirmed')]:
            install_language(self.app,lang)
            with tempfile.TemporaryDirectory() as tmp:
                window=MainWindow(auto_start=False,store=ProfileStore(Path(tmp)/'unused.sqlite'),prompt_unsaved=False)
                try:
                    window.restore_profile(payload(replace(self.birth,zone='Asia/Taipei',local_iso='2017-01-01T07:59:59')))
                    window.time.setText('07:59:60');window.refresh_time()
                    self.assertIn(valid,window.time_info.text());self.assertEqual(window.input().local_iso,'2017-01-01T07:59:60')
                    with patch('desktop.window.Calculation') as worker,patch.object(QMessageBox,'warning') as warning:
                        window.calculate();worker.assert_not_called();self.assertIn(valid,warning.call_args.args[2])
                    self.assertEqual(window.time.text(),'07:59:60');self.assertFalse(window.export_ready());self.assertFalse(window.export_button.isEnabled())
                    window.time.setText('07:58:60');window.refresh_time();self.assertIn(invalid,window.time_info.text())
                    self.assertEqual(window.time.text(),'07:58:60')
                finally:window.close()

    def test_corrupt_table_cannot_be_used_as_confirmation(self):
        leap_anchors.cache_clear()
        try:
            with patch('desktop.leap_seconds.sha',return_value='bad'),self.assertRaisesRegex(UserError,'資料損壞'):
                resolve_local(self.birth)
        finally:leap_anchors.cache_clear()

    def test_boundary_harness_accepts_only_the_specific_new_refusal(self):
        from boundary_latitude_baselines import calculate_case
        suite=json.loads((ROOT/'regression/boundary-v2/product/actual/cases.json').read_text(encoding='utf-8'))
        case=next(c for c in suite['cases'] if c['id']=='edge-utc-leap-second-input')
        group=next(g for g in suite['groups'] if g['id']==case['group_id'])
        row=calculate_case(self.engine,'product',case,group)
        self.assertEqual(row['status'],'UserError');self.assertEqual(row['outcome_kind'],'expected_error')
        self.assertEqual(case['expected'],'ValueError')
        with patch.object(self.engine,'calculate',side_effect=UserError('unrelated failure')):
            self.assertEqual(calculate_case(self.engine,'product',case,group)['outcome_kind'],'unexpected_error')


if __name__=='__main__':unittest.main()
