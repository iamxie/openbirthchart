# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Verify the manifest and create a zip of the complete portable directory."""
from pathlib import Path
import sys,json,hashlib,zipfile
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'scripts')]
from desktop.model import APP_VERSION

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

target=root/'dist'/('OpenBirthChart-'+APP_VERSION)
manifest=json.loads((target/'package-manifest.json').read_text(encoding='utf-8'))
assert manifest['version']==APP_VERSION
assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file() and p.name!='package-manifest.json'}=={e['path'] for e in manifest['files']}
for entry in manifest['files']:
    p=target/entry['path']
    assert p.is_file() and p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'],entry['path']
    assert 'swisseph' not in entry['path'].lower() and not entry['path'].lower().endswith('.se1')
for asset in ('down.svg','up.svg','check.svg'):
    assert (target/'_internal/data/desktop/theme'/asset).is_file()
assert (target/'_internal/templates/report/zh-TW/style.css').read_text(encoding='utf-8')==(root/'templates/report/zh-TW/style.css').read_text(encoding='utf-8')
for language in ('zh-TW','en-US'):
    for filename in ('labels.json','report.html','style.css'):
        assert sha(target/'_internal/templates/report'/language/filename)==sha(root/'templates/report'/language/filename)
for filename in ('Astronomicon.ttf','OFL-License.txt'):
    assert sha(target/'_internal/data/desktop/astronomicon'/filename)==sha(root/'data/desktop/astronomicon'/filename)
assert sha(target/'licenses/Astronomicon-OFL.txt')==sha(root/'data/desktop/astronomicon/OFL-License.txt')
for name in ('desktop_en_US.ts','desktop_en_US.qm','README.md'):
    assert sha(target/'_internal/translations'/name)==sha(root/'translations'/name)
    assert sha(target/'source/translations'/name)==sha(root/'translations'/name)
assert (target/'_internal/PySide6/translations/qtbase_zh_TW.qm').is_file()
for filename in (p.relative_to(root/'docs') for p in (root/'docs').rglob('*') if p.is_file()):
    assert sha(target/'_internal/docs'/filename)==sha(root/'docs'/filename)
    assert sha(target/'source/docs'/filename)==sha(root/'docs'/filename)
    assert sha(target/'docs'/filename)==sha(root/'docs'/filename)
for path in (root/'desktop').glob('*.py'):
    assert sha(target/'source/desktop'/path.name)==sha(path)
assert sha(target/'_internal/data/time/Leap_Second.dat')==sha(root/'data/time/Leap_Second.dat')
assert sha(target/'_internal/time-data-sources.lock.json')==sha(root/'time-data-sources.lock.json')
archive=root/'dist'/f'OpenBirthChart-{APP_VERSION}-windows-x64.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(target.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(target.parent).as_posix())
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
result=dict(version=APP_VERSION,manifest_files=len(manifest['files']),all_hashes_verified=True,offline_azimuth_help_verified=True,
            all_docs_verified=True,desktop_sources_verified=True,leap_data_verified=True,
            no_swiss_artifacts=True,theme_assets_present=True,zip=str(archive),zip_bytes=archive.stat().st_size,zip_sha256=sha(archive))
(archive.with_suffix(archive.suffix+'.sha256')).write_text(result['zip_sha256']+'  '+archive.name+'\n',encoding='ascii')
(root/'results/desktop'/f'package-checks-{APP_VERSION}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
