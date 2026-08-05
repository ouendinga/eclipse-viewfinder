"""Render a map of the totality band over Iberia, from our own DEM mosaic.

Writes map.svg: a terrain raster (PNG embedded as a data URI, encoded by hand with
zlib -- no image libraries needed) plus the centreline, the band limits and the
recommended sites drawn as SVG on top.
"""
import json, os, struct, zlib, base64
import numpy as np
from . import field
from .paths import LIMITS_JSON, MAP_SVG, DATA_DIR

_here = os.path.dirname(os.path.abspath(__file__))

# Map window
LA_N, LA_S, LO_W, LO_E = 44.6, 38.4, -9.6, 4.4
W, H = 900, 400


def png_bytes(rgb):
    """Encode an (h, w, 3) uint8 array as a PNG."""
    h, w, _ = rgb.shape
    raw = b''.join(b'\x00' + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def terrain_raster():
    from .terrain import dem, PER_DEG, LAT_N, LON_W
    d = dem()
    r0 = int((LAT_N - LA_N) * PER_DEG); r1 = int((LAT_N - LA_S) * PER_DEG)
    c0 = int((LO_W - LON_W) * PER_DEG); c1 = int((LO_E - LON_W) * PER_DEG)
    sub = d[r0:r1, c0:c1].astype(np.float32)
    # nearest-neighbour resample to W x H
    yi = (np.linspace(0, sub.shape[0] - 1, H)).astype(np.int64)
    xi = (np.linspace(0, sub.shape[1] - 1, W)).astype(np.int64)
    z = sub[np.ix_(yi, xi)]

    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    sea = z <= 0
    # muted ink-on-paper palette; land ramps warm-grey -> pale
    t = np.clip(z / 2200.0, 0, 1)
    rgb[..., 0] = (68 + t * 150).astype(np.uint8)
    rgb[..., 1] = (66 + t * 140).astype(np.uint8)
    rgb[..., 2] = (60 + t * 120).astype(np.uint8)
    rgb[sea] = np.array([22, 30, 38], dtype=np.uint8)
    return rgb


def contour_segments(grid, lats, lons, level):
    """Marching squares: segments where `grid` crosses `level`, in (lon, lat).

    Written out rather than pulled from a plotting library because the map is hand
    drawn as SVG and the whole project ships with only numpy.
    """
    segs = []
    for i in range(len(lats) - 1):
        for j in range(len(lons) - 1):
            # corners, counter-clockwise from bottom-left
            v = [grid[i, j], grid[i, j + 1], grid[i + 1, j + 1], grid[i + 1, j]]
            if min(v) > level or max(v) < level:
                continue
            corners = [(lons[j], lats[i]), (lons[j + 1], lats[i]),
                       (lons[j + 1], lats[i + 1]), (lons[j], lats[i + 1])]
            pts = []
            for k in range(4):
                a, b = v[k], v[(k + 1) % 4]
                if (a < level) == (b < level) or a == b:
                    continue
                t = (level - a) / (b - a)
                (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
                pts.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
            for k in range(0, len(pts) - 1, 2):
                segs.append((pts[k], pts[k + 1]))
    return segs


def main():
    f = field.load()

    def X(lon):
        return (np.asarray(lon) - LO_W) / (LO_E - LO_W) * W

    def Y(lat):
        return (LA_N - np.asarray(lat)) / (LA_N - LA_S) * H

    lim_path = LIMITS_JSON
    if os.path.exists(lim_path):
        # exact limits, solved by bisection with the real engine
        with open(lim_path) as fh:
            lim = json.load(fh)
        centre = [(r['lon'], r['centre']) for r in lim]
        north = [(r['lon'], r['north']) for r in lim]
        south = [(r['lon'], r['south']) for r in lim]
        print('using exact limits from limits.json')
    else:
        lons = np.arange(LO_W, LO_E + 0.01, 0.1)
        las = np.arange(38.4, 44.61, 0.004)
        centre, north, south = [], [], []
        for lo in lons:
            dur = field.interp(f['dur'], las, np.full_like(las, lo))
            if dur.max() < 1.0:
                continue
            centre.append((lo, las[int(np.argmax(dur))]))
            tot = las[dur > 0.5]
            north.append((lo, tot.max())); south.append((lo, tot.min()))
        print('using interpolated limits (limits.json not present)')

    def path(pts):
        return ' '.join(f'{X(lo):.1f},{Y(la):.1f}' for lo, la in pts)

    # Every recommended viewpoint, coloured by the margin that survives trees and
    # buildings. The map and the search now show the same dataset.
    pts_path = os.path.join(DATA_DIR, 'points.json')
    sites = []
    if os.path.exists(pts_path):
        with open(pts_path) as fh:
            sites = json.load(fh)['points']

    png = base64.b64encode(png_bytes(terrain_raster())).decode()
    o = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" class="map" '
         f'role="img"><title>Franja de totalidad del eclipse del 12 de agosto de 2026 '
         f'sobre la peninsula iberica</title>']
    o.append(f'<image href="data:image/png;base64,{png}" x="0" y="0" '
             f'width="{W}" height="{H}" preserveAspectRatio="none"/>')
    # band as a filled ribbon
    ribbon = path(north) + ' ' + path(list(reversed(south)))
    o.append(f'<polygon points="{ribbon}" fill="#ffd9a0" fill-opacity="0.20" '
             f'stroke="#ffd9a0" stroke-opacity="0.55" stroke-width="1"/>')
    o.append(f'<polyline points="{path(centre)}" fill="none" stroke="#ff9b3d" '
             f'stroke-width="1.6" stroke-dasharray="7 4"/>')
    for s in sites:
        net = s.get('clear_net', s.get('clear', 0))
        if net < 1.5:
            col, r = '#ff5c5c', 2.0
        elif net >= 5:
            col, r = '#8ce99a', 2.6
        else:
            col, r = '#ffe066', 2.3
        x, y = float(X(s['lon'])), float(Y(s['lat']))
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}" '
                 f'fill-opacity="0.9" stroke="#0e1116" stroke-width="0.7"/>')
    # a few reference cities for orientation
    # --- Sun altitude at maximum, as contours -------------------------------
    # Xavier Jubier's map draws the line where maximum eclipse coincides with sunset.
    # For this project the useful generalisation is the whole family: how high the Sun
    # actually is, which is what decides whether the terrain swallows it.
    las_f, lons_f = f['lats'], f['lons']
    mag = f['mag']
    inside = mag >= 0.90
    alt = np.where(inside, f['a_mx'], np.nan)
    for lvl in (2, 4, 6, 8, 10, 12):
        segs = contour_segments(np.nan_to_num(alt, nan=-99.0), las_f, lons_f, lvl)
        if not segs:
            continue
        d = ' '.join(f'M{X(a[0]):.1f},{Y(a[1]):.1f} L{X(b[0]):.1f},{Y(b[1]):.1f}'
                     for a, b in segs)
        o.append(f'<path d="{d}" fill="none" stroke="#7fd4ff" stroke-opacity="0.5" '
                 f'stroke-width="0.9" stroke-dasharray="2 3"/>')
        # label on the segment closest to the middle of the drawn map
        mid = min(segs, key=lambda sg: abs(sg[0][0] - (LO_W + LO_E) / 2))
        o.append(f'<text x="{X(mid[0][0]):.1f}" y="{Y(mid[0][1]):.1f}" '
                 f'fill="#7fd4ff" fill-opacity="0.85" font-size="9" '
                 f'text-anchor="middle">{lvl}&#176;</text>')

    # --- Time of maximum, every 10 minutes ----------------------------------
    tmx = np.where(inside, f['t_mx'] / 60.0, np.nan)      # minutes UTC
    t0 = np.nanmin(tmx); t1 = np.nanmax(tmx)
    start = int(np.ceil(t0 / 10.0) * 10)
    for m in range(start, int(t1) + 1, 10):
        segs = contour_segments(np.nan_to_num(tmx, nan=-999.0), las_f, lons_f, m)
        if not segs:
            continue
        d = ' '.join(f'M{X(a[0]):.1f},{Y(a[1]):.1f} L{X(b[0]):.1f},{Y(b[1]):.1f}'
                     for a, b in segs)
        o.append(f'<path d="{d}" fill="none" stroke="#ffb37a" stroke-opacity="0.38" '
                 f'stroke-width="0.8"/>')
        lo_lab = min(segs, key=lambda sg: abs(sg[0][1] - 43.6))
        hh = int((m + 120) // 60) % 24
        o.append(f'<text x="{X(lo_lab[0][0]):.1f}" y="{Y(lo_lab[0][1]) - 3:.1f}" '
                 f'fill="#ffb37a" fill-opacity="0.75" font-size="8" '
                 f'text-anchor="middle">{hh:02d}:{int(m % 60):02d}</text>')

    for nm, la, lo in [('Barcelona', 41.39, 2.17), ('Madrid', 40.42, -3.70),
                       ('Zaragoza', 41.65, -0.89), ('Oviedo', 43.36, -5.85),
                       ('Valencia', 39.47, -0.38), ('Palma', 39.57, 2.65),
                       ('Burgos', 42.34, -3.70)]:
        x, y = float(X(lo)), float(Y(la))
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="#cbd5e1"/>')
        o.append(f'<text x="{x+5:.1f}" y="{y+3.5:.1f}" fill="#cbd5e1" '
                 f'font-size="10">{nm}</text>')
    o.append('</svg>')
    with open(MAP_SVG, 'w') as fh:
        fh.write(''.join(o))
    print('wrote map.svg', len(''.join(o)) // 1024, 'KB')
    print('centreline sampled at', len(centre), 'longitudes')


if __name__ == '__main__':
    main()
