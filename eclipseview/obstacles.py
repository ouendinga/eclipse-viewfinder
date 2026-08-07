# -*- coding: utf-8 -*-
"""Árboles y edificios: el punto ciego que comparten los modelos de elevación.

El propio visor de eclipses del IGN lo dice sin rodeos: usa el relieve GMTED2010 y
«no se han tenido en cuenta ni las edificaciones ni el arbolado». Nuestro SRTM es
diez veces más fino, pero sigue siendo suelo pelado: una hilera de pinos de 20 m a
300 m al oeste es invisible para los dos, y es exactamente lo que arruina un Sol a 4°.

Así que se le pregunta a OpenStreetMap qué hay plantado en la línea de visión. Para
cada mirador se consulta un corredor estrecho hacia el azimut del Sol y se convierten
edificios y arbolado en un ángulo de obstrucción extra, que luego se resta del margen.

Alturas: los edificios traen `height` o `building:levels` con la frecuencia suficiente
para servir; el arbolado casi nunca, así que se aplica un valor conservador y el
resultado se MARCA como suposición en vez de venderlo como una medida.

Street View no se rasca a propósito. Bajar y analizar sus imágenes de forma automática
exige una clave de API con factura y va contra los términos de Google; en su lugar
cada punto lleva un enlace de un clic apuntando al rumbo exacto, para que una persona
compruebe lo que ningún modelo puede.
"""
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .paths import DATA_DIR

# Varios servidores públicos de Overpass, rotando al fallar: el principal corta por
# tasa (HTTP 429) mucho antes de acabar unos cientos de consultas de corredor.
OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
]
OVERPASS = OVERPASS_ENDPOINTS[0]
UA = 'eclipse-viewfinder/1.0 (https://github.com/ouendinga/eclipse-viewfinder)'
CACHE_PATH = os.path.join(DATA_DIR, 'obstacles_cache.json')

CORRIDOR_M = 2500.0      # how far ahead local clutter still matters at low Sun
HALF_WIDTH_M = 90.0      # cuánto se desvía del rumbo algo y sigue estorbando
EYE_H = 1.6

# Alturas por defecto (metros). NO son medidas ni citas: son suposiciones declaradas,
# y por eso cada una viaja con `measured=False` hasta la ficha, que escribe «altura
# estimada» en vez de «altura del mapa». Es la única forma de respetar la regla del
# repo —ninguna cifra sin origen— cuando el origen no existe: OSM casi nunca etiqueta
# la altura del arbolado, y suponer cero sería peor que suponer un pinar maduro,
# porque un cero se lee como «aquí no hay nada».
DEFAULT_HEIGHTS = {
    'wood': 18.0,        # copa de pinar o robledal ibérico ya crecido
    'forest': 18.0,
    'scrub': 3.0,
    'orchard': 6.0,
    'vineyard': 2.0,
    'building': 8.0,     # sólo se usa si no hay etiqueta height ni levels
}
LEVEL_HEIGHT_M = 3.0

# Ritmo de las consultas. Overpass es un servicio público y gratuito, y el 2026-08-05
# nos ganamos un "Connection refused" a nivel TCP en overpass-api.de después de lanzar
# ~1.150 peticiones en 25 minutos desde la misma IP. El coste de ir despacio es tiempo
# nuestro; el de ir deprisa es que nos cierren la puerta y encima no enterarnos.
MIN_INTERVAL_S = 6.0          # entre peticiones; se sube con OVERPASS_MIN_INTERVAL
BAN_COOLDOWN_S = 900.0        # a un endpoint que rechaza la conexión no se le insiste
MAX_BACKOFF_S = 300.0

_last = [0.0]
_cache = None
_healthy = None
_cooldown = {}                # url -> instante en que se le puede volver a hablar


def _min_interval():
    try:
        return max(0.5, float(os.environ.get('OVERPASS_MIN_INTERVAL', MIN_INTERVAL_S)))
    except ValueError:
        return MIN_INTERVAL_S


def healthy_endpoints(force=False, timeout=20):
    """Los endpoints que de verdad contestan. Lista vacía si no contesta ninguno.

    Antes, cuando fallaban los tres, devolvía la lista entera «para intentarlo igual».
    Eso convirtió una caída total en 25 minutos de barra de progreso avanzando y 401
    puntos fallando en silencio, con el script diciendo «OK» al final. Una comprobación
    que nunca puede decir «no» no comprueba nada: si no hay a quién preguntar, hay que
    decirlo y no arrancar.
    """
    global _healthy
    if _healthy is not None and not force:
        return _healthy
    probe = ('[out:json][timeout:10];way["building"](41.65,2.73,41.66,2.74);'
             'out ids;')
    ok = []
    for url in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode({'data': probe}).encode(),
                headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                json.load(r)
            ok.append(url)
        except Exception:
            pass
    _healthy = ok
    return _healthy


def available_endpoints():
    """Sanos y fuera del periodo de castigo."""
    now = time.time()
    return [u for u in healthy_endpoints() if _cooldown.get(u, 0.0) <= now]


def _penalise(url, seconds):
    _cooldown[url] = max(_cooldown.get(url, 0.0), time.time() + seconds)


def _is_refusal(err):
    """¿Nos están cerrando la puerta, en vez de estar ocupados?

    Un «Connection refused» o un «Network is unreachable» no mejoran reintentando
    rápido: o nos han bloqueado o el servicio no está. Insistir sólo empeora la fama
    de la IP.
    """
    if isinstance(err, urllib.error.HTTPError):
        return err.code in (403, 429)
    s = str(getattr(err, 'reason', err))
    return ('refused' in s or 'unreachable' in s or 'Name or service not known' in s)


def _retry_after(err, attempt):
    """Cuánto esperar: lo que diga el servidor, si lo dice; si no, exponencial."""
    if isinstance(err, urllib.error.HTTPError):
        try:
            ra = float(err.headers.get('Retry-After', ''))
            return min(MAX_BACKOFF_S, max(ra, 1.0))
        except (TypeError, ValueError):
            pass
    # sin jitter, N procesos reintentarían a la vez y volverían a tumbarlo; el tope se
    # aplica DESPUÉS de dispersar, o el jitter se lo salta por arriba
    base = _min_interval() * (2 ** attempt)
    disperso = base * (0.7 + 0.6 * ((time.time() * 1000) % 1000) / 1000.0)
    return min(MAX_BACKOFF_S, disperso)


def _load():
    global _cache
    if _cache is None:
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH) as f:
                    _cache = json.load(f)
            except Exception:
                _cache = {}
        else:
            _cache = {}
    return _cache


def _save():
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CACHE_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(_cache, f)
    os.replace(tmp, CACHE_PATH)


def _throttle(min_interval=None):
    min_interval = _min_interval() if min_interval is None else min_interval
    dt = time.time() - _last[0]
    if dt < min_interval:
        time.sleep(min_interval - dt)
    _last[0] = time.time()


class NoEndpoints(RuntimeError):
    """No hay ningún Overpass al que preguntar. No es un punto que falla: es que no
    se puede trabajar, y hay que decirlo en vez de fabricar 401 fallos silenciosos."""


def _ask(q, timeout, tries=4):
    """Una consulta a Overpass, rotando endpoints y esperando de verdad entre intentos.

    Rota por endpoints disponibles, castiga al que rechaza la conexión y respeta el
    Retry-After del servidor cuando lo manda. Si se queda sin endpoints, levanta
    NoEndpoints: quien llama debe parar, no seguir dando vueltas.
    """
    last = None
    for attempt in range(tries):
        eps = available_endpoints()
        if not eps:
            raise NoEndpoints(
                'ningún Overpass disponible' +
                (f' (último error: {str(last)[:90]})' if last else ''))
        url = eps[attempt % len(eps)]
        try:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode({'data': q}).encode(),
                headers={'User-Agent': UA})
            _throttle()
            with urllib.request.urlopen(req, timeout=timeout + 15) as r:
                return json.load(r)
        except Exception as e:
            last = e
            if _is_refusal(e):
                _penalise(url, BAN_COOLDOWN_S)
                continue          # otro endpoint, sin dormir: a éste ya no se le habla
            time.sleep(_retry_after(e, attempt))
    raise last


def _bbox(lat, lon, az_deg, reach_m=CORRIDOR_M, pad_m=HALF_WIDTH_M):
    """Rectángulo que cubre el corredor desde el punto hacia `az_deg`."""
    R = 6371000.0
    az = math.radians(az_deg)
    dlat = reach_m * math.cos(az) / R
    dlon = reach_m * math.sin(az) / (R * math.cos(math.radians(lat)))
    la2 = lat + math.degrees(dlat)
    lo2 = lon + math.degrees(dlon)
    p_la = math.degrees(pad_m / R)
    p_lo = math.degrees(pad_m / (R * math.cos(math.radians(lat))))
    return (min(lat, la2) - p_la, min(lon, lo2) - p_lo,
            max(lat, la2) + p_la, max(lon, lo2) + p_lo)


def _query(bbox, timeout=90, tries=4):
    """Ask Overpass, rotating endpoints and backing off on rate limits."""
    eps = healthy_endpoints()
    last = None
    for attempt in range(tries):
        url = eps[attempt % len(eps)]
        try:
            return _query_one(url, bbox, timeout)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 504, 503):
                time.sleep(3.0 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last = e
            time.sleep(2.0 * (attempt + 1))
    raise last


def _query_one(url, bbox, timeout=90):
    s, w, n, e = bbox
    q = (f'[out:json][timeout:{timeout}];('
         f'way["building"]({s},{w},{n},{e});'
         f'way["natural"~"^(wood|scrub)$"]({s},{w},{n},{e});'
         f'way["landuse"~"^(forest|orchard|vineyard)$"]({s},{w},{n},{e});'
         f');out tags center;')
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode({'data': q}).encode(),
        headers={'User-Agent': UA})
    _throttle()
    with urllib.request.urlopen(req, timeout=timeout + 20) as r:
        return json.load(r)


def _height(tags):
    """(altura_m, medida). `medida=False` significa que la hemos supuesto.

    La segunda cifra es tan importante como la primera: es la que hace que la ficha
    escriba «altura estimada» en vez de «altura del mapa». Un 18 que se cuele como
    medido convierte la única suposición del proyecto en un dato.
    """
    for key in ('height', 'building:height'):
        v = tags.get(key)
        if v:
            try:
                return float(str(v).split()[0]), True
            except ValueError:
                pass
    lv = tags.get('building:levels')
    if lv:
        try:
            return float(str(lv).split(';')[0]) * LEVEL_HEIGHT_M, True
        except ValueError:
            pass
    for key in ('natural', 'landuse'):
        v = tags.get(key)
        if v in DEFAULT_HEIGHTS:
            return DEFAULT_HEIGHTS[v], False
    if tags.get('building'):
        return DEFAULT_HEIGHTS['building'], False
    return None, False


def _along(lat, lon, az_deg, tlat, tlon):
    """Distancia a lo largo del rumbo y desviación perpendicular, en metros."""
    R = 6371000.0
    dy = math.radians(tlat - lat) * R
    dx = math.radians(tlon - lon) * R * math.cos(math.radians(lat))
    az = math.radians(az_deg)
    along = dy * math.cos(az) + dx * math.sin(az)
    across = abs(-dy * math.sin(az) + dx * math.cos(az))
    return along, across


def check_batch(items, elev_lookup=None, batch=25, progress=None,
                min_dist_m=40.0, timeout=45):
    """Corredores de MUCHOS miradores en una sola consulta a Overpass.

    Una consulta por punto no sobrevive al contacto con los servidores públicos:
    empiezan a rechazar, cada intento se come entero su tiempo de espera del socket y
    la ejecución deja de avanzar. La unión de N rectángulos de corredor devuelve los
    mismos elementos en una única respuesta, que sigue siendo pequeña, y baja de ~1750
    peticiones a ~70.

    `items` es una secuencia de (lat, lon, az_deg, obs_elev). Devuelve los resultados
    en el mismo orden.
    """
    cache = _load()
    out = [None] * len(items)
    todo = []
    for i, (lat, lon, az, elev) in enumerate(items):
        key = f'{lat:.4f},{lon:.4f},{az:.0f}'
        if key in cache:
            out[i] = cache[key]
        else:
            todo.append(i)

    if todo and not available_endpoints():
        raise NoEndpoints('ningún Overpass responde: no se arranca')

    def resolver(chunk, profundidad=0):
        """Un lote; si falla, se parte por la mitad antes de darlo por perdido.

        Un lote de 25 que falla perdía los 25 puntos aunque el problema fuese uno solo
        (una zona densa que hace reventar el timeout). Partiéndolo, lo que se pierde es
        lo que de verdad no se puede resolver.
        """
        boxes = [_bbox(*items[i][:3]) for i in chunk]
        try:
            data = _query_multi(boxes, timeout=timeout)
        except NoEndpoints:
            raise
        except Exception as e:
            if len(chunk) > 1 and profundidad < 3:
                mitad = len(chunk) // 2
                resolver(chunk[:mitad], profundidad + 1)
                resolver(chunk[mitad:], profundidad + 1)
                return
            for i in chunk:
                out[i] = dict(ok=False, error=str(e)[:120], angle=0.0)
            return
        elements = data.get('elements', [])
        for i in chunk:
            lat, lon, az, elev = items[i]
            res = _evaluate(elements, lat, lon, az, elev, elev_lookup, min_dist_m)
            cache[f'{lat:.4f},{lon:.4f},{az:.0f}'] = res
            out[i] = res

    for start in range(0, len(todo), batch):
        chunk = [todo[k] for k in range(start, min(start + batch, len(todo)))]
        if progress:
            progress(start + len(chunk), len(todo), 'OSM por lotes')
        resolver(chunk)
        _save()
    return out


def _query_multi(boxes, timeout=45, tries=3):
    """Una petición, muchos rectángulos. Misma rotación y espera que la suelta."""
    parts = []
    for (s, w, n, e) in boxes:
        parts.append(f'way["building"]({s},{w},{n},{e});')
        parts.append(f'way["natural"~"^(wood|scrub)$"]({s},{w},{n},{e});')
        parts.append(f'way["landuse"~"^(forest|orchard|vineyard)$"]({s},{w},{n},{e});')
    q = f'[out:json][timeout:{timeout}];(' + ''.join(parts) + ');out tags center;'
    return _ask(q, timeout, tries=tries)


def _evaluate(elements, lat, lon, az_deg, obs_elev, elev_lookup, min_dist_m):
    """Convierte los elementos de OSM en el peor ángulo de obstrucción del mirador."""
    h0 = obs_elev + EYE_H
    worst, n_seen = None, 0
    for el in elements:
        c = el.get('center') or {}
        if 'lat' not in c:
            continue
        along, across = _along(lat, lon, az_deg, c['lat'], c['lon'])
        if along < min_dist_m or along > CORRIDOR_M or across > HALF_WIDTH_M:
            continue
        tags = el.get('tags', {})
        h, measured = _height(tags)
        if not h:
            continue
        ground = (elev_lookup(c['lat'], c['lon']) if elev_lookup else obs_elev)
        ang = math.degrees(math.atan2(ground + h - h0, along))
        # Por debajo de la horizontal no puede tapar nada: informar de «el peor
        # obstáculo es un edificio a -13°» sería ruido disfrazado de hallazgo.
        if ang <= 0:
            continue
        n_seen += 1
        if worst is None or ang > worst['angle']:
            worst = dict(angle=round(ang, 2), dist_m=round(along),
                         height_m=round(h, 1), measured=measured,
                         kind=(tags.get('natural') or tags.get('landuse')
                               or ('building:' + str(tags.get('building')))),
                         name=tags.get('name'))
    return dict(ok=True, n=n_seen, angle=(worst['angle'] if worst else 0.0),
                worst=worst)


def check(lat, lon, az_deg, obs_elev, elev_lookup=None, use_cache=True,
          min_dist_m=40.0):
    """Ángulo de obstrucción extra de los elementos de OSM en la línea de visión.

    Devuelve un diccionario con el peor culpable y el ángulo que abarca. `elev_lookup`
    tiene que llevar de (lat, lon) a la altura del suelo; sin él se supone suelo
    llano, lo que se queda corto con los obstáculos ladera arriba del observador.
    """
    key = f'{lat:.4f},{lon:.4f},{az_deg:.0f}'
    cache = _load()
    if use_cache and key in cache:
        return cache[key]

    try:
        data = _query(_bbox(lat, lon, az_deg))
    except Exception as e:
        return dict(ok=False, error=str(e)[:120], angle=0.0)

    h0 = obs_elev + EYE_H
    worst = None
    n_seen = 0
    for el in data.get('elements', []):
        c = el.get('center') or {}
        if 'lat' not in c:
            continue
        along, across = _along(lat, lon, az_deg, c['lat'], c['lon'])
        if along < min_dist_m or along > CORRIDOR_M or across > HALF_WIDTH_M:
            continue
        tags = el.get('tags', {})
        h, measured = _height(tags)
        if not h:
            continue
        n_seen += 1
        ground = (elev_lookup(c['lat'], c['lon']) if elev_lookup else obs_elev)
        top = ground + h
        ang = math.degrees(math.atan2(top - h0, along))
        if worst is None or ang > worst['angle']:
            worst = dict(angle=round(ang, 2), dist_m=round(along),
                         height_m=round(h, 1), measured=measured,
                         kind=(tags.get('natural') or tags.get('landuse')
                               or ('building:' + str(tags.get('building')))),
                         name=tags.get('name'))
    out = dict(ok=True, n=n_seen, angle=(worst['angle'] if worst else 0.0),
               worst=worst)
    cache[key] = out
    _save()
    return out


ROAD_RADIUS_M = 250.0        # más allá de esto no hay ni Street View ni acceso fácil
SV_MAX_ROAD_M = 60.0         # Street View se toma desde la vía: sin vía, no hay foto

# Street View se graba desde vías rodadas. Un sendero a 66 m o una pista forestal a 1 m
# no dan foto -- fue justo el caso del primer enlace roto que apareció en producción.
DRIVABLE = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'unclassified',
            'residential', 'living_street', 'motorway_link', 'trunk_link',
            'primary_link', 'secondary_link', 'tertiary_link'}
# Se llega, pero en general sin cobertura fotográfica.
ROUGH = {'service', 'track'}
WALKABLE = {'path', 'footway', 'bridleway', 'steps', 'cycleway'}

# Señales de que hace falta 4x4 o al menos altura libre. OSM las etiqueta a propósito;
# lo que NO se puede es dar por bueno el silencio: la mayoría de vías no llevan estas
# etiquetas, así que "sin datos" tiene que decirse, no interpretarse como "fácil".
ROUGH_SMOOTH = {'bad', 'very_bad', 'horrible', 'impassable'}
ROUGH_SURFACE = {'ground', 'dirt', 'earth', 'mud', 'sand', 'grass', 'unpaved'}
ACCESS_RADIUS_M = 1200.0


def check_roads_batch(items, batch=15, progress=None, timeout=60):
    """Distancia a la vía transitable más cercana, para cada punto.

    Nació de un enlace roto: el Street View de un punto en pleno campo abría una
    pantalla negra porque allí no hay fotos. Pero el dato sirve para algo más
    importante que esconder un enlace: si no hay vía cerca, probablemente tampoco se
    llega, y eso es justo lo que el modelo de elevación no puede decirte.

    `items` es una secuencia de (lat, lon). Devuelve metros a la vía más cercana, o
    None si no se pudo consultar.
    """
    cache = _load()
    out = [None] * len(items)
    todo = []
    for i, (lat, lon) in enumerate(items):
        key = f'road2:{lat:.4f},{lon:.4f}'
        if key in cache:
            out[i] = cache[key]
        else:
            todo.append(i)

    R = 6371000.0
    for start in range(0, len(todo), batch):
        chunk = [todo[k] for k in range(start, min(start + batch, len(todo)))]
        if progress:
            progress(start + len(chunk), len(todo), 'vías de acceso (OSM)')
        parts = []
        for i in chunk:
            lat, lon = items[i]
            dla = math.degrees(ACCESS_RADIUS_M / R)
            dlo = math.degrees(ACCESS_RADIUS_M / (R * math.cos(math.radians(lat))))
            parts.append(f'way["highway"]({lat-dla},{lon-dlo},{lat+dla},{lon+dlo});')
        q = (f'[out:json][timeout:{timeout}];(' + ''.join(parts) +
             ');out tags geom;')
        try:
            data = _query_raw(q, timeout)
        except Exception:
            continue
        ways = [w for w in data.get('elements', []) if w.get('geometry')]
        for i in chunk:
            lat, lon = items[i]
            any_best = drive_best = walk_best = None
            for w in ways:
                tg = w.get('tags') or {}
                hw = tg.get('highway', '')
                if hw in ('proposed', 'construction', 'raceway'):
                    continue
                d = min((math.hypot(
                    math.radians(nd['lon'] - lon) * R * math.cos(math.radians(lat)),
                    math.radians(nd['lat'] - lat) * R)) for nd in w['geometry'])
                if d > ACCESS_RADIUS_M:
                    continue
                cand = (d, hw, tg)
                if any_best is None or d < any_best[0]:
                    any_best = cand
                if hw in DRIVABLE | ROUGH and (drive_best is None or d < drive_best[0]):
                    drive_best = cand
                if hw in WALKABLE and (walk_best is None or d < walk_best[0]):
                    walk_best = cand

            def profile(c):
                if not c:
                    return None
                d, hw, tg = c
                hard = []
                if tg.get('4wd_only') == 'yes':
                    hard.append('4wd_only')
                if tg.get('smoothness') in ROUGH_SMOOTH:
                    hard.append('smoothness=' + tg['smoothness'])
                if tg.get('tracktype') in ('grade4', 'grade5'):
                    hard.append(tg['tracktype'])
                if tg.get('surface') in ROUGH_SURFACE:
                    hard.append('surface=' + tg['surface'])
                return dict(m=round(d), kind=hw, surface=tg.get('surface'),
                            smoothness=tg.get('smoothness'),
                            tracktype=tg.get('tracktype'),
                            access=tg.get('access') or tg.get('motor_vehicle'),
                            hard=hard,
                            # sin ninguna de esas etiquetas no se puede afirmar nada
                            rated=bool(tg.get('surface') or tg.get('smoothness')
                                       or tg.get('tracktype') or tg.get('4wd_only')))

            paved = None
            for w in ways:
                tg = w.get('tags') or {}
                if tg.get('highway') not in DRIVABLE:
                    continue
                d = min((math.hypot(
                    math.radians(nd['lon'] - lon) * R * math.cos(math.radians(lat)),
                    math.radians(nd['lat'] - lat) * R)) for nd in w['geometry'])
                if d <= ACCESS_RADIUS_M and (paved is None or d < paved[0]):
                    paved = (d, tg.get('highway'), tg)

            res = dict(near=profile(any_best), drive=profile(drive_best),
                       walk=profile(walk_best), paved=profile(paved),
                       radius_m=ACCESS_RADIUS_M)
            cache[f'road2:{lat:.4f},{lon:.4f}'] = res
            out[i] = res
        _save()
    return out


def _query_raw(q, timeout=45, tries=3):
    return _ask(q, timeout, tries=tries)


def streetview_url(lat, lon, heading_deg, pitch=0):
    """Street View de un clic, con el rumbo exacto hacia el Sol.

    Un enlace, no un rascado: sin clave de API, sin términos que incumplir, y un ojo
    humano detecta una hilera de pinos mejor que nada de lo que se pueda automatizar
    aquí.
    """
    return ('https://www.google.com/maps/@?api=1&map_action=pano'
            f'&viewpoint={lat:.6f},{lon:.6f}'
            f'&heading={heading_deg:.1f}&pitch={pitch}&fov=90')


def mapillary_url(lat, lon, heading_deg):
    """Open alternative to Street View, usable without an API key."""
    return (f'https://www.mapillary.com/app/?lat={lat:.6f}&lng={lon:.6f}'
            f'&z=17&bearing={heading_deg:.1f}')
