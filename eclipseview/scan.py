"""Scan the whole Spanish totality band for viewpoints whose WNW skyline is low
enough that the eclipsed Sun stays clear of the terrain for the WHOLE of totality.

Metric: clearance = (apparent Sun altitude) - (apparent terrain horizon altitude),
evaluated at C2, mid-totality and C3, in each case at that instant's own azimuth.
The score is the MINIMUM of the three: the Sun must be clear the entire time, and it
is sinking while the eclipse runs, so C3 is usually the binding constraint.
"""
import os, pickle
import numpy as np
from . import field
from .terrain import elev_at, horizon_per_point, PER_DEG, LAT_N, LON_W
from .paths import SCAN_PKL

_here = os.path.dirname(os.path.abspath(__file__))
OUT = SCAN_PKL

STRIDE = 6            # mosaic cells -> ~1.1 km grid
MIN_DUR = 60.0        # s of totality demanded
CHUNK = 40000

# Ranking pass: sampling to 150 km. Terrain beyond that would have to exceed ~3 km
# to intrude above 1 deg, which does not occur west of the band.
DISTS = np.concatenate([np.arange(400.0, 25000.0, 180.0),
                        np.arange(25000.0, 150000.0, 800.0)])


def main():
    f = field.load()

    # Candidate grid over the mosaic
    rows = np.arange(0, 3600, STRIDE)
    cols = np.arange(0, 8400, STRIDE)
    lat_g = LAT_N - rows / PER_DEG
    lon_g = LON_W + cols / PER_DEG
    LO, LA = np.meshgrid(lon_g, lat_g)
    LA = LA.ravel(); LO = LO.ravel()
    print(f'grid points: {LA.size:,}')

    elev = elev_at(LA, LO)
    dur = field.interp(f['dur'], LA, LO)

    keep = (dur >= MIN_DUR) & (elev >= 2.0)
    LA, LO, elev, dur = LA[keep], LO[keep], elev[keep], dur[keep]
    print(f'inside band, on land, dur>={MIN_DUR:.0f}s: {LA.size:,}')

    a_c2 = field.interp(f['a_c2'], LA, LO); z_c2 = field.interp(f['z_c2'], LA, LO)
    a_c3 = field.interp(f['a_c3'], LA, LO); z_c3 = field.interp(f['z_c3'], LA, LO)
    a_mx = field.interp(f['a_mx'], LA, LO); z_mx = field.interp(f['z_mx'], LA, LO)

    clear = np.full(LA.size, np.nan)
    hz_c3 = np.full(LA.size, np.nan)
    bd_c3 = np.full(LA.size, np.nan)
    for s in range(0, LA.size, CHUNK):
        e = min(s + CHUNK, LA.size)
        sl = slice(s, e)
        c = np.full(e - s, np.inf)
        for alt, az, tag in ((a_c2[sl], z_c2[sl], 'c2'),
                             (a_mx[sl], z_mx[sl], 'mx'),
                             (a_c3[sl], z_c3[sl], 'c3')):
            h, bd = horizon_per_point(LA[sl], LO[sl], elev[sl], az, DISTS,
                                      return_distance=True)
            c = np.minimum(c, alt - h)
            if tag == 'c3':
                hz_c3[sl] = h
                bd_c3[sl] = bd
        clear[sl] = c
        print(f'  {e:,}/{LA.size:,}', flush=True)

    d = dict(lat=LA, lon=LO, elev=elev, dur=dur, clear=clear,
             hz_c3=hz_c3, bd_c3=bd_c3, a_c2=a_c2, a_c3=a_c3,
             z_c2=z_c2, z_c3=z_c3, a_mx=a_mx, z_mx=z_mx)
    with open(OUT, 'wb') as fh:
        pickle.dump(d, fh)

    print(f'\nclearance: min {np.nanmin(clear):+.2f}  max {np.nanmax(clear):+.2f} deg')
    for thr in (0.0, 0.5, 1.0, 2.0, 3.0):
        n = int((clear > thr).sum())
        print(f'  sites with clearance > {thr:.1f} deg: {n:,} '
              f'({100.0*n/clear.size:.1f}%)')
    good = clear > 1.0
    if good.any():
        print(f'\nof those, longest totality: {dur[good].max():.0f}s')


if __name__ == '__main__':
    main()
