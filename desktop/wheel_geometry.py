# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Presentation coordinates; never replace the astronomical longitude/latitude.

The house view linearly maps the *effective* continuous house position into
the corresponding cusp sector. It is a house diagram, not a sky projection.
Legacy captures without the explicit option retain their old longitude view.
"""
import math
from .model import house_direction


def house_view(chart):
    return chart['input'].get('house_latitude',False)


def wheel_points(chart):
    """Return separate drawing records, including undefined-house markers.

    Undefined points have no house anchor. They remain visible as open markers
    at their real longitude on the outer edge, never inside an invented house.
    """
    spatial=house_view(chart);cusps=chart['cusps'];direction=house_direction(cusps)
    records=[]
    for point in chart['points']:
        house=point['house'];lon=point['lon'];position=None
        if spatial and house is not None:
            position=chart['house_positions'][str(point['id'])]['position']
            if not math.isfinite(position) or not 1<=position<13 or math.floor(position)!=house:
                raise ValueError('Inconsistent house coordinate in chart')
            start=cusps[house-1];width=direction*(cusps[house%12]-start)%360
            lon=(start+direction*width*(position-house))%360
        records.append(dict(point,plot_lon=lon,house_position=position,
                            plot_radius=275 if house is not None else 365))
    return records
