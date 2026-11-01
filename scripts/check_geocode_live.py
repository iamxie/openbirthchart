# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""One opt-in public-place lookup. No address, key, or response is written to disk."""
import os,sys
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'scripts')]
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from desktop.geocoding import GeocodeDialog
app=QApplication([]);dialog=GeocodeDialog(key=os.environ.pop('OBC_GEOCODE_TEST_KEY',''))
dialog.address.setText('臺北車站 台灣');dialog.lookup()
timer=QTimer()
def done():
    if dialog.reply is None:
        print('Live lookup:', 'PASS' if dialog.results else 'UNAVAILABLE', 'candidates:',len(dialog.results))
        if not dialog.results:print(dialog.info.text())
        success=bool(dialog.results);dialog.key.clear();dialog.address.clear();dialog.results=[];app.exit(0 if success else 2)
timer.timeout.connect(done);timer.start(100);sys.exit(app.exec())
