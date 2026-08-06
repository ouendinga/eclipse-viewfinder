#!/usr/bin/env bash
# Recalcula la geometría del eclipse de cada punto con el radio lunar actual,
# conservando el trabajo de OpenStreetMap (árboles, edificios, accesos, topónimos).
#
# Por qué no un `recommend.build()` entero: el barrido de horizontes cuesta ~40 min de
# CPU y, sobre todo, volvería a partir de cero el perfil de acceso, que son horas de
# Overpass. El terreno no ha cambiado —el perfil del horizonte de cada punto es el
# mismo—, lo único que cambia al tocar el radio lunar es la geometría del eclipse.
set -uo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
import json, os, sys, time
import numpy as np
from eclipseview import events, obstacles, recommend, sources
from eclipseview.ephem import circumstances, moon_offset, sun_track
from eclipseview.recommend import AZIMUTHS, AZ_LO, AZ_HI, _local, _ts_at, _ts_utc
from eclipseview.paths import DATA_DIR

path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path)); P = d['points']
ev = events.DEFAULT
print(f'{len(P)} puntos | radio lunar {sources.LUNAR_UMBRAL_RADIUS["km"]} km', flush=True)

antes_total = sum(1 for p in P if p.get('total'))
antes_dur = [p['dur'] for p in P if p.get('total')]
cambios, t0 = [], time.time()

for k, p in enumerate(P, 1):
    if k % 100 == 0:
        el = time.time() - t0
        print(f'[{k}/{len(P)}] ~{(len(P)-k)*el/k/60:.0f} min restantes', flush=True)
    la, lo, e = p['lat'], p['lon'], p['elev']
    c = circumstances(la, lo, e)
    hz = np.array(p['prof'], dtype=float) / 100.0     # el terreno no cambia

    total = bool(c['total'])
    if total:
        alt_ref, az_ref = c['c3_alt_app'], c['c3_az']
        clear = min(c['c2_alt_app'] - float(np.interp(c['c2_az'], AZIMUTHS, hz)),
                    c['c3_alt_app'] - float(np.interp(c['c3_az'], AZIMUTHS, hz)))
    else:
        alt_ref, az_ref = c['max_alt_app'], c['max_az']
        clear = alt_ref - float(np.interp(az_ref, AZIMUTHS, hz))

    viejo = (p.get('total'), p.get('dur'))
    p['total'] = total
    p['dur'] = round(c['duration_s'], 1)
    p['obsc'] = round(c['obscuration'] * 100, 3)
    p['alt'] = round(alt_ref, 2)
    p['az'] = round(az_ref, 2)
    p['alt2'] = round(c['c2_alt_app'], 2) if total else round(alt_ref, 2)
    p['hz'] = round(float(np.interp(az_ref, AZIMUTHS, hz)), 2)
    p['clear'] = round(clear, 2)
    p['t'] = _local(ev, c['max_utc'])
    p['t2'] = _local(ev, c['c2_utc']) if total else None
    p['t3'] = _local(ev, c['c3_utc']) if total else None

    saz, _, salt, _ = sun_track(la, lo, e, _ts_utc(ev, -60), _ts_utc(ev, 75), step_s=600.0)
    keep = (saz >= AZ_LO - 2) & (saz <= AZ_HI + 2)
    p['sun'] = [[round(float(a), 2), round(float(v), 2)]
                for a, v in zip(saz[keep], salt[keep])]
    d_az, d_alt, r_sun, r_moon = moon_offset(la, lo, e, _ts_at(c['max_utc']))
    p['moon'] = [round(d_az, 4), round(d_alt, 4), round(r_sun, 4), round(r_moon, 4)]

    # el margen NETO depende del obstáculo ya medido, que no cambia
    if p.get('obs_ok'):
        p['clear_net'] = round(min(clear, alt_ref - max(p['hz'], p.get('obs', 0.0))), 2)
    else:
        p['clear_net'] = p['clear']

    if viejo[0] != total:
        cambios.append((p, viejo))

# el índice sigue siendo correlativo y Street View no se toca aquí
fallos = recommend.check_invariants(P)
if fallos:
    print('NO se guarda, el dataset quedaría inválido:', fallos); sys.exit(1)

meta = recommend._dump(path, ev, P)
dur = [p['dur'] for p in P if p.get('total')]
print()
print(f'totalidad: {antes_total} puntos -> {sum(1 for p in P if p.get("total"))}')
print(f'duración media de las totalidades: {np.mean(antes_dur):.1f}s -> {np.mean(dur):.1f}s')
print(f'la más corta: {min(antes_dur):.1f}s -> {min(dur):.1f}s')
print(f'puntos que dejan de tener totalidad: {sum(1 for p,v in cambios if v[0] and not p["total"])}')
print(f'puntos que pasan a tenerla:          {sum(1 for p,v in cambios if not v[0] and p["total"])}')
for p, v in cambios[:10]:
    print(f'   {p["lat"]:.3f},{p["lon"]:.3f}  {v[1]:.1f}s -> '
          f'{p["dur"]:.1f}s {"(ya no es total)" if v[0] else "(ahora sí)"}  {p.get("place")}')
print(f'\nOK -> {path}')
PY
