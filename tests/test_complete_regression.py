# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Integrity and coverage tests for the separate complete-v1 batch harness."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as cr
import generate_complete_cases as gen

class IntegrityTests(unittest.TestCase):
    def test_signed_zero_is_not_equal(self):
        self.assertNotEqual(cr.exact(0.),cr.exact(-0.))
        self.assertNotEqual(cr.digest(cr.exact({'x':0.})),cr.digest(cr.exact({'x':-0.})))

    def test_only_timings_are_excluded(self):
        row={'id':'a','raw':{'house':4,'raw_position':3.9999999},'elapsed_seconds':1.}
        other=copy.deepcopy(row);other['elapsed_seconds']=9.
        self.assertEqual(cr.semantic(row),cr.semantic(other))
        other['raw']['raw_position']=4.
        self.assertNotEqual(cr.semantic(row),cr.semantic(other))

    def test_resume_rejects_tampered_or_wrong_environment_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.json';payload={'records':[{'id':'a'}]}
            cr.checkpoint(path,payload,'env1')
            self.assertEqual(cr.read_checkpoint(path,'env1',['a']),payload)
            with self.assertRaises(ValueError):cr.read_checkpoint(path,'env2',['a'])
            with self.assertRaises(ValueError):cr.read_checkpoint(path,'env1',['b'])
            wrapper=cr.read(path);wrapper['payload']['records'][0]['id']='b';cr.write(path,wrapper)
            with self.assertRaises(ValueError):cr.read_checkpoint(path,'env1',['b'])

    def test_checkpoint_cannot_replace_committed_result(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.json';cr.checkpoint(path,{'records':[{'id':'a'}]},'env')
            with self.assertRaises(FileExistsError):cr.checkpoint(path,{'records':[{'id':'b'}]},'env')
            self.assertEqual(cr.read_checkpoint(path,'env',['a'])['records'][0]['id'],'a')

    def test_checkpoint_integer_keys_survive_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.json'
            payload={'records':[{'id':'a','raw':{'orbs':{0:4.,30:1.,90:3.,180:3.},'negative_zero':-0.}}]}
            cr.checkpoint(path,payload,'env')
            loaded=cr.read_checkpoint(path,'env',['a'])
            self.assertEqual(cr.exact(payload),cr.exact(loaded))
            self.assertEqual(cr.digest(payload),cr.digest(loaded))

    def test_frozen_suite_coverage_and_corruption(self):
        suitepath=ROOT/'regression/complete-v1/cases.json'
        if not suitepath.exists():self.skipTest('Run fixture authoring first')
        suite=cr.read(suitepath);self.assertEqual(gen.validate(suite)['cases'],2016)
        broken=copy.deepcopy(suite);broken['groups'][1]['city']=broken['groups'][0]['city']
        with self.assertRaises(AssertionError):gen.validate(broken)
        broken=copy.deepcopy(suite);broken['cases'][1]['input']['system']=broken['cases'][0]['input']['system']
        with self.assertRaises(AssertionError):gen.validate(broken)
        broken=copy.deepcopy(suite);g=next(g for g in broken['groups'] if g['year']==2000 and g['month']==2)
        g['local_iso']=g['local_iso'].replace('-02-29','-02-28')
        with self.assertRaises(AssertionError):gen.validate(broken)

if __name__=='__main__':unittest.main()
