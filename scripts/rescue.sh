#!/usr/bin/env bash
# Cambia los miradores a los que no se llega por otros igual de buenos a los que sí.
#
# Sólo toca los puntos donde el margen SATURA (por encima del tope el criterio deja de
# desempatar) Y el acceso es malo. Ahí, y sólo ahí, cambiar un punto por otro de su
# misma celda no cuesta calidad: los dos están por encima del tope.
#
# Los tres primeros pasos son gratis (candidatos del barrido + recomprobación a 30 m).
# Overpass sólo se toca en el cuarto, y sólo para los que han sobrevivido.
#
# Deja trabajo detrás a propósito: los puntos cambiados se quedan SIN limbo, y el test
# de calidad de datos exige que lo tengan todos o ninguno. Es la forma de que no se
# pueda publicar un dataset a medio rehacer sin que salte algo.
#
# Va DESPACIO por lo mismo que night.sh: Overpass limita por coste de consulta, no por
# número. La primera pasada salió a 6 s (el defecto) con un solo endpoint sano y se
# comió un 429 a los 75 puntos. Una consulta por minuto y a dormir.
set -uo pipefail
cd "$(dirname "$0")/.."
export OVERPASS_MIN_INTERVAL="${OVERPASS_MIN_INTERVAL:-60}"
echo "una consulta cada ${OVERPASS_MIN_INTERVAL}s"
.venv/bin/python - <<'PY'
import json, os, pickle, sys, time
from eclipseview import events, gazetteer, obstacles, recommend, rescue
from eclipseview.paths import DATA_DIR, SCAN_PKL

path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path)); P = d['points']
ev = events.DEFAULT

wide = os.path.join(DATA_DIR, 'scan_wide.pkl')
scan = pickle.load(open(wide if os.path.exists(wide) else SCAN_PKL, 'rb'))

sat = sum(1 for p in P if rescue.net_clear(p) > recommend.CLEAR_SATURATION)
obj = [p for p in P if rescue.needs_rescue(p)]
print(f'{len(P)} puntos | {sat} con el margen saturado | {len(obj)} de esos mal '
      f'comunicados', flush=True)

# --- pasos 1 y 2: alternativas de la misma celda, gratis -----------------------------
cands = rescue.candidates(P, scan)
n_cand = sum(len(v) for v in cands.values())
print(f'paso 1-2: {len(cands)} puntos con alternativas, {n_cand} candidatos', flush=True)
if not cands:
    print('nada que rescatar'); sys.exit(0)

# --- paso 3: recomprobar a 30 m ------------------------------------------------------
# Se guarda el resultado: Overpass va a hacer falta varias noches, y repetir media hora
# de CPU en cada reintento sólo para llegar otra vez al mismo sitio no tiene sentido.
ckpt = os.path.join(DATA_DIR, 'rescue_candidates.json')
t0 = time.time()
def prog(a, b, m):
    if a % 25 == 0 or a == b:
        el = time.time() - t0
        print(f'  [{a}/{b}] {m}  ~{(b-a)*el/a/60 if a else 0:.0f} min', flush=True)

if os.path.exists(ckpt):
    guardado = json.load(open(ckpt))
    finos = {int(k): v for k, v in guardado['finos'].items()}
    print(f'paso 3: reutilizando el guardado de {guardado["cuando"]}', flush=True)
else:
    finos = rescue.refine(cands, ev, progress=prog)
    json.dump({'cuando': time.strftime('%Y-%m-%d %H:%M'),
               'finos': {str(k): v for k, v in finos.items()}},
              open(ckpt, 'w'))
n_fino = sum(len(v) for v in finos.values())
print(f'paso 3: {n_fino} de {n_cand} candidatos aguantan el margen a 30 m', flush=True)
if not finos:
    print('ninguno aguanta; el dataset se queda como está'); sys.exit(0)

# --- paso 4: OSM, sólo para los supervivientes ---------------------------------------
# El sondeo va primero: sin él, una caída de Overpass se ve como una barra avanzando y
# un "OK" al final, con todos los candidatos descartados en silencio por falta de datos.
eps = obstacles.healthy_endpoints(force=True)
if not eps:
    print('ABORTADO: ningún Overpass responde. No se toca el dataset.'); sys.exit(2)
print(f'paso 4: {len(eps)} endpoints responden, una consulta cada '
      f'{obstacles._min_interval():.0f} s', flush=True)

plano = [q for qs in finos.values() for q in qs]
t0 = time.time()
try:
    # árboles y edificios: la MISMA función que usa build(), no una copia
    recommend.enrich_obstacles(plano, progress=prog)
    vias = obstacles.check_roads_batch([(q['lat'], q['lon']) for q in plano],
                                       progress=prog)
except obstacles.NoEndpoints as e:
    print(f'ABORTADO a mitad: {e}. El dataset se queda como estaba.'); sys.exit(2)

for q, via in zip(plano, vias):
    if via:
        q['acc_ok'] = True
        q['acc'] = {k: v for k, v in via.items() if k in ('near','drive','walk','paved')}
        q['acc_hard'] = bool((via.get('drive') or {}).get('hard'))
    else:
        q['acc_ok'] = False

# --- el cambio ------------------------------------------------------------------------
por_id = {p['i']: p for p in P}
cambios = []
for pid, qs in finos.items():
    orig = por_id[pid]
    mejores = [q for q in qs if rescue.better(orig, q)]
    if mejores:
        cambios.append((orig, max(mejores, key=rescue.access_rank)))

print(f'\n{len(cambios)} puntos mejoran de acceso sin perder nada', flush=True)
hechos = 0
for k, (orig, nuevo) in enumerate(cambios, 1):
    # El topónimo NO se hereda: el punto nuevo puede caer a 20 km, en otro municipio.
    # Decir "en el término de X" sobre un sitio que ya no está en X es exactamente el
    # tipo de mentira que este proyecto no puede permitirse. Se pide ANTES de tocar
    # nada: si el geocodificador falla justo en este punto, se deja como estaba en vez
    # de tirar la pasada entera por culpa de uno.
    nombre = gazetteer.reverse(nuevo['lat'], nuevo['lon'])
    if not nombre:
        print(f'  sin topónimo para {nuevo["lat"]:.4f},{nuevo["lon"]:.4f}: '
              f'se queda el original', flush=True)
        continue
    idx = orig['i']
    orig.clear(); orig.update(nuevo)
    orig['i'] = idx
    orig['place'] = nombre
    hechos += 1
    if k % 10 == 0:
        print(f'  [{k}/{len(cambios)}] poniendo nombres', flush=True)
print(f'{hechos} cambios aplicados', flush=True)

n_sv = recommend.apply_streetview(P)
fallos = recommend.check_invariants(P)
if fallos:
    print('NO se guarda, el dataset quedaría inválido:', fallos); sys.exit(1)

recommend._dump(path, ev, P)
quedan = sum(1 for p in P if rescue.needs_rescue(p))
print(f'\nmal comunicados y saturados: {len(obj)} -> {quedan}')
print(f'Street View en {n_sv} puntos')
if hechos:
    os.remove(ckpt)      # ya aplicado: el guardado dejaría de valer para el dataset nuevo
    print(f'\nFALTA: los {hechos} puntos cambiados no tienen limbo. '
          f'Lanza scripts/limbrun.sh antes de construir el sitio.')
print(f'OK -> {path}')
PY
