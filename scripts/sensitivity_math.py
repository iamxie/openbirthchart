# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Circular-angle helpers for finite time perturbations; not a linear rate model."""
import math
from common import angular_delta
from compare import stats

def describe(values):
    result=stats(values)
    result['min']=min(abs(v) for v in values)
    return result

def sampled_span(angles):
    """Unwrap adjacent samples (each adjacent step must be less than 180 deg)."""
    if not angles or not all(math.isfinite(a) for a in angles): raise ValueError('Invalid angle series')
    path=[0.0]
    for before,after in zip(angles,angles[1:]): path.append(path[-1]+angular_delta(after,before))
    return (max(path)-min(path))*3600

def find_crossing(angle_at,target,left,right,tolerance_seconds=.001):
    """Bracket a local increasing crossing, including 360->0, to a time tolerance."""
    a=angular_delta(angle_at(left),target);b=angular_delta(angle_at(right),target)
    if not (a<=0<=b and a<b): raise ValueError('No increasing crossing bracket')
    while right-left>tolerance_seconds:
        mid=(left+right)/2
        if angular_delta(angle_at(mid),target)<0: left=mid
        else: right=mid
    return (left+right)/2
