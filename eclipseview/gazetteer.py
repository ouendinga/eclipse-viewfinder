# -*- coding: utf-8 -*-
"""Resolving a place name to coordinates, from a source we can stand behind.

Rule for this project: **the user never types free text that becomes a coordinate.**
They pick from a list of real, identified settlements. Every candidate carries the
identifiers needed to trace it back (OSM type + id), its administrative hierarchy and
its population where known, so a result can always be audited later.

Source: Nominatim / OpenStreetMap. Chosen because it is open, worldwide, needs no key
and returns stable object ids. Results are filtered to settlements
(`class=place`, `type in SETTLEMENT_TYPES`) plus administrative boundaries that carry
a place rank -- so "Malgrat de Mar" resolves, and "a nice hill I like" does not.

Nominatim's usage policy: max 1 request/second, a real User-Agent, and cache results.
All three are honoured here.
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
    """Turn a Nominatim record into our candidate shape, or None if not a place."""
    # jsonv2 calls it "category"; the older format calls it "class".
    cls = raw.get('class') or raw.get('category')
    typ = raw.get('type')
    atype = raw.get('addresstype')
    kind = None
    if cls == 'place' and typ in SETTLEMENT_TYPES:
        kind = 'settlement'
    elif cls == 'natural' and typ in FEATURE_TYPES:
        kind = 'feature'
    elif typ == 'administrative' and atype in SETTLEMENT_TYPES:
        # an administrative boundary whose address type is a settlement
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
    """Candidate places for a query. Returns a LIST -- the caller must make the user
    choose. Never silently takes the first hit for an ambiguous name.

    Raises LookupError when nothing matches, so a caller cannot mistake "no result"
    for "somewhere at 0,0".
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
    """One-line label for a candidate.

    `short` drops the population, for headlines: "Soria, Castilla y Leon" reads as a
    title, "Soria, Castilla y Leon - 40.941 hab." does not.
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
