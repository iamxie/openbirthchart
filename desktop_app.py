# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Run from source or a frozen desktop bundle. --smoke-output renders offscreen."""
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke-output',type=Path);parser.add_argument('--language',choices=['zh-TW','en-US'])
    parser.add_argument('--smoke-fixture',type=Path,help='Synthetic profile JSON; requires --smoke-output')
    parser.add_argument('--timeline-smoke',action='store_true',help='Run isolated timeline UI/process verification; requires --smoke-output')
    parser.add_argument('--timeline-replay-smoke',action='store_true',help='Replay completed history from --smoke-output without calculation')
    args=parser.parse_args()
    if args.smoke_fixture and not args.smoke_output:parser.error('--smoke-fixture requires --smoke-output')
    if args.timeline_smoke and not args.smoke_output:parser.error('--timeline-smoke requires --smoke-output')
    if args.timeline_replay_smoke and not args.smoke_output:parser.error('--timeline-replay-smoke requires --smoke-output')
    if args.smoke_output:os.environ['QT_QPA_PLATFORM']='offscreen'
    from guard import RuntimeGuard
    guard=RuntimeGuard();guard.install()
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QFont
    from PySide6.QtCore import QCoreApplication, QEvent
    from desktop.window import MainWindow
    from desktop.storage import ProfileStore
    app=QApplication(sys.argv[:1]);app.setApplicationName('Open BirthChart');app.setOrganizationName('Open BirthChart')
    from common import ROOT as data_root
    font_id=QFontDatabase.addApplicationFont(str(data_root/'data/desktop/NotoSansTC.ttf'))
    if font_id<0:raise RuntimeError('Unable to load bundled Traditional Chinese font')
    app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0],10))
    test_store=ProfileStore()
    if args.smoke_output:
        args.smoke_output.mkdir(parents=True,exist_ok=True)
        test_store=ProfileStore(args.smoke_output/'data.sqlite')
    from desktop.i18n import install_language
    try:preferred=test_store.load_ui_language()
    except Exception:preferred='zh-TW'
    install_language(app,args.language or preferred)
    window=MainWindow(auto_start=not bool(args.smoke_output),store=test_store,
                      prompt_unsaved=not bool(args.smoke_output));window.show()
    if args.timeline_smoke:
        from desktop.timeline_smoke import run_timeline_smoke
        return run_timeline_smoke(app,window,args.smoke_output,guard)
    if args.timeline_replay_smoke:
        from desktop.sky_player_smoke import run_replay_smoke
        return run_replay_smoke(app,window,args.smoke_output,guard)
    if args.smoke_output:
        from desktop.model import ChartEngine
        from desktop.chart import export_chart
        from common import dump
        out=args.smoke_output;out.mkdir(parents=True,exist_ok=True)
        window.resize(1440,900);app.processEvents();window.grab().save(str(out/'blank.png'))
        from dataclasses import asdict
        from desktop.model import BirthInput,ASPECTS,APP_VERSION
        fixture=dict(schema=1,input=asdict(BirthInput(name='示範姓名',gender='女',longitude=120.22582)),
            custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS},app_version=APP_VERSION)
        if args.smoke_fixture:
            import json
            fixture=json.loads(args.smoke_fixture.read_text(encoding='utf-8'))
        window.restore_profile(fixture)
        profile=window.profile_payload();first_id=test_store.save(profile)
        other_gender='男' if profile['input']['gender']=='女' else '女'
        second=dict(profile,input=dict(profile['input'],gender=other_gender));second_id=test_store.save(second)
        reopened=ProfileStore(test_store.path)
        if first_id==second_id or reopened.load(first_id)!=profile or reopened.load(second_id)!=second:
            raise RuntimeError('Profile database roundtrip failed')
        window.restore_profile(reopened.load(first_id),first_id)
        chart=ChartEngine().calculate(window.input(),window.orbs());window.apply_chart(chart)
        # Allow deferred layout/word-wrap passes before recording the first frame.
        for _ in range(4):app.processEvents()
        if not window.grab().save(str(out/'desktop.png')):raise RuntimeError('Window capture failed')
        export_chart(chart,out/'chart.png');export_chart(chart,out/'chart.svg','svg')
        from desktop.report import export_html,available_templates
        export_html(chart,out/'report.html')
        report_languages=[]
        for template,label in available_templates():
            export_html(chart,out/('report-'+template.name+'.html'),template_dir=template)
            report_languages.append(template.name)
        window.tabs.setCurrentIndex(3);app.processEvents()
        if not window.grab().save(str(out/'matrix.png')):raise RuntimeError('Matrix capture failed')
        window.advanced_toggle.setChecked(True)
        app.processEvents()
        from PySide6.QtWidgets import QScrollArea
        window.form_scroll.ensureWidgetVisible(window.minor);app.processEvents()
        if not window.grab().save(str(out/'settings.png')):raise RuntimeError('Settings capture failed')
        dump(out/'chart.json',chart)
        loaded=[n for n in sys.modules if n.split('.')[0] in ('swisseph','pysweph','pyswisseph')]
        dump(out/'runtime.json',dict(ui_language=args.language or preferred,guard_events=guard.events,loaded_swiss=loaded,frozen=getattr(sys,'frozen',False),
                                   database_roundtrip=True,distinct_same_name_records=True,
                                   report_languages=report_languages))
        if guard.events or loaded:raise RuntimeError('Unexpected dependency or network attempt')
        # The offscreen check never enters app.exec(). Explicitly process deferred
        # widget destruction before QApplication is released on Windows.
        window.close();window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        app.processEvents()
        print('Desktop render and offline calculation passed.');return 0
    return app.exec()

if __name__=='__main__':
    # PyInstaller must dispatch spawned workers before argparse/Qt startup.
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        sys.exit(main())
    except Exception:
        import traceback
        if '--smoke-output' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--smoke-output')+1]);out.mkdir(parents=True,exist_ok=True)
            (out/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
            sys.exit(1)
        raise
