# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
from __future__ import annotations
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
BODIES = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Mean_Node', 'True_Node']
HOUSES = ['first_house', 'second_house', 'third_house', 'fourth_house', 'fifth_house', 'sixth_house',
          'seventh_house', 'eighth_house', 'ninth_house', 'tenth_house', 'eleventh_house', 'twelfth_house']

def configure_core():
    for key in list(os.environ):
        if key.startswith(('LIBEPHEMERIS_', 'KERYKEION_')):
            del os.environ[key]
    settings = dict(LIBEPHEMERIS_DATA_DIR=str(ROOT/'data/core'), LIBEPHEMERIS_EPHEMERIS='de440s.bsp',
        LIBEPHEMERIS_MODE='skyfield', LIBEPHEMERIS_NETWORK_POLICY='sealed',
        LIBEPHEMERIS_AUTO_SPK='0', LIBEPHEMERIS_PRECISION='base',
        LIBEPHEMERIS_CONFIG=str(ROOT/'config/isolated.toml'),
        LIBEPHEMERIS_DELTAT_MODEL='smh2016', LIBEPHEMERIS_IERS_DELTA_T='0',
        KERYKEION_BACKEND='libephemeris', KERYKEION_LEB_MODE='skyfield')
    os.environ.update(settings)
    return settings

def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def angular_delta(a, b):
    return (a - b + 180.0) % 360.0 - 180.0

def finite_vector(values, length):
    if len(values) != length or not all(math.isfinite(float(x)) for x in values):
        raise ValueError(f'Expected {length} finite values: {values}')
    return list(map(float, values))
