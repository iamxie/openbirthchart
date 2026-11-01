# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Axis identities, near-boundary ownership and the 39 archived failures."""
import copy,json,math,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.model import APP_VERSION,BirthInput,ChartEngine,axis_house_number,house_number

class AxisBoundaryTests(unittest.TestCase):
    def test_defined_axis_cusp_identity_across_zero_and_float_neighbors(self):
        for axis,systems,index in [('asc','PKCREOBUT',0),('mc','PKCROBUTX',9)]:
            for origin in (0.,17.25,359.99999999999994):
                cusps=[(origin+(i-index)*30)%360 for i in range(12)]
                original=cusps.copy();center=cusps[index]
                for lon in (center,math.nextafter(center,-math.inf),math.nextafter(center,math.inf),center-5e-11,center+5e-11):
                    for system in systems:
                        with self.subTest(axis=axis,system=system,origin=origin,lon=lon):
                            self.assertEqual(axis_house_number(lon,cusps,system,axis),index+1)
                            self.assertEqual(cusps,original)

    def test_nearby_distinct_positions_are_not_snapped(self):
        cusps=[float(i*30) for i in range(12)]
        for axis,system,index in [('asc','U',0),('mc','X',9)]:
            self.assertEqual(axis_house_number((cusps[index]-1e-8)%360,cusps,system,axis),(index-1)%12+1)
            self.assertEqual(axis_house_number((cusps[index]+1e-8)%360,cusps,system,axis),index+1)

    def test_axis_not_defined_as_that_cusp_keeps_interval_policy(self):
        cusps=[float(i*30) for i in range(12)]
        for system,axis,lon in [('W','asc',359.99999999999),('E','mc',269.99999999999),
                                ('M','mc',269.99999999999),('V','asc',359.99999999999),('X','asc',359.99999999999)]:
            self.assertEqual(axis_house_number(lon,cusps,system,axis),house_number(lon,cusps))
            self.assertNotEqual(axis_house_number(lon,cusps,system,axis),1 if axis=='asc' else 10)

    def test_residual_subtraction_gap_has_a_strict_interval_owner(self):
        cusps=[float(i*30) for i in range(12)]
        lon=math.nextafter(30.,-math.inf)
        # At some representable endpoints, modulo subtraction rounds away the gap.
        # Mock only the exhausted lookup; ownership must still be below cusp 2.
        with patch('desktop.model.house_number',return_value=None):
            self.assertEqual(axis_house_number(lon,cusps,'W','asc'),1)
            self.assertEqual(axis_house_number(30.,cusps,'W','asc'),2)

    def test_azimuth_delegates_unchanged_even_for_a_missing_result(self):
        cusps=[float(i*30) for i in range(12)]
        for direction in (1,-1):
            ring=[direction*x%360 for x in cusps]
            for axis in ('asc','mc'):
                for lon in (0.,math.nextafter(30.,0.),270.):
                    self.assertEqual(axis_house_number(lon,ring,'H',axis),house_number(lon,ring))
                with patch('desktop.model.house_number',return_value=None):
                    self.assertIsNone(axis_house_number(0.,ring,'H',axis))

    def test_invalid_axis_is_rejected(self):
        with self.assertRaises(ValueError):axis_house_number(0.,[i*30. for i in range(12)],'U','planet')

class ArchivedAxisCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numerical_regression as nr
        cls.fixtures=json.loads((ROOT/'tests/fixtures/axis-boundary-original.json').read_text(encoding='utf-8'))
        _,_,cls.old=nr.load_run(ROOT/'regression/baselines/0.6.1')
        cls.engine=ChartEngine()

    def test_archived_axis_helper_repairs_39_charts_without_redefining_production(self):
        self.assertEqual(len(self.fixtures),39);changes=0
        for fixture in self.fixtures:
            with self.subTest(case=fixture['id']):
                expected=copy.deepcopy(self.old[fixture['id']]['raw']);expected['version']=APP_VERSION
                for key in ('all_points','points'):
                    for p in expected[key]:
                        if p['name'] in fixture['changes']:
                            self.assertIn(p['id'],(-2,-3))
                            change=fixture['changes'][p['name']]
                            self.assertEqual(p['house'],change['before']);p['house']=change['after']
                            if key=='all_points':changes+=1
                actual=copy.deepcopy(self.old[fixture['id']]['raw']);actual['version']=APP_VERSION
                for key in ('all_points','points'):
                    for p in actual[key]:
                        if p['id'] in (-2,-3):
                            p['house']=axis_house_number(p['lon'],actual['cusps'],actual['input']['system'],
                                                        'asc' if p['id']==-2 else 'mc')
                # Use the exact-float JSON representation: archived tuples are
                # lists and integer mapping keys are strings, without value loss.
                import numerical_regression as nr
                self.assertEqual(nr.exact(actual),nr.exact(expected))
                self.assertTrue(all(p['house'] is not None for p in actual['all_points'] if p['id'] in (-2,-3)))
        self.assertEqual(changes,40)

    def test_all_101_azimuth_axis_assignments_remain_original(self):
        charts=[r['raw'] for r in self.old.values() if r['result']['status']=='ok' and isinstance(r['raw'],dict)
                and r['raw'].get('input',{}).get('system')=='H']
        self.assertEqual(len(charts),101)
        for chart in charts:
            for p in chart['all_points']:
                if p['id'] in (-2,-3):
                    self.assertEqual(axis_house_number(p['lon'],chart['cusps'],'H','asc' if p['id']==-2 else 'mc'),p['house'])

    def test_both_exports_show_current_spatial_axis_house_cells(self):
        import os,re
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFontDatabase
        from desktop.report import render_html,TEMPLATES
        app=QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
        for ident,zh,en,house in [('main-1968-12','上升點','Ascendant','1'),('main-1932-06','天頂','Midheaven','10')]:
            fixture=next(f for f in self.fixtures if f['id']==ident)
            chart=self.engine.calculate(BirthInput(**fixture['input']))
            house=str(next(p['house'] for p in chart['all_points'] if p['name']==zh))
            for lang,label in [('zh-TW',zh),('en-US',en)]:
                html=render_html(chart,template_dir=TEMPLATES/lang)
                rows=[re.findall(r'<td[^>]*>(.*?)</td>',r,re.S) for r in re.findall(r'<tr[^>]*>(.*?)</tr>',html,re.S)]
                row=next(r for r in rows if r and r[0]==label)
                self.assertIn(house,row)
        self.assertIsNotNone(app)

if __name__=='__main__':unittest.main()
