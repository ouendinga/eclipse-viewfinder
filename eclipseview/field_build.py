"""Construcción en paralelo del campo de geometría del eclipse, un trabajador por fila de
latitud.

Usa el método de arranque 'spawn' a propósito: las efemérides del JPL van mapeadas en
memoria de forma perezosa, y un hijo por `fork` hereda ese mapeo a medio hacer, que
revienta dentro de jplephem («cannot reshape array of size ...»). Los hijos lanzados
con spawn se lo importan y lo mapean ellos.
"""
import multiprocessing as mp
import os, pickle
import numpy as np
from .paths import FIELD_PKL

LATS = np.arange(38.0, 45.01, 0.25)
LONS = np.arange(-10.0, 4.51, 0.25)
CACHE = FIELD_PKL


def row(la):
    # Se importa DENTRO del worker por lo del mmap (ver el docstring de arriba). El
    # módulo se llama eclipseview.ephem; ponía `from eclipse import ...`, que es un
    # nombre que no existe: `eclipseview setup` reventaba en el primer worker.
    from .ephem import circumstances
    out = []
    for lo in LONS:
        c = circumstances(float(la), float(lo), 0.0, coarse_step_s=60.0)
        iso = c['max_utc']
        tsec = float(iso[11:13]) * 3600 + float(iso[14:16]) * 60 + float(iso[17:19])
        if c['total']:
            out.append((c['duration_s'], c['magnitude'], c['c2_alt_app'], c['c2_az'],
                        c['c3_alt_app'], c['c3_az'], c['max_alt_app'], c['max_az'], tsec))
        else:
            out.append((0.0, c['magnitude'], c['max_alt_app'], c['max_az'],
                        c['max_alt_app'], c['max_az'], c['max_alt_app'], c['max_az'], tsec))
    return np.array(out)


def main():
    for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[v] = '1'
    ctx = mp.get_context('spawn')
    with ctx.Pool(14) as p:
        rows = p.map(row, [float(x) for x in LATS], chunksize=1)
    A = np.stack(rows)
    d = dict(lats=LATS, lons=LONS,
             dur=A[:, :, 0], mag=A[:, :, 1],
             a_c2=A[:, :, 2], z_c2=A[:, :, 3],
             a_c3=A[:, :, 4], z_c3=A[:, :, 5],
             a_mx=A[:, :, 6], z_mx=A[:, :, 7], t_mx=A[:, :, 8])
    with open(CACHE, 'wb') as fh:
        pickle.dump(d, fh)
    print('saved', CACHE)
    print('max totality in box: %.1f s' % d['dur'].max())
    i, j = np.unravel_index(np.argmax(d['dur']), d['dur'].shape)
    print('  at lat %.2f lon %.2f' % (LATS[i], LONS[j]))


if __name__ == '__main__':
    main()
