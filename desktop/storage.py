# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Local profiles. A name is a label, never a database key."""
from .errors import UserError
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from uuid import uuid4

from .model import APP_VERSION, ASPECTS, BirthInput, HOUSE_SYSTEMS, resolve_local, local_datetime
from .text import trim_text


class DuplicateProfile(UserError):
    def __init__(self, matches):
        super().__init__('已有相同姓名、性別、出生座標、日期時間及時區的檔案。請填寫備註以區分。')
        self.matches = matches


def identity_key(payload):
    b=payload['input']
    return (trim_text(b['name']),b['gender'],round(b['longitude']*100000),
            round(b['latitude']*100000),b['local_iso'],b['zone'])

def default_database_path():
    return Path.home()/'Documents'/'openbirthchart'/'data.sqlite'

def validate_profile(payload):
    if payload.get('schema')!=1:
        raise UserError('不支援這筆資料的格式版本。')
    values=dict(payload['input'])
    for key in ('name','notes','zone','local_iso','gender'):
        if key in values:values[key]=trim_text(values[key])
    birth=BirthInput(**values)
    if not isinstance(birth.name,str) or len(birth.name)>80 or any(ord(c)<32 for c in birth.name):
        raise UserError('姓名需為 80 字以內的單行文字。')
    if birth.gender not in ('男','女'):raise UserError('性別需為男或女。')
    if len(birth.notes)>2000:raise UserError('備註最多 2000 字。')
    if not math.isfinite(birth.longitude) or not -180<=birth.longitude<=180:raise UserError('經度超出範圍。')
    if not math.isfinite(birth.latitude) or not -89.99999<=birth.latitude<=89.99999:raise UserError('緯度超出範圍。')
    if birth.system not in HOUSE_SYSTEMS:raise UserError('不支援的分宮制。')
    wall=local_datetime(birth)
    if wall.tzinfo is not None or len(birth.local_iso)!=19:raise UserError('請完整填寫當地出生日期及時、分、秒。')
    if not datetime(1850,1,2)<=wall<=datetime(2149,12,30,23,59,59) or wall.microsecond:
        raise UserError('出生日期或時間超出支援範圍。')
    for value in (birth.small_bodies,birth.minor_aspects,birth.manual_dst,birth.dst_enabled,birth.house_latitude,payload['custom_orbs']):
        if type(value) is not bool:raise UserError('設定值需為勾選狀態。')
    if type(birth.dst_minutes) is not int or not -120<=birth.dst_minutes<=180:raise UserError('夏令分鐘數超出範圍。')
    resolved=resolve_local(birth)
    if not datetime(1850,1,2,tzinfo=timezone.utc)<=resolved['utc']<datetime(2149,12,31,tzinfo=timezone.utc):
        raise UserError('換算 UTC 後的日期超出支援範圍。')
    controls=payload['orb_values']
    if set(controls)!={str(a) for a,_,_,_,_ in ASPECTS}:raise UserError('相位設定不完整。')
    for value in controls.values():
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=15:
            raise UserError('相位容許度需在 0～15 度內。')
        if abs(value*10-round(value*10))>1e-8:raise UserError('相位容許度最多一位小數。')
    return dict(schema=1,input=asdict(birth),custom_orbs=payload['custom_orbs'],
                orb_values=dict(controls),app_version=payload.get('app_version',APP_VERSION))

class ProfileStore:
    def __init__(self,path=None):
        self.path=Path(path) if path is not None else default_database_path()

    def load_ui_language(self):
        if not self.path.exists():return 'zh-TW'
        with closing(self._connect()) as conn:
            row=conn.execute('SELECT value FROM app_settings WHERE name=?',('ui_language',)).fetchone()
        return row[0] if row and row[0] in ('zh-TW','en-US') else 'zh-TW'

    def save_ui_language(self,language):
        if language not in ('zh-TW','en-US'):raise ValueError('Unsupported interface language')
        with closing(self._connect()) as conn,conn:
            conn.execute('INSERT INTO app_settings(name,value) VALUES (?,?) '
                         'ON CONFLICT(name) DO UPDATE SET value=excluded.value',('ui_language',language))

    def _connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        connection=sqlite3.connect(self.path,timeout=5)
        try:
            version=connection.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1,2):raise UserError('資料庫來自較新版本，請更新程式再開啟。')
            with connection:
                connection.execute('CREATE TABLE IF NOT EXISTS profiles ('
                    'id TEXT PRIMARY KEY, name TEXT NOT NULL, gender TEXT NOT NULL, '
                    'local_iso TEXT NOT NULL, payload TEXT NOT NULL, '
                    'created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
                columns={row[1] for row in connection.execute('PRAGMA table_info(profiles)')}
                if 'notes_required' not in columns:
                    connection.execute('ALTER TABLE profiles ADD COLUMN notes_required INTEGER NOT NULL DEFAULT 0')
                connection.execute('CREATE TABLE IF NOT EXISTS app_settings ('
                    'name TEXT PRIMARY KEY, value TEXT NOT NULL)')
                connection.execute('PRAGMA user_version = 2')
            return connection
        except Exception:
            connection.close();raise

    def load_geocode_key(self):
        if not self.path.exists():return ''
        with closing(self._connect()) as conn:
            row=conn.execute('SELECT value FROM app_settings WHERE name=?',('geocode_api_key',)).fetchone()
        return row[0] if row else ''

    def save_geocode_key(self,key):
        key=trim_text(key)
        with closing(self._connect()) as conn,conn:
            if key:
                conn.execute('INSERT INTO app_settings(name,value) VALUES (?,?) '
                    'ON CONFLICT(name) DO UPDATE SET value=excluded.value',('geocode_api_key',key))
            else:
                conn.execute('DELETE FROM app_settings WHERE name=?',('geocode_api_key',))

    def save(self,payload,record_id=None,confirm_duplicate=False):
        payload=validate_profile(payload)
        if not payload['input']['name']:raise UserError('儲存前請填寫姓名。')
        birth=payload['input'];now=datetime.now(timezone.utc).isoformat()
        encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False)
        with closing(self._connect()) as conn,conn:
            conn.execute('BEGIN IMMEDIATE')
            old=None;required=False
            if record_id is not None:
                old=conn.execute('SELECT payload,notes_required FROM profiles WHERE id=?',(record_id,)).fetchone()
                if old is None:raise UserError('原紀錄已不存在，請重新載入清單確認。')
                required=bool(old[1])
            changed=old is None or identity_key(validate_profile(json.loads(old[0])))!=identity_key(payload)
            matches=[]
            if changed:
                for ident,raw in conn.execute('SELECT id,payload FROM profiles WHERE id != ?', (record_id or '',)):
                    candidate=validate_profile(json.loads(raw))
                    if identity_key(candidate)==identity_key(payload):
                        matches.append(dict(id=ident,**candidate['input']))
                if matches and (not birth['notes'] or not confirm_duplicate):raise DuplicateProfile(matches)
                required=required or bool(matches)
            if required and not birth['notes']:raise UserError('這筆檔案曾以備註區分重複資料，備註不能清空。')
            if record_id is None:
                record_id=str(uuid4())
                conn.execute('INSERT INTO profiles (id,name,gender,local_iso,payload,created_at,updated_at,notes_required) VALUES (?,?,?,?,?,?,?,?)',
                    (record_id,birth['name'],birth['gender'],birth['local_iso'],encoded,now,now,int(required)))
            else:
                conn.execute('UPDATE profiles SET name=?,gender=?,local_iso=?,payload=?,updated_at=?,notes_required=? WHERE id=?',
                    (birth['name'],birth['gender'],birth['local_iso'],encoded,now,int(required),record_id))
        return record_id

    def list(self):
        with closing(self._connect()) as conn:
            conn.row_factory=sqlite3.Row
            result=[]
            for row in conn.execute('SELECT id,name,gender,local_iso,updated_at,payload FROM profiles ORDER BY updated_at DESC,id'):
                item=dict(row);birth=validate_profile(json.loads(item.pop('payload')))['input']
                item.update(notes=birth['notes'],longitude=birth['longitude'],latitude=birth['latitude'],zone=birth['zone'])
                result.append(item)
            return result

    def load(self,record_id):
        with closing(self._connect()) as conn:
            row=conn.execute('SELECT payload FROM profiles WHERE id=?',(record_id,)).fetchone()
        if row is None:raise UserError('找不到這筆星盤。')
        return validate_profile(json.loads(row[0]))
