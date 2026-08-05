# -*- coding: utf-8 -*-
"""Precomputed recommendation points for one eclipse.

The insight that makes the site work without a backend: the answer to "where should I
go from X" does not depend on X. It is always the same set of good viewpoints; X and
the radius only decide which of them are close enough. So compute the viewpoints once,
ship them, and let the query be a filter.

This dataset is specific to ONE eclipse: the Sun's azimuth and altitude at every point
are baked into the clearances and into the drawn horizon.

Output (points.json):
  meta   - event, azimuth window, how the set was built
  points - one entry per recommended viewpoint, including a compact horizon profile so
           the browser can draw the panorama without shipping an SVG each.
"""
import json
import os
import pickle

import numpy as np

from . import events, gazetteer, obstacles
from .analysis import evaluate, km
from .ephem import circumstances, sun_track
from .panorama import AZ_LO, AZ_HI
from .paths import DATA_DIR, SCAN_PKL

# Prefer the magnitude-selected sweep: it reaches the deep-partial ground outside the
# path, so a town 100 km north of the shadow gets viewpoints instead of an empty list.
WIDE_PKL = os.path.join(DATA_DIR, 'scan_wide.pkl')
from .terrain import elev_fine, horizon_fine

# Horizon sampled across the plotted window; 0.25 deg is finer than the Sun's diameter.
AZ_STEP = 0.25
AZIMUTHS = np.arange(AZ_LO, AZ_HI + 1e-9, AZ_STEP)

MIN_CLEAR = 2.0        # a recommendation must have real margin, not just be positive
SEP_KM = 14.0          # spacing inside the path; ~1100 cells over the band
MAX_POINTS = 700


def select(scan_path=None, min_clear=MIN_CLEAR, sep_km=SEP_KM,
           sep_km_partial=25.0, max_points=2000, progress=None):
    """Pick the BEST viewpoint in each cell, rather than the globally top-scoring ones.

    Ranking globally looks sensible and is wrong: totality outscores everything, so the
    whole quota lands inside the path and a town 100 km outside it gets an empty
    result. Coverage is the requirement here, so the map is divided into cells and each
    cell contributes its own best spot.

    Cells are finer inside the path (where people will actually travel) and coarser
    outside it, which keeps the dataset small without leaving holes.
    """
    scan_path = scan_path or (WIDE_PKL if os.path.exists(WIDE_PKL) else SCAN_PKL)
    with open(scan_path, 'rb') as f:
        d = pickle.load(f)
    lat, lon, clear, dur = d['lat'], d['lon'], d['clear'], d['dur']
    alt = d['a_c3']

    ok = clear >= min_clear
    idx = np.where(ok)[0]
    score = (np.minimum(clear[idx], 8.0) + dur[idx] / 20.0
             + np.minimum(alt[idx], 12) * 0.5)

    best = {}
    for pos, i in enumerate(idx):
        total = dur[i] >= 1.0
        cell_km = sep_km if total else sep_km_partial
        c = cell_km / 111.2
        key = (bool(total), int(lat[i] / c),
               int(lon[i] / (c / np.cos(np.radians(lat[i])))))
        cur = best.get(key)
        if cur is None or score[pos] > cur[0]:
            best[key] = (score[pos], int(i))

    # Cap each category separately. A single global cap sorted by score is the bug
    # this function exists to avoid: totality always wins it, and the partial cells --
    # the ones a city outside the path depends on -- get truncated away.
    tot = sorted(((k, v) for k, v in best.items() if k[0]), key=lambda t: -t[1][0])
    par = sorted(((k, v) for k, v in best.items() if not k[0]), key=lambda t: -t[1][0])
    # No global cap: every cell that exists is a place someone might be standing.
    n_tot = min(len(tot), max_points)
    n_par = min(len(par), max_points)
    picks = [v[1] for _, v in tot[:n_tot]] + [v[1] for _, v in par[:n_par]]
    if progress:
        progress(len(picks), len(picks), f'seleccionando ({n_tot} totalidad, {n_par} parciales)')
    return d, picks


def build(out_path=None, progress=None, geocode=True, event=None,
          check_obstacles=True):
    ev = event or events.DEFAULT
    out_path = out_path or os.path.join(DATA_DIR, 'points.json')
    d, picks = select(progress=progress)
    lat, lon = d['lat'], d['lon']

    points = []
    n = len(picks)
    for k, i in enumerate(picks, 1):
        if progress and k % 10 == 0:
            progress(k, n, 'calculando horizontes')
        la, lo = float(lat[i]), float(lon[i])
        e = float(elev_fine(la, lo)[0])
        c = circumstances(la, lo, e)
        hz = horizon_fine(la, lo, AZIMUTHS, obs_elev=e)

        # Sun track every 10 min through the plotted window, for the browser to draw.
        t0 = _ts_utc(ev, -60)
        t1 = _ts_utc(ev, 75)
        saz, _, salt, _ = sun_track(la, lo, e, t0, t1, step_s=600.0)
        keep = (saz >= AZ_LO - 2) & (saz <= AZ_HI + 2)

        total = bool(c['total'])
        if total:
            alt_ref, az_ref = c['c3_alt_app'], c['c3_az']
            clear = min(c['c2_alt_app'] - float(np.interp(c['c2_az'], AZIMUTHS, hz)),
                        c['c3_alt_app'] - float(np.interp(c['c3_az'], AZIMUTHS, hz)))
        else:
            alt_ref, az_ref = c['max_alt_app'], c['max_az']
            clear = alt_ref - float(np.interp(az_ref, AZIMUTHS, hz))
        horizon = float(np.interp(az_ref, AZIMUTHS, hz))

        from .ephem import moon_offset
        iso = c['max_utc']
        tmax = _ts_at(iso)
        d_az, d_alt, r_sun, r_moon = moon_offset(la, lo, e, tmax)

        points.append(dict(
            i=k, lat=round(la, 5), lon=round(lo, 5), elev=round(e),
            total=total, dur=round(c['duration_s'], 1),
            obsc=round(c['obscuration'] * 100, 3),
            alt=round(alt_ref, 2), az=round(az_ref, 2),
            alt2=round(c['c2_alt_app'], 2) if total else round(alt_ref, 2),
            hz=round(horizon, 2), clear=round(clear, 2),
            t=_local(ev, c['max_utc']),
            t2=_local(ev, c['c2_utc']) if total else None,
            t3=_local(ev, c['c3_utc']) if total else None,
            # horizon profile in hundredths of a degree keeps the payload small
            prof=[int(round(v * 100)) for v in hz],
            sun=[[round(float(a), 2), round(float(v), 2)]
                 for a, v in zip(saz[keep], salt[keep])],
            moon=[round(d_az, 4), round(d_alt, 4), round(r_sun, 4), round(r_moon, 4)],
        ))

    # Checkpoint antes de tocar nada externo. Los horizontes cuestan ~40 min de CPU y
    # no se pueden perder porque un servicio ajeno esté caído.
    _dump(out_path, ev, points)

    if check_obstacles:
        # The DEM's blind spot, filled from OpenStreetMap: trees and buildings in the
        # sight line. The IGN's visualiser states it ignores both; this is where we
        # can actually do better rather than just finer.
        enrich_obstacles(points, progress=progress)

    if geocode:
        for k, p in enumerate(points, 1):
            if progress and k % 10 == 0:
                progress(k, len(points), 'poniendo nombres')
            p['place'] = gazetteer.reverse(p['lat'], p['lon'])
        points = drop_offshore(points, progress=progress)

    meta = _dump(out_path, ev, points)
    return out_path, meta


RETRY_ZOOM = 16        # el zoom de la segunda oportunidad, ver drop_offshore


def drop_offshore(points, progress=None, retry=True):
    """Quita los puntos que no se confirman en tierra firme.

    Sobre el mar el DEM vale 0 y el horizonte sale impecable, así que un punto en mar
    abierto se cuela en lo más alto del ranking por margen libre: exactamente el sitio
    donde nadie puede plantar un trípode. Va después de poner nombres porque el
    topónimo es la prueba (ver gazetteer.on_land), y renumera para que `i` siga siendo
    correlativo.

    Segunda oportunidad antes de tirar nada: al zoom 13 con el que se etiqueta, la costa
    da falsos positivos — 43,44/-2,94 salía «España» y es Gorliz (Bizkaia), y
    42,94/-9,29 es el Monte de Arnela en Fisterra, de los mejores márgenes del país.
    Se reconsulta al zoom 16 y, si aparece municipio, el punto se queda **y de paso
    arregla su topónimo**. Sólo se descarta lo que sigue sin tierra a ese detalle.
    """
    kept, dropped, fixed = [], [], 0
    for p in points:
        if gazetteer.on_land(p.get('place')):
            kept.append(p)
            continue
        fine = gazetteer.reverse(p['lat'], p['lon'], zoom=RETRY_ZOOM) if retry else ''
        if gazetteer.on_land(fine):
            p['place'] = fine
            fixed += 1
            kept.append(p)
        else:
            dropped.append(p)
    for k, p in enumerate(kept, 1):
        p['i'] = k
    if progress:
        progress(len(kept), len(points),
                 f'descartados {len(dropped)} sin tierra confirmada, '
                 f'{fixed} topónimos recuperados')
    return kept


def enrich_obstacles(points, progress=None):
    """Add the trees-and-buildings check to points already computed.

    Kept separate and resumable on purpose: the public Overpass instances go down or
    saturate (observed: HTTP 504 "server too busy" on one, no answer at all on two
    others), and a viewpoint dataset must not depend on a third party being healthy at
    the moment it is built. Points not checked keep obs_ok=False, which the interface
    must render as "sin comprobar" -- never as "clear".
    """
    lookup = lambda a, b: float(elev_fine(a, b)[0])          # noqa: E731
    items = [(p['lat'], p['lon'], p['az'], p['elev']) for p in points]
    res = obstacles.check_batch(items, elev_lookup=lookup, progress=progress)
    n_ok = 0
    for p, o in zip(points, res):
        # OJO: aquí NO se toca 'sv'. Quien decide si hay foto de Street View es
        # apply_streetview(), que necesita saber si hay carretera cerca — un dato que
        # esta función no tiene. Ponerlo aquí se lo daba a los 1.457 puntos y deshacía
        # la regla en silencio cada vez que se reintentaban los árboles.
        if not o or not o.get('ok'):
            p['obs_ok'] = False
            p.setdefault('obs', 0.0)
            p['clear_net'] = p['clear']      # sin comprobar, no "limpio"
            continue
        n_ok += 1
        p['obs'] = round(o.get('angle', 0.0), 2)
        p['obs_ok'] = True
        w = o.get('worst')
        if w:
            p['obs_what'] = w['kind']; p['obs_d'] = w['dist_m']
            p['obs_h'] = w['height_m']; p['obs_meas'] = w['measured']
        p['clear_net'] = round(min(p['clear'], p['alt'] - max(p['hz'], p['obs'])), 2)
    return n_ok


def apply_streetview(points):
    """Decide el enlace de Street View de cada punto, en un único sitio.

    Street View se graba desde la vía: sin carretera asfaltada muy cerca, el enlace
    abre una pantalla negra (pasó en producción). La regla vive aquí y no repartida
    por los scripts, porque cuando estaba repartida `enrich_obstacles` volvió a
    ponérselo a los 1.457 puntos sin que nadie se enterase.

    Sin perfil de acceso comprobado no hay enlace: un dato que falta no se disfraza.
    """
    n = 0
    for p in points:
        pv = (p.get('acc') or {}).get('paved') if p.get('acc_ok') else None
        if pv and pv.get('m') is not None and pv['m'] <= obstacles.SV_MAX_ROAD_M:
            p['sv'] = obstacles.streetview_url(p['lat'], p['lon'], p['az'])
            n += 1
        else:
            p.pop('sv', None)
    return n


def _dump(out_path, ev, points, extra=None):
    meta = dict(
        event=ev.key, event_label=ev.label, date=ev.iso_date, tz_label=ev.tz_label,
        az_lo=AZ_LO, az_hi=AZ_HI, az_step=AZ_STEP,
        min_clear=MIN_CLEAR, sep_km=SEP_KM, n=len(points),
        # se recuentan aquí y no los pasa quien llama: si cada script tuviera que
        # acordarse de arrastrar el contador del otro, el primero que lo olvide deja
        # el meta mintiendo sobre cuántos puntos están comprobados
        n_obs_checked=sum(1 for p in points if p.get('obs_ok')),
        n_access_checked=sum(1 for p in points if p.get('acc_ok')),
        note=('Puntos recomendados precalculados para este eclipse. Buscar por '
              'localidad y radio es un filtro sobre este conjunto: no se calcula '
              'nada en vivo.'))
    if extra:
        meta.update(extra)
    with open(out_path, 'w') as f:
        json.dump(dict(meta=meta, points=points), f, ensure_ascii=False,
                  separators=(',', ':'))
    return meta


def _ts_utc(ev, minutes_from_mid):
    """A skyfield Time offset from the middle of the event's search window."""
    from .ephem import _ts
    h0, m0 = ev.search_start_utc
    h1, m1 = ev.search_end_utc
    mid = ((h0 * 60 + m0) + (h1 * 60 + m1)) / 2 + minutes_from_mid
    return _ts.utc(ev.date[0], ev.date[1], ev.date[2], 0, mid, 0)


def _ts_at(iso):
    from .ephem import _ts
    return _ts.utc(int(iso[0:4]), int(iso[5:7]), int(iso[8:10]),
                   int(iso[11:13]), int(iso[14:16]), float(iso[17:19]))


def _local(ev, iso):
    h = (int(iso[11:13]) + int(ev.tz_offset_h)) % 24
    return f'{h:02d}:{iso[14:16]}'


if __name__ == '__main__':
    path, meta = build(progress=lambda a, b, m: print(f'  [{a}/{b}] {m}', flush=True))
    print(f"\n{meta['n']} puntos -> {path}")
    print(f"tamaño: {os.path.getsize(path)/1e6:.1f} MB")
