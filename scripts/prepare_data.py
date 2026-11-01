# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Provision reference data explicitly. Never called by the offline benchmark."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import urllib.request
import ssl
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data-sources.lock.json'

def fetch(url: str, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print(f'Downloading {url}', flush=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'ephemeris-validation/0.1'})
        partial = path.with_suffix(path.suffix + '.part')
        try:
            with urllib.request.urlopen(req, timeout=180) as response, partial.open('wb') as out:
                while block := response.read(1024 * 1024):
                    out.write(block)
        except urllib.error.URLError as exc:
            if not isinstance(exc.reason, ssl.SSLCertVerificationError) or __import__('os').name != 'nt':
                raise
            # Windows uses its own trusted certificate store. Never disable HTTPS verification.
            print('Retrying with Windows certificate store.', flush=True)
            quote = lambda s: "'" + str(s).replace("'", "''") + "'"
            command = "$ErrorActionPreference='Stop'; Invoke-WebRequest -Uri " + quote(url) + ' -OutFile ' + quote(partial)
            subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],check=True)
        partial.replace(path)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': path.relative_to(ROOT).as_posix(), 'url': url,
            'bytes': path.stat().st_size, 'sha256': digest}

def main():
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        for item in manifest['files']:
            found = fetch(item['url'], ROOT / item['path'])
            if found['sha256'] != item['sha256']:
                raise RuntimeError(f'Hash mismatch: {item["path"]}')
        print('Existing pinned data verified.')
        return
    req = urllib.request.Request('https://api.github.com/repos/aloistr/swisseph/commits/master',
                                 headers={'User-Agent': 'ephemeris-validation/0.1'})
    with urllib.request.urlopen(req, timeout=60) as response:
        swiss_commit = json.load(response)['sha']
    files = [fetch('https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp', ROOT / 'data/core/de440s.bsp')]
    for name in ('sepl_18.se1', 'semo_18.se1'):
        files.append(fetch(f'https://raw.githubusercontent.com/aloistr/swisseph/{swiss_commit}/ephe/{name}',
                           ROOT / 'data/reference' / name))
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(),
                'swiss_data_commit': swiss_commit, 'files': files,
                'note': 'Hashes identify downloaded artifacts, not an independent authenticity signature. Swiss files are comparison-only.'}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
