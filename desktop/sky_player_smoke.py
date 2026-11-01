# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Synthetic, opt-in source/frozen playback checks, including restart without calculation."""
import time
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog
from common import dump
from .sky_history import SkyHistory


def verify_player(app,page,out,prefix='player'):
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
        for rate,start in ((15,0),(30,50),(-30,150)):
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
             last_endpoint=result.end,frames=result.samples,closed_timer=True))


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
