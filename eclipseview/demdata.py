"""Construye un mosaico de elevación agrupado por máximo sobre la franja del eclipse, a
partir de teselas SRTM .hgt.gz.

Agrupar por máximo (y no promediar) es deliberado: la pregunta es «¿puede taparme el
Sol algo del terreno en este rumbo?», así que el punto más alto de cada celda es la
respuesta conservadora. Promediar alisaría las crestas y haría que los sitios
parecieran mejores de lo que son.

Salida: mosaic.npy (int16) + mosaic.json con la georreferenciación.
"""
import gzip, json, os
import numpy as np
from .paths import DEM_DIR, MOSAIC_NPY, MOSAIC_JSON, ensure


POOL = 6                     # 1 arcsec -> 6 arcsec (~185 m)
PER_DEG = 3600 // POOL       # 600 samples per degree
LAT_N, LAT_S = 45, 39        # mosaic covers lat 39..45
LON_W, LON_E = -10, 4        # and lon -10..4

ROWS = (LAT_N - LAT_S) * PER_DEG
COLS = (LON_E - LON_W) * PER_DEG


def tile_name(lat, lon):
    ns = 'N' if lat >= 0 else 'S'
    ew = 'E' if lon >= 0 else 'W'
    return f'{ns}{abs(lat):02d}{ew}{abs(lon):03d}.hgt.gz'


def load_tile(lat, lon):
    """Devuelve un array int16 de 600x600 agrupado por máximo para la tesela de 1x1 grado, o
    None.
    """
    path = os.path.join(DEM_DIR, tile_name(lat, lon))
    if not os.path.exists(path):
        return None
    with gzip.open(path, 'rb') as f:
        raw = np.frombuffer(f.read(), dtype='>i2')
    if raw.size != 3601 * 3601:
        print(f'  ! {tile_name(lat, lon)} unexpected size {raw.size}, skipping')
        return None
    a = raw.reshape(3601, 3601).astype(np.int16)
    a = np.where(a < -1000, 0, a)          # SRTM voids -> sea level
    a = a[:3600, :3600]                    # fuera la fila/columna que comparte vecino
    return a.reshape(PER_DEG, POOL, PER_DEG, POOL).max(axis=(1, 3)).astype(np.int16)


def main():
    mosaic = np.zeros((ROWS, COLS), dtype=np.int16)
    found = 0
    for lat in range(LAT_S, LAT_N):
        for lon in range(LON_W, LON_E):
            t = load_tile(lat, lon)
            if t is None:
                continue
            found += 1
            # la fila 0 del mosaico es el borde norte (lat = LAT_N)
            r0 = (LAT_N - (lat + 1)) * PER_DEG
            c0 = (lon - LON_W) * PER_DEG
            mosaic[r0:r0 + PER_DEG, c0:c0 + PER_DEG] = t
    np.save(MOSAIC_NPY, mosaic)
    meta = dict(lat_n=LAT_N, lat_s=LAT_S, lon_w=LON_W, lon_e=LON_E,
                per_deg=PER_DEG, rows=ROWS, cols=COLS, pool=POOL)
    with open(MOSAIC_JSON, 'w') as f:
        json.dump(meta, f, indent=1)
    print(f'tiles used: {found}')
    print(f'mosaic {mosaic.shape} int16 = {mosaic.nbytes/1e6:.0f} MB')
    print(f'elev range {mosaic.min()} .. {mosaic.max()} m')
    # cordura: el punto más alto de la caja tiene que caer en el Pirineo (Aneto 3404 m)
    r, c = np.unravel_index(np.argmax(mosaic), mosaic.shape)
    print(f'highest cell at lat {LAT_N - r/PER_DEG:.3f}, lon {LON_W + c/PER_DEG:.3f} '
          f'= {mosaic[r, c]} m')


if __name__ == '__main__':
    main()
