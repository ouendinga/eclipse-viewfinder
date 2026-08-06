"""Barre la franja de totalidad española buscando miradores cuya silueta al ONO sea lo
bastante baja como para que el Sol eclipsado no toque el terreno durante TODA la
totalidad.

La métrica: margen = (altura aparente del Sol) - (altura aparente del horizonte),
evaluado en C2, a mitad de totalidad y en C3, cada uno con su propio azimut. La
puntuación es el MÍNIMO de los tres: el Sol tiene que estar libre todo el rato, y va
bajando mientras dura el eclipse, así que el que suele mandar es C3.
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

# Pasada de ranking: se muestrea hasta 150 km. Para asomar por encima de 1° desde más
# lejos, el terreno tendría que pasar de ~3 km, y eso no ocurre al oeste de la banda.
DISTS = np.concatenate([np.arange(400.0, 25000.0, 180.0),
                        np.arange(25000.0, 150000.0, 800.0)])


def main(min_dur=MIN_DUR, min_mag=None, out_path=None, stride=STRIDE):
    """Recorre la región y calcula el margen de cada punto de tierra que pase el filtro.

    `min_mag` selecciona por magnitud del eclipse en vez de por segundos de totalidad, que
    es como se llega al terreno de parcial profundo fuera de la franja: desde un pueblo a
    100 km al norte de la sombra, la recomendación honrada sigue siendo un mirador y no
    una lista vacía.
    """
    f = field.load()

    # Rejilla de candidatos sobre el mosaico
    rows = np.arange(0, 3600, stride)
    cols = np.arange(0, 8400, stride)
    lat_g = LAT_N - rows / PER_DEG
    lon_g = LON_W + cols / PER_DEG
    LO, LA = np.meshgrid(lon_g, lat_g)
    LA = LA.ravel(); LO = LO.ravel()
    print(f'grid points: {LA.size:,}')

    elev = elev_at(LA, LO)
    dur = field.interp(f['dur'], LA, LO)

    if min_mag is not None:
        keep = (field.interp(f['mag'], LA, LO) >= min_mag) & (elev >= 2.0)
    else:
        keep = (dur >= min_dur) & (elev >= 2.0)
    LA, LO, elev, dur = LA[keep], LO[keep], elev[keep], dur[keep]
    print(f'seleccionados (land + filtro): {LA.size:,}')

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
    with open(out_path or OUT, 'wb') as fh:
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
