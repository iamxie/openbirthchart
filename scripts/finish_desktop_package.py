# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Attach readable sources, notices and file inventory to a local desktop build."""
from pathlib import Path
import importlib.metadata as md
import shutil
import sys
from common import ROOT, dump, sha
sys.path.insert(0,str(ROOT))
from desktop.model import APP_VERSION

def main():
    target=ROOT/'dist'/('OpenBirthChart-'+APP_VERSION)
    if not target.is_dir():raise ValueError('Build the desktop package first')
    from prepare_public_release import public_paths
    for name in ('README.md','README.en.md','DESKTOP_README.md','THIRD_PARTY_DESKTOP.md','LICENSING.md','LICENSE','NOTICE.md','third-party-sources.lock.json'):
        shutil.copy2(ROOT/name,target/name)
    for source in public_paths():
        relative=source.relative_to(ROOT);dest=target/'source'/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    shutil.copytree(ROOT/'docs',target/'docs',dirs_exist_ok=True)
    shutil.copytree(ROOT/'licenses',target/'licenses',dirs_exist_ok=True)
    licenses=target/'licenses';licenses.mkdir(exist_ok=True)
    for distribution in md.distributions():
        name=distribution.metadata['Name']
        for file in distribution.files or []:
            if ('licenses' in file.parts or file.name.lower().startswith(('license','copying','notice'))) and file.suffix.lower() not in ('.py','.pyc'):
                origin=Path(distribution.locate_file(file))
                if origin.is_file():
                    dest=licenses/name/Path(str(file)).name;dest.parent.mkdir(parents=True,exist_ok=True)
                    # Retain relative paths when a distribution has repeated names.
                    if dest.exists() and sha(dest)!=sha(origin):dest=licenses/name/str(file).replace('/','_')
                    shutil.copy2(origin,dest)
    shutil.copy2(ROOT/'data/desktop/OFL.txt',licenses/'NotoSansTC-OFL.txt')
    shutil.copy2(ROOT/'data/desktop/astronomicon/OFL-License.txt',licenses/'Astronomicon-OFL.txt')
    inventory=[dict(path=p.relative_to(target).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
               for p in sorted(target.rglob('*')) if p.is_file() and p.name!='package-manifest.json']
    if any(p['path'].lower().endswith('.se1') or 'swisseph' in p['path'].lower() for p in inventory):
        raise ValueError('Swiss artifact in desktop package')
    dump(target/'package-manifest.json',dict(version=APP_VERSION,platform='Windows x64',files=inventory))
    print('Portable package:',len(inventory),'files,',round(sum(i['bytes'] for i in inventory)/1024**2,1),'MiB')

if __name__=='__main__':main()
