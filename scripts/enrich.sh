#!/usr/bin/env bash
# Completa el chequeo de árboles y edificios sobre points.json y redespliega.
set -uo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
import json, sys, time
from eclipseview import recommend, obstacles, events
from eclipseview.paths import DATA_DIR
import os
path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path))
pts = d['points']

# Sondeo antes de empezar. Sin esto, una caída total de Overpass se veía como 25
# minutos de barra avanzando, 401 puntos fallando y un "OK" al final.
eps = obstacles.healthy_endpoints(force=True)
if not eps:
    print('ABORTADO: ningún Overpass responde. No se toca el dataset.', flush=True)
    sys.exit(2)
print(f'{len(eps)} de {len(obstacles.OVERPASS_ENDPOINTS)} endpoints responden; '
      f'una consulta cada {obstacles._min_interval():.0f} s', flush=True)
antes = sum(1 for p in pts if p.get('obs_ok'))
t0 = time.time()
def prog(a, b, m):
    el = time.time() - t0
    eta = (b - a) * el / a / 60 if a else 0
    print(f'[{a}/{b}] {m}  ~{eta:.0f} min restantes', flush=True)
try:
    n_ok = recommend.enrich_obstacles(pts, progress=prog)
except obstacles.NoEndpoints as e:
    print(f'ABORTADO a mitad: {e}. El dataset se queda como estaba.', flush=True)
    sys.exit(2)
# el chequeo de árboles no sabe si hay carretera, así que se vuelve a aplicar la regla
# de Street View sobre el perfil de acceso que ya está en el dataset
n_sv = recommend.apply_streetview(pts)
meta = recommend._dump(path, events.DEFAULT, pts)
nuevos = n_ok - antes
print(f"comprobados: {n_ok}/{len(pts)} (nuevos en esta pasada: {nuevos})")
print(f"Street View en {n_sv} puntos -> {path}")
if nuevos <= 0:
    # decirlo alto: la pasada anterior tardó 25 min para no añadir ni uno y lo llamó OK
    print('AVISO: esta pasada no ha añadido ni un punto. Overpass no está colaborando.')
    sys.exit(1)
print('OK')
PY
