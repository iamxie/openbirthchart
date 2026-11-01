# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Deterministic cases; thresholds fixed before examining benchmark results."""
import calendar
from datetime import datetime, timezone
import random
from common import ROOT, dump

def jd(dt):
    return (dt - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400 + 2451545.0

def main():
    rng = random.Random(20261026)
    dates = [datetime(year, (month := rng.randint(1, 12)), rng.randint(1, calendar.monthrange(year, month)[1]),
                      rng.randrange(24), rng.randrange(60), tzinfo=timezone.utc) for year in range(1850, 2150)]
    dates += [datetime(y, m, 15, 12, tzinfo=timezone.utc) for y in (2024, 2025, 2026) for m in range(1, 13)]
    for value in ['1850-01-01T00:00:00', '2149-12-31T12:00:00', '1900-02-28T23:59:59',
                  '2000-02-29T12:00:00', '2000-01-01T12:00:00', '2024-03-20T03:06:00',
                  '2024-04-01T22:14:00', '2024-04-25T12:54:00', '2100-02-28T23:59:59']:
        dates.append(datetime.fromisoformat(value).replace(tzinfo=timezone.utc))
    epochs = [{'id': f'e{i:04d}', 'calendar_label': d.isoformat(), 'jd': jd(d)} for i, d in enumerate(sorted(set(dates)))]
    locations = [('Tainan', 22.9999, 120.2269), ('Greenwich', 51.4779, 0.0),
                 ('Sydney', -33.8688, 151.2093), ('Equator', 0.0, 0.0),
                 ('NearPolarN', 65.5, 25.0), ('NearPolarS', -65.5, -70.0)]
    house_cases = []
    for epoch in epochs[::25]:
        for location, lat, lon in locations:
            for system in ('P', 'K', 'O', 'E', 'W'):
                house_cases.append(dict(id=f'h{len(house_cases):04d}', epoch=epoch['id'], jd=epoch['jd'],
                                        location=location, lat=lat, lon=lon, system=system))
    charts = []
    for index, epoch in enumerate(epochs[::20]):
        location, lat, lon = locations[index % 4]
        charts.append(dict(id=f'c{index:03d}', iso=epoch['calendar_label'], lat=lat, lon=lon,
                           system=('P','A','W')[index % 3], location=location))
    dump(ROOT/'cases.json', {'schema': 1, 'seed': 20261026,
         'scope': 'Tropical, apparent geocentric; 1850-2149; Sun-Pluto; nodes exploratory; five house systems.',
         'thresholds': {'position_arcsec': 1.0, 'speed_arcsec_per_day': 1.0, 'house_arcsec': 1.0,
                        'distance_au': 1e-6, 'integration_arcsec': 1e-6},
         'threshold_note': 'Project acceptance targets, not vendor guarantees. Never changed to fit observations.',
         'epochs': epochs, 'houses': house_cases, 'charts': charts,
         'polar': [{'id': f'p{i}', 'jd':2451545.0, 'lat':lat, 'lon':18.95, 'system':system}
                   for i,(lat,system) in enumerate([(69.65,'P'),(-69.65,'P'),(69.65,'K'),(-69.65,'K')])]})
    print(f'{len(epochs)} epochs, {len(house_cases)} house cases, {len(charts)} Kerykeion charts')

if __name__ == '__main__': main()
