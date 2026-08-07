# -*- coding: utf-8 -*-
"""Miradores precalculados para un eclipse.

La idea que permite que el sitio funcione sin servidor: la respuesta a «desde dónde
voy si salgo de X» no depende de X. Es siempre el mismo conjunto de buenos miradores;
X y el radio sólo deciden cuáles caen cerca. Así que los miradores se calculan una
vez, se publican, y la consulta se queda en un filtro.

Este conjunto vale para UN eclipse: el azimut y la altura del Sol en cada punto están
horneados dentro de los márgenes y del horizonte dibujado.

Salida (points.json):
  meta   - evento, ventana de azimut, cómo se construyó el conjunto
  points - una entrada por mirador, con un perfil de horizonte compacto para que el
           navegador dibuje el panorama sin mandar un SVG por punto.
"""
import json
import math
import os
import pickle

import numpy as np

from . import events, gazetteer, obstacles
from .analysis import evaluate, km
from .ephem import circumstances, sun_track
from .panorama import AZ_LO, AZ_HI
from .paths import DATA_DIR, SCAN_PKL

# Se prefiere el barrido seleccionado por magnitud: llega al terreno de parcial
# profundo fuera de la franja, así que un pueblo 100 km al norte de la sombra recibe
# miradores en vez de una lista vacía.
WIDE_PKL = os.path.join(DATA_DIR, 'scan_wide.pkl')
from .terrain import elev_fine, horizon_fine

# El horizonte se muestrea en toda la ventana dibujada; 0,25° es más fino que el
# diámetro del Sol.
AZ_STEP = 0.25
AZIMUTHS = np.arange(AZ_LO, AZ_HI + 1e-9, AZ_STEP)

MIN_CLEAR = 2.0        # recomendar exige margen de verdad, no que salga positivo
SEP_KM = 14.0          # separación dentro de la franja; ~1100 celdas sobre la banda
SEP_KM_PARTIAL = 25.0  # fuera de la franja las celdas son más gruesas
MAX_POINTS = 700

# Por encima de este margen da igual cuánto más haya: 8° son quince veces el diámetro
# del Sol y nadie nota la diferencia entre eso y 20°. El score lo recorta aquí, y eso
# tiene una consecuencia que hay que mirar de frente: en el 27 % de los puntos el
# criterio satura y deja de desempatar, así que quien decide pasa a ser la geometría
# pura. `rescue.py` usa este mismo tope para saber dónde puede cambiar un punto por
# otro sin perder nada.
CLEAR_SATURATION = 8.0


def cell_key(lat, lon, total, sep_km=SEP_KM, sep_km_partial=SEP_KM_PARTIAL):
    """La celda de la rejilla en la que cae un punto. Una sola definición.

    La tenían copiada `select()` y el rescate de accesos; si se separan, el rescate
    busca alternativas en una celda que no es la del punto que quiere sustituir y no
    encuentra nada, o peor, encuentra a cien kilómetros.
    """
    cell_km = sep_km if total else sep_km_partial
    c = cell_km / 111.2
    return (bool(total), int(lat / c),
            int(lon / (c / np.cos(np.radians(lat)))))


def select(scan_path=None, min_clear=MIN_CLEAR, sep_km=SEP_KM,
           sep_km_partial=25.0, max_points=2000, progress=None):
    """Coge el MEJOR mirador de cada celda, no los mejores del ranking global.

    Ordenar globalmente parece lo sensato y está mal: la totalidad le gana a todo, así
    que el cupo entero cae dentro de la franja y un pueblo a 100 km fuera se queda sin
    resultados. Aquí lo que se exige es cobertura, así que el mapa se parte en celdas
    y cada celda aporta su propio mejor sitio.

    Las celdas son más finas dentro de la franja (donde la gente va a ir de verdad) y
    más gruesas fuera, que mantiene el conjunto pequeño sin dejar agujeros.
    """
    scan_path = scan_path or (WIDE_PKL if os.path.exists(WIDE_PKL) else SCAN_PKL)
    with open(scan_path, 'rb') as f:
        d = pickle.load(f)
    lat, lon, clear, dur = d['lat'], d['lon'], d['clear'], d['dur']
    alt = d['a_c3']

    ok = clear >= min_clear
    idx = np.where(ok)[0]
    score = (np.minimum(clear[idx], CLEAR_SATURATION) + dur[idx] / 20.0
             + np.minimum(alt[idx], 12) * 0.5)

    best = {}
    for pos, i in enumerate(idx):
        total = dur[i] >= 1.0
        key = cell_key(lat[i], lon[i], total, sep_km, sep_km_partial)
        cur = best.get(key)
        if cur is None or score[pos] > cur[0]:
            best[key] = (score[pos], int(i))

    # El tope se aplica por categoría. Un tope global ordenado por puntuación es
    # justo el fallo que esta función existe para evitar: la totalidad siempre lo gana
    # y las celdas de parcial —de las que depende una ciudad fuera de la franja— se
    # quedan cortadas.
    tot = sorted(((k, v) for k, v in best.items() if k[0]), key=lambda t: -t[1][0])
    par = sorted(((k, v) for k, v in best.items() if not k[0]), key=lambda t: -t[1][0])
    # Sin tope global: cada celda que existe es un sitio donde alguien puede estar.
    n_tot = min(len(tot), max_points)
    n_par = min(len(par), max_points)
    picks = [v[1] for _, v in tot[:n_tot]] + [v[1] for _, v in par[:n_par]]
    if progress:
        progress(len(picks), len(picks), f'seleccionando ({n_tot} totalidad, {n_par} parciales)')
    return d, picks


def point_at(la, lo, event=None, index=0, prof=None, elev=None):
    """Un punto publicable, con su horizonte fino a 30 m y su geometría.

    Está fuera de `build()` porque el rescate de accesos y el recálculo de geometría
    también fabrican puntos, y tres copias de esto se separan a la primera: bastaría
    con que una redondease distinto para que el mismo sitio saliera con dos cifras
    según por dónde hubiera entrado.

    Con `prof` se reutiliza el perfil del horizonte de una pasada anterior en vez de
    volver a trazarlo. El terreno no se mueve, y trazarlo son ~40 min de CPU para el
    conjunto entero: recalcular la geometría con un radio lunar nuevo no tiene por qué
    pagarlos.
    """
    ev = event or events.DEFAULT
    e = float(elev_fine(la, lo)[0]) if elev is None else float(elev)
    c = circumstances(la, lo, e)
    hz = (horizon_fine(la, lo, AZIMUTHS, obs_elev=e) if prof is None
          else np.asarray(prof, dtype=float) / 100.0)

    # Traza del Sol cada 10 min por la ventana dibujada, para que la pinte el navegador.
    saz, _, salt, _ = sun_track(la, lo, e, _ts_utc(ev, -60), _ts_utc(ev, 75),
                                step_s=600.0)
    keep = (saz >= AZ_LO - 2) & (saz <= AZ_HI + 2)

    total = bool(c['total'])
    if total:
        alt_ref, az_ref = c['c3_alt_app'], c['c3_az']
        clear = min(c['c2_alt_app'] - float(np.interp(c['c2_az'], AZIMUTHS, hz)),
                    c['c3_alt_app'] - float(np.interp(c['c3_az'], AZIMUTHS, hz)))
    else:
        alt_ref, az_ref = c['max_alt_app'], c['max_az']
        clear = alt_ref - float(np.interp(az_ref, AZIMUTHS, hz))
    horizon = float(np.interp(az_ref, AZIMUTHS, hz))

    from .ephem import moon_offset
    d_az, d_alt, r_sun, r_moon = moon_offset(la, lo, e, _ts_at(c['max_utc']))

    # Redondear la obscuración de un parcial puede dejarla en 100,0 exactos, y entonces
    # el dato se contradice con `total=False` antes incluso de pintarlo. Ahí se trunca:
    # de las dos direcciones del redondeo, la de abajo es la que no promete de más.
    pct = c['obscuration'] * 100
    obsc = round(pct, 3) if total else min(round(pct, 3), math.floor(pct * 1000) / 1000)

    return dict(
        i=index, lat=round(la, 5), lon=round(lo, 5), elev=round(e),
        total=total, dur=round(c['duration_s'], 1),
        obsc=obsc,
        alt=round(alt_ref, 2), az=round(az_ref, 2),
        alt2=round(c['c2_alt_app'], 2) if total else round(alt_ref, 2),
        hz=round(horizon, 2), clear=round(clear, 2),
        t=_local(ev, c['max_utc']),
        t2=_local(ev, c['c2_utc'], seconds=True) if total else None,
        t3=_local(ev, c['c3_utc'], seconds=True) if total else None,
        # el perfil en centésimas de grado mantiene pequeño lo que se descarga
        prof=[int(round(v * 100)) for v in hz],
        sun=[[round(float(a), 2), round(float(v), 2)]
             for a, v in zip(saz[keep], salt[keep])],
        moon=[round(d_az, 4), round(d_alt, 4), round(r_sun, 4), round(r_moon, 4)],
    )


def build(out_path=None, progress=None, geocode=True, event=None,
          check_obstacles=True):
    ev = event or events.DEFAULT
    out_path = out_path or os.path.join(DATA_DIR, 'points.json')
    d, picks = select(progress=progress)
    lat, lon = d['lat'], d['lon']

    points = []
    n = len(picks)
    for k, i in enumerate(picks, 1):
        if progress and k % 10 == 0:
            progress(k, n, 'calculando horizontes')
        points.append(point_at(float(lat[i]), float(lon[i]), ev, index=k))

    # Checkpoint antes de tocar nada externo. Los horizontes cuestan ~40 min de CPU y
    # no se pueden perder porque un servicio ajeno esté caído.
    _dump(out_path, ev, points)

    if check_obstacles:
        # El punto ciego del modelo de elevación, tapado con OpenStreetMap: árboles y
        # edificios en la línea de visión. El visor del IGN dice que ignora los dos;
        # aquí es donde de verdad se puede hacer mejor, y no sólo más fino.
        enrich_obstacles(points, progress=progress)

    if geocode:
        for k, p in enumerate(points, 1):
            if progress and k % 10 == 0:
                progress(k, len(points), 'poniendo nombres')
            p['place'] = gazetteer.reverse(p['lat'], p['lon'])
        points = drop_offshore(points, progress=progress)

    meta = _dump(out_path, ev, points)
    return out_path, meta


RETRY_ZOOM = 16        # el zoom de la segunda oportunidad, ver drop_offshore


def drop_offshore(points, progress=None, retry=True):
    """Quita los puntos que no se confirman en tierra firme.

    Sobre el mar el DEM vale 0 y el horizonte sale impecable, así que un punto en mar
    abierto se cuela en lo más alto del ranking por margen libre: exactamente el sitio
    donde nadie puede plantar un trípode. Va después de poner nombres porque el
    topónimo es la prueba (ver gazetteer.on_land), y renumera para que `i` siga siendo
    correlativo.

    Segunda oportunidad antes de tirar nada: al zoom 13 con el que se etiqueta, la costa
    da falsos positivos — 43,44/-2,94 salía «España» y es Gorliz (Bizkaia), y
    42,94/-9,29 es el Monte de Arnela en Fisterra, de los mejores márgenes del país.
    Se reconsulta al zoom 16 y, si aparece municipio, el punto se queda **y de paso
    arregla su topónimo**. Sólo se descarta lo que sigue sin tierra a ese detalle.
    """
    kept, dropped, fixed = [], [], 0
    for p in points:
        if gazetteer.on_land(p.get('place')):
            kept.append(p)
            continue
        fine = gazetteer.reverse(p['lat'], p['lon'], zoom=RETRY_ZOOM) if retry else ''
        if gazetteer.on_land(fine):
            p['place'] = fine
            fixed += 1
            kept.append(p)
        else:
            dropped.append(p)
    for k, p in enumerate(kept, 1):
        p['i'] = k
    if progress:
        progress(len(kept), len(points),
                 f'descartados {len(dropped)} sin tierra confirmada, '
                 f'{fixed} topónimos recuperados')
    return kept


def enrich_obstacles(points, progress=None):
    """Añade la comprobación de árboles y edificios a puntos ya calculados.

    Va aparte y se puede reanudar a propósito: las instancias públicas de Overpass se
    caen o se saturan (visto: HTTP 504 «server too busy» en una, y silencio total en
    otras dos), y un conjunto de miradores no puede depender de que un tercero esté
    sano justo el rato en que se construye. Los puntos sin comprobar se quedan con
    obs_ok=False, que la interfaz tiene que pintar como «sin comprobar» y nunca como
    «despejado».
    """
    lookup = lambda a, b: float(elev_fine(a, b)[0])          # noqa: E731
    items = [(p['lat'], p['lon'], p['az'], p['elev']) for p in points]
    res = obstacles.check_batch(items, elev_lookup=lookup, progress=progress)
    n_ok = 0
    for p, o in zip(points, res):
        # OJO: aquí NO se toca 'sv'. Quien decide si hay foto de Street View es
        # apply_streetview(), que necesita saber si hay carretera cerca — un dato que
        # esta función no tiene. Ponerlo aquí se lo daba a los 1.457 puntos y deshacía
        # la regla en silencio cada vez que se reintentaban los árboles.
        if not o or not o.get('ok'):
            p['obs_ok'] = False
            p.setdefault('obs', 0.0)
            p['clear_net'] = p['clear']      # sin comprobar, no "limpio"
            continue
        n_ok += 1
        p['obs'] = round(o.get('angle', 0.0), 2)
        p['obs_ok'] = True
        w = o.get('worst')
        if w:
            p['obs_what'] = w['kind']; p['obs_d'] = w['dist_m']
            p['obs_h'] = w['height_m']; p['obs_meas'] = w['measured']
        p['clear_net'] = round(min(p['clear'], p['alt'] - max(p['hz'], p['obs'])), 2)
    return n_ok


def apply_streetview(points):
    """Decide el enlace de Street View de cada punto, en un único sitio.

    Street View se graba desde la vía: sin carretera asfaltada muy cerca, el enlace
    abre una pantalla negra (pasó en producción). La regla vive aquí y no repartida
    por los scripts, porque cuando estaba repartida `enrich_obstacles` volvió a
    ponérselo a los 1.457 puntos sin que nadie se enterase.

    Sin perfil de acceso comprobado no hay enlace: un dato que falta no se disfraza.
    """
    n = 0
    for p in points:
        if _sv_allowed(p):
            p['sv'] = obstacles.streetview_url(p['lat'], p['lon'], p['az'])
            n += 1
        else:
            p.pop('sv', None)
    return n


def check_invariants(points):
    """Lo que un dataset publicable tiene que cumplir SIEMPRE. Devuelve la lista de
    incumplimientos, vacía si está sano.

    Existe porque el 2026-08-05 el fichero local apareció con 1.469 puntos, los 26 del
    mar de vuelta y 50 enlaces de Street View, sin que ningún proceso conocido lo
    escribiera. No se pudo averiguar la causa; lo que sí se puede es impedir que un
    dataset así se publique. Un guardia sirve precisamente para lo que no viste venir.
    """
    from . import gazetteer
    fallos = []
    mar = [p for p in points if not gazetteer.on_land(p.get('place'))]
    if mar:
        fallos.append(f'{len(mar)} puntos sin tierra confirmada (p. ej. '
                      f'{mar[0]["lat"]:.3f},{mar[0]["lon"]:.3f})')
    ahogados = [p for p in points if is_at_sea(p)]
    if ahogados:
        fallos.append(f'{len(ahogados)} puntos en mar abierto '
                      f'(p. ej. {ahogados[0]["lat"]:.3f},{ahogados[0]["lon"]:.3f} — '
                      f'{ahogados[0].get("place")})')
    malos_sv = [p for p in points if p.get('sv') and not _sv_allowed(p)]
    if malos_sv:
        fallos.append(f'{len(malos_sv)} enlaces de Street View sin carretera cerca')
    idx = [p.get('i') for p in points]
    if idx != list(range(1, len(points) + 1)):
        fallos.append(f'los índices no son correlativos (1..{len(points)}): '
                      f'van de {idx[0]} a {idx[-1]}')
    return fallos


SEA_RELIEF_KM = 8.0        # radio en el que se busca relieve
SEA_RELIEF_M = 100.0       # por debajo de esto no hay costa que valga


def is_at_sea(p, relief=None):
    """¿Este punto está en mar abierto? Tres condiciones a la vez, y hacen falta las tres.

    El topónimo solo no basta: 39,890/0,670 está a 57 km de la costa de Castellón, sobre
    el bajo submarino «Escala d'Espanya», y Nominatim le devolvió el municipio.
    «Sin carretera cerca» solo tampoco: 43,610/-7,280 es una vivienda aislada en la costa
    de Lugo a la que Overpass no le encontró vía, y es tierra de verdad.
    Y «sin relieve alrededor» solo, menos: el Delta de l'Ebre es de los mejores puntos
    del país y tiene 2 m de desnivel en 8 km a la redonda.

    Juntas sí: a nivel del mar, sin una sola vía en kilómetros y sin nada que levante el
    terreno en 8 km. El Delta se salva por la carretera a 41 m; Foz, por los 368 m de
    monte que tiene detrás.
    """
    if (p.get('elev') or 0) > 3 or not p.get('acc_ok'):
        return False
    if ((p.get('acc') or {}).get('near') or {}).get('m') is not None:
        return False
    if relief is None:
        relief = _relief_around(p['lat'], p['lon'])
    return relief < SEA_RELIEF_M


def _relief_around(lat, lon, km=SEA_RELIEF_KM, n=11):
    import numpy as np
    from .terrain import elev_fine
    dlat = km / 111.2
    dlon = km / (111.32 * np.cos(np.radians(lat)))
    return max(float(elev_fine(lat + i * dlat, lon + j * dlon)[0])
               for i in np.linspace(-1, 1, n) for j in np.linspace(-1, 1, n))


def _sv_allowed(p):
    pv = (p.get('acc') or {}).get('paved') if p.get('acc_ok') else None
    return bool(pv and pv.get('m') is not None and pv['m'] <= obstacles.SV_MAX_ROAD_M)


def _dump(out_path, ev, points, extra=None):
    meta = dict(
        event=ev.key, event_label=ev.label, date=ev.iso_date, tz_label=ev.tz_label,
        az_lo=AZ_LO, az_hi=AZ_HI, az_step=AZ_STEP,
        min_clear=MIN_CLEAR, sep_km=SEP_KM, n=len(points),
        # se recuentan aquí y no los pasa quien llama: si cada script tuviera que
        # acordarse de arrastrar el contador del otro, el primero que lo olvide deja
        # el meta mintiendo sobre cuántos puntos están comprobados
        n_obs_checked=sum(1 for p in points if p.get('obs_ok')),
        n_access_checked=sum(1 for p in points if p.get('acc_ok')),
        note=('Puntos recomendados precalculados para este eclipse. Buscar por '
              'localidad y radio es un filtro sobre este conjunto: no se calcula '
              'nada en vivo.'))
    if extra:
        meta.update(extra)
    with open(out_path, 'w') as f:
        json.dump(dict(meta=meta, points=points), f, ensure_ascii=False,
                  separators=(',', ':'))
    return meta


def _ts_utc(ev, minutes_from_mid):
    """Un Time de skyfield desplazado desde el centro de la ventana de búsqueda."""
    from .ephem import _ts
    h0, m0 = ev.search_start_utc
    h1, m1 = ev.search_end_utc
    mid = ((h0 * 60 + m0) + (h1 * 60 + m1)) / 2 + minutes_from_mid
    return _ts.utc(ev.date[0], ev.date[1], ev.date[2], 0, mid, 0)


def _ts_at(iso):
    from .ephem import _ts
    return _ts.utc(int(iso[0:4]), int(iso[5:7]), int(iso[8:10]),
                   int(iso[11:13]), int(iso[14:16]), float(iso[17:19]))


def _local(ev, iso, seconds=False):
    """Hora local del evento. Con `seconds`, hasta el segundo.

    Los contactos LLEVAN segundos y el instante del máximo no. No es una inconsistencia:
    C2 y C3 acotan un intervalo que dura alrededor de un minuto, así que a resolución de
    minuto la ficha llegaba a decir «totalidad 58 s, de 20:28 a 20:28», que se lee como
    un fallo del cálculo. El máximo es un instante suelto y ahí el segundo sobra.
    """
    h = (int(iso[11:13]) + int(ev.tz_offset_h)) % 24
    if not seconds:
        return f'{h:02d}:{iso[14:16]}'
    # el mismo corte que usa _ts_at: skyfield cierra el ISO con una «Z»
    return f'{h:02d}:{iso[14:16]}:{int(float(iso[17:19])):02d}'


if __name__ == '__main__':
    path, meta = build(progress=lambda a, b, m: print(f'  [{a}/{b}] {m}', flush=True))
    print(f"\n{meta['n']} puntos -> {path}")
    print(f"tamaño: {os.path.getsize(path)/1e6:.1f} MB")
