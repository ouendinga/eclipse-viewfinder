# -*- coding: utf-8 -*-
"""Static site generator: precomputed reports plus an index to pick from.

Why static: a live query needs ~700 MB of elevation tiles on disk and tens of seconds
of CPU, which no serverless platform will give you. So the site ships the answers for
a curated list of places, computed ahead of time, and is honest in the interface about
what is precomputed and what still needs the command line.

This is also the shape the eventual backend wants: precompute the likely places, fall
back to live computation only for the rest.
"""
import json
import os
import unicodedata

from . import finder_ui, gazetteer, i18n, overview, report, verify
from .analysis import evaluate, km, search_area
from .paths import REPORTS_DIR, ensure
from .style import CSS

# Places worth having ready: on or near the path, plus the big cities people will try.
PRESET = [
    # query,                        radius, note
    ('Luarca, Asturias', 45),
    ('Oviedo, Asturias', 45),
    ('Aguilar de Campoo, Palencia', 45),
    ('Palencia', 45),
    ('Burgos', 45),
    ('Soria', 45),
    ('Zaragoza', 50),
    ('Teruel', 50),
    ('Tortosa, Tarragona', 45),
    ('Tarragona', 45),
    ('Castelló de la Plana', 45),
    ('Palma, Illes Balears', 45),
    ('Barcelona', 45),
    ('Madrid', 50),
    ('Valencia', 45),
    ('Malgrat de Mar, Barcelona', 45),
]


def slug(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    out = ''.join(c if c.isalnum() else '-' for c in s.lower())
    while '--' in out:
        out = out.replace('--', '-')
    return out.strip('-')[:48]


def build_one(query, radius, lang='es', top=5, min_clear=1.5, progress=None):
    cands = gazetteer.search(query, lang=lang)
    origin = cands[0]
    label = gazetteer.describe(origin, short=True)
    full = gazetteer.describe(origin)
    if progress:
        progress(f'{label} (r={radius:.0f} km)')
    auto, n_cand, n_ok = search_area(origin['lat'], origin['lon'], radius,
                                     min_clear=min_clear, want=top)
    rows, kept = [], 0
    for lat, lon in auto:
        if kept >= top:
            break
        r = evaluate(lat, lon)
        if r['clear'] < min_clear:
            continue
        r['place'] = gazetteer.reverse(r['lat'], r['lon'], lang=lang)
        r['dist'] = float(km(r['lat'], r['lon'], origin['lat'], origin['lon']))
        rows.append(r); kept += 1
    # always show the origin itself: "can I see it from the town?" is the first question
    home = evaluate(origin['lat'], origin['lon'], label=f'{origin["name"]} (el pueblo)')
    home['place'] = label
    home['dist'] = 0.0
    home['is_origin'] = True
    rows.append(home)
    rows.sort(key=lambda r: (-r['dur'], -r['clear']))
    return origin, label, full, rows


def render_index(entries, lang='es'):
    cards = []
    for e in sorted(entries, key=lambda x: x['label']):
        best = e['best']
        cls = 'g' if best['clear'] >= 2 else ('w' if best['clear'] >= 0 else 'b')
        if e['origin_total']:
            tot = f"totalidad {i18n.number(lang, e['origin_dur'], 0)} s"
        else:
            tot = f"parcial {i18n.obscuration(lang, e['origin_obsc'], False)}"
            if e['nearest_total_km'] is not None:
                tot += (f" · totalidad a "
                        f"{i18n.number(lang, e['nearest_total_km'], 0)} km")
        cards.append(f'''
    <a class="pcard" href="./{e['slug']}.html">
      <span class="pname">{report.esc(e['label'])}</span>
      <span class="pmeta">{tot} · mejor margen
        <b class="{cls}">{i18n.deg(lang, best['clear'], 1, True)}</b></span>
      <span class="pbest">{report.esc(best.get('place') or '')}</span>
    </a>''')

    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eclipse Viewfinder — desde dónde ver el eclipse del 12 de agosto de 2026</title>
<meta name="description" content="Desde dónde ver el eclipse total del 12 de agosto de 2026 en España, teniendo en cuenta el terreno real: el Sol estará entre 2° y 12° y una loma cercana puede taparlo.">
<style>{CSS}
.pgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
  gap:1px;background:var(--line-soft);border:1px solid var(--line-soft);margin:22px 0 0}}
.pcard{{background:var(--panel);padding:14px 16px;display:flex;flex-direction:column;
  gap:4px;text-decoration:none;color:var(--text)}}
.pcard:hover{{background:var(--ground)}}
.pname{{font-family:var(--serif);font-size:17px}}
.pmeta{{font:600 11px var(--mono);letter-spacing:.04em;color:var(--muted)}}
.pmeta b.g{{color:var(--good)}} .pmeta b.w{{color:var(--warn)}} .pmeta b.b{{color:var(--bad)}}
.pbest{{font-size:12px;color:var(--dim)}}
.big{{display:block;border:1px solid var(--sun);background:var(--panel);
  padding:20px 22px;text-decoration:none;color:var(--text);margin:22px 0 0}}
.big:hover{{background:var(--ground)}}
.big .t{{font-family:var(--serif);font-size:22px;color:var(--sun)}}
.big .d{{font-size:14px;color:var(--muted);margin-top:6px;max-width:60ch}}
</style></head><body>
<div class="wrap">
<header class="top">
  <p class="eyebrow">Eclipse total de Sol · 12 agosto 2026</p>
  <h1>El sitio no lo decide el pueblo.<br>Lo decide el horizonte.</h1>
  <p class="lede">Durante la totalidad el Sol estará entre <b>2° y 12°</b> sobre el
  horizonte. A esa altura, una loma a 3 km o una sierra a 80 km te lo tapa. Esto
  calcula la geometría del eclipse y el <b>perfil real del terreno</b> en la dirección
  del Sol para decirte si desde un sitio concreto lo vas a ver.</p>
</header>

<section>
  <a class="big" href="./overview.html">
    <span class="t">Informe general de España →</span>
    <span class="d">Toda la franja de totalidad: dónde ir, qué zonas perdonan un mal
    sitio, dónde están las trampas y qué compra cada hora de coche.</span>
  </a>
</section>

<section>
  <h2>Sitios ya calculados</h2>
  <p class="prose">Para cada uno: los mejores miradores de su comarca, con la silueta
  real del horizonte y la trayectoria del Sol dibujada encima.</p>
  <div class="pgrid">{''.join(cards)}</div>
  <p class="caption">¿No está tu pueblo? Los informes se calculan por adelantado
  porque cada consulta necesita cientos de megas de datos de elevación y decenas de
  segundos de cálculo. Puedes generarlo tú con la herramienta:
  <code>python -m eclipseview place "tu pueblo" -r 45</code> —
  <a href="https://github.com/ouendinga/eclipse-viewfinder">código en GitHub</a>.</p>
</section>

<section>
  <h2>Qué significa el margen</h2>
  <ul class="prose">
    <li><b>Margen libre</b>: grados entre el Sol y la silueta del terreno en el momento
    clave. Negativo = el Sol se pone detrás del monte antes de tiempo.</li>
    <li>Por debajo de <b>+1,5°</b> no me fiaría: el modelo del terreno no sabe de
    árboles, naves ni casas.</li>
    <li><b>Zona apta</b>: qué parte del entorno mantiene margen suficiente. Distingue
    un buen sitio de un píxel con suerte.</li>
  </ul>
</section>

<footer><p>Efemérides JPL DE421 · relieve SRTM 1″ (~30 m) · topónimos de
OpenStreetMap · contrastado con IGN y NASA GSFC.
<a href="https://github.com/ouendinga/eclipse-viewfinder">Código y metodología</a>.
Hecho por <a href="https://alvarosolis.dev">Álvaro Solís</a>.</p></footer>
</div></body></html>'''


def build(out_dir=None, lang='es', preset=None, progress=None, with_overview=True):
    """Build the site: one page with everything, plus the points dataset it searches.

    The 16 static per-town pages are gone: with the precomputed points shipped as data,
    any town is answered client-side, so keeping frozen copies of a few of them would
    only mean two places to keep in sync.
    """
    import shutil
    from .paths import DATA_DIR
    out_dir = out_dir or os.path.join(REPORTS_DIR, 'site')
    os.makedirs(out_dir, exist_ok=True)
    ensure()
    if progress:
        progress('calculando el informe general')
    data = overview.build()
    html = overview.render(data,
                           finder_html=finder_ui.html(),
                           finder_css=finder_ui.CSS,
                           finder_js=finder_ui.script())
    _write(os.path.join(out_dir, 'index.html'), html)

    src = os.path.join(DATA_DIR, 'points.json')
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(out_dir, 'points.json'))
    else:
        raise FileNotFoundError(
            'Falta data/points.json. Genera los puntos recomendados primero:\n'
            '  python -c "from eclipseview import recommend; recommend.build()"')
    _write(os.path.join(out_dir, 'robots.txt'),
           'User-agent: *\nAllow: /\n')
    return out_dir, data


def _write(path, text):
    with open(path, 'w') as f:
        f.write(text)
