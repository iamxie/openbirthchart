# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Compare both frozen suites and observe every actual wheel paint call."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import copy,csv,gzip,json,math,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from latitude_mode_audit import OUT,read,write,sha
from numerical_regression import exact
from desktop.chart import paint_wheel
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter,QPicture,QFontDatabase,QFont
from PySide6.QtWidgets import QApplication

def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return {r['id']:r for r in map(json.loads,f)}
def csv_file(path,values):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
class Trace:
    def __init__(self,p):self.p=p;self.rays=[];self.dots=[];self.open=[]
    def __getattr__(self,k):return getattr(self.p,k)
    def drawLine(self,*args):
        if len(args)==2 and isinstance(args[0],QPointF) and self.p.pen().color().name()=='#c5ceca':
            v=self.p.transform().map(args[1]);self.rays.append([v.x(),v.y()])
        return self.p.drawLine(*args)
    def drawEllipse(self,*args):
        if len(args)==3 and isinstance(args[0],QPointF):
            v=self.p.transform().map(args[0])
            if args[1:]==(2.5,2.5):self.dots.append([v.x(),v.y()])
            if args[1:]==(3.,3.):self.open.append([v.x(),v.y()])
        return self.p.drawEllipse(*args)
def angle(xy):return math.degrees(math.atan2(500-xy[1],xy[0]-500))%360
def sector(a,rays):
    near=[i for i,c in enumerate(rays) if abs(math.remainder(a-c,360))<1e-9]
    if near:return near[0]+1,True
    d=1 if abs(sum((rays[(i+1)%12]-rays[i])%360 for i in range(12))-360)<1e-7 else -1
    for i,c in enumerate(rays):
        if d*(a-c)%360<d*(rays[(i+1)%12]-c)%360:return i+1,False
    raise AssertionError('Unowned rendered point')
def trace_chart(chart):
    picture=QPicture();p=QPainter(picture);trace=Trace(p)
    try:paint_wheel(trace,chart)
    finally:p.end()
    assert len(trace.rays)==12 and len(trace.dots)==len(chart['points'])
    rays=list(map(angle,trace.rays));points=[]
    for body,xy in zip(chart['points'],trace.dots):
        h,boundary=sector(angle(xy),rays);r=math.hypot(xy[0]-500,xy[1]-500)
        if body['house'] is None:
            assert abs(r-365*.9)<1e-9;h=None
        else:assert abs(r-275*.9)<1e-9
        points.append(dict(id=body['id'],house=body['house'],drawn_house=h,boundary=boundary,xy=xy))
    return dict(cusps=trace.rays,points=points)

def main():
    app=QApplication([])
    font=QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
    app.setFont(QFont(QFontDatabase.applicationFontFamilies(font)[0],10))
    start=time.perf_counter();summaries={};changes=[];mismatches=[];case_rows=[]
    with gzip.open(OUT/'paint-traces.jsonl.gz','wt',encoding='utf-8') as trace_file:
        for suite in ('complete','legacy'):
            on=rows(OUT/'final'/f'{suite}-on/results.jsonl.gz');off=rows(OUT/'final'/f'{suite}-off/results.jsonl.gz')
            previous=rows(ROOT/'results/numerical/azimuth-patch-20261031'/('product' if suite=='complete' else 'legacy-product')/'results.jsonl.gz')
            assert on.keys()==off.keys()==previous.keys()
            stats=Counter();affected=set();by_system=Counter();by_body=Counter();undefined=Counter()
            for ident,rr in on.items():
                a=rr['raw'];b=off[ident]['raw'];old=previous[ident]
                assert rr['result']['status']==off[ident]['result']['status']==old['result']['status'],ident
                original=copy.deepcopy(a)
                if isinstance(original,dict) and 'input' in original:original['input'].pop('house_latitude')
                assert exact(original)==exact(old['raw']),(suite,ident,'default changed')
                stats['default_exact_matches_previous']+=1
                if not isinstance(a,dict) or 'all_points' not in a:
                    assert exact(a)==exact(b);continue
                stats['charts']+=1;chart_changes=0
                for key in ('cusps','asc','mc','times','utc','local','utc_offset','dst_minutes','aspects','day_chart','house_policy','house_notices'):
                    assert exact(a[key])==exact(b[key]),(ident,key)
                for p,q in zip(a['all_points'],b['all_points'],strict=True):
                    stats['points']+=1
                    assert exact({k:v for k,v in p.items() if k!='house'})==exact({k:v for k,v in q.items() if k!='house'}),(ident,p['id'])
                    aa=a['house_positions'][str(p['id'])];bb=b['house_positions'][str(p['id'])]
                    assert aa['arguments'][:4]==bb['arguments'][:4] and aa['arguments'][5:]==bb['arguments'][5:]
                    assert aa['arguments'][4]==p['lat'] and bb['arguments'][4]==0
                    if p['id'] in (-2,-3):
                        stats['axis_points']+=1;assert p['house']==q['house'];assert aa==bb
                    if p['lat']==0:assert p['house']==q['house']
                    if p['house'] is None:undefined['on']+=1
                    if q['house'] is None:undefined['off']+=1
                    if p['house']!=q['house']:
                        chart_changes+=1;affected.add(ident);by_system[a['input']['system']]+=1;by_body[p['name']]+=1
                        changes.append(dict(suite=suite,case=ident,system=a['input']['system'],local_time=a['input']['local_iso'],
                          zone=a['input']['zone'],geographic_longitude=a['input']['longitude'],geographic_latitude=a['input']['latitude'],
                          body_id=p['id'],body=p['name'],longitude=p['lon'],latitude=p['lat'],
                          house_on=p['house'],house_off=q['house'],position_on=aa['position'],position_off=bb['position'],
                          kind='undefined_to_defined' if p['house'] is None else 'defined_to_undefined' if q['house'] is None else 'house_change'))
                case_rows.append(dict(suite=suite,case=ident,system=a['input']['system'],changed_points=chart_changes))
                for mode,c in (('on',a),('off',b)):
                    tr=trace_chart(c);stats['painted_charts']+=1
                    for pt in tr['points']:
                        stats['painted_points']+=1
                        if pt['house'] is not None and pt['boundary']:stats['cusp_anchors']+=1
                        if pt['house']!=pt['drawn_house']:mismatches.append(dict(suite=suite,case=ident,mode=mode,**pt))
                    trace_file.write(json.dumps(dict(suite=suite,case=ident,mode=mode,**tr),ensure_ascii=False)+'\n')
                if stats['charts']%350==0:print(suite,stats['charts'],'charts verified',flush=True)
            summaries[suite]=dict(stats,changed_charts=len(affected),changed_points=sum(by_system.values()),
                                  by_system=dict(by_system),by_body=dict(by_body),undefined_points=dict(undefined))
    csv_file(OUT/'affected-planets.csv',changes);csv_file(OUT/'cases.csv',case_rows)
    write(OUT/'paint-mismatches.json',mismatches)
    write(OUT/'summary.json',dict(suites=summaries,paint_mismatches=len(mismatches),elapsed_seconds=time.perf_counter()-start))
    print(json.dumps(summaries,ensure_ascii=True),flush=True)
    assert not mismatches,f'{len(mismatches)} actual paint mismatches; see paint-mismatches.json'
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT)
    OUT=parser.parse_args().output.resolve();main()
