# -*- coding: utf-8 -*-
"""El análisis que comparten los dos informes: evaluar un sitio, buscar en un área,
puntuar una zona.

Todo el proyecto gira sobre un único número, el **margen libre**: cuántos grados
separan al Sol de la silueta real del terreno mientras el eclipse está en lo mejor.
Lo que hay aquí existe para calcular eso con honradez.
"""
import json
import numpy as np

from . import field, panorama
from .ephem import circumstances
from .terrain import (elev_at, elev_fine, horizon_fine, horizon_per_point)

# Muestreo de rayos de la pasada de ranking. 150 km bastan: para asomar por encima
# de 1° desde más lejos, el terreno tendría que pasar de 3 km, y eso no ocurre al
# oeste de la franja española.
RANK_DISTS = np.concatenate([np.arange(400.0, 25000.0, 180.0),
                             np.arange(25000.0, 150000.0, 800.0)])


def km(la1, lo1, la2, lo2):
    """Great-circle-ish distance in km; fine at these scales."""
    return np.hypot((np.asarray(la1) - la2) * 111.2,
                    (np.asarray(lo1) - lo2) * 111.32
                    * np.cos(np.radians((np.asarray(la1) + la2) / 2)))


def snap_to_peak(lat, lon, radius_km=1.0, n=21):
    """Se mueve a la celda de 30 m más alta que tenga cerca. Los geocodificadores
    colocan una cumbre con nombre a cientos de metros del sitio, o directamente en el
    valle de al lado."""
    dla = radius_km / 111.2
    dlo = radius_km / (111.32 * np.cos(np.radians(lat)))
    las = np.linspace(lat - dla, lat + dla, n)
    los = np.linspace(lon - dlo, lon + dlo, n)
    grid = np.array([[float(elev_fine(a, b)[0]) for b in los] for a in las])
    i, j = np.unravel_index(np.argmax(grid), grid.shape)
    return float(las[i]), float(los[j])


def evaluate(lat, lon, label=None, snap_km=0.0, with_svg=True):
    """Circunstancias exactas más la silueta a 30 m para un solo sitio."""
    if snap_km > 0:
        lat, lon = snap_to_peak(lat, lon, snap_km)

    p = panorama.build(lat, lon, name=label or '')
    c = p['circ']
    if c['total']:
        azs = np.arange(c['c2_az'] - 1.2, c['c3_az'] + 1.201, 0.1)
    else:
        azs = np.arange(c['max_az'] - 1.2, c['max_az'] + 1.201, 0.1)
    hz, bd, _ = horizon_fine(lat, lon, azs, obs_elev=p['obs_elev'],
                             return_distance=True)

    if c['total']:
        # El Sol tiene que librar el terreno durante TODA la totalidad, y va bajando,
        # así que se coge el peor de los dos contactos.
        clear = min(c['c2_alt_app'] - float(np.interp(c['c2_az'], azs, hz)),
                    c['c3_alt_app'] - float(np.interp(c['c3_az'], azs, hz)))
        alt_ref, az_ref = c['c3_alt_app'], c['c3_az']
    else:
        alt_ref, az_ref = c['max_alt_app'], c['max_az']
        clear = alt_ref - float(np.interp(az_ref, azs, hz))
    horizon = float(np.interp(az_ref, azs, hz))
    blocker = float(np.interp(az_ref, azs, bd)) / 1000.0

    su = p['set_utc']
    return dict(
        lat=lat, lon=lon, elev=round(p['obs_elev']), label=label,
        total=bool(c['total']), dur=round(c.get('duration_s', 0.0), 1),
        obsc=round(c['obscuration'] * 100, 2), mag=round(c['magnitude'], 4),
        alt=round(alt_ref, 2), az=round(az_ref, 2),
        alt_start=round(c['c2_alt_app'], 2) if c['total'] else round(alt_ref, 2),
        horizon=round(horizon, 2), clear=round(clear, 2),
        blocker_km=round(blocker, 1),
        max_local=_local(c['max_utc']),
        c2_local=_local(c['c2_utc']) if c['total'] else None,
        c3_local=_local(c['c3_utc']) if c['total'] else None,
        set_local=_local(su) if su else None,
        set_az=round(p['set_az'], 1) if p['set_az'] == p['set_az'] else None,
        svg=panorama.svg(p) if with_svg else None)


def _local(iso):
    """UTC ISO -> peninsular clock time (UTC+2 in August)."""
    return f'{(int(iso[11:13]) + 2) % 24:02d}:{iso[14:16]}:{iso[17:19]}'


def search_area(olat, olon, radius_km, min_clear=1.5, want=6, sep_km=None,
                overfetch=3):
    """Ordena candidatos en un disco alrededor de un punto. Devuelve pares
    (lat, lon), el mejor primero.

    Es sólo la pasada gruesa: quien llame tiene que recomprobar cada ganador con
    evaluate(), que usa la superficie real a 30 m. El mosaico de aquí agrupa por
    máximo a 185 m, que es lo conservador para las crestas pero no dice nada de
    árboles ni de edificios.
    """
    f = field.load()
    step_km = float(np.clip(radius_km / 55.0, 0.25, 1.5))
    dlat = step_km / 111.2
    dlon = step_km / (111.32 * np.cos(np.radians(olat)))
    n_la = int(radius_km / 111.2 / dlat) + 1
    n_lo = int(radius_km / (111.32 * np.cos(np.radians(olat))) / dlon) + 1
    LO, LA = np.meshgrid(olon + np.arange(-n_lo, n_lo + 1) * dlon,
                         olat + np.arange(-n_la, n_la + 1) * dlat)
    LA, LO = LA.ravel(), LO.ravel()
    inside = km(LA, LO, olat, olon) <= radius_km
    LA, LO = LA[inside], LO[inside]
    land = elev_at(LA, LO) >= 1.0
    LA, LO = LA[land], LO[land]
    if LA.size == 0:
        return [], 0, 0

    # La altura del OBSERVADOR tiene que salir de la superficie real a 30 m. Sacada
    # del mosaico agrupado por máximo, te subiría a la cresta que tienes delante.
    elev = elev_fine(LA, LO)
    dur = field.interp(f['dur'], LA, LO)
    mag = field.interp(f['mag'], LA, LO)

    clear = np.full(LA.size, np.inf)
    for a_key, z_key in (('a_c2', 'z_c2'), ('a_mx', 'z_mx'), ('a_c3', 'z_c3')):
        alt = field.interp(f[a_key], LA, LO)
        az = field.interp(f[z_key], LA, LO)
        clear = np.minimum(clear, alt - horizon_per_point(LA, LO, elev, az,
                                                          RANK_DISTS))
    ok = clear >= min_clear
    n_ok = int(ok.sum())
    if not n_ok:
        return [], LA.size, 0

    idx = np.where(ok)[0]
    score = (dur[idx] / 10.0 + np.minimum(clear[idx], 8.0)
             + (mag[idx] - 0.98) * 50.0)
    order = idx[np.argsort(-score)]
    sep = sep_km if sep_km else max(2.0, radius_km / 7.0)
    picks = []
    for i in order:
        if all(km(LA[i], LO[i], LA[j], LO[j]) > sep for j in picks):
            picks.append(i)
        if len(picks) >= want * overfetch:
            break
    return [(float(LA[i]), float(LO[i])) for i in picks], LA.size, n_ok


def zone_stats(clat, clon, half_km=9.0, n=13, threshold=2.0):
    """¿Un buen horizonte es propiedad del ÁREA, o de un píxel con suerte?

    Evalúa una rejilla a 30 m enteros y devuelve el reparto. Es el número que
    reordena los rankings ingenuos: un mirador espectacular rodeado de terreno
    tapado es peor apuesta que uno mediocre en un sitio que perdona.
    """
    c = circumstances(clat, clon, 0.0)
    if c['total']:
        azs = np.array([c['c2_az'], c['max_az'], c['c3_az']])
        alts = np.array([c['c2_alt_app'], c['max_alt_app'], c['c3_alt_app']])
    else:
        azs = np.array([c['max_az']])
        alts = np.array([c['max_alt_app']])

    dla = half_km / 111.2
    dlo = half_km / (111.32 * np.cos(np.radians(clat)))
    vals, best = [], (-99.0, None)
    for la in np.linspace(clat - dla, clat + dla, n):
        for lo in np.linspace(clon - dlo, clon + dlo, n):
            e = float(elev_fine(la, lo)[0])
            if e < 1.0:
                continue
            v = float(np.min(alts - horizon_fine(la, lo, azs, obs_elev=e)))
            vals.append(v)
            if v > best[0]:
                best = (v, (float(la), float(lo), e))
    if not vals:
        return None
    v = np.array(vals)
    return dict(n=int(v.size), worst=round(float(v.min()), 2),
                median=round(float(np.median(v)), 2),
                best=round(float(v.max()), 2),
                frac_ok=round(float((v >= threshold).mean()), 3),
                threshold=threshold, half_km=half_km,
                best_lat=round(best[1][0], 5), best_lon=round(best[1][1], 5),
                best_elev=round(best[1][2]))


def path_limits():
    """Límites umbrales norte y sur y anchura perpendicular, del fichero bisecado."""
    from .paths import LIMITS_JSON
    import os
    if not os.path.exists(LIMITS_JSON):
        return None
    with open(LIMITS_JSON) as fh:
        res = json.load(fh)
    lon = np.array([r['lon'] for r in res])
    n = np.array([r['north'] for r in res])
    s = np.array([r['south'] for r in res])
    c = np.array([r['centre'] for r in res])
    dlat = np.gradient(c) * 111.2
    dlon = np.gradient(lon) * 111.32 * np.cos(np.radians(c))
    width = (n - s) * 111.2 * np.abs(np.cos(np.arctan2(dlat, dlon)))
    over = (lon >= -7.5) & (lon <= 3.0)
    return dict(lon=lon, north=n, south=s, centre=c, width=width,
                width_min=float(width[over].min()), width_max=float(width[over].max()),
                width_mean=float(width[over].mean()))
