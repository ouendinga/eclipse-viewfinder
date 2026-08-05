# -*- coding: utf-8 -*-
"""The Spain-wide overview report.

Spanish only, on purpose: this one is an essay about a specific country's terrain,
not a template. The parameterised, translatable report is `report.render_place`.

Every figure is computed here and interpolated into the prose. Cloud statistics are
the one exception and are rendered from `sources.CLIMATOLOGY` with the attribution
attached, because we cannot derive them from ephemerides and elevation.
"""
import json
import os

import numpy as np

from . import i18n, minimap, roster, sources, verify
from .analysis import evaluate, km, path_limits, zone_stats
from .paths import MAP_SVG, SCAN_PKL
from .report import esc, _num, _margin_class, _td_class, site_note
from .style import CSS

LANG = 'es'
D = lambda v, s=True: i18n.deg(LANG, v, 2, s)        # noqa: E731
N = lambda v, d=0: i18n.number(LANG, v, d)           # noqa: E731


def build(progress=None, zone_half_km=9.0, zone_n=13):
    """Compute everything the overview needs. Returns a dict of results."""
    origin = roster.LADDER_ORIGIN
    sites = {}
    total = len(roster.SITES)
    for i, s in enumerate(roster.SITES, 1):
        if progress:
            progress(i, total, s['label'])
        row = evaluate(s['lat'], s['lon'], label=s['label'])
        row.update(key=s['key'], tier=s['tier'], role=s['role'],
                   hero=s.get('hero', False), warn=s.get('warn', False))
        row['dist'] = float(km(row['lat'], row['lon'], origin['lat'], origin['lon']))
        zl, zo, zh = s['zone']
        row['zone'] = zone_stats(zl, zo, half_km=zh or zone_half_km, n=zone_n)
        sites[s['key']] = row

    # Fail loudly: without the band-wide scan the headline silently renders em-dashes
    # instead of figures, which looks like a design choice rather than missing data.
    if not os.path.exists(SCAN_PKL):
        raise FileNotFoundError(
            f'Falta {SCAN_PKL}. El informe general necesita el barrido de la franja.\n'
            f'Ejecuta:  python -c "from eclipseview import scan; scan.main()"')
    scan = None
    if os.path.exists(SCAN_PKL):
        import pickle
        d = pickle.load(open(SCAN_PKL, 'rb'))
        clear = d['clear']
        scan = dict(n=int(clear.size),
                    blocked=float((clear < 0).mean()),
                    alt_min=float(np.nanmin(d['a_c3'])),
                    alt_max=float(np.nanmax(d['a_c2'])),
                    az_min=float(np.nanmin(d['z_c2'])),
                    az_max=float(np.nanmax(d['z_c3'])),
                    dur_max=float(np.nanmax(d['dur'])))
    lim = path_limits()
    checks = verify.run_all()
    return dict(sites=sites, scan=scan, limits=lim, checks=checks,
                summary=verify.summarise(checks), origin=origin)


# ------------------------------------------------------------------ rendering

def _site_card(r):
    cl = r['clear']
    z = r['zone']
    badge, bcls = ('TOTALIDAD', 'g') if r['total'] else (
        f"{i18n.obscuration(LANG, r['obsc'], False)} parcial",
        'w' if cl >= 2 else 'b')
    if r['warn']:
        bcls = 'b'
        badge = 'BLOQUEADO' if cl < 0 else 'MUY JUSTO'
    nums = [
        _num('coordenadas', f"{N(r['lat'], 4)}, {N(r['lon'], 4)}"),
        _num('altitud', f"{r['elev']} m"),
        _num('totalidad', f"{N(r['dur'], 0)} s" if r['total'] else '—'),
        _num('sol al final', i18n.deg(LANG, r['alt'], 2), 'hi'),
        _num('horizonte real', D(r['horizon'])),
        _num('margen libre', D(cl), _margin_class(cl)),
        _num('hora (CEST)', (r['c2_local'] or r['max_local'])[:5]),
        (f'<div class="num dcol" data-lat="{r["lat"]:.5f}" data-lon="{r["lon"]:.5f}">'
         f'<div class="k">distancia</div><div class="v">—</div></div>'),
    ]
    if z:
        nums.append(_num('zona apta', f"{N(z['frac_ok'] * 100, 0)}%"))
    zone_txt = ''
    if z:
        zone_txt = (f" En un cuadrado de {N(z['half_km'] * 2, 0)} km alrededor, "
                    f"<b>{N(z['frac_ok'] * 100, 1)}%</b> del terreno mantiene más de "
                    f"{D(z['threshold'])} de margen (mediana {D(z['median'])}, "
                    f"peor punto {D(z['worst'])}).")
    klass = ' hero' if r['hero'] else (' bad' if r['warn'] else '')
    return f'''
<article class="site{klass}">
  <div class="site-h">
    <h3>{esc(r['label'])}</h3>
    <span class="place">{esc(r.get('place') or '')}</span>
    <span class="badge {bcls}">{badge}</span>
  </div>
  <div class="nums">{''.join(nums)}</div>
  <div class="panowrap">{r['svg']}</div>
  <div class="why">{esc(r['role'])}{zone_txt} {site_note(r, LANG)}</div>
</article>'''


# «¿A cuántos km me queda?» no tiene respuesta hasta que el lector dice desde dónde
# viene. Antes se contestaba siempre desde Barcelona, que para quien lee esto desde
# Vigo es ruido. Se marcan las celdas con su coordenada y el buscador las rellena con
# el origen que ponga; hasta entonces valen «—», que es la marca de «no aplica» que ya
# usa el resto de la página.
def _dist_th():
    return '<th class="dcol">km hasta el punto</th>'


def _dist_td(r):
    return (f'<td class="dcol" data-lat="{r["lat"]:.5f}" '
            f'data-lon="{r["lon"]:.5f}">—</td>')


def _ladder(sites):
    rows = []
    for key in roster.LADDER:
        r = sites.get(key)
        if not r:
            continue
        rows.append(
            f"<tr><td>{esc(r['label'])}</td>{_dist_td(r)}"
            f"<td>{N(r['dur'], 0) + ' s' if r['total'] else '—'}</td>"
            f"<td>{i18n.deg(LANG, r['alt'], 1)}</td>"
            f"<td class=\"{_td_class(r['clear'])}\">{D(r['clear'])}</td>"
            f"<td>{N(r['zone']['frac_ok'] * 100, 0) + '%' if r['zone'] else '—'}</td>"
            f"</tr>")
    return ('<div class="tablewrap"><table><thead><tr><th>sitio</th>'
            f'{_dist_th()}<th>totalidad</th><th>sol</th>'
            '<th>margen</th><th>zona apta</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


def _full_table(sites):
    rows = []
    for r in sorted(sites.values(), key=lambda x: (-x['total'], -x['clear'])):
        z = r['zone']
        rows.append(
            f"<tr><td>{esc(r['label'])}</td>"
            f"<td>{N(r['lat'], 4)}, {N(r['lon'], 4)}</td><td>{r['elev']}</td>"
            f"<td>{N(r['dur'], 0) if r['total'] else '—'}</td>"
            f"<td>{i18n.obscuration(LANG, r['obsc'], r['total'])}</td>"
            f"<td>{i18n.deg(LANG, r['alt'], 2)}</td>"
            f"<td>{i18n.deg(LANG, r['az'], 1)}</td>"
            f"<td>{D(r['horizon'])}</td>"
            f"<td class=\"{_td_class(r['clear'])}\">{D(r['clear'])}</td>"
            f"<td>{N(z['frac_ok'] * 100, 0) + '%' if z else '—'}</td>"
            f"{_dist_td(r)}</tr>")
    return ('<div class="tablewrap"><table><thead><tr><th>sitio</th>'
            '<th>lat, lon</th><th>m</th><th>totalidad s</th><th>sol oculto</th>'
            '<th>altura sol</th><th>azimut</th><th>horizonte</th><th>margen</th>'
            f'<th>zona apta</th>{_dist_th()}</tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


def _climatology():
    c = sources.CLIMATOLOGY
    items = ''.join(
        f"<tr><td>{esc(r['label'])}</td><td style=\"text-align:left;"
        f"font-family:var(--sans);white-space:normal\">{esc(r['rating'])}</td>"
        f"<td style=\"text-align:left;font-family:var(--sans);white-space:normal;"
        f"color:var(--muted)\">{esc(r['text'])}</td></tr>"
        for r in c['regions'])
    return f'''
<section>
  <p class="eyebrow">Dato externo, no calculado por mí</p>
  <h2>Dónde suele estar despejado</h2>
  <p class="prose">Esto no sale de las efemérides ni del relieve: es
  <b>climatología publicada</b> de agosto. La incluyo porque sin ella el análisis de
  terreno te puede mandar al sitio con el mejor horizonte y las peores nubes.</p>
  <div class="tablewrap"><table><thead><tr><th>zona</th><th>pronóstico</th>
  <th>qué dice la fuente</th></tr></thead><tbody>{items}</tbody></table></div>
  <p class="caption">{esc(c['note'])} Fuente: {sources.cite(c['source'])}.</p>
  <div class="note">{esc(c['low_sun_warning'])}</div>
</section>'''


def _verification(checks, summary):
    rows = []
    for g in checks:
        for it in g['items']:
            ok = '✓' if it['ok'] else '✗'
            cls = 'g' if it['ok'] else 'b'
            src = g.get('source')
            src_html = sources.cite(src) if src in sources.CITATIONS else esc(
                g.get('source_url') or src or '')
            rows.append(
                f"<tr><td>{esc(g['name'])} — {esc(it['what'])}</td>"
                f"<td>{esc(it['ours'])} {esc(it['unit'])}</td>"
                f"<td>{esc(it['published'])} {esc(it['unit'])}</td>"
                f"<td class=\"{cls}\">{ok}</td>"
                f"<td style=\"text-align:left;font-family:var(--sans);"
                f"white-space:normal;color:var(--muted)\">{src_html}</td></tr>")
    return f'''
<section>
  <h2>Cómo sé que esto no me lo estoy inventando</h2>
  <p class="prose">Esta tabla no está escrita a mano: se calcula cada vez que se
  genera el informe, comparando el motor con valores publicados y con cálculos
  analíticos. Ahora mismo pasan
  <b>{summary['passed']} de {summary['total']}</b>.</p>
  <div class="tablewrap"><table><thead><tr><th>comprobación</th><th>calculado</th>
  <th>publicado</th><th>ok</th><th>fuente</th></tr></thead><tbody>
  {''.join(rows)}</tbody></table></div>
</section>'''


def render(data, finder_html='', finder_css='', finder_js=''):
    s = data['sites']
    scan = data['scan']
    lim = data['limits']

    alt_hi = max(r['alt_start'] for r in s.values())
    alt_lo = min(r['alt'] for r in s.values())
    az_lo = min(r['az'] for r in s.values())
    az_hi = max(r['az'] for r in s.values())
    best_dur = max((r['dur'] for r in s.values() if r['total']), default=0)
    scanned = f"{scan['n']:,}".replace(',', '.') if scan else '—'
    blocked_pct = N(scan['blocked'] * 100, 1) + '%' if scan else '—'

    tiers = ''
    for t in roster.TIERS:
        cards = ''.join(_site_card(r) for r in
                        sorted((x for x in s.values() if x['tier'] == t['key']),
                               key=lambda x: -x['clear']))
        if not cards:
            continue
        tiers += (f'<section><p class="eyebrow">{esc(t["eyebrow"])}</p>'
                  f'<h2>{esc(t["title"])}</h2>'
                  f'<p class="prose">{esc(t["intro"])}</p>{cards}</section>')

    others = ''.join(
        f"<li><b>{esc(o['date'])}</b> — {esc(o['kind'])} sobre {esc(o['where'])}: "
        f"{esc(o['headline'])} ({sources.cite(o['source'])}).</li>"
        for o in sources.OTHER_ECLIPSES)

    map_svg = open(MAP_SVG).read() if os.path.exists(MAP_SVG) else ''
    width_txt = (f"entre {N(lim['width_min'], 0)} y {N(lim['width_max'], 0)} km "
                 f"({N(lim['width_mean'], 0)} km de media)") if lim else '—'

    body = f'''
<header class="top">
  <p class="eyebrow">{esc(sources.EVENT['name'])} · análisis de terreno</p>
  <h1>El sitio no lo decide el pueblo.<br>Lo decide el horizonte.</h1>
  <p class="lede">Durante la totalidad el Sol estará entre
  <b>{i18n.deg(LANG, alt_lo, 1)} y {i18n.deg(LANG, alt_hi, 1)}</b> sobre el horizonte,
  en el azimut <b>{i18n.deg(LANG, az_lo, 0)}–{i18n.deg(LANG, az_hi, 0)}</b>
  (oeste-noroeste). A esa altura, una loma a 3 km o una sierra a 80 km se lo come.
  He calculado la geometría del eclipse y el perfil real del terreno en esa dirección
  para <b>{scanned} puntos</b> de la franja.</p>
</header>

{finder_html}

<section>
  <h2>Lo esencial</h2>
  <div class="facts">
    <div class="fact"><div class="k">Duración máxima</div>
      <div class="v">{N(best_dur, 0)} s</div>
      <div class="n">de los sitios analizados, en la línea central</div></div>
    <div class="fact"><div class="k">Altura del Sol</div>
      <div class="v">{i18n.deg(LANG, alt_hi, 0)} → {i18n.deg(LANG, alt_lo, 0)}</div>
      <div class="n">de Asturias a Baleares. Cuanto más al este, más bajo</div></div>
    <div class="fact"><div class="k">Azimut</div>
      <div class="v">{i18n.deg(LANG, az_lo, 0)} → {i18n.deg(LANG, az_hi, 0)}</div>
      <div class="n">hacia dónde mirar: ONO, no el oeste exacto</div></div>
    <div class="fact"><div class="k">Terreno que estorba</div>
      <div class="v">{blocked_pct}</div>
      <div class="n">de la franja tiene el Sol tapado por el relieve</div></div>
    <div class="fact"><div class="k">Anchura de la sombra</div>
      <div class="v">{N(lim['width_mean'], 0) if lim else '—'} km</div>
      <div class="n">sobre España, resuelta por bisección</div></div>
    <div class="fact"><div class="k">Verificación</div>
      <div class="v">{data['summary']['passed']}/{data['summary']['total']}</div>
      <div class="n">comprobaciones contra NASA, IGN y cálculo analítico</div></div>
  </div>
  <div class="note">
    <b>Hay más eclipses, y el que viene es mucho más fácil.</b>
    <ul>{others}</ul>
    El de 2026 es el difícil de los tres: también el más fotogénico, porque la corona
    sale junto al paisaje y no en lo alto del cielo.
  </div>
</section>

<section>
  <h2>Dónde cae la franja</h2>
  <div class="mapbox">{map_svg}</div>
  <div class="legendrow">
    <span><i style="background:#ff9b3d"></i>línea central</span>
    <span><i style="background:#ffd9a0"></i>franja de totalidad</span>
    <span><i style="background:#8ce99a"></i>buen margen</span>
    <span><i style="background:#ffe066"></i>aceptable</span>
    <span><i style="background:#ff5c5c"></i>bloqueado</span>
  </div>
  <p class="caption">Relieve dibujado con el mismo modelo de elevación
  ({sources.cite('srtm')}) que uso para los cálculos. Los bordes los he resuelto por
  bisección con el motor de eclipses, no interpolando: sobre España la sombra mide
  <b>{width_txt}</b>.</p>
</section>

<section>
  <h2>Qué se gana yendo más al oeste</h2>
  <p class="prose">Cuanto más al oeste, más alto está el Sol, más dura la totalidad y
  más perdona el terreno. La columna que de verdad importa es <b>zona apta</b>: qué
  porcentaje del entorno mantiene margen suficiente, o sea cuánto perdona el sitio si
  no aciertas con el punto exacto. Si pones tu localidad en el buscador de arriba, la
  columna de kilómetros se recalcula desde ahí.</p>
  {_ladder(s)}
</section>

{tiers}

<section>
  <h2>Todo junto</h2>
  {_full_table(s)}
  <p class="caption"><b>margen</b> = grados entre el Sol y el terreno real durante
  todo el evento (negativo = el Sol se pone antes). <b>zona apta</b> = porcentaje del
  entorno que mantiene más de {D(2.0)} de margen. Las distancias son en línea recta
  desde la localidad que pongas en el buscador; por carretera, cuenta aproximadamente
  un 25 % más.</p>
</section>

{_climatology()}

{_verification(data['checks'], data['summary'])}


<section id="fuentes">
  <p class="eyebrow">De dónde sale cada dato</p>
  <h2>Fuentes</h2>
  <p class="prose">Regla del proyecto: <b>cada cifra o la calcula el código, o tiene
  cita</b>. Lo que no es ninguna de las dos cosas no entra.</p>
  <div class="tablewrap"><table><thead><tr><th>dato</th><th>fuente</th>
  <th>licencia</th></tr></thead><tbody>
    <tr><td>Geometría del eclipse (contactos, duración, magnitud, obscuración,
        altura y azimut del Sol)</td><td>calculado con efemérides
        {sources.cite('de421')}</td><td>dominio público</td></tr>
    <tr><td>Relieve y perfil del horizonte</td><td>SRTM 1&Prime; (~30 m) vía
        {sources.cite('srtm')}</td><td>dominio público</td></tr>
    <tr><td>Árboles, edificios y vías de acceso</td><td>{sources.cite('overpass')}</td><td>ODbL</td></tr>
    <tr><td>Topónimos</td><td>{sources.cite('osm')}</td><td>ODbL</td></tr>
    <tr><td>Nubosidad de agosto</td><td>{sources.cite('eclipsophile')}</td><td>citada, no
        redistribuida</td></tr>
    <tr><td>Contraste de los cálculos</td><td>{sources.cite('ign')} y {sources.cite('nasa_gsfc')}</td><td>citadas</td></tr>
  </tbody></table></div>
  <p class="caption">El código es público y la metodología está escrita:
  <a href="https://github.com/ouendinga/eclipse-viewfinder">github.com/ouendinga/eclipse-viewfinder</a>.
  Los cálculos son reproducibles: mismo commit y mismos datos, mismos números.</p>
</section>

<section id="aviso">
  <p class="eyebrow">Léelo antes de conducir 200 km</p>
  <h2>Aviso: esto no es una garantía</h2>
  <div class="note warn">
    <p><b>No me hago responsable de que llegues a ver el eclipse.</b> Esto es una
    herramienta de cálculo, no una promesa. Aunque la geometría sea correcta, entre tú
    y la corona hay cosas que ningún modelo controla: <b>nubes, calima, humo de
    incendios</b> o simplemente que ese día haga mal tiempo.</p>

    <p><b>Los datos no son 100 % fiables.</b> Con nombres y apellidos:</p>
    <ul>
      <li>Las <b>duraciones</b> llevan un sesgo de +2–3 % frente al IGN por el convenio
      de radio lunar: cuéntalas como ±3 s. Para horarios oficiales, el IGN.</li>
      <li>No modelo el <b>perfil real del limbo lunar</b>. Justo en el borde de la
      franja, eso es lo que decide entre ver corona y no verla.</li>
      <li>El relieve es SRTM: <b>no ve árboles ni edificios</b>. Eso se cubre aparte
      con OpenStreetMap, pero <b>no en todos los puntos</b> — los que no se han podido
      comprobar lo dicen.</li>
      <li>Las <b>alturas del arbolado son estimadas</b> (18 m de pinar maduro): OSM
      casi nunca las trae.</li>
      <li>La <b>refracción</b> cerca del horizonte varía con la temperatura y puede
      mover el terreno lejano una o dos décimas de grado.</li>
      <li>La <b>nubosidad</b> es climatología de años anteriores, <b>no un
      pronóstico</b>.</li>
    </ul>

    <p><b>Ni el acceso ni el punto están garantizados.</b> Las coordenadas son puntos
    del <b>terreno</b>, elegidos por su horizonte, no por poder aparcar allí. La
    información de accesibilidad sale de OpenStreetMap, que lo mantiene gente
    voluntaria: puede estar incompleta, desactualizada o equivocada. <b>Un punto puede
    caer en finca privada, en camino cerrado o en terreno protegido.</b> Comprueba el
    acceso en el mapa antes de ir, respeta las propiedades y las señales, y no te
    metas donde no debes.</p>

    <p class="prose"><b>Lo que sí puedes hacer para asegurarte:</b> ir un par de días
    antes a la misma hora. El 10 de agosto a las 20:30 el Sol estará casi en el mismo
    sitio, así que verás con tus ojos lo que ningún modelo puede confirmarte — el pino,
    la nave, el poste y si se llega.</p>
  </div>
</section>'''

    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eclipse Viewfinder — desde dónde ver el eclipse del 12 de agosto de 2026</title>
<meta name="description" content="Desde dónde ver el eclipse total del 12 de agosto de 2026 en España teniendo en cuenta el terreno real, los árboles y los edificios. El Sol estará entre 2° y 12°: una loma cercana lo tapa.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E%3Ccircle cx=%2216%22 cy=%2216%22 r=%2213%22 fill=%22%23e08a2e%22/%3E%3Ccircle cx=%2221%22 cy=%2213%22 r=%2213%22 fill=%22%230e131a%22/%3E%3C/svg%3E">
<style>{CSS}
{finder_css}
{minimap.CSS}</style></head><body>
{minimap.html()}
<div class="wrap">{body}
<footer><p>Efemérides {sources.cite('de421')} · relieve {sources.cite('srtm')} ·
topónimos {sources.cite('osm')} · contraste con {sources.cite('ign')} y
{sources.cite('nasa_gsfc')}. Hora peninsular = UTC+2.
<a href="https://github.com/ouendinga/eclipse-viewfinder">Código y metodología</a>.
Hecho por <a href="https://alvarosolis.dev">Álvaro Solís</a>.</p></footer>
</div>
{finder_js}
{minimap.script()}
<!-- Vercel Web Analytics: sin cookies y sin datos personales, así que no hace falta
     banner de consentimiento. Se sirve desde el propio dominio, no desde un tercero.
     Requiere tenerlo activado en el panel del proyecto (ver docs/pending-human.md);
     si no lo está, el script da 404 y la página sigue funcionando igual. -->
<script defer src="/_vercel/insights/script.js"></script>
</body></html>'''
