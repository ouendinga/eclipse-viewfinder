#!/usr/bin/env bash
# Genera la tarjeta social (1200x630) que sale al compartir el enlace.
#
# Sin ella, WhatsApp enseña "eclipse.alvarosolis.dev" tres veces seguidas y el enlace
# parece spam al lado de cualquier otro. La imagen se monta con el CSS y el mapa del
# propio sitio —no con una plantilla— y se captura con el Chromium de Playwright, que
# es el único renderizador de SVG a PNG que hay en esta máquina.
#
# NO va en el build: el PNG se versiona y sólo se regenera si cambia el diseño.
set -uo pipefail
cd "$(dirname "$0")"

PW="${PW:-/home/alvaro/projects/folio-doctor/node_modules/playwright}"
[ -d "$PW" ] || { echo "no encuentro playwright en $PW (pásalo con PW=...)"; exit 1; }

OUT="site/og.png"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

.venv/bin/python - "$TMP/card.html" <<'PY'
import json, os, sys
from eclipseview import events, sources
from eclipseview.paths import DATA_DIR, MAP_SVG
from eclipseview.style import CSS

ev = events.DEFAULT
P = json.load(open(os.path.join(DATA_DIR, 'points.json')))['points']
n = len(P)
tot = sum(1 for p in P if p.get('total'))
mapa = open(MAP_SVG).read() if os.path.exists(MAP_SVG) else ''

def es(n, d=0):
    return f'{n:,.{d}f}'.replace(',', '.')

html = f'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<style>{CSS}
html,body{{margin:0;padding:0;background:var(--ground)}}
.card{{width:1200px;height:630px;position:relative;overflow:hidden;
  display:flex;flex-direction:column;justify-content:space-between;
  padding:52px 56px;box-sizing:border-box}}
/* Doble degradado: el mapa es un rectángulo y su borde inferior se veía como una raya
   recta cruzando la tarjeta. Se difumina por la izquierda y por abajo. */
.card .mapa{{position:absolute;right:-120px;top:-60px;width:880px;opacity:.45;
  -webkit-mask-image:linear-gradient(to left,#000 40%,transparent 94%),
    linear-gradient(to top,transparent 2%,#000 34%);
  -webkit-mask-composite:source-in;mask-composite:intersect}}
.card .mapa svg{{width:100%;height:auto;display:block}}
.eyebrow2{{font:600 15px var(--mono);letter-spacing:.2em;text-transform:uppercase;
  color:var(--sun);position:relative}}
.card h1{{font-family:var(--serif);font-size:62px;line-height:1.06;margin:16px 0 0;
  max-width:15ch;position:relative}}
.card .sub{{font-size:23px;color:var(--muted);margin:20px 0 0;max-width:30ch;
  position:relative;line-height:1.45}}
.stats{{display:flex;gap:44px;position:relative;align-items:flex-end}}
.stat .n{{font:700 40px var(--mono);color:var(--sun);line-height:1}}
.stat .k{{font:600 12px var(--mono);letter-spacing:.14em;text-transform:uppercase;
  color:var(--dim);margin-top:8px}}
.dom{{margin-left:auto;font:600 17px var(--mono);color:var(--muted)}}
</style></head><body>
<div class="card">
  <div class="mapa">{mapa}</div>
  <div>
    <div class="eyebrow2">{ev.iso_date} · eclipse total de Sol</div>
    <h1>El sitio no lo decide el pueblo. Lo decide el horizonte.</h1>
    <p class="sub">El Sol estará a 2°–11°. Una loma a 3 km te lo tapa. Esto cruza la
    geometría del eclipse con el terreno real, los árboles y los edificios.</p>
  </div>
  <div class="stats">
    <div class="stat"><div class="n">{es(n)}</div><div class="k">miradores calculados</div></div>
    <div class="stat"><div class="n">{es(tot)}</div><div class="k">con totalidad</div></div>
    <div class="stat"><div class="n">30 m</div><div class="k">resolución del relieve</div></div>
    <div class="dom">eclipse.alvarosolis.dev</div>
  </div>
</div></body></html>'''
open(sys.argv[1], 'w').write(html)
print(f'tarjeta: {n} miradores, {tot} con totalidad')
PY

node -e "
const { chromium } = require('$PW');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 630 },
                              deviceScaleFactor: 1, colorScheme: 'dark' });
  await p.goto('file://$TMP/card.html', { waitUntil: 'load' });
  await p.waitForTimeout(600);
  await p.screenshot({ path: '$OUT' });
  await b.close();
})();
" || exit 1

echo "escrito $OUT ($(du -h "$OUT" | cut -f1))"
