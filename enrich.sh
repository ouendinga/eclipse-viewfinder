#!/usr/bin/env bash
# Completa el chequeo de árboles y edificios sobre points.json y redespliega.
set -uo pipefail
cd "$(dirname "$0")"
.venv/bin/python - <<'PY'
import json, time
from eclipseview import recommend, obstacles, events
from eclipseview.paths import DATA_DIR
import os
path = os.path.join(DATA_DIR, 'points.json')
d = json.load(open(path))
pts = d['points']
t0 = time.time()
def prog(a, b, m):
    el = time.time() - t0
    eta = (b - a) * el / a / 60 if a else 0
    print(f'[{a}/{b}] {m}  ~{eta:.0f} min restantes', flush=True)
n_ok = recommend.enrich_obstacles(pts, progress=prog)
meta = recommend._dump(path, events.DEFAULT, pts)
print(f"OK enriquecido: {n_ok}/{len(pts)} comprobados -> {path}")
PY
