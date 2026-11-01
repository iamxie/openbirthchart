# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Prepare all pinned desktop data without downloading the Swiss test data."""
from common import ROOT,read,sha
from prepare_data import fetch
from prepare_time_data import main as prepare_time
from prepare_desktop_data import main as prepare_desktop

def main():
    for item in read(ROOT/'data-sources.lock.json')['files']:
        if not item['path'].startswith('data/core/'):continue
        fetch(item['url'],ROOT/item['path'])
        if sha(ROOT/item['path'])!=item['sha256']:raise ValueError('Core data hash mismatch: '+item['path'])
    prepare_time();prepare_desktop()
    for name in ('down.svg','up.svg','check.svg'):
        if not (ROOT/'data/desktop/theme'/name).is_file():raise ValueError('Missing source theme asset: '+name)
    print('All desktop runtime data ready; Swiss reference data not required.')

if __name__=='__main__':main()
