# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
# Build natively on each target OS. Only the offline application data is included.
from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root=Path(SPECPATH)
sys.path[:0]=[str(root),str(root/'scripts')]
from desktop.model import APP_VERSION
# Qt uses Windows' ICU forwarding DLL. Do not collect an unrelated ICU from
# another application's PATH (for example Poppler's versioned ICU ABI).
if sys.platform=='win32':
    win=Path(os.environ['SystemRoot'])
    os.environ['PATH']=os.pathsep.join([str(Path(sys.executable).parent),str(win/'System32'),str(win)])
datas=[]
for folder in ['data/core','data/time','data/desktop','config','templates/report','translations','docs']:
    datas.append((str(root/folder),folder))
for name in ['data-sources.lock.json','time-data-sources.lock.json','desktop-data-sources.lock.json','LICENSE','NOTICE.md','THIRD_PARTY_DESKTOP.md']:
    datas.append((str(root/name),'.'))
for package in ['libephemeris','skyfield','skyfield_data','tzdata','erfa']:
    datas+=collect_data_files(package)
for package in ['libephemeris','skyfield','tzdata','PySide6-Essentials','numpy','pyerfa']:
    datas+=copy_metadata(package)
hidden=collect_submodules('libephemeris')+collect_submodules('tzdata')
a=Analysis([str(root/'desktop_app.py')],pathex=[str(root),str(root/'scripts')],
    binaries=[],datas=datas,hiddenimports=hidden,
    excludes=['swisseph','pyswisseph','pysweph','kerykeion','pytest','IPython','matplotlib'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='OpenBirthChart',debug=False,
        bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='OpenBirthChart-'+APP_VERSION)
if sys.platform=='darwin':
    app=BUNDLE(coll,name='OpenBirthChart.app',bundle_identifier='org.openbirthchart.desktop')
