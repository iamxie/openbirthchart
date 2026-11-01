# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Opt-in, isolated source/frozen timeline verification. Never loads profiles."""
import multiprocessing
import time
from PySide6.QtCore import QDate, QTime, QEventLoop, QTimer, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from common import dump
from .timeline import result_dict, worker_count


def run_timeline_smoke(app,window,out,guard):
    out.mkdir(parents=True,exist_ok=True)
    window.resize(1440,900)
    window.mode_tabs.setCurrentIndex(1)
    page=window.timeline_page
    page.start_date.setDate(QDate(2026,11,16))
    page.end_date.setDate(QDate(2026,11,17))
    page.start_time.setTime(QTime(0,0))
    page.end_time.setTime(QTime(15,59))
    page.zone.setCurrentText('Asia/Taipei')
    updates=[]

    def settle():
        for _ in range(4):app.processEvents()

    def capture(name):
        settle()
        if not window.grab().save(str(out/name)):
            raise RuntimeError('Timeline screenshot failed')

    def await_worker(cancel=False):
        loop=QEventLoop()
        deadline=QTimer()
        deadline.setSingleShot(True)
        expired=[]
        def timeout():
            expired.append(True)
            page.cancel()
        deadline.timeout.connect(timeout)
        # Explicit smoke mode exercises frozen spawning even on the 4-core VM,
        # whose ordinary user-facing policy correctly chooses one worker.
        from . import timeline_ui
        factory=timeline_ui.TimelineWorker
        timeline_ui.TimelineWorker=lambda request,parent:factory(request,parent,workers=2)
        try:page.start_calculation()
        finally:timeline_ui.TimelineWorker=factory
        if page.worker is None:raise RuntimeError(page.status.text())
        page.worker.progress.connect(lambda p:updates.append(p))
        page.worker.finished.connect(loop.quit)
        deadline.start(180000)
        if cancel:QTimer.singleShot(1000,page.cancel)
        else:QTimer.singleShot(1000,lambda:capture('running.png'))
        loop.exec()
        deadline.stop()
        settle()
        if expired:raise TimeoutError('Timeline smoke timed out')

    from .storage import ProfileStore
    from .settings import orb_dialog
    from .fields import DateField,TimeField
    assert isinstance(page.start_date,DateField) and isinstance(page.start_time,TimeField)
    original=window.orbs()
    window.apply_orbs({**original,0:5.})
    assert page.request().orbs[0]==5. and ProfileStore(window.store.path).load_orbs()[0]==5.
    dialog,_=orb_dialog(window.orbs(),window);dialog.show();settle()
    dialog.grab().save(str(out/'global-settings.png'));dialog.close()
    window.apply_orbs(original)
    capture('initial.png')
    await_worker()
    if page.result is None:raise RuntimeError(page.status.text())
    result=page.result
    if result.samples!=241:raise AssertionError('Wrong coarse sample count')
    if len(result.worker_pids)!=2:raise AssertionError('Smoke did not execute in two distinct workers')
    if any(e.a in (0,1) or e.b in (0,1) for e in result.events):raise AssertionError('Luminary event')
    dump(out/'timeline.json',result_dict(result))
    exact=next(e for e in result.events if e.exact)
    page.canvas.selection=exact
    page.show_event(exact)
    if len(result.zodiac_segments)<8:raise AssertionError('Missing zodiac coverage')
    detail=page.detail_dialog
    settle();detail.grab().save(str(out/'event-history.png'))
    detail.tabs.setCurrentIndex(1);settle();detail.grab().save(str(out/'overlapping-events.png'))
    detail.scope.setCurrentIndex(2);settle();detail.grab().save(str(out/'exact-concurrent.png'))
    from .timeline_report import export_timeline_html,TEMPLATES
    from .dialogs import ExportDialog
    export_dialog=ExportDialog(page,timeline=True,has_selection=True)
    export_dialog.show();settle();export_dialog.grab().save(str(out/'export-dialog.png'));export_dialog.close()
    for locale in ('zh-TW','en-US'):
        export_timeline_html(result,out/f'timeline-{locale}.html',TEMPLATES/locale)
        export_timeline_html(result,out/f'selected-{locale}.html',TEMPLATES/locale,exact)
    detail.hide()
    capture('complete.png')
    sizes=[]
    for width,height in ((1440,900),(1280,720),(1024,650),(920,540)):
        window.resize(width,height)
        settle()
        if page.settings_scroll.horizontalScrollBar().maximum():
            raise AssertionError('Timeline settings overflow')
        if page.chart_scroll.horizontalScrollBar().maximum():
            raise AssertionError('Timeline horizontal overflow')
        for button in (page.export_button,page.detail_button):
            if button.width()<button.fontMetrics().horizontalAdvance(button.text())+14:
                raise AssertionError('Clipped timeline action label')
        sizes.append([window.width(),window.height()])
        capture(f'{width}x{height}.png')
    page.aspect_filter.setCurrentIndex(1)
    page.zoom.setCurrentIndex(3)
    capture('filtered-day.png')
    await_worker(cancel=True)
    if page.result is not None:raise AssertionError('Cancelled job retained a result')
    if page.export_button.isEnabled():raise AssertionError('Stale export remained enabled')
    if multiprocessing.active_children():raise AssertionError('Timeline workers survived cancellation')
    capture('cancelled.png')
    import sys
    dump(out/'runtime.json',dict(frozen=getattr(sys,'frozen',False),samples=241,
        default_worker_policy=worker_count(),smoke_workers_override=2,worker_pids=result.worker_pids,
        events=len(result.events),exact=sum(len(e.exact) for e in result.events),
        cancelled=True,remaining_workers=len(multiprocessing.active_children()),sizes=sizes,
        guard_events=guard.events,loaded_swiss=[s for s in sys.modules if s.split('.')[0]=='swisseph']))
    dump(out/'progress.json',updates)
    if guard.events:raise AssertionError(guard.events)
    window.close();window.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()
    print('Timeline source/frozen verification passed.',flush=True)
    return 0
