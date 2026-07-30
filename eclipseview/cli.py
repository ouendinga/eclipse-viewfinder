# -*- coding: utf-8 -*-
"""Command line interface.

    eclipseview places "Malgrat de Mar"          # candidatos validados
    eclipseview place  "Malgrat de Mar" -r 45    # informe de miradores
    eclipseview overview                          # informe general de España
    eclipseview coverage "Lisboa" -r 40           # qué datos faltarían
    eclipseview check                             # verificación del motor
"""
import argparse
import json
import os
import sys

from . import coverage, events, gazetteer, i18n, jobs, verify
from .analysis import evaluate, km, search_area
from .paths import REPORTS_DIR, ensure, missing as missing_prereqs


def _pick(query, lang, country, index=None, interactive=True):
    """Resolve a place name to ONE candidate, always via an explicit list."""
    cands = gazetteer.search(query, lang=lang, country_codes=country)
    if index is not None:
        if not 1 <= index <= len(cands):
            sys.exit(f'--pick {index} fuera de rango (hay {len(cands)})')
        return cands[index - 1]
    if len(cands) == 1:
        return cands[0]
    print(f'"{query}" tiene {len(cands)} coincidencias:', file=sys.stderr)
    for i, c in enumerate(cands, 1):
        print(f'  {i}. {gazetteer.describe(c)}   [{c["osm_type"]}/{c["osm_id"]}]',
              file=sys.stderr)
    if not interactive or not sys.stdin.isatty():
        sys.exit('Elige una con --pick N (no invento cuál querías).')
    while True:
        try:
            n = int(input('Número: '))
            if 1 <= n <= len(cands):
                return cands[n - 1]
        except (ValueError, EOFError):
            sys.exit(1)


# ------------------------------------------------------------------ commands

def cmd_places(a):
    for i, c in enumerate(gazetteer.search(a.query, lang=a.lang,
                                           country_codes=a.country,
                                           limit=a.limit), 1):
        print(f'{i}. {gazetteer.describe(c)}')
        print(f'     {c["lat"]:.5f}, {c["lon"]:.5f}   '
              f'{c["osm_type"]}/{c["osm_id"]}   ({c["kind"]}/{c["place_type"]})')


def cmd_coverage(a):
    c = _pick(a.query, a.lang, a.country, a.pick, interactive=not a.no_input) \
        if a.query else dict(lat=a.lat, lon=a.lon, name=f'{a.lat},{a.lon}')
    rep = coverage.report(c['lat'], c['lon'], a.radius)
    print(f"Origen: {c.get('name')} ({c['lat']:.4f}, {c['lon']:.4f}), radio "
          f"{a.radius:.0f} km")
    print(f"  teselas necesarias : {rep['needed']}")
    print(f"  ya descargadas     : {rep['have']}")
    print(f"  faltan             : {rep['missing_count']}  (~{rep['mb']} MB)")
    if rep['missing']:
        print('  ' + ', '.join(coverage.tile_name(*t)
                               for t in rep['missing'][:12])
              + (' ...' if len(rep['missing']) > 12 else ''))
        if a.fetch:
            got, sea, failed = coverage.fetch(
                rep['missing'],
                progress=lambda i, n, nm: print(f'    [{i}/{n}] {nm}'))
            print(f'  descargadas {len(got)}, solo mar {len(sea)}, '
                  f'fallos {len(failed)}')
            if failed:
                for t, why in failed:
                    print(f'    ! {coverage.tile_name(*t)}: {why}')
            print('  ahora ejecuta:  eclipseview build-mosaic')
    else:
        print('  COMPLETO: esta consulta se resuelve sin descargar nada.')


def cmd_place(a):
    ev = events.get(a.event)
    if not events.is_ready(ev.key):
        sys.exit(f'El evento {ev.key} aún no tiene datos precalculados en este repo.')
    gaps = missing_prereqs()
    if gaps:
        sys.exit('Faltan datos base: ' + ', '.join(gaps) + '. Ejecuta: eclipseview setup')

    # Resolve and check coverage BEFORE opening the progress bar. Both are quick, and
    # sizing the bar needs their answers -- a bar whose total changes mid-run is
    # exactly the fake progress this project is trying not to ship.
    if not a.quiet:
        print('Localizando el sitio...', file=sys.stderr)
    origin = (_pick(a.query, a.lang, a.country, a.pick, interactive=not a.no_input)
              if a.query else dict(name=f'{a.lat:.4f}, {a.lon:.4f}',
                                   lat=a.lat, lon=a.lon, admin=[], country=None,
                                   osm_type=None, osm_id=None))
    label = gazetteer.describe(origin) if origin.get('osm_id') else origin['name']
    rep = coverage.report(origin['lat'], origin['lon'], a.radius)
    if not a.quiet:
        print(f"{label}\n{rep['have']}/{rep['needed']} teselas de elevación "
              f"disponibles" + (f", faltan {rep['missing_count']} (~{rep['mb']} MB)"
                                if rep['missing'] else ' (completo)'),
              file=sys.stderr)

    n_manual = len(a.also) + len(a.peak)
    reporter = jobs.cli_reporter(not a.quiet)
    stream = open(a.progress_json, 'w') if a.progress_json else None
    job = jobs.Job('place',
                   jobs.plan_for_place(rep['missing_count'], a.top + n_manual,
                                       bool(rep['missing'])),
                   on_event=reporter, stream=stream)
    if rep['missing']:
        if not a.fetch:
            sys.exit(f"\nFaltan {rep['missing_count']} teselas de elevación "
                     f"(~{rep['mb']} MB) para cubrir esta zona y sus visuales.\n"
                     f"Repite con --fetch para descargarlas, o mira "
                     f"'eclipseview coverage'.")
        job.stage('download', f"Descargando {rep['missing_count']} teselas")
        coverage.fetch(rep['missing'],
                       progress=lambda i, n, nm: job.step(i, n, nm))
        job.stage('mosaic', 'Reconstruyendo el mosaico de elevación')
        from . import demdata
        demdata.main()

    job.stage('scan', f'Explorando {a.radius:.0f} km de terreno')
    auto, n_cand, n_ok = search_area(origin['lat'], origin['lon'], a.radius,
                                     min_clear=a.min_clear, want=a.top,
                                     sep_km=a.sep)
    job.info(f'{n_cand} puntos evaluados, {n_ok} con margen suficiente')

    manual = [(_parse_pt(s), 0.0) for s in a.also] + \
             [(_parse_pt(s), a.snap) for s in a.peak]

    job.stage('refine', 'Recomprobando finalistas a 30 m')
    rows, kept, i = [], 0, 0
    for (lat, lon, lab), snap in manual:
        i += 1
        job.step(i, len(manual) + a.top, lab or 'punto propio')
        rows.append(evaluate(lat, lon, lab, snap_km=snap))
    for lat, lon in auto:
        if kept >= a.top:
            break
        i += 1
        job.step(i, len(manual) + a.top, f'{lat:.3f},{lon:.3f}')
        r = evaluate(lat, lon)
        if r['clear'] < a.min_clear:
            continue          # the 185 m pass can be wrong on steep ground
        rows.append(r)
        kept += 1

    job.stage('label', 'Poniendo nombre a los sitios')
    for n, r in enumerate(rows, 1):
        job.step(n, len(rows), '')
        r['place'] = gazetteer.reverse(r['lat'], r['lon'], lang=a.lang)
        r['dist'] = float(km(r['lat'], r['lon'], origin['lat'], origin['lon']))
    rows.sort(key=lambda r: (-r['dur'], -r['clear']))

    job.stage('render', 'Generando el informe')
    from . import report as rep_mod
    summary = verify.summarise(verify.run_all(include_width=False)) \
        if a.verify else None
    html = rep_mod.render_place(dict(label=label, lat=origin['lat'],
                                     lon=origin['lon']),
                                a.radius, rows, a.min_clear, lang=a.lang,
                                event=ev, verification=summary)
    ensure()
    out = a.out or os.path.join(REPORTS_DIR, f'place_{_slug(origin["name"])}.html')
    open(out, 'w').write(html)
    json.dump([{k: v for k, v in r.items() if k != 'svg'} for r in rows],
              open(out.replace('.html', '.json'), 'w'), ensure_ascii=False, indent=1)
    job.finish(output=out)
    if stream:
        stream.close()
    print(f'\n{out}')
    for r in rows[:12]:
        print(f"  {(r.get('label') or r['place'])[:38]:38s} {r['elev']:5.0f} m  "
              f"{r['dist']:6.1f} km  oculto {r['obsc']:6.2f}%  "
              f"margen {r['clear']:+6.2f}")


def _parse_pt(s):
    p = s.split(',')
    return float(p[0]), float(p[1]), (','.join(p[2:]).strip() or None)


def _slug(s):
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ''.join(c if c.isalnum() else '-' for c in s.lower()).strip('-')[:40]


def cmd_overview(a):
    from . import overview
    gaps = missing_prereqs()
    if gaps:
        sys.exit('Faltan datos base: ' + ', '.join(gaps) + '. Ejecuta: eclipseview setup')
    print('Calculando el informe general (esto tarda unos minutos)...')
    data = overview.build(progress=lambda i, n, lbl:
                          print(f'  [{i}/{n}] {lbl}'))
    ensure()
    out = a.out or os.path.join(REPORTS_DIR, 'overview.html')
    open(out, 'w').write(overview.render(data))
    print(f'\n{out}')
    print(f"verificación: {data['summary']['passed']}/{data['summary']['total']}")


def cmd_check(a):
    groups = verify.run_all()
    width = 0
    for g in groups:
        print(f"\n{g['name']}  [{g.get('detail', '')}]")
        for it in g['items']:
            mark = 'OK  ' if it['ok'] else 'FALLA'
            ours = it['ours']
            if isinstance(ours, float):
                ours = round(ours, 3)
            print(f"  {mark} {it['what']:26s} calculado={ours} "
                  f"publicado={it['published']} {it['unit']}")
            width += 1
    s = verify.summarise(groups)
    print(f"\n{s['passed']}/{s['total']} comprobaciones pasan")
    return 0 if not s['failed'] else 1


def cmd_setup(a):
    from . import demdata
    ensure()
    print('1) mosaico de elevación')
    demdata.main()
    print('2) campo del eclipse (paralelo, unos minutos)')
    from . import field_build
    field_build.main()
    print('listo.')


def cmd_build_mosaic(a):
    from . import demdata
    demdata.main()


def cmd_site(a):
    from . import site
    out, entries = site.build(out_dir=a.out, lang=a.lang,
                              progress=lambda m: print(f'  {m}', flush=True),
                              with_overview=not a.no_overview)
    print(f'\n{len(entries)} sitios -> {out}')


def cmd_langs(a):
    for lang in i18n.available():
        gaps = i18n.check(lang)
        print(f"{lang}  ({i18n.t(lang, 'lang_name')})  "
              f"{'completo' if not gaps else f'faltan {len(gaps)}: {gaps[:5]}'}")


# ------------------------------------------------------------------ parser

def build_parser():
    p = argparse.ArgumentParser(prog='eclipseview', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--event', default=None, help='clave del eclipse (por defecto tse2026)')
    sub = p.add_subparsers(dest='cmd', required=True)

    def common_place(sp):
        sp.add_argument('query', nargs='?', help='nombre del sitio')
        sp.add_argument('--lat', type=float); sp.add_argument('--lon', type=float)
        sp.add_argument('--pick', type=int, help='elegir el candidato N sin preguntar')
        sp.add_argument('--country', default=None, help='p.ej. es,fr')
        sp.add_argument('--lang', default='es', choices=i18n.available())
        sp.add_argument('--no-input', action='store_true')

    sp = sub.add_parser('places', help='buscar candidatos validados')
    sp.add_argument('query'); sp.add_argument('--limit', type=int, default=8)
    sp.add_argument('--country', default=None)
    sp.add_argument('--lang', default='es')
    sp.set_defaults(func=cmd_places)

    sp = sub.add_parser('place', help='informe de miradores cerca de un sitio')
    common_place(sp)
    sp.add_argument('-r', '--radius', type=float, default=45.0)
    sp.add_argument('--top', type=int, default=6)
    sp.add_argument('--min-clear', type=float, default=1.5)
    sp.add_argument('--sep', type=float, default=None)
    sp.add_argument('--snap', type=float, default=1.0)
    sp.add_argument('--also', action='append', default=[], metavar='LAT,LON,NOMBRE')
    sp.add_argument('--peak', action='append', default=[], metavar='LAT,LON,NOMBRE')
    sp.add_argument('--fetch', action='store_true', help='descargar datos que falten')
    sp.add_argument('--verify', action='store_true', help='incluir el resumen de verificación')
    sp.add_argument('--progress-json', default=None, help='volcar eventos NDJSON aquí')
    sp.add_argument('--quiet', action='store_true')
    sp.add_argument('-o', '--out', default=None)
    sp.set_defaults(func=cmd_place)

    sp = sub.add_parser('coverage', help='qué datos harían falta')
    common_place(sp)
    sp.add_argument('-r', '--radius', type=float, default=45.0)
    sp.add_argument('--fetch', action='store_true')
    sp.set_defaults(func=cmd_coverage)

    sp = sub.add_parser('overview', help='informe general de España')
    sp.add_argument('-o', '--out', default=None)
    sp.set_defaults(func=cmd_overview)

    sp = sub.add_parser('check', help='verificar el motor contra valores publicados')
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser('setup', help='construir mosaico y campo del eclipse')
    sp.set_defaults(func=cmd_setup)

    sp = sub.add_parser('build-mosaic', help='reconstruir solo el mosaico')
    sp.set_defaults(func=cmd_build_mosaic)

    sp = sub.add_parser('site', help='generar el sitio estatico con lugares precalculados')
    sp.add_argument('-o', '--out', default=None)
    sp.add_argument('--lang', default='es')
    sp.add_argument('--no-overview', action='store_true')
    sp.set_defaults(func=cmd_site)

    sp = sub.add_parser('langs', help='idiomas disponibles y huecos de traducción')
    sp.set_defaults(func=cmd_langs)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    if getattr(a, 'query', None) is None and getattr(a, 'lat', None) is None \
            and a.cmd in ('place', 'coverage'):
        sys.exit('Dame un nombre de sitio o --lat/--lon.')
    return a.func(a) or 0


if __name__ == '__main__':
    sys.exit(main())
