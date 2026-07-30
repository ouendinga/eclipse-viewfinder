# -*- coding: utf-8 -*-
"""Trees and buildings: the blind spot that elevation models share.

The IGN's own eclipse visualiser states it plainly -- it uses GMTED2010 relief and
"no se han tenido en cuenta ni las edificaciones ni el arbolado". Our SRTM is ten
times finer, but it is still bare ground: a 20 m pine belt 300 m to the west is
invisible to both, and it is exactly what ruins a 4-degree Sun.

So we ask OpenStreetMap what is standing in the sight line. For each viewpoint we
query a narrow corridor toward the Sun's azimuth and turn buildings and woodland into
an extra obstruction angle, which is then subtracted from the clearance.

Heights: buildings carry `height` or `building:levels` often enough to be useful;
woodland almost never does, so a conservative default is applied and the result is
FLAGGED as an assumption rather than presented as a measurement.

Street View is deliberately not scraped. Automated download and analysis of Street
View imagery needs a billed API key and runs against Google's terms; instead every
point gets a one-click link pointing at the exact heading, so a human can check the
thing a model cannot.
"""
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .paths import DATA_DIR

# Several public Overpass endpoints, rotated on failure: the main one rate-limits
# hard (HTTP 429) well before a few hundred corridor queries are done.
OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
]
OVERPASS = OVERPASS_ENDPOINTS[0]
UA = 'eclipse-viewfinder/1.0 (https://github.com/ouendinga/eclipse-viewfinder)'
CACHE_PATH = os.path.join(DATA_DIR, 'obstacles_cache.json')

CORRIDOR_M = 2500.0      # how far ahead local clutter still matters at low Sun
HALF_WIDTH_M = 90.0      # how far off the bearing something still intrudes
EYE_H = 1.6

# Conservative default heights (metres). Documented as assumptions, not measurements.
DEFAULT_HEIGHTS = {
    'wood': 18.0,        # mature Iberian pine/oak canopy
    'forest': 18.0,
    'scrub': 3.0,
    'orchard': 6.0,
    'vineyard': 2.0,
    'building': 8.0,     # only used when no height/levels tag exists
}
LEVEL_HEIGHT_M = 3.0

_last = [0.0]
_cache = None


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


def _throttle(min_interval=2.5):
    dt = time.time() - _last[0]
    if dt < min_interval:
        time.sleep(min_interval - dt)
    _last[0] = time.time()


def _bbox(lat, lon, az_deg, reach_m=CORRIDOR_M, pad_m=HALF_WIDTH_M):
    """Bounding box covering the corridor from the point toward `az_deg`."""
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
    last = None
    for attempt in range(tries):
        url = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
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
    """(height_m, measured) -- measured=False means we assumed a default."""
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
    """Distance along the bearing and perpendicular offset, in metres."""
    R = 6371000.0
    dy = math.radians(tlat - lat) * R
    dx = math.radians(tlon - lon) * R * math.cos(math.radians(lat))
    az = math.radians(az_deg)
    along = dy * math.cos(az) + dx * math.sin(az)
    across = abs(-dy * math.sin(az) + dx * math.cos(az))
    return along, across


def check(lat, lon, az_deg, obs_elev, elev_lookup=None, use_cache=True,
          min_dist_m=40.0):
    """Extra obstruction angle from OSM features in the sight line.

    Returns a dict with the worst offender and the angle it subtends. `elev_lookup`
    should map (lat, lon) -> ground elevation; without it, flat ground is assumed,
    which understates obstacles uphill of the viewer.
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


def streetview_url(lat, lon, heading_deg, pitch=0):
    """One-click Street View at the exact bearing to the Sun.

    A link, not a scrape: no API key, no terms to breach, and a human eye is better
    at spotting a pine belt than anything automatable here.
    """
    return ('https://www.google.com/maps/@?api=1&map_action=pano'
            f'&viewpoint={lat:.6f},{lon:.6f}'
            f'&heading={heading_deg:.1f}&pitch={pitch}&fov=90')


def mapillary_url(lat, lon, heading_deg):
    """Open alternative to Street View, usable without an API key."""
    return (f'https://www.mapillary.com/app/?lat={lat:.6f}&lng={lon:.6f}'
            f'&z=17&bearing={heading_deg:.1f}')
