# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Meaningful fault injection and frozen suite coverage; no 1,200-chart work in unit tests."""
import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numerical_regression as nr

class NumericalRegressionTests(unittest.TestCase):
    def test_frozen_balancing(self):
        counts=nr.coverage(nr.read(nr.CASES))
        self.assertEqual(counts['balanced'],1200)
        self.assertEqual(len(counts['city_house_counts']),12)
        self.assertTrue(all(len(row)==14 for row in counts['city_house_counts'].values()))

    def test_reject_missing_and_duplicate_cases(self):
        suite=nr.read(nr.CASES)
        with self.assertRaises(ValueError): nr.coverage(dict(suite,cases=suite['cases'][1:]))
        with self.assertRaises(ValueError): nr.coverage(dict(suite,cases=suite['cases']+[suite['cases'][0]]))

    def test_same_one_city_one_house_cycle_is_rejected(self):
        suite=nr.read(nr.CASES)
        for i,c in enumerate(suite['cases'][:1200]): c['input']['system']=suite['house_systems'][i%14]
        with self.assertRaises(ValueError): nr.coverage(suite)

    def test_exact_roundtrip_and_one_ulp_detected(self):
        for a in [0.,-0.,1e-300,359.999999,2460000.5]:
            self.assertEqual(float.fromhex(nr.exact(a)['$float']).hex(),a.hex())
            self.assertEqual(len(list(nr.differences(nr.exact(a),nr.exact(math.nextafter(a,math.inf))))),1)

    def test_signed_zero_and_type_changes_detected(self):
        self.assertEqual(len(list(nr.differences(nr.exact(0.),nr.exact(-0.)))),1)
        self.assertEqual(len(list(nr.differences(True,1))),1)
        self.assertEqual(len(list(nr.differences(1,1.))),1)

    def test_nonfinite_rejected(self):
        for value in (math.nan,math.inf,-math.inf):
            with self.assertRaises(ValueError): nr.exact({'lon':value})

    def test_angular_wrap_has_small_diagnostic_but_still_differs(self):
        d=list(nr.differences(nr.exact({'lon':359.999}),nr.exact({'lon':.001})))[0]
        self.assertAlmostEqual(d['absolute_delta_arcseconds'],7.2)
        self.assertEqual(d['kind'],'float')

    def test_added_removed_discrete_fields_detected(self):
        d=list(nr.differences({'house':1,'retrograde':False},{'house':2,'added':True}))
        self.assertEqual({x['kind'] for x in d},{'added','removed','value'})

    def test_comparator_fails_real_value_and_outcome_changes(self):
        manifest=dict(cases_sha256='same',unexpected_outcomes=[],guard_events=[],contracts={},
                      coverage={'total':1},elapsed_seconds=1.)
        environment={'app_version':'0.6.0'}
        original={'a':{'raw':{'lon':1.},'result':nr.exact({'status':'ok','lon':1.})}}
        for mutation in [nr.exact({'status':'ok','lon':math.nextafter(1.,math.inf)}),
                         {'status':'UserError','error':{'type':'UserError'}}]:
            current={'a':{'raw':{'lon':2.},'result':mutation}}
            cm=copy.deepcopy(manifest)
            if mutation.get('status')=='UserError': cm['unexpected_outcomes']=['a']
            with tempfile.TemporaryDirectory() as tmp, patch.object(nr,'load_run',side_effect=[
                    (manifest,environment,original),(cm,environment,current)]):
                out=Path(tmp)/'report'
                self.assertEqual(nr.compare('baseline','run',out),1)
                self.assertGreater(nr.read(out/'summary.json')['changed_fields'],0)

    def test_new_app_version_alone_does_not_fail(self):
        manifest=dict(cases_sha256='same',unexpected_outcomes=[],guard_events=[],contracts={},
                      coverage={'total':1},elapsed_seconds=1.)
        records={'a':{'raw':{},'result':{'status':'ok'}}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(nr,'load_run',side_effect=[
                (manifest,{'app_version':'0.6.0'},records),(manifest,{'app_version':'0.7.0'},records)]):
            out=Path(tmp)/'report'
            self.assertEqual(nr.compare('baseline','run',out),0)
            self.assertTrue(nr.read(out/'summary.json')['environment_changed'])

    def test_changed_inputs_never_pass(self):
        manifest=dict(cases_sha256='same',unexpected_outcomes=[],guard_events=[],contracts={},
                      coverage={'total':1},elapsed_seconds=1.)
        records={'a':{'raw':{},'result':{'status':'ok'}}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(nr,'load_run',side_effect=[
                (manifest,{'app_version':'0.6.0'},records),
                (dict(manifest,cases_sha256='changed'),{'app_version':'0.6.0'},records)]):
            self.assertEqual(nr.compare('baseline','run',Path(tmp)/'report'),1)

    def test_seal_refuses_existing_directory(self):
        m=dict(unexpected_outcomes=[],guard_events=[])
        with tempfile.TemporaryDirectory() as tmp, patch.object(nr,'load_run',return_value=(m,{'app_version':'future'},{})):
            marker=Path(tmp)/'do-not-touch';marker.write_text('original')
            with self.assertRaises(FileExistsError): nr.seal('run',tmp,'future')
            self.assertEqual(marker.read_text(),'original')

    def test_seal_hash_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            files=['manifest.json','environment.json','cases.json','results.jsonl.gz','origin.json']
            for f in files: (out/f).write_text('original')
            nr.write(out/'SHA256SUMS.json',{f:nr.sha(out/f) for f in files})
            nr.verify_seal(out)
            (out/'results.jsonl.gz').write_text('changed')
            with self.assertRaises(ValueError): nr.verify_seal(out)

if __name__=='__main__': unittest.main()
