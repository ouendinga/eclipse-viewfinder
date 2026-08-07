# -*- coding: utf-8 -*-
"""Cambiar un mirador al que no se llega por otro igual de bueno al que sí.

El problema que resuelve. La puntuación de `select()` recorta el margen en
`CLEAR_SATURATION`, y por encima de ese tope deja de desempatar: en el 27 % de los
puntos publicados el margen satura, así que quien elige pasa a ser la geometría pura.
Y el acceso NO entra en la puntuación —se consulta a OpenStreetMap *después* de
seleccionar—, así que la selección no puede preferir un sitio al que se llega aunque
lo tenga al lado. El resultado medido: 880 de 1.456 puntos publicados tenían un acceso
pobre.

Rehacer la selección entera costaría el barrido de horizontes completo y otra tanda
de OSM sobre los 1.456. No hace falta, porque el problema está acotado: sólo importa
donde el margen satura Y el acceso es malo.

  1. Se localizan los puntos publicados que saturan y tienen mal acceso.
  2. De su MISMA celda se sacan candidatos del barrido que también saturen. Al estar
     los dos por encima del tope son igual de buenos según el criterio que empataba:
     no se cambia calidad por comodidad, que es lo que haría esto discutible.
  3. Cada candidato se recomprueba a 30 m. El barrido es grueso (mosaico de 185 m) y
     un candidato que ahí parece saturar puede no hacerlo de verdad. Este paso no
     estaba en el plan original y es el que impide que el rescate empeore un punto.
  4. Sólo entonces se consulta OSM, y sólo para los que han sobrevivido.

Un punto se sustituye únicamente si el candidato mantiene la totalidad, no pierde
segundos y su acceso es estrictamente mejor. Si ninguno cumple, se queda el original.
"""
import math

import numpy as np

from . import gazetteer, obstacles, recommend

# Cuánto tiene que separarse un candidato del punto al que aspira a sustituir. Por
# debajo de esto el corredor que se le consulta a OSM es casi el mismo, así que la
# respuesta también: se gastaría una consulta para enterarse de lo que ya se sabía.
MIN_SEP_KM = 1.5

# Cuántos candidatos por celda. Con tres se cubre el caso normal sin que la tanda de
# OSM se dispare; el coste es lineal y aquí lo que escasea son las consultas.
MAX_CANDIDATES = 3

# Margen de segundos que se le permite perder a un cambio. Cero sería demasiado
# estricto (el ruido del cálculo son décimas) y mucho más convertiría "igual de bueno"
# en una excusa.
DUR_TOLERANCE_S = 2.0


def net_clear(p):
    """El margen que manda: el del terreno menos lo que haya plantado encima.

    Sin comprobar árboles y edificios se usa el del terreno pelado, igual que hace la
    interfaz. Un dato que falta no puede aparentar ser un dato bueno.
    """
    if p.get('clear_net') is not None and p.get('obs_ok'):
        return p['clear_net']
    return p['clear']


def access_rank(p):
    """Lo bueno que es el acceso, de 0 (no se sabe o no hay) a 3 (asfalto al lado).

    Ordenar hace falta para poder decir "estrictamente mejor" sin discutir. El silencio
    de OSM se queda en 0 y nunca sube: la mayoría de vías no llevan etiqueta de firme,
    así que "sin datos" no se puede traducir por "fácil".
    """
    if not p.get('acc_ok') or not p.get('acc'):
        return 0
    a = p['acc']
    paved, drive = a.get('paved'), a.get('drive')
    if paved and paved['m'] <= 150:
        return 3
    if drive and drive['m'] <= 150 and not (drive.get('hard') or []):
        return 2
    if paved or drive:
        return 1
    return 0


def needs_rescue(p, saturation=None):
    """¿Es un punto que satura el margen y al que además no se llega bien?"""
    sat = recommend.CLEAR_SATURATION if saturation is None else saturation
    return net_clear(p) > sat and access_rank(p) < 2


def _km(la1, lo1, la2, lo2):
    x = (la1 - la2) * 111.2
    y = (lo1 - lo2) * 111.32 * math.cos(math.radians((la1 + la2) / 2))
    return math.hypot(x, y)


def candidates(points, scan, saturation=None, max_per_cell=MAX_CANDIDATES,
               min_sep_km=MIN_SEP_KM):
    """Pasos 1 y 2: qué alternativas hay, sin gastar ni una consulta.

    Devuelve {índice del punto: [(lat, lon), …]}, ordenadas de mejor a peor según la
    misma puntuación que usó `select()`.
    """
    sat = recommend.CLEAR_SATURATION if saturation is None else saturation
    lat, lon, clear, dur = scan['lat'], scan['lon'], scan['clear'], scan['dur']
    alt = scan['a_c3']

    idx = np.where(clear > sat)[0]
    score = (np.minimum(clear[idx], sat) + dur[idx] / 20.0
             + np.minimum(alt[idx], 12) * 0.5)
    por_celda = {}
    for pos, i in enumerate(idx):
        key = recommend.cell_key(lat[i], lon[i], dur[i] >= 1.0)
        por_celda.setdefault(key, []).append((float(score[pos]), int(i)))

    out = {}
    for p in points:
        if not needs_rescue(p, sat):
            continue
        key = recommend.cell_key(p['lat'], p['lon'], p['total'])
        elegidos = []
        for _, i in sorted(por_celda.get(key, ()), reverse=True):
            la, lo = float(lat[i]), float(lon[i])
            if _km(la, lo, p['lat'], p['lon']) < min_sep_km:
                continue
            if any(_km(la, lo, a, b) < min_sep_km for a, b in elegidos):
                continue
            elegidos.append((la, lo))
            if len(elegidos) >= max_per_cell:
                break
        if elegidos:
            out[p['i']] = elegidos
    return out


def refine(cands, event=None, saturation=None, progress=None):
    """Paso 3: recomprobar a 30 m y tirar lo que no aguante.

    El barrido es de mosaico agrupado a 185 m. Un candidato que ahí satura puede tener
    delante una loma que a 30 m sí se ve, así que sin esta pasada el rescate podría
    cambiar un punto bueno por uno peor creyendo que son iguales.
    """
    sat = recommend.CLEAR_SATURATION if saturation is None else saturation
    out = {}
    total = sum(len(v) for v in cands.values())
    hecho = 0
    for pid, sitios in cands.items():
        buenos = []
        for la, lo in sitios:
            hecho += 1
            if progress:
                progress(hecho, total, 'recomprobando candidatos a 30 m')
            q = recommend.point_at(la, lo, event)
            if q['clear'] > sat:
                buenos.append(q)
        if buenos:
            out[pid] = buenos
    return out


def better(original, candidato, saturation=None, dur_tol=DUR_TOLERANCE_S):
    """¿Merece la pena el cambio? Tiene que ganar en acceso y no perder en nada más."""
    sat = recommend.CLEAR_SATURATION if saturation is None else saturation
    if candidato['total'] != original['total']:
        return False                       # no se cambia una totalidad por un parcial
    if candidato['dur'] < original['dur'] - dur_tol:
        return False                       # ni se regalan segundos de corona
    if net_clear(candidato) <= sat:
        return False                       # tiene que seguir saturando de verdad
    if 'place' in candidato and not gazetteer.on_land(candidato['place']):
        return False                       # sobre el mar el horizonte sale impecable
    return access_rank(candidato) > access_rank(original)


def _coord(p):
    return (round(p['lat'], 5), round(p['lon'], 5))


def choose_swaps(points, finos, saturation=None):
    """Qué cambio se hace en cada punto, sin que dos acaben en el mismo sitio.

    Los candidatos salen de la celda, y una celda puede contener a varios puntos
    publicados. Cada uno recibe entonces la MISMA lista de alternativas y, si nadie lo
    impide, todos se quedan con la mejor: la primera pasada dejó cuatro puntos en la
    misma coordenada de Silleda. Dos puntos idénticos ocupan dos huecos de la lista de
    ocho y le quitan al usuario una alternativa de verdad.

    Devuelve [(original, sustituto)] y reserva cada sitio en cuanto se asigna.
    """
    ocupadas = {_coord(p) for p in points}
    por_id = {p['i']: p for p in points}
    out = []
    for pid, qs in finos.items():
        orig = por_id.get(pid)
        if orig is None:
            continue
        mejores = sorted((q for q in qs if better(orig, q, saturation)),
                         key=access_rank, reverse=True)
        for q in mejores:
            if _coord(q) in ocupadas:
                continue
            ocupadas.discard(_coord(orig))   # el sitio que deja queda libre
            ocupadas.add(_coord(q))
            out.append((orig, q))
            break
    return out
