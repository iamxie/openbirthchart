# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Provision pinned upstream JPL-derived LEB data explicitly; no runtime network."""
from common import ROOT, read, sha
from prepare_data import fetch
from zipfile import ZipFile

def main():
    for item in read(ROOT/'desktop-data-sources.lock.json')['files']:
        destination=ROOT/item['path']
        if 'archive_member' in item:
            archive=ROOT/'.cache/downloads'/('astronomicon-'+item['archive_sha256']+'.zip')
            if not destination.exists():
                fetch(item['url'],archive)
                if sha(archive)!=item['archive_sha256']:raise ValueError('Astronomicon archive hash mismatch')
                with ZipFile(archive) as bundle:data=bundle.read(item['archive_member'])
                from hashlib import sha256
                if sha256(data).hexdigest()!=item['sha256']:raise ValueError('Astronomicon member hash mismatch')
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(data)
        else:
            fetch(item['url'],destination)
        if sha(ROOT/item['path']) != item['sha256']:
            raise ValueError('Desktop data hash mismatch: '+item['path'])
    print('Pinned desktop data verified.')

if __name__=='__main__': main()
