# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Native spawn smoke/benchmark using synthetic inputs and private output."""
import argparse
from datetime import datetime, timedelta
import multiprocessing
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--minutes', type=int, default=120)
    parser.add_argument('--workers', type=int)
    parser.add_argument('--start', default='2027-01-02T00:00')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cancel-after', type=float)
    args = parser.parse_args()
    from common import dump
    from desktop.timeline import TimelineInput, calculate_timeline, result_dict, Cancelled
    request = TimelineInput(args.start, (datetime.fromisoformat(args.start)+timedelta(minutes=args.minutes-1)).isoformat())
    began = time.monotonic()
    previous = [None, -1]
    updates = []

    def progress(p):
        if p['stage'] != previous[0] or p['done'] != previous[1]:
            print(p, flush=True)
            updates.append(p)
            previous[:] = p['stage'],p['done']

    try:
        result = calculate_timeline(request,progress,
            lambda: args.cancel_after is not None and time.monotonic()-began>=args.cancel_after,
            workers=args.workers)
        dump(args.output,result_dict(result))
    except Cancelled:
        dump(args.output,dict(cancelled=True,elapsed=time.monotonic()-began,children=len(multiprocessing.active_children())))
    dump(args.output.with_suffix('.progress.json'),updates)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
