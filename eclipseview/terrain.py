"""El motor del horizonte: ángulo aparente de la silueta del terreno en un rumbo.

Desde cada mirador se lanzan rayos hacia fuera y se pregunta cuánto se levanta el
terreno por encima de la horizontal astronómica, contando:
  - la caída por curvatura terrestre:  d² / (2R) * (1 - k)
  - la refracción terrestre estándar, k = 0,13, que levanta un poco el terreno lejano
El resultado se puede comparar directamente con la altura *aparente* (refractada) del
Sol.

Dos regímenes de resolución, separados a propósito:
  * campo CERCANO -- SRTM de 1 segundo de arco (~30 m) entero, interpolado bilineal.
    Aquí NO se puede usar el dato agrupado por máximo: la celda de 185 m del propio
    observador guarda el punto más alto que haya dentro, y eso fabrica un muro a
    metros de quien mira.
  * campo LEJANO  -- el mosaico de 6 segundos agrupado por máximo, que conserva las
    crestas del lado conservador, que es lo que importa cuando la pregunta es si
    asoma *algo* de terreno en ese rumbo.
"""
import gzip, json, os
import numpy as np
from .paths import DEM_DIR, MOSAIC_NPY, MOSAIC_JSON

R_EARTH = 6371000.0
K_REFR = 0.13            # standard terrestrial refraction coefficient
NEAR_FAR_SPLIT = 25000.0  # m: por debajo, resolución entera; por encima, el mosaico

_here = os.path.dirname(os.path.abspath(__file__))

_meta = None
_dem = None
_tiles = {}

_META_KEYS = {'PER_DEG': 'per_deg', 'LAT_N': 'lat_n', 'LON_W': 'lon_w',
              'ROWS': 'rows', 'COLS': 'cols'}


def meta():
    global _meta
    if _meta is None:
        with open(MOSAIC_JSON) as f:
            _meta = json.load(f)
    return _meta


def __getattr__(name):
    """Las dimensiones del mosaico se leen al usarlas, no al importar.

    Importar este módulo tiene que funcionar en un clon recién bajado, donde
    `data/` todavía no existe: si no, ni siquiera se pueden lanzar los tests de
    geometría, que no tocan el terreno para nada. Con PEP 562 los nombres de
    siempre (PER_DEG, LAT_N…) se resuelven igual, pero sólo cuando alguien los
    pide de verdad.
    """
    key = _META_KEYS.get(name)
    if key is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    return meta()[key]


def dem():
    global _dem
    if _dem is None:
        _dem = np.asarray(np.load(MOSAIC_NPY))
    return _dem


# ---------------------------------------------------------------- coarse (mosaic)

def elev_at(lat, lon):
    """Altura (m) de la celda más cercana del mosaico. Mar o fuera del área -> 0."""
    m = meta()
    per_deg, lat_n, lon_w = m['per_deg'], m['lat_n'], m['lon_w']
    rows, cols = m['rows'], m['cols']
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    r = np.rint((lat_n - lat) * per_deg).astype(np.int64)
    c = np.rint((lon - lon_w) * per_deg).astype(np.int64)
    ok = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
    out = np.zeros(np.shape(r), dtype=np.float64)
    v = dem()[np.clip(r, 0, rows - 1), np.clip(c, 0, cols - 1)].astype(np.float64)
    out[ok] = v[ok]
    return np.maximum(out, 0.0)


# ---------------------------------------------------------------- fine (1 arcsec)

def _tile(lat_i, lon_i):
    """Full-resolution 3601x3601 tile, cached. Missing (all-ocean) -> None."""
    key = (lat_i, lon_i)
    if key in _tiles:
        return _tiles[key]
    ns = 'N' if lat_i >= 0 else 'S'
    ew = 'E' if lon_i >= 0 else 'W'
    path = os.path.join(DEM_DIR, f'{ns}{abs(lat_i):02d}{ew}{abs(lon_i):03d}.hgt.gz')
    arr = None
    if os.path.exists(path):
        with gzip.open(path, 'rb') as f:
            raw = np.frombuffer(f.read(), dtype='>i2')
        if raw.size == 3601 * 3601:
            a = raw.reshape(3601, 3601).astype(np.float32)
            arr = np.where(a < -500, 0.0, a)
    if len(_tiles) > 12:
        _tiles.clear()
    _tiles[key] = arr
    return arr


def elev_fine(lat, lon):
    """Bilinearly interpolated 1-arcsec elevation (m). Sea / missing -> 0."""
    lat = np.atleast_1d(np.asarray(lat, dtype=np.float64))
    lon = np.atleast_1d(np.asarray(lon, dtype=np.float64))
    out = np.zeros(lat.shape, dtype=np.float64)
    li = np.floor(lat).astype(np.int64)
    oi = np.floor(lon).astype(np.int64)
    for (a, b) in set(zip(li.tolist(), oi.tolist())):
        t = _tile(a, b)
        m = (li == a) & (oi == b)
        if t is None:
            continue
        # row 0 = north edge (lat a+1); col 0 = west edge (lon b)
        y = (a + 1 - lat[m]) * 3600.0
        x = (lon[m] - b) * 3600.0
        y = np.clip(y, 0, 3599.999)
        x = np.clip(x, 0, 3599.999)
        y0 = y.astype(np.int64); x0 = x.astype(np.int64)
        fy = y - y0; fx = x - x0
        v = (t[y0, x0] * (1 - fy) * (1 - fx) + t[y0 + 1, x0] * fy * (1 - fx)
             + t[y0, x0 + 1] * (1 - fy) * fx + t[y0 + 1, x0 + 1] * fy * fx)
        out[m] = v
    return np.maximum(out, 0.0)


# ---------------------------------------------------------------- geometry

def _offset(lat, lon, az_deg, d_m):
    """Great-circle offset. lat/lon degrees (arrays), az degrees, d metres."""
    lat1 = np.radians(lat); lon1 = np.radians(lon); az = np.radians(az_deg)
    dr = d_m / R_EARTH
    sin_lat2 = np.sin(lat1) * np.cos(dr) + np.cos(lat1) * np.sin(dr) * np.cos(az)
    lat2 = np.arcsin(np.clip(sin_lat2, -1, 1))
    y = np.sin(az) * np.sin(dr) * np.cos(lat1)
    x = np.cos(dr) - np.sin(lat1) * sin_lat2
    return np.degrees(lat2), np.degrees(lon1 + np.arctan2(y, x))


def _angle(h_target, h_obs, d):
    drop = d * d * (1.0 - K_REFR) / (2.0 * R_EARTH)
    return np.degrees(np.arctan2(h_target - h_obs - drop, d))


def coarse_distances(d_min=400.0, d_split=NEAR_FAR_SPLIT, step_near=180.0,
                     d_max=200000.0, step_far=500.0):
    """Muestreo a resolución del mosaico. d_min vale por defecto más de 2 celdas para
    que la celda agrupada del propio observador no se lea como un obstáculo."""
    return np.concatenate([np.arange(d_min, d_split, step_near),
                           np.arange(d_split, d_max, step_far)])


def horizon_coarse(lat, lon, obs_elev, azimuths, dists=None, eye_h=1.6,
                   return_distance=False):
    """Vectorizado sobre miradores, a resolución de mosaico. Devuelve (n_az, n_pt) en
    grados.

    Sirve para ORDENAR muchos candidatos; los ganadores se afinan con horizon_fine.
    """
    lat = np.atleast_1d(np.asarray(lat, dtype=np.float64))
    lon = np.atleast_1d(np.asarray(lon, dtype=np.float64))
    h0 = np.atleast_1d(np.asarray(obs_elev, dtype=np.float64)) + eye_h
    dists = coarse_distances() if dists is None else dists
    azimuths = np.atleast_1d(np.asarray(azimuths, dtype=np.float64))

    best = np.full((azimuths.size, lat.size), -90.0)
    best_d = np.zeros((azimuths.size, lat.size))
    for ia, az in enumerate(azimuths):
        for d in dists:
            tlat, tlon = _offset(lat, lon, az, d)
            ang = _angle(elev_at(tlat, tlon), h0, d)
            upd = ang > best[ia]
            best[ia] = np.where(upd, ang, best[ia])
            best_d[ia] = np.where(upd, d, best_d[ia])
    return (best, best_d) if return_distance else best


def horizon_per_point(lat, lon, obs_elev, az, dists, eye_h=1.6,
                      return_distance=False):
    """Como horizon_coarse pero cada mirador lleva SU azimut (misma forma que lat).

    Hace falta porque el azimut del Sol durante la totalidad cambia a lo largo de la
    franja: unos 279° en Galicia y 288° en Baleares.
    """
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    az = np.asarray(az, dtype=np.float64)
    h0 = np.asarray(obs_elev, dtype=np.float64) + eye_h
    best = np.full(lat.shape, -90.0)
    best_d = np.zeros(lat.shape)
    for d in dists:
        tlat, tlon = _offset(lat, lon, az, d)
        ang = _angle(elev_at(tlat, tlon), h0, d)
        upd = ang > best
        best = np.where(upd, ang, best)
        best_d = np.where(upd, d, best_d)
    return (best, best_d) if return_distance else best


def horizon_fine(lat, lon, azimuths, obs_elev=None, eye_h=1.6, d_min=60.0,
                 step_near=25.0, d_split=NEAR_FAR_SPLIT, step_far=400.0,
                 d_max=200000.0, return_distance=False):
    """Un solo mirador: campo cercano a 1 segundo entero y campo lejano de mosaico.

    Si no se da obs_elev, se toma la altura interpolada a resolución entera del propio
    mirador.
    """
    lat = float(lat); lon = float(lon)
    if obs_elev is None:
        obs_elev = float(elev_fine(lat, lon)[0])
    h0 = obs_elev + eye_h
    azimuths = np.atleast_1d(np.asarray(azimuths, dtype=np.float64))
    d_near = np.arange(d_min, d_split, step_near)
    d_far = np.arange(d_split, d_max, step_far)

    best = np.full(azimuths.size, -90.0)
    best_d = np.zeros(azimuths.size)
    for ia, az in enumerate(azimuths):
        tlat, tlon = _offset(lat, lon, az, d_near)
        a1 = _angle(elev_fine(tlat, tlon), h0, d_near)
        tlat, tlon = _offset(lat, lon, az, d_far)
        a2 = _angle(elev_at(tlat, tlon), h0, d_far)
        allang = np.concatenate([a1, a2])
        alld = np.concatenate([d_near, d_far])
        i = int(np.argmax(allang))
        best[ia] = allang[i]
        best_d[ia] = alld[i]
    return (best, best_d, obs_elev) if return_distance else best


def sea_horizon_dip(obs_elev, eye_h=1.6):
    """Depresión aparente del horizonte marino (grados): el mejor caso teórico."""
    h = np.asarray(obs_elev, dtype=np.float64) + eye_h
    return -np.degrees(np.sqrt(2.0 * h * (1.0 - K_REFR) / R_EARTH))


if __name__ == '__main__':
    print('Independent checks (expected values derived by hand):\n')
    # 1. Open ocean to the west -> must come out at the sea-horizon dip.
    h, d, e = horizon_fine(43.1585, -9.2124, [275.0], return_distance=True)
    print(f'Cabo Vilan -> open Atlantic (az 275)      : {h[0]:+.3f} deg  '
          f'[sea dip at {e:.0f} m = {sea_horizon_dip(e):+.3f}]')
    # 2. Zaragoza -> Moncayo (2314 m, ~85 km, az ~285). Hand calc: ~+1.0 deg
    h, d, e = horizon_fine(41.6488, -0.8891, [285.0], return_distance=True)
    print(f'Zaragoza -> Moncayo (az 285)              : {h[0]:+.3f} deg  '
          f'blocker {d[0]/1000:5.1f} km   [hand calc ~+1.0 deg]')
    # 3. Sea-level beach looking west over water near Valencia
    h, d, e = horizon_fine(39.4200, -0.3300, [285.0], return_distance=True)
    print(f'Valencia coast -> inland (az 285)         : {h[0]:+.3f} deg  '
          f'blocker {d[0]/1000:5.1f} km')
    # 4. Consistency: coarse vs fine on a far-field-dominated view
    hc = horizon_coarse(41.6488, -0.8891, 225.0, [285.0])[0, 0]
    print(f'\ncoarse vs fine at Zaragoza az 285         : {hc:+.3f} vs '
          f'{horizon_fine(41.6488, -0.8891, [285.0])[0]:+.3f} deg')
