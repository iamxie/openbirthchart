# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Provision a pinned Astropy redistribution of IERS data; no calculation downloads."""
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile
from common import ROOT, read, dump, sha
from prepare_data import fetch

VERSION = '0.2026.10.19.0.52.1'
URL = 'https://files.pythonhosted.org/packages/13/00/b3f595b34b339e4c3a9f8f622ee7e2a6f3b85a9af9b69789aecf3ef18752/astropy_iers_data-0.2026.10.19.0.52.1-py3-none-any.whl'
HASH = '14665720aa481c7b97dfd104d7218b38ed7e2ba30a70ff53a5c26a0e14d4025c'

def main():
    path=ROOT/'data/time/astropy_iers_data.whl'
    artifact=fetch(URL,path)
    if artifact['sha256'] != HASH: raise RuntimeError('Data wheel hash mismatch')
    lock_path=ROOT/'time-data-sources.lock.json'
    previous=read(lock_path) if lock_path.exists() else None
    files=[]
    with ZipFile(BytesIO(path.read_bytes())) as archive:
        for name in ('finals2000A.all','Leap_Second.dat','ReadMe.finals2000A'):
            member='astropy_iers_data/data/'+name
            destination=ROOT/'data/time'/name
            content=archive.read(member)
            if destination.exists() and destination.read_bytes()!=content:
                raise RuntimeError(f'Refusing to replace different data: {destination}')
            destination.write_bytes(content)
            files.append(dict(path=destination.relative_to(ROOT).as_posix(),sha256=sha(destination),bytes=len(content)))
    manifest=dict(version=VERSION,wheel=artifact,files=files,
        captured_utc=datetime.now(timezone.utc).isoformat(),
        source='Astropy maintained redistribution of IERS finals2000A and Leap_Second.dat; official direct downloads unavailable during this run.',
        upstream_eop='https://datacenter.iers.org/data/9/finals2000A.all',
        upstream_leaps='https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat')
    if previous:
        if previous['files']!=files or previous['wheel']!=artifact: raise RuntimeError('Pinned time data changed')
    else: dump(lock_path,manifest)
    print('Pinned IERS data verified:',VERSION)

if __name__=='__main__': main()
