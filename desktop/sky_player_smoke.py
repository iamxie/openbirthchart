# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Synthetic, opt-in source/frozen playback checks, including restart without calculation."""
import time
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtCore import QTimer,QCoreApplication,QEvent
from PySide6.QtWidgets import QDialog
from common import dump
from .sky_history import SkyHistory

_fault_output=None


def verify_player(app,page,out,prefix='player'):
    # Preserve native-fault diagnostics through QApplication teardown in opt-in tests.
    import faulthandler
    global _fault_output
    if _fault_output is None:
        _fault_output=(out/'native-fault.log').open('w',encoding='utf-8')
        faulthandler.enable(_fault_output)
    before=page.orb_provider()
    result=page.result
    with patch('desktop.timeline._positions',side_effect=AssertionError('Playback recomputed positions')), \
         patch('desktop.model.ChartEngine.calculate',side_effect=AssertionError('Playback recomputed chart')), \
         patch('desktop.timeline_ui.calculate_timeline',side_effect=AssertionError('History recomputed timeline')):
        page.load_history(result.history_id)
        assert before==page.orb_provider()
        page.show_player();player=page.player
        if player is None:raise AssertionError('Missing player')
        for _ in range(4):app.processEvents()
        player.grab().save(str(out/f'{prefix}-start.png'))
        assert player.index==0 and len(player.view.icons)==10
        identities=[id(i) for i in player.view.icons]
        # Drive an actual Qt event loop; report observed cadence, not a promised FPS.
        timings=[]
        original=player.show_frame
        def record(index):
            original(index);timings.append((index,time.perf_counter()))
        player.show_frame=record
        runs=[]
        speeds=[]
        for rate in range(30,121,15):
            player.buttons[4].click();assert player.rate==rate;speeds.append(rate)
        assert not player.buttons[4].isEnabled()
        player.buttons[3].click();assert player.rate==0
        player.buttons[3].click();assert player.rate==120
        player.seek(50);player.buttons[1].click();assert player.rate==-30
        player.buttons[4].click();assert player.rate==120
        player.pause();player.grab().save(str(out/f'{prefix}-speed-cap.png'))
        for rate,start in ((15,0),(30,50),(120,0),(-30,150)):
            player.seek(start);timings.clear();began=time.perf_counter()
            player.play(rate);QTest.qWait(1600);player.pause();elapsed=time.perf_counter()-began
            assert len(timings)>5
            direction=1 if rate>0 else -1
            assert [i for i,t in timings]==list(range(start+direction,player.index+direction,direction))
            runs.append(dict(target_fps=rate,frames=len(timings),elapsed=elapsed,
                             observed_fps=len(timings)/elapsed,ticks=timings.copy()))
        assert identities==[id(i) for i in player.view.icons]
        assert all(a>=2 and b>=2 for a,b,_ in player.view.visible_aspects)
        player.seek(player.reader.count-1);assert player.index==player.reader.count-1
        assert player.reader.frame(player.index)[0]==result.end
        player.grab().save(str(out/f'{prefix}-end.png'))
        player.resize(600,540);app.processEvents();player.grab().save(str(out/f'{prefix}-small.png'))
        player.seek(100);player.play(30);QTest.qWait(100);page.close_player()
        assert player.closed and not player.timer.isActive()
        dump(out/f'{prefix}-runtime.json',dict(runs=runs,retained_items=True,no_ephemeris=True,
             speed_steps=speeds,speed_cap=120,pause_resume=True,reverse_to_forward=True,
             last_endpoint=result.end,frames=result.samples,closed_timer=True))
        verify_motion_styles(app,out,prefix)


def verify_motion_styles(app,out,prefix):
    """Explicitly synthetic motion changes exercise all badge states in the EXE."""
    import numpy as np
    from .timeline import TimelineInput,TimelineResult
    from .sky_player import SkyPlayer,RETRO_TEXT
    from .model import BODIES
    path=out/'motion-styles.sqlite';history=SkyHistory(path)
    request=TimelineInput('2026-11-01T00:00','2026-11-01T00:20')
    start,end,_=request.resolve();stamps=[start.timestamp()+i*600 for i in range(3)]
    data=np.zeros((3,10,2));data[:,:,0]=np.arange(10)*30;data[:,:,1]=1
    data[1,[2,6,8],1]=-1;data[2,:,1]=-1
    run=history.begin(request,3);history.append(run,0,stamps,data)
    history.complete(run,TimelineResult(request,stamps[0],stamps[-1],3,[],0,[]))
    player=SkyPlayer(path,history.load(run));player.show();app.processEvents()
    try:
        identities=[id(item) for item in player.view.icons]
        bounds=[item.sceneBoundingRect() for item in player.view.icons]
        for frame,active in ((0,()),(1,(2,6,8)),(2,tuple(range(2,10))),(1,(2,6,8)),(0,())):
            player.seek(frame);app.processEvents()
            assert player.retrograde_summary.active==active
            for i,item in enumerate(player.view.icons):
                assert item.retrograde==(i in active)
                assert item.text.font().bold()==(i in active)
                assert item.text.brush().color().name()==(RETRO_TEXT if i in active else BODIES[i][3])
                assert item.sceneBoundingRect()==bounds[i]
            player.grab().save(str(out/f'{prefix}-synthetic-motion-{frame}.png'))
        player.seek(2);player.resize(600,540);app.processEvents()
        rects,_=player.retrograde_summary.badge_rects(player.retrograde_summary.names)
        assert all(r.right()<=player.retrograde_summary.width() and r.bottom()<=player.retrograde_summary.height() for r in rects)
        for i,item in enumerate(player.view.icons):
            for other in player.view.icons[i+1:]:assert not item.sceneBoundingRect().intersects(other.sceneBoundingRect())
        assert identities==[id(item) for item in player.view.icons]
        player.grab().save(str(out/f'{prefix}-synthetic-motion-small.png'))
        dump(out/f'{prefix}-motion-styles.json',dict(synthetic=True,states=[0,3,8,3,0],
            stable_geometry=True,retained_items=True,small_badges_fit=True,small_labels_separated=True))
    finally:
        # This extra test dialog has no parent and no app.exec() ownership cycle.
        # Dispose it while its Python graphics subclasses and QApplication are alive.
        player.close();player.deleteLater()
        QCoreApplication.sendPostedEvents(player,QEvent.Type.DeferredDelete)
        app.processEvents()


def run_replay_smoke(app,window,out,guard):
    window.mode_tabs.setCurrentIndex(1);page=window.timeline_page
    rows=SkyHistory(page.history_path).list_complete()
    if not rows:raise AssertionError('No persisted history for restart test')
    page.result=SkyHistory(page.history_path).load(rows[0][0])
    verify_player(app,page,out,'restart-player')
    def capture_history():
        dialog=next(w for w in page.findChildren(QDialog) if w.isVisible())
        dialog.grab().save(str(out/'history-list.png'));dialog.reject()
    QTimer.singleShot(100,capture_history);page.open_history()
    if guard.events:raise AssertionError(guard.events)
    window.close()
    print('Persisted playback restart verification passed.',flush=True)
    return 0
