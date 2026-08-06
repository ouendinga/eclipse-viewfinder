#!/usr/bin/env bash
# Añade a cada punto la totalidad calculada con el PERFIL REAL del limbo lunar.
#
# No sustituye a la duración publicada. El IGN y la NASA publican sus duraciones con
# limbo MEDIO por convenio, y quien mire nuestra web va a contrastar con el IGN: cambiar
# el titular por un número que no cuadra con el suyo sería peor servicio aunque el
# modelo sea más fino. Lo que aporta el limbo es la respuesta a la pregunta que de
# verdad importa en el filo: ¿hay corona o no la hay?
set -uo pipefail
cd "$(dirname "$0")"
.venv/bin/python - <<'PY'
import json, os, sys, time
from eclipseview import events, limb, recommend
from eclipseview.ephem import circumstances
from eclipseview.paths import DATA_DIR

if not limb.available():
    print('faltan los datos del limbo (LOLA + núcleos NAIF) en data/moon/', flush=True)
    sys.exit(2)

path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path)); P = d['points']
print(f'{len(P)} puntos con el perfil real del limbo', flush=True)

t0, cambios = time.time(), []
for k, p in enumerate(P, 1):
    if k % 100 == 0:
        el = time.time() - t0
        print(f'[{k}/{len(P)}] ~{(len(P)-k)*el/k/60:.0f} min restantes', flush=True)
    c = circumstances(p['lat'], p['lon'], p['elev'], use_limb=True)
    p['dur_limb'] = round(c['duration_s'], 1) if c['total'] else 0.0
    p['total_limb'] = bool(c['total'])
    if p['total_limb'] != p['total']:
        cambios.append(p)

meta = recommend._dump(path, events.DEFAULT, P)
tot = sum(1 for p in P if p['total'])
totl = sum(1 for p in P if p['total_limb'])
solidos = sum(1 for p in P if p['total'] and p['total_limb'])
print()
print(f'totalidad con esfera : {tot}')
print(f'totalidad con limbo  : {totl}')
print(f'las dos de acuerdo   : {solidos}')
print(f'los modelos discrepan: {len(cambios)} puntos')
for p in cambios[:15]:
    print(f"   {p['lat']:.3f},{p['lon']:.3f}  esfera {p['dur']:.1f}s / limbo "
          f"{p['dur_limb']:.1f}s   {p.get('place')}")
print(f'\nOK -> {path}')
PY
