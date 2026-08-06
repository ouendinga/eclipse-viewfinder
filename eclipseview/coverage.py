# -*- coding: utf-8 -*-
"""Qué datos de elevación necesita una consulta, cuáles hay ya, y cómo bajar el resto.

El detalle que hace esto menos trivial de lo que parece: analizar un mirador NO
necesita sólo la elevación bajo el mirador. Los rayos salen hacia el azimut del Sol
hasta `RAY_MAX_KM`, así que una consulta centrada en la costa sigue necesitando
teselas muy tierra adentro (o mar adentro) hacia el ONO. El conjunto necesario es el
disco de búsqueda *barrido* a lo largo del rumbo del Sol, no el disco solo.

Equivocarse aquí es silencioso y peligroso: una tesela que falta se lee como nivel del
mar, y eso convertiría un horizonte tapado en uno despejado sin que nadie se entere.
"""
import gzip
import os
import urllib.error
import urllib.request

import numpy as np

from .paths import DEM_DIR
from .terrain import R_EARTH, _offset

# El muestreo de rayos llega a 150 km; el margen de teselas va acorde.
RAY_MAX_KM = 150.0
# En este evento el Sol está al ONO; se ensancha con holgura para que el corredor
# vaya sobrado.
DEFAULT_AZ_RANGE = (255.0, 305.0)
TILE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}/{name}'
TYPICAL_TILE_BYTES = 9_000_000       # observed average for 1x1 deg SRTM .hgt.gz


def tile_name(lat_i, lon_i):
    ns = 'N' if lat_i >= 0 else 'S'
    ew = 'E' if lon_i >= 0 else 'W'
    return f'{ns}{abs(lat_i):02d}{ew}{abs(lon_i):03d}.hgt.gz'


def tiles_covering(lat_min, lat_max, lon_min, lon_max):
    out = set()
    for la in range(int(np.floor(lat_min)), int(np.floor(lat_max)) + 1):
        for lo in range(int(np.floor(lon_min)), int(np.floor(lon_max)) + 1):
            out.add((la, lo))
    return out


def required_tiles(lat, lon, radius_km, az_range=DEFAULT_AZ_RANGE,
                   ray_km=RAY_MAX_KM):
    """Todas las teselas de 1x1 grado que hacen falta para analizar un disco de candidatos.

    = las teselas bajo el disco, más las que caen bajo el corredor barrido desde el borde
    del disco a lo largo del rango de azimutes del Sol hasta `ray_km`.
    """
    need = set()
    # el disco de búsqueda en sí
    dlat = radius_km / 111.2
    dlon = radius_km / (111.32 * max(np.cos(np.radians(lat)), 0.05))
    need |= tiles_covering(lat - dlat, lat + dlat, lon - dlon, lon + dlon)

    # el corredor de rayos: se muestrea el borde del disco y el centro, y se proyecta
    # hacia fuera
    az0, az1 = az_range
    azs = np.linspace(az0, az1, 9)
    origins = [(lat, lon)]
    for b in np.linspace(0, 360, 13)[:-1]:
        la, lo = _offset(np.array([lat]), np.array([lon]), b, radius_km * 1000.0)
        origins.append((float(la[0]), float(lo[0])))
    dists = np.linspace(5000.0, ray_km * 1000.0, 24)
    for (ola, olo) in origins:
        for az in azs:
            la, lo = _offset(np.full(dists.shape, ola), np.full(dists.shape, olo),
                             az, dists)
            for a, b in zip(la, lo):
                need.add((int(np.floor(a)), int(np.floor(b))))
    return need


def status(tiles):
    """Parte un conjunto de teselas en las que hay y las que faltan."""
    have, missing = [], []
    for t in sorted(tiles):
        p = os.path.join(DEM_DIR, tile_name(*t))
        (have if os.path.exists(p) else missing).append(t)
    return have, missing


def estimate(missing):
    return dict(count=len(missing),
                bytes=len(missing) * TYPICAL_TILE_BYTES,
                mb=round(len(missing) * TYPICAL_TILE_BYTES / 1e6))


def fetch(missing, progress=None, timeout=120):
    """Baja las teselas que faltan. Las que son sólo océano dan 404 con toda la razón: se
    apuntan como 'sea' para no reintentarlas nunca ni confundirlas con un hueco.

    Devuelve (bajadas, mar, fallidas).
    """
    os.makedirs(DEM_DIR, exist_ok=True)
    downloaded, sea, failed = [], [], []
    for i, t in enumerate(sorted(missing), 1):
        name = tile_name(*t)
        ns = name[:3]
        url = TILE_URL.format(ns=ns, name=name)
        dest = os.path.join(DEM_DIR, name)
        if progress:
            progress(i, len(missing), name)
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'eclipse-viewfinder/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            tmp = dest + '.part'
            with open(tmp, 'wb') as f:
                f.write(data)
            # comprobar que de verdad es una rejilla int16 de 3601x3601 legible antes
            # de darla por buena
            with gzip.open(tmp, 'rb') as f:
                n = len(f.read())
            if n != 3601 * 3601 * 2:
                os.remove(tmp)
                failed.append((t, f'tamaño inesperado: {n} bytes'))
                continue
            os.replace(tmp, dest)
            downloaded.append(t)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                sea.append(t)          # no tile published = all ocean
            else:
                failed.append((t, f'HTTP {e.code}'))
        except Exception as e:
            failed.append((t, str(e)))
    return downloaded, sea, failed


def report(lat, lon, radius_km, az_range=DEFAULT_AZ_RANGE):
    """Human-readable coverage answer for a request."""
    need = required_tiles(lat, lon, radius_km, az_range)
    have, missing = status(need)
    est = estimate(missing)
    return dict(needed=len(need), have=len(have), missing=missing,
                missing_count=len(missing), mb=est['mb'],
                complete=not missing)
