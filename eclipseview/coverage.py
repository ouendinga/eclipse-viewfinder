# -*- coding: utf-8 -*-
"""Which elevation data a request needs, what we already have, and fetching the rest.

The subtlety that makes this non-trivial: analysing a viewpoint does **not** only need
elevation under the viewpoint. Rays are cast toward the Sun's azimuth out to
`RAY_MAX_KM`, so a request centred on the coast still needs tiles far inland (or
offshore) in the WNW. The needed set is therefore the search disc *swept* along the
Sun's bearing, not the disc alone.

Getting this wrong is silent and dangerous: missing tiles read as sea level, which
would quietly turn a blocked horizon into a clear one.
"""
import gzip
import os
import urllib.error
import urllib.request

import numpy as np

from .paths import DEM_DIR
from .terrain import R_EARTH, _offset

# Ray sampling reaches 150 km; keep the tile margin consistent with it.
RAY_MAX_KM = 150.0
# The Sun sits in the WNW for this event; widen generously so the corridor is safe.
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
    """Every 1x1 degree tile needed to analyse a disc of candidates.

    = tiles under the disc, plus tiles under the corridor swept from the disc edge
    along the Sun's azimuth range out to `ray_km`.
    """
    need = set()
    # the search disc itself
    dlat = radius_km / 111.2
    dlon = radius_km / (111.32 * max(np.cos(np.radians(lat)), 0.05))
    need |= tiles_covering(lat - dlat, lat + dlat, lon - dlon, lon + dlon)

    # the ray corridor: sample the disc boundary and the centre, project outward
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
    """Split a tile set into what we have and what we are missing."""
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
    """Download the missing tiles. Ocean-only tiles legitimately 404: they are
    recorded as 'sea' so we never retry them and never mistake them for a gap.

    Returns (downloaded, sea, failed).
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
            # verify it really is a readable 3601x3601 int16 grid before accepting
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
