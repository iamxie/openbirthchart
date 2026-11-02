# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Run every desktop test module in its own process to isolate Qt lifetimes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results/desktop'/('tests-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    modules=sorted((ROOT/'tests').glob('test_desktop*.py'))
    if not modules:raise RuntimeError('No desktop test modules found')
    results=[]
    for path in modules:
        started=time.perf_counter()
        try:
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',path.name,'-v'],
                                cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            output=proc.stdout;code=proc.returncode
        except subprocess.TimeoutExpired as exc:
            output=(exc.stdout or b'')+b'\nTest module timed out after 300 seconds.\n';code=-1
        (args.output/(path.stem+'.log')).write_bytes(output)
        match=re.search(rb'Ran (\d+) tests?',output)
        row=dict(module=path.name,exit_code=code,tests=int(match[1]) if match else 0,wall_seconds=time.perf_counter()-started)
        results.append(row);print(json.dumps(row),flush=True)
        if code or not row['tests']:print(output.decode('utf-8','replace'),flush=True)
    passed=all(row['exit_code']==0 and row['tests']>0 for row in results)
    summary=dict(status='passed' if passed else 'failed',tests=sum(row['tests'] for row in results),modules=results)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(f"{summary['tests']} desktop tests; {summary['status']}. Logs: {args.output}",flush=True)
    return 0 if passed else 1


if __name__=='__main__':sys.exit(main())
