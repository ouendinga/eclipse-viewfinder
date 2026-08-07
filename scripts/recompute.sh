#!/usr/bin/env bash
# Recalcula la geometría del eclipse de cada punto, conservando el trabajo de
# OpenStreetMap (árboles, edificios, accesos, topónimos).
#
# Por qué no un `recommend.build()` entero: el barrido de horizontes cuesta ~40 min de
# CPU y, sobre todo, volvería a partir de cero el perfil de acceso, que son horas de
# consultas a Overpass. El terreno no se mueve, así que el perfil del horizonte que ya
# está calculado sigue siendo válido y sólo hay que rehacer lo que depende de las
# efemérides.
set -uo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
import json, os, sys, time
import numpy as np
from eclipseview import events, recommend, sources
from eclipseview.paths import DATA_DIR

path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path)); P = d['points']
ev = events.DEFAULT
print(f'{len(P)} puntos | radio lunar {sources.LUNAR_UMBRAL_RADIUS["km"]} km', flush=True)

antes_total = sum(1 for p in P if p.get('total'))
antes_dur = [p['dur'] for p in P if p.get('total')]
cambios, t0 = [], time.time()

# Los campos que NO dependen de las efemérides y hay que conservar tal cual: son horas
# de Overpass y de geocodificación que este script no tiene por qué volver a pagar.
CONSERVAR = ('place', 'acc', 'acc_ok', 'acc_hard', 'obs', 'obs_ok', 'obs_h', 'obs_d',
             'obs_what', 'obs_meas', 'sv', 'dur_limb', 'total_limb')

for k, p in enumerate(P, 1):
    if k % 100 == 0:
        el = time.time() - t0
        print(f'[{k}/{len(P)}] ~{(len(P)-k)*el/k/60:.0f} min restantes', flush=True)
    viejo = (p.get('total'), p.get('dur'))
    guardado = {c: p[c] for c in CONSERVAR if c in p}

    # La MISMA función que usa build(), reutilizando el perfil del terreno ya trazado.
    # Tenerla copiada aquí es lo que hacía que este script se quedara atrás cada vez
    # que cambiaba el formato de un punto.
    nuevo = recommend.point_at(p['lat'], p['lon'], ev, index=p['i'],
                               prof=p['prof'], elev=p['elev'])
    p.clear(); p.update(nuevo); p.update(guardado)

    # el margen NETO depende del obstáculo ya medido, que no cambia
    if p.get('obs_ok'):
        p['clear_net'] = round(min(p['clear'], p['alt'] - max(p['hz'], p.get('obs', 0.0))), 2)
    else:
        p['clear_net'] = p['clear']

    if viejo[0] != p['total']:
        cambios.append((p, viejo))

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
