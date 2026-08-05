# -*- coding: utf-8 -*-
"""Verification suite: compare this engine against published values and analytic truth.

The same function feeds both the test suite and the "how do I know this is right"
section of the report, so the numbers shown to a reader are the numbers that were
actually just computed -- never transcribed by hand.
"""
import numpy as np

from . import sources
from .ephem import circumstances
from .terrain import horizon_fine, sea_horizon_dip, elev_fine


def check_greatest_eclipse():
    """NASA's point of greatest eclipse: duration and time."""
    r = sources.REFERENCE_GREATEST
    c = circumstances(r['lat'], r['lon'], 0.0)
    return dict(
        name='Punto de máximo eclipse (NASA)',
        detail=f"{r['lat']:.4f}, {r['lon']:.4f}",
        items=[
            dict(what='duración de la totalidad', ours=c['duration_s'],
                 published=r['duration_s'], unit='s', tol=r['tolerance_s'],
                 ok=abs(c['duration_s'] - r['duration_s']) <= r['tolerance_s']),
            dict(what='instante del máximo', ours=c['max_utc'][11:19],
                 published=r['utc'][11:19], unit='UTC',
                 tol=r['tolerance_time_s'],
                 ok=abs(_secs(c['max_utc'][11:19]) - _secs(r['utc'][11:19]))
                 <= r['tolerance_time_s']),
        ],
        source=r['source'])


def _secs(hms):
    h, m, s = hms.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def check_cities():
    """IGN city circumstances. Sun altitude is the tight check; duration is loose
    because the published figure depends where in the municipality you stand."""
    out = []
    for city in sources.REFERENCE_CITIES:
        c = circumstances(city['lat'], city['lon'], city['elev'])
        alt_mid = (c['c2_alt_app'] + c['c3_alt_app']) / 2 if c['total'] \
            else c['max_alt_app']
        out.append(dict(
            name=city['name'], detail='IGN',
            items=[
                dict(what='duración', ours=round(c['duration_s'], 1),
                     published=city['duration_s'], unit='s', tol=8.0,
                     ok=abs(c['duration_s'] - city['duration_s']) <= 8.0),
                dict(what='altura del Sol', ours=round(alt_mid, 1),
                     published=city['sun_alt_deg'], unit='°', tol=0.6,
                     ok=abs(alt_mid - city['sun_alt_deg']) <= 0.6),
            ],
            source=city['source']))
    return out


def check_edge():
    """Northern-edge towns, against an independently published duration."""
    out = []
    for e in sources.REFERENCE_EDGE:
        c = circumstances(e['lat'], e['lon'], e['elev'])
        items = [dict(what='duración', ours=round(c['duration_s'], 1),
                      published=e['duration_s'], unit='s', tol=e['tolerance_s'],
                      ok=(c['total'] and
                          abs(c['duration_s'] - e['duration_s']) <= e['tolerance_s']))]
        # La altura del Sol es la comprobación que aprieta: la duración arrastra el
        # sesgo conocido del convenio de radio lunar, la altura no.
        if e.get('sun_alt_deg') is not None:
            tol = e.get('tolerance_alt_deg', 0.5)
            items.append(dict(
                what='altura del Sol', ours=round(c['max_alt_app'], 2),
                published=e['sun_alt_deg'], unit='°', tol=tol,
                ok=abs(c['max_alt_app'] - e['sun_alt_deg']) <= tol))
        out.append(dict(name=e['name'], detail=e['source_label'], items=items,
                        source_url=e['source_url']))
    return out


def check_partial():
    """Places that must NOT be inside the umbra."""
    out = []
    for p in sources.REFERENCE_PARTIAL:
        c = circumstances(p['lat'], p['lon'], p['elev'])
        out.append(dict(
            name=p['name'], detail='debe quedar fuera de la totalidad',
            items=[dict(what='¿totalidad?', ours='no' if not c['total'] else 'sí',
                        published='no', unit='', tol=None, ok=not c['total']),
                   dict(what='obscuración', ours=round(c['obscuration'] * 100, 2),
                        published='<100', unit='%', tol=None,
                        ok=c['obscuration'] < 1.0)]))
    return out


def check_sea_horizon():
    """Looking out over open ocean, the skyline must equal the analytic dip.

    This exercises curvature, refraction and the near-field DEM handling at once:
    there is no terrain to hide behind, so any error shows up directly.
    """
    lat, lon, az = 43.1585, -9.2124, 275.0       # Cabo Vilán -> open Atlantic
    e = float(elev_fine(lat, lon)[0])
    ours = float(horizon_fine(lat, lon, [az], obs_elev=e)[0])
    theory = float(sea_horizon_dip(e))
    return dict(
        name='Horizonte marino (cabo Vilán)',
        detail=f'{e:.0f} m, azimut {az:.0f}°',
        items=[dict(what='depresión del horizonte', ours=round(ours, 3),
                    published=round(theory, 3), unit='°', tol=0.02,
                    ok=abs(ours - theory) <= 0.02)],
        source='analítico')


def check_known_summit():
    """From Zaragoza the skyline in the WNW is the Moncayo. Compare against the
    hand calculation h = (H - h0 - d^2(1-k)/2R) / d for the real summit."""
    lat, lon, elev = 41.6488, -0.8891, 228.0
    azs = np.arange(276.0, 286.01, 0.5)
    hz, bd, _ = horizon_fine(lat, lon, azs, obs_elev=elev, return_distance=True)
    i = int(np.argmax(hz))
    ours, dist = float(hz[i]), float(bd[i]) / 1000.0
    H, R, k = 2314.0, 6371000.0, 0.13         # Moncayo summit elevation
    d = dist * 1000.0
    hand = np.degrees(np.arctan2(H - (elev + 1.6) - d * d * (1 - k) / (2 * R), d))
    return dict(
        name='Cumbre conocida (Moncayo desde Zaragoza)',
        detail=f'detectada en azimut {azs[i]:.0f}° a {dist:.0f} km',
        items=[dict(what='altura aparente', ours=round(ours, 2),
                    published=round(float(hand), 2), unit='°', tol=0.25,
                    ok=abs(ours - float(hand)) <= 0.25),
               dict(what='distancia a la cumbre', ours=round(dist, 0),
                    published=80.0, unit='km', tol=6.0,
                    ok=abs(dist - 80.0) <= 6.0)],
        source='analítico + altitud publicada del Moncayo')


def check_path_width():
    """Perpendicular umbral width over Spain, from the bisected limits."""
    from .analysis import path_limits
    lim = path_limits()
    if lim is None:
        return None
    ref = sources.REFERENCE_PATH_WIDTH_KM
    return dict(
        name='Anchura de la sombra sobre España',
        detail='límites resueltos por bisección',
        items=[dict(what='anchura perpendicular', ours=round(lim['width_mean']),
                    published=ref['value'], unit='km', tol=ref['tolerance'],
                    ok=abs(lim['width_mean'] - ref['value']) <= ref['tolerance'])],
        source=ref['source'])


def run_all(include_width=True):
    """Every check. Returns a list of groups; each item carries ours/published/ok."""
    groups = [check_greatest_eclipse()]
    groups += check_cities()
    groups += check_edge()
    groups += check_partial()
    groups.append(check_sea_horizon())
    groups.append(check_known_summit())
    if include_width:
        w = check_path_width()
        if w:
            groups.append(w)
    return groups


def summarise(groups):
    items = [it for g in groups for it in g['items']]
    return dict(total=len(items), passed=sum(1 for i in items if i['ok']),
                failed=[i for i in items if not i['ok']])
