#!/usr/bin/env bash
# Filtra el dataset, reconstruye el sitio y redespliega.
set -uo pipefail
cd "$(dirname "$0")"
until grep -q '^OK enriquecido' /tmp/enrich2.log 2>/dev/null; do
  grep -qE 'Traceback' /tmp/enrich2.log 2>/dev/null && { echo "FALLO en el enriquecido"; exit 1; }
  sleep 30
done
echo "== enriquecido listo: $(grep '^OK enriquecido' /tmp/enrich2.log | tail -1)"

.venv/bin/python - <<'PY'
import json, os
from eclipseview import events, recommend
from eclipseview.paths import DATA_DIR
path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path)); P = d['points']
n0 = len(P)

# 1) Fuera de alcance: el barrido por magnitud >= 0,97 llegaba hasta la costa atlántica
#    francesa (Lacanau, 97,8 %), a 600 km de la franja. La página habla de España y el
#    mapa ni los muestra: recomendarlos es ruido.
scope = [p for p in P if p['obsc'] >= 98.5]
n_scope = n0 - len(scope)

# 2) No recomendables: comprobados y con el Sol tapado por lo que hay plantado encima.
#    Un "mirador" con un bloque de pisos a 44 m no es una recomendación, es un error
#    de selección que el chequeo acaba de destapar.
keep = [p for p in scope
        if not (p.get('obs_ok') and p.get('clear_net', 9) < 1.5)]
n_blocked = len(scope) - len(keep)

meta = recommend._dump(path, events.DEFAULT, keep, extra=dict(
    n_dropped_out_of_scope=n_scope,
    n_dropped_blocked=n_blocked,
    obs_note=('Margen neto = terreno + árboles y edificios de OpenStreetMap en la '
              'línea de visión. Los puntos sin comprobar conservan el margen del '
              'terreno y se marcan como tales.')))
print(f'  {n0} -> {len(keep)} puntos  (fuera de alcance {n_scope}, tapados {n_blocked})')
print(f'  comprobados con OSM: {meta["n_obs_checked"]}')
PY

.venv/bin/python -c "
from eclipseview import site
out, data = site.build(out_dir='site', progress=lambda m: print(' ', m, flush=True))
print('sitio ->', out, '| verificación', data['summary']['passed'], '/', data['summary']['total'])
" || exit 1
TOKEN="$(grep -oE 'vcp_[A-Za-z0-9]+' /home/alvaro/projects/services.md | head -1)"
cd site && npx --yes vercel@latest deploy --prod --yes --token "$TOKEN" --name eclipse-viewfinder 2>&1 | tail -1
echo "== redesplegado =="
curl -s -o /dev/null -w "produccion -> %{http_code}\n" https://eclipse.alvarosolis.dev/
