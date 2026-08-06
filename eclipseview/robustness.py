"""Barrido de robustez local: ¿un buen horizonte es propiedad del ÁREA o de un píxel con
suerte?

De cada zona se evalúa el margen en una rejilla fina a resolución entera y se informa
del reparto, más el mejor sitio concreto. Un sitio sólo merece recomendarse si una
parte decente de su alrededor también funciona; si no, la recomendación es un artefacto
de dónde cayó exactamente la muestra del modelo de elevación.
"""
import json, os, sys
import numpy as np
from .ephem import circumstances
from .terrain import horizon_fine, elev_fine
from .paths import ZONES_JSON

_here = os.path.dirname(os.path.abspath(__file__))

ZONES = [
    ('Sierra de Gudar / Cañizar (Teruel)', 40.760, -0.640, 9.0),
    ('Maestrazgo (Teruel)',                40.550, -0.520, 9.0),
    ('Soria - Golmayo / Duero',            41.730, -2.610, 9.0),
    ('Soria - Matamala (centreline)',      41.500, -2.620, 9.0),
    ('Aguilar de Campoo (Palencia)',       42.740, -4.230, 9.0),
    ('Palencia meseta (Boedo)',            42.510, -4.300, 9.0),
    ('Asturias - Valdes / Luarca',         43.545, -6.520, 7.0),
    ('Asturias - Cabo Vidio / Cudillero',  43.570, -6.200, 7.0),
    ('Peniscola / Benicarlo coast',        40.380,  0.390, 9.0),
    ('Ebro valley S of Zaragoza',          41.450, -1.050, 12.0),
    ('Mallorca NW coast (Tramuntana)',     39.700,  2.560, 9.0),
]

N = 13          # la rejilla es de N x N


def zone(name, clat, clon, half_km):
    dlat = half_km / 111.2
    dlon = half_km / (111.32 * np.cos(np.radians(clat)))
    las = np.linspace(clat - dlat, clat + dlat, N)
    los = np.linspace(clon - dlon, clon + dlon, N)

    c = circumstances(clat, clon, 0.0)
    if not c['total']:
        print(f'{name}: not in totality')
        return None
    azs = np.array([c['c2_az'], c['max_az'], c['c3_az']])
    alts = np.array([c['c2_alt_app'], c['max_alt_app'], c['c3_alt_app']])

    best = (-99, None)
    vals, elevs = [], []
    for la in las:
        for lo in los:
            e = float(elev_fine(la, lo)[0])
            if e < 1.0:                       # sea
                continue
            hz = horizon_fine(la, lo, azs, obs_elev=e)
            cl = float(np.min(alts - hz))
            vals.append(cl); elevs.append(e)
            if cl > best[0]:
                best = (cl, (float(la), float(lo), e))
    if not vals:
        print(f'{name}: all sea')
        return None
    v = np.array(vals)
    frac = float((v >= 2.0).mean())
    print(f'{name:36s} n={v.size:4d}  clear: worst {v.min():+6.2f}  median '
          f'{np.median(v):+6.2f}  best {v.max():+6.2f}   {100*frac:5.1f}% of area '
          f'>= +2.0 deg   best at {best[1][0]:.4f},{best[1][1]:.4f} ({best[1][2]:.0f} m)')
    return dict(name=name, n=int(v.size), worst=round(float(v.min()), 2),
                median=round(float(np.median(v)), 2), best=round(float(v.max()), 2),
                frac_ok=round(frac, 3), dur=round(c['duration_s'], 1),
                alt_c3=round(c['c3_alt_app'], 2),
                best_lat=round(best[1][0], 5), best_lon=round(best[1][1], 5),
                best_elev=round(best[1][2]))


if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else None
    out = []
    for nm, la, lo, hk in ZONES:
        if only and only.lower() not in nm.lower():
            continue
        r = zone(nm, la, lo, hk)
        if r:
            out.append(r)
    with open(ZONES_JSON, 'w') as f:
        json.dump(out, f, indent=1)
