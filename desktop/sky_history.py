# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Transactional, append-only sky runs. Connections belong to their caller thread."""
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import numpy as np

from .errors import UserError
from .model import APP_VERSION
from .timeline import TimelineInput, TimelineResult, SkyEvent, ZodiacSegment, result_dict

FORMAT = 1
CALCULATION = 'geocentric-tropical-tt-libephemeris-skyfield-v1'


class SkyHistory:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        try:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, FORMAT):
                raise UserError('不支援這份天象歷史的格式版本。')
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS runs(
                    id INTEGER PRIMARY KEY, created TEXT NOT NULL,
                    status TEXT NOT NULL, request TEXT NOT NULL,
                    app_version TEXT NOT NULL, calculation TEXT NOT NULL,
                    step INTEGER NOT NULL, expected INTEGER NOT NULL,
                    saved INTEGER NOT NULL DEFAULT 0, result TEXT);
                CREATE TABLE IF NOT EXISTS frames(
                    run_id INTEGER NOT NULL REFERENCES runs(id),
                    idx INTEGER NOT NULL, stamp REAL NOT NULL,
                    positions BLOB NOT NULL CHECK(length(positions)=160),
                    PRIMARY KEY(run_id,idx)) WITHOUT ROWID;
            ''')
            db.execute(f'PRAGMA user_version={FORMAT}')
            db.commit()
            return db
        except BaseException:
            db.close()
            raise

    def begin(self, request, expected, step=600):
        with closing(self.connect()) as db, db:
            return db.execute('''INSERT INTO runs(created,status,request,app_version,
                calculation,step,expected) VALUES(?,?,?,?,?,?,?)''',
                (datetime.now(timezone.utc).isoformat(), 'running', json.dumps(asdict(request)),
                 APP_VERSION, CALCULATION, step, expected)).lastrowid

    def append(self, run_id, offset, stamps, data):
        data = np.asarray(data, dtype='<f8')
        if data.shape != (len(stamps),10,2) or not np.isfinite(data).all():
            raise ValueError('Invalid sky frames')
        with closing(self.connect()) as db, db:
            row = db.execute('SELECT status,saved,expected FROM runs WHERE id=?',(run_id,)).fetchone()
            if not row or row[0]!='running' or offset!=row[1] or offset+len(data)>row[2]:
                raise ValueError('Noncontiguous or closed sky run')
            db.executemany('INSERT INTO frames VALUES(?,?,?,?)',
                ((run_id,offset+i,float(stamp),data[i].tobytes()) for i,stamp in enumerate(stamps)))
            db.execute('UPDATE runs SET saved=saved+? WHERE id=?',(len(data),run_id))

    def complete(self, run_id, result):
        with closing(self.connect()) as db, db:
            row = db.execute('SELECT saved,expected,status FROM runs WHERE id=?',(run_id,)).fetchone()
            if not row or row!=(result.samples,result.samples,'running'):
                raise ValueError('Incomplete sky history')
            db.execute("UPDATE runs SET status='complete',result=? WHERE id=?",
                       (json.dumps(result_dict(result),ensure_ascii=False),run_id))

    def abort(self, run_id, status):
        if status not in ('cancelled','failed'):raise ValueError(status)
        with closing(self.connect()) as db, db:
            db.execute("UPDATE runs SET status=? WHERE id=? AND status='running'",(status,run_id))

    def list_complete(self):
        if not self.path.exists():return []
        with closing(self.connect()) as db:
            return db.execute("SELECT id,created,request,saved FROM runs WHERE status='complete' ORDER BY id DESC").fetchall()

    def load(self, run_id):
        with closing(self.connect()) as db:
            row=db.execute("SELECT result FROM runs WHERE id=? AND status='complete'",(run_id,)).fetchone()
        if not row:raise UserError('這份天象歷史尚未完成，無法播放。')
        raw=json.loads(row[0]);raw['request']=TimelineInput(**{**raw['request'],'orbs':tuple(raw['request']['orbs'])})
        raw['events']=[SkyEvent(**e) for e in raw['events']]
        raw['zodiac_segments']=[ZodiacSegment(**s) for s in raw['zodiac_segments']]
        result=TimelineResult(**raw)
        # Local identity is not part of portable astronomical result JSON.
        result.history_id=run_id
        return result


class FrameReader:
    """One bounded block in memory, usable in either direction without ephemeris."""
    def __init__(self, path, run_id, block_size=512):
        self.db=SkyHistory(path).connect()
        row=self.db.execute("SELECT saved FROM runs WHERE id=? AND status='complete'",(run_id,)).fetchone()
        if not row:
            self.db.close()
            raise UserError('這份天象歷史尚未完成，無法播放。')
        self.run_id=run_id;self.count=row[0];self.block_size=block_size
        self.block_start=-1;self.block=[];self.reads=0

    def frame(self, index):
        if not 0<=index<self.count:raise IndexError(index)
        start=index//self.block_size*self.block_size
        if start!=self.block_start:
            rows=self.db.execute('SELECT idx,stamp,positions FROM frames WHERE run_id=? AND idx>=? AND idx<? ORDER BY idx',
                                 (self.run_id,start,min(self.count,start+self.block_size))).fetchall()
            if [r[0] for r in rows]!=list(range(start,min(self.count,start+self.block_size))):
                raise UserError('天象歷史資料不完整，請重新計算。')
            self.block=[(r[1],np.frombuffer(r[2],dtype='<f8').reshape(10,2)) for r in rows]
            self.block_start=start;self.reads+=1
        return self.block[index-start]

    def close(self):
        self.db.close()
