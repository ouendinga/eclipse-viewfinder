# -*- coding: utf-8 -*-
"""Resolver un nombre de sitio a coordenadas, desde una fuente que se pueda defender.

Regla del proyecto: **el usuario nunca escribe texto libre que acabe siendo una
coordenada.** Elige de una lista de poblaciones reales e identificadas. Cada candidato
lleva los identificadores para poder rastrearlo (tipo + id de OSM), su jerarquía
administrativa y su población cuando se sabe, así que un resultado siempre se puede
auditar después.

Fuente: Nominatim / OpenStreetMap. Elegida por ser abierta, mundial, no pedir clave y
devolver identificadores estables. Los resultados se filtran a poblaciones
(`class=place`, `type in SETTLEMENT_TYPES`) más los límites administrativos que llevan
rango de lugar: así «Malgrat de Mar» resuelve y «un cerro majo que me gusta» no.

La política de uso de Nominatim pide como mucho 1 petición por segundo, un User-Agent
de verdad y cachear los resultados. Las tres se cumplen aquí.
"""
import json
import os
import time
import unicodedata
import urllib.parse
import urllib.request

from .paths import DATA_DIR

USER_AGENT = ('eclipse-viewfinder/1.0 (https://github.com/ouendinga/'
              'eclipse-viewfinder; open-source eclipse viewpoint finder)')
BASE = 'https://nominatim.openstreetmap.org'
CACHE_PATH = os.path.join(DATA_DIR, 'gazetteer_cache.json')

# What counts as "a place someone can travel to".
SETTLEMENT_TYPES = {
    'city', 'town', 'village', 'hamlet', 'municipality', 'borough',
    'suburb', 'quarter', 'isolated_dwelling', 'locality', 'island',
}
# Natural features people legitimately name as a viewpoint.
FEATURE_TYPES = {'peak', 'volcano', 'saddle', 'ridge', 'cape', 'cliff'}

_last_call = [0.0]


def _throttle(min_interval=1.1):
    dt = time.time() - _last_call[0]
    if dt < min_interval:
        time.sleep(min_interval - dt)
    _last_call[0] = time.time()


def _load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            return json.load(open(CACHE_PATH))
        except Exception:
            return {}
    return {}


def _save_cache(c):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CACHE_PATH + '.tmp'
    json.dump(c, open(tmp, 'w'), ensure_ascii=False, indent=0)
    os.replace(tmp, CACHE_PATH)


def _norm(s):
    """Accent- and case-insensitive key for cache lookups."""
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(ch for ch in s if not unicodedata.combining(ch)).strip().lower()


def _get(path, params):
    url = f'{BASE}/{path}?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT,
                                               'Accept-Language': params.get(
                                                   'accept-language', 'es')})
    _throttle()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _shape(raw):
    """Convierte un registro de Nominatim en nuestra forma de candidato, o None si no es un
    lugar.
    """
    # jsonv2 lo llama «category»; el formato antiguo lo llama «class».
    cls = raw.get('class') or raw.get('category')
    typ = raw.get('type')
    atype = raw.get('addresstype')
    kind = None
    if cls == 'place' and typ in SETTLEMENT_TYPES:
        kind = 'settlement'
    elif cls == 'natural' and typ in FEATURE_TYPES:
        kind = 'feature'
    elif typ == 'administrative' and atype in SETTLEMENT_TYPES:
        # un límite administrativo cuyo tipo de dirección es una población
        kind = 'settlement'
    elif cls is None and atype in SETTLEMENT_TYPES:
        kind = 'settlement'
    if kind is None:
        return None
    a = raw.get('address', {}) or {}
    name = (raw.get('name') or a.get(raw.get('addresstype', '')) or
            raw.get('display_name', '').split(',')[0])
    admin = [a.get(k) for k in ('county', 'state_district', 'state', 'region')]
    admin = [x for x in admin if x]
    seen, admin_clean = set(), []
    for x in admin:
        if x not in seen:
            seen.add(x); admin_clean.append(x)
    extratags = raw.get('extratags') or {}
    pop = extratags.get('population')
    try:
        pop = int(str(pop).replace(' ', '')) if pop else None
    except ValueError:
        pop = None
    return dict(
        name=name,
        admin=admin_clean[:2],
        country=a.get('country'),
        country_code=(a.get('country_code') or '').upper(),
        lat=float(raw['lat']), lon=float(raw['lon']),
        kind=kind, place_type=typ,
        osm_type=raw.get('osm_type'), osm_id=raw.get('osm_id'),
        population=pop,
        importance=raw.get('importance'),
        display=raw.get('display_name', ''),
    )


def search(query, lang='es', limit=8, country_codes=None, use_cache=True):
    """Lugares candidatos para una consulta. Devuelve una LISTA: quien llame tiene que hacer
    que elija el usuario. Nunca se queda con el primero en silencio si el nombre es
    ambiguo.

    Lanza LookupError cuando no encaja nada, para que nadie pueda confundir «sin
    resultados» con «algo que hay en 0,0».
    """
    if not query or not query.strip():
        raise ValueError('Consulta vacía')
    key = f'search:{_norm(query)}:{lang}:{limit}:{country_codes or ""}'
    cache = _load_cache()
    if use_cache and key in cache:
        return cache[key]

    params = {'q': query, 'format': 'jsonv2', 'limit': max(limit * 3, 15),
              'addressdetails': 1, 'extratags': 1, 'accept-language': lang}
    if country_codes:
        params['countrycodes'] = country_codes
    raw = _get('search', params)

    out = []
    for r in raw:
        c = _shape(r)
        if c:
            out.append(c)
    # settlements before natural features, then by importance
    order = {'settlement': 0, 'feature': 1}
    out.sort(key=lambda c: (order[c['kind']], -(c['importance'] or 0)))
    out = out[:limit]
    if not out:
        raise LookupError(
            f'"{query}" no aparece como población ni como accidente geográfico '
            f'en OpenStreetMap. Prueba con el nombre oficial del municipio, '
            f'o pasa coordenadas con --lat/--lon.')
    cache[key] = out
    _save_cache(cache)
    return out


def describe(c, short=False):
    """Etiqueta de una línea para un candidato.

    `short` quita la población, para los titulares: «Soria, Castilla y León» se lee como
    un título; «Soria, Castilla y León - 40.941 hab.» no.
    """
    bits = [c['name']] + c['admin'][:1 if short else 2]
    if c.get('country') and c.get('country_code') != 'ES':
        bits.append(c['country'])
    s = ', '.join(b for b in bits if b)
    if c['kind'] == 'feature':
        s += f" ({c['place_type']})"
    if short:
        return s
    if c.get('population'):
        s += f" · {c['population']:,} hab.".replace(',', '.')
    return s


def reverse(lat, lon, lang='es', zoom=13, use_cache=True):
    """Nearest administrative description of a coordinate. Used to LABEL computed
    viewpoints -- never to choose them."""
    key = f'rev:{lat:.4f},{lon:.4f}:{lang}:{zoom}'
    cache = _load_cache()
    if use_cache and key in cache:
        return cache[key]
    try:
        j = _get('reverse', {'lat': f'{lat:.5f}', 'lon': f'{lon:.5f}',
                             'format': 'jsonv2', 'zoom': zoom,
                             'accept-language': lang})
    except Exception:
        return ''
    a = j.get('address', {}) or {}
    parts, seen = [], set()
    for k in ('village', 'town', 'city', 'municipality', 'county', 'state'):
        v = a.get(k)
        if v and v not in seen:
            seen.add(v); parts.append(v)
    label = ', '.join(parts[:3]) or (j.get('display_name', '') or '').split(',')[0]
    cache[key] = label
    _save_cache(cache)
    return label


# Nominatim no adscribe a ningún municipio lo que cae fuera de tierra firme: en mar
# abierto falla ("Unable to geocode" -> etiqueta vacía) y dentro de aguas territoriales
# devuelve sólo el país, que es de lo único que la ficha puede tirar. Sobre tierra
# siempre aparece villa, municipio, comarca o comunidad. Comprobado el 2026-08-05:
# 44,01/-7,48 (mar, ~37 km al norte de Lugo) -> "Unable to geocode"; 43,93/-7,63 ->
# "España" a secas; 43,26/-8,99 -> "O Porto de Corme, Ponteceso, Bergantiños".
# De ahí que sirva de test tierra/mar: no para elegir un punto, sino para NO
# recomendar uno donde nadie puede ponerse de pie.
COUNTRY_ONLY = frozenset(
    ('españa', 'spain', 'francia', 'france', 'portugal', 'andorra'))


def on_land(place):
    """¿El topónimo confirma tierra firme?

    False cuando el reverse no devolvió nada o sólo el país. Es deliberadamente
    conservador: un punto que no se confirma como tierra no se recomienda, igual que
    un dato que falta se marca «sin comprobar» y nunca «limpio».
    """
    return bool(place) and place.strip().lower() not in COUNTRY_ONLY
