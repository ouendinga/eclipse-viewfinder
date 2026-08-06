#!/usr/bin/env bash
# Añade el perfil de accesibilidad (vías, firme, 4x4, sendero) a points.json
set -uo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
import json, os, sys, time
from eclipseview import obstacles, recommend, events
from eclipseview.paths import DATA_DIR
path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path)); P = d['points']

# Mismo sondeo que enrich.sh: sin esto, una caída de Overpass se ve como una barra
# avanzando y un "OK" al final, con los puntos fallando en silencio.
eps = obstacles.healthy_endpoints(force=True)
if not eps:
    print('ABORTADO: ningún Overpass responde. No se toca el dataset.', flush=True)
    sys.exit(2)
antes = sum(1 for p in P if p.get('acc_ok'))
print(f'{len(eps)} de {len(obstacles.OVERPASS_ENDPOINTS)} endpoints responden; '
      f'una consulta cada {obstacles._min_interval():.0f} s', flush=True)

t0 = time.time()
def prog(a,b,m):
    el=time.time()-t0
    print(f'[{a}/{b}] {m}  ~{(b-a)*el/a/60 if a else 0:.0f} min restantes', flush=True)
try:
    res = obstacles.check_roads_batch([(p['lat'], p['lon']) for p in P], progress=prog)
except obstacles.NoEndpoints as e:
    print(f'ABORTADO a mitad: {e}. El dataset se queda como estaba.', flush=True)
    sys.exit(2)
n=0
for p, r in zip(P, res):
    if not r:
        p['acc_ok'] = False
        p.pop('sv', None)          # sin datos no se promete una foto que puede no existir
        continue
    n += 1
    p['acc_ok'] = True
    p['acc'] = {k: v for k, v in r.items() if k in ('near','drive','walk','paved')}
    dr = r.get('drive')
    p['acc_hard'] = bool(dr and dr.get('hard'))
# la regla de Street View vive en un único sitio, no repartida por los scripts
n_sv = recommend.apply_streetview(P)
meta = recommend._dump(path, events.DEFAULT, P, extra=dict(n_access_checked=n))
print(f'Street View en {n_sv} puntos (sólo con asfalto a <={obstacles.SV_MAX_ROAD_M:.0f} m)')
nuevos = n - antes
print(f'accesibilidad: {n}/{len(P)} comprobados (nuevos en esta pasada: {nuevos})')
if nuevos <= 0:
    print('AVISO: esta pasada no ha añadido ni un punto. Overpass no está colaborando.')
    sys.exit(1)
print('OK')
PY
