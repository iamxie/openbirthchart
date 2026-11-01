# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Ensure reference mode changes only placement input, and mode labels cannot lie."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch
from swiss_reference import calculate

class SwissSpy:
    FLG_JPLEPH=1;FLG_SWIEPH=2;FLG_MOSEPH=4;FLG_SPEED=256;FLG_EQUATORIAL=2048
    ECL_NUT=-1;SUN=0
    def __init__(self):self.calls=[]
    def calc(self,tt,body,flags):
        if body==self.ECL_NUT:return (23.4,23.4,0.,0.,0.,0.),flags
        return (body*11.+5.,2.5+body/100.,1.,.1,0.,0.),flags
    def sidtime0(self,*args):return 6.
    def houses_armc(self,*args):return list(range(0,360,30)),[0.,270.,90.,0.,0.,0.,0.,0.]
    def house_pos(self,*args):self.calls.append(args);return 7.25+args[3][1]/100.

class ModeTests(unittest.TestCase):
    def item(self):return dict(id='fixture',tt_jd=2451545.,ut1_jd=2451545.,utc='2000-01-01T12:00:00+00:00',
        input=dict(longitude=121.,latitude=23.,system='P'))

    def test_swiss_modes_retain_real_coordinates_and_pass_distinct_latitudes(self):
        actual=SwissSpy();zero=SwissSpy();item=self.item()
        item['input']['house_latitude']=True;a=calculate(actual,copy.deepcopy(item))
        item['input']['house_latitude']=False;b=calculate(zero,copy.deepcopy(item))
        self.assertEqual(len(actual.calls),20);self.assertEqual(len(zero.calls),20)
        self.assertTrue(any(call[3][1]!=0 for call in actual.calls))
        self.assertTrue(all(call[3][1]==0 for call in zero.calls))
        for p,q in zip(a['all_points'],b['all_points'],strict=True):
            self.assertEqual({k:v for k,v in p.items() if k!='house'},{k:v for k,v in q.items() if k!='house'})
            key=str(p['id'])
            self.assertEqual(a['house_positions'][key]['arguments'][4],p['lat'])
            self.assertEqual(b['house_positions'][key]['arguments'][4],0.)
        self.assertEqual(a['cusps'],b['cusps']);self.assertEqual(a['angles'],b['angles'])

    def test_legacy_swiss_input_defaults_to_actual(self):
        old=calculate(SwissSpy(),self.item());item=self.item();item['input']['house_latitude']=True
        new=calculate(SwissSpy(),item);new['input'].pop('house_latitude')
        self.assertEqual(old,new)

    def test_swiss_rejects_truthy_non_boolean(self):
        item=self.item();item['input']['house_latitude']='false'
        with self.assertRaises(ValueError):calculate(SwissSpy(),item)

    def test_mode_inventory_and_metadata_must_agree(self):
        suite=dict(baseline_suite='complete-v2',house_latitude_mode='actual',cases=[dict(input=dict(house_latitude=True))])
        self.assertEqual(batch.house_latitude_mode(suite),'actual')
        suite['cases'].append(dict(input=dict(house_latitude=False)))
        with self.assertRaises(ValueError):batch.house_latitude_mode(suite)
        suite['cases'].pop();suite['house_latitude_mode']='zero'
        with self.assertRaises(ValueError):batch.house_latitude_mode(suite)
        suite['house_latitude_mode']='actual';suite['cases'][0]['input'].clear()
        with self.assertRaises(ValueError):batch.house_latitude_mode(suite)

if __name__=='__main__':unittest.main()
