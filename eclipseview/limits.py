"""Exact northern/southern limits of the umbral path, by bisection on latitude.

The interpolated 0.25 deg field is fine for ranking sites but its band edge is
piecewise-linear, which shows up as visible faceting when drawn. Here the limit is
solved with the real engine so the drawn ribbon and the quoted width are computed,
not remembered.
"""
import json, multiprocessing as mp, os
import numpy as np
from .paths import LIMITS_JSON

LONS = np.arange(-9.5, 4.01, 0.25)
CACHE = LIMITS_JSON


def solve(lon):
    from eclipse import circumstances

    def total(la):
        return circumstances(float(la), float(lon), 0.0, coarse_step_s=120.0)['total']

    # locate any latitude inside the umbra by scanning coarsely
    las = np.arange(37.0, 46.01, 0.25)
    inside = [la for la in las if total(la)]
    if not inside:
        return dict(lon=float(lon), ok=False)
    mid = float(np.mean(inside))

    def edge(lo, hi):
        """lo is inside, hi is outside; return the boundary latitude."""
        for _ in range(16):
            m = 0.5 * (lo + hi)
            if total(m):
                lo = m
            else:
                hi = m
        return 0.5 * (lo + hi)

    north = edge(mid, mid + 3.0)
    south = edge(mid, mid - 3.0)
    return dict(lon=float(lon), ok=True, north=north, south=south,
                centre=0.5 * (north + south))


def main():
    for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[v] = '1'
    with mp.get_context('spawn').Pool(14) as p:
        res = p.map(solve, [float(x) for x in LONS])
    res = [r for r in res if r.get('ok')]
    json.dump(res, open(CACHE, 'w'), indent=1)

    lon = np.array([r['lon'] for r in res])
    n = np.array([r['north'] for r in res])
    s = np.array([r['south'] for r in res])
    c = np.array([r['centre'] for r in res])
    # perpendicular width = N-S chord * cos(angle of the path from the E-W direction)
    dlat = np.gradient(c) * 111.2
    dlon = np.gradient(lon) * 111.32 * np.cos(np.radians(c))
    theta = np.arctan2(dlat, dlon)
    width = (n - s) * 111.2 * np.abs(np.cos(theta))
    print(f'{"lon":>7s} {"south":>8s} {"centre":>8s} {"north":>8s} '
          f'{"N-S km":>8s} {"width km":>9s}')
    for i in range(0, len(res), 2):
        print(f'{lon[i]:+7.2f} {s[i]:8.3f} {c[i]:8.3f} {n[i]:8.3f} '
              f'{(n[i]-s[i])*111.2:8.1f} {width[i]:9.1f}')
    over_spain = (lon >= -7.5) & (lon <= 3.0)
    print(f'\nperpendicular umbral width over Spain: '
          f'{width[over_spain].min():.0f}-{width[over_spain].max():.0f} km '
          f'(mean {width[over_spain].mean():.0f} km)')


if __name__ == '__main__':
    main()
