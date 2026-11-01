# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Explicit online provisioning only; never changes pinned source hashes."""
import gzip
from common import ROOT, read, sha
from prepare_data import fetch
from observation_data import verify_sources, load_records

def main():
    for item in read(ROOT/'observation-data-sources.lock.json')['files']:
        path=ROOT/item['path']
        if item['url']:
            fetch(item['url'],path)
        elif not path.exists():
            path.write_bytes(gzip.decompress((path.parent/item['derived_gzip']).read_bytes()))
        if sha(path) != item['sha256']:
            raise ValueError('Pinned source changed: '+item['path'])
    verify_sources()
    print('Verified',len(load_records()),'official CMC observations.')

if __name__=='__main__': main()
