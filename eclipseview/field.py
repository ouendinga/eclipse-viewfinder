"""Calcula el campo de geometría del eclipse sobre la Península en una rejilla gruesa y
expone luego interpoladores bilineales rápidos. La geometría varía suavemente en
decenas de km, así que una rejilla de 0,25° interpola con un error muy por debajo de
0,01° de altura del Sol.
"""
import os, pickle
import numpy as np
from .ephem import circumstances
from .paths import FIELD_PKL

_here = os.path.dirname(os.path.abspath(__file__))
CACHE = FIELD_PKL

LATS = np.arange(38.0, 45.01, 0.25)
LONS = np.arange(-10.0, 4.51, 0.25)


def build():
    n_la, n_lo = LATS.size, LONS.size
    dur = np.zeros((n_la, n_lo))
    mag = np.zeros((n_la, n_lo))
    a_c2 = np.zeros((n_la, n_lo)); z_c2 = np.zeros((n_la, n_lo))
    a_c3 = np.zeros((n_la, n_lo)); z_c3 = np.zeros((n_la, n_lo))
    a_mx = np.zeros((n_la, n_lo)); z_mx = np.zeros((n_la, n_lo))
    t_mx = np.zeros((n_la, n_lo))
    for i, la in enumerate(LATS):
        for j, lo in enumerate(LONS):
            c = circumstances(float(la), float(lo), 0.0, coarse_step_s=60.0)
            mag[i, j] = c['magnitude']
            a_mx[i, j] = c['max_alt_app']; z_mx[i, j] = c['max_az']
            t_mx[i, j] = float(c['max_utc'][11:13]) * 3600 + \
                float(c['max_utc'][14:16]) * 60 + float(c['max_utc'][17:19])
            if c['total']:
                dur[i, j] = c['duration_s']
                a_c2[i, j] = c['c2_alt_app']; z_c2[i, j] = c['c2_az']
                a_c3[i, j] = c['c3_alt_app']; z_c3[i, j] = c['c3_az']
            else:
                a_c2[i, j] = a_c3[i, j] = c['max_alt_app']
                z_c2[i, j] = z_c3[i, j] = c['max_az']
        print(f'  lat {la:.2f} done  (max dur in row {dur[i].max():.0f}s)', flush=True)
    d = dict(lats=LATS, lons=LONS, dur=dur, mag=mag, a_c2=a_c2, z_c2=z_c2,
             a_c3=a_c3, z_c3=z_c3, a_mx=a_mx, z_mx=z_mx, t_mx=t_mx)
    with open(CACHE, 'wb') as f:
        pickle.dump(d, f)
    return d


def load():
    if not os.path.exists(CACHE):
        return build()
    with open(CACHE, 'rb') as f:
        return pickle.load(f)


def interp(grid, lat, lon):
    """Bilinear interpolation of a field defined on (LATS, LONS)."""
    lat = np.atleast_1d(np.asarray(lat, dtype=np.float64))
    lon = np.atleast_1d(np.asarray(lon, dtype=np.float64))
    fi = np.clip((lat - LATS[0]) / 0.25, 0, LATS.size - 1.0001)
    fj = np.clip((lon - LONS[0]) / 0.25, 0, LONS.size - 1.0001)
    i0 = fi.astype(np.int64); j0 = fj.astype(np.int64)
    dy = fi - i0; dx = fj - j0
    return (grid[i0, j0] * (1 - dy) * (1 - dx) + grid[i0 + 1, j0] * dy * (1 - dx)
            + grid[i0, j0 + 1] * (1 - dy) * dx + grid[i0 + 1, j0 + 1] * dy * dx)


if __name__ == '__main__':
    d = load()
    dur = d['dur']
    print(f"\nmax totality anywhere in box: {dur.max():.1f}s")
    i, j = np.unravel_index(np.argmax(dur), dur.shape)
    print(f"  at lat {LATS[i]:.2f} lon {LONS[j]:.2f}")
    # ¿Por dónde pasa la línea central? Para cada longitud, la latitud de duración
    # máxima.
    print("\ncentreline (latitude of longest totality per longitude):")
    for j, lo in enumerate(LONS):
        col = dur[:, j]
        if col.max() < 30:
            continue
        i = int(np.argmax(col))
        print(f"  lon {lo:+6.2f}  lat {LATS[i]:.2f}  dur {col[i]:5.1f}s  "
              f"sun alt {d['a_mx'][i,j]:5.2f} az {d['z_mx'][i,j]:6.2f}")
