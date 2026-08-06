# -*- coding: utf-8 -*-
"""Perfil real del limbo lunar, con topografía LOLA y la libración del momento.

La Luna no es una esfera. Su borde tiene montañas y valles de hasta ±10 km, y la
totalidad empieza y acaba cuando el último trozo de fotosfera desaparece **detrás de
ese borde de verdad**, no detrás de un círculo. En el centro de la franja da igual: hay
kilómetros de margen. En el filo de la sombra es lo único que decide entre ver corona y
no verla, y es la diferencia entre publicar «5 s de totalidad» y publicar la verdad.

Cómo se calcula:

* La topografía sale del **LOLA** de la sonda LRO (16 píxeles por grado, ~1,9 km sobre
  el limbo), como radio respecto al centro de la Luna.
* La orientación de la Luna —la libración, o sea qué cara nos enseña ese día— sale de
  los núcleos de la NAIF (`moon_pa_de421`), no de una aproximación.
* Para cada ángulo de posición del borde se busca el **punto de tangencia** visto desde
  el observador, se pasa a coordenadas selenográficas y se lee el radio ahí.

El punto de tangencia no está a 90° de la dirección al observador sino a `arccos(R/D)`,
unos 0,26° más allá. Son ~8 km sobre la superficie: más que el tamaño de celda, así que
se corrige en vez de despreciarlo.

Y lo importante para los contactos: la totalidad exige que el disco del Sol quepa entero
dentro del limbo, así que el radio que manda es el del **ángulo de posición donde el Sol
asoma**, que es el de la separación entre centros. Eso es lo que devuelve
`moon_radius_toward()`.
"""
import os

import numpy as np

from .paths import DATA_DIR

MOON_DIR = os.path.join(DATA_DIR, 'moon')
LDEM = os.path.join(MOON_DIR, 'ldem_16.img')
BPC = os.path.join(MOON_DIR, 'moon_pa_de421_1900-2050.bpc')
TF = os.path.join(MOON_DIR, 'moon_080317.tf')
TPC = os.path.join(MOON_DIR, 'pck00011.tpc')

# de la etiqueta PDS de ldem_16
PPD = 16                      # píxeles por grado
NLINES, NSAMPLES = 2880, 5760
SCALE_M = 0.5                 # el entero de 16 bits está en unidades de medio metro
OFFSET_M = 1737400.0          # radio de la esfera de referencia
LINE_OFF, SAMPLE_OFF = 1439.5, 2879.5
CENTER_LON = 180.0

SOURCE = {'label': 'LOLA (LRO) — topografía lunar',
          'url': 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/'}

_grid = None
_frame = None


def available():
    return all(os.path.exists(p) for p in (LDEM, BPC, TF, TPC))


def _radius_grid():
    """Radio lunar en km, indexado [línea, muestra]."""
    global _grid
    if _grid is None:
        a = np.fromfile(LDEM, dtype='<i2').reshape(NLINES, NSAMPLES)
        _grid = (a.astype(np.float32) * SCALE_M + OFFSET_M) / 1000.0
    return _grid


def _moon_frame():
    global _frame
    if _frame is None:
        from skyfield.planetarylib import PlanetaryConstants
        pc = PlanetaryConstants()
        pc.read_text(open(TF, 'rb'))
        pc.read_text(open(TPC, 'rb'))
        pc.read_binary(open(BPC, 'rb'))
        _frame = pc.build_frame_named('MOON_PA_DE421')
    return _frame


def radius_at(lat_deg, lon_deg):
    """Radio lunar (km) en unas coordenadas selenográficas. Vectorial."""
    g = _radius_grid()
    line = (0.0 - np.asarray(lat_deg)) * PPD + LINE_OFF
    samp = (np.asarray(lon_deg) - CENTER_LON) * PPD + SAMPLE_OFF
    li = np.clip(np.rint(line).astype(np.int64), 0, NLINES - 1)
    si = np.rint(samp).astype(np.int64) % NSAMPLES
    return g[li, si]


def _basis(moon_from_observer_km):
    """Base del plano del cielo: (dirección de mirada, norte, este).

    Se define desde el observador, y el MISMO par (norte, este) se usa para medir el
    ángulo de posición del Sol y para muestrear el limbo. Así el convenio de signos se
    cancela por construcción, que es donde es fácil equivocarse.
    """
    m = np.asarray(moon_from_observer_km, dtype=float)
    look = m / np.linalg.norm(m)
    z = np.array([0.0, 0.0, 1.0])
    north = z - np.dot(z, look) * look
    north /= np.linalg.norm(north)
    east = np.cross(look, north)
    return look, north, east


def profile(t, moon_from_observer_km, n=720):
    """Radio del limbo (km) en `n` ángulos de posición. Devuelve (ángulos_rad, radios)."""
    look, north, east = _basis(moon_from_observer_km)
    D = np.linalg.norm(moon_from_observer_km)
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    # dirección en el plano del cielo, perpendicular a la línea de mirada
    l = (north[None, :] * np.cos(theta)[:, None] +
         east[None, :] * np.sin(theta)[:, None])
    # punto de tangencia: inclinado arccos(R/D) desde la dirección al observador
    s = OFFSET_M / 1000.0 / D
    tang = l * np.sqrt(max(0.0, 1.0 - s * s)) - look[None, :] * s
    R = _moon_frame().rotation_at(t)
    v = tang @ R.T                      # a coordenadas fijas de la Luna
    lat = np.degrees(np.arcsin(np.clip(v[:, 2], -1, 1)))
    lon = np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 360.0
    return theta, radius_at(lat, lon)


def rotation_at(t):
    """Matriz ICRF -> coordenadas fijas de la Luna. Cara, se calcula una vez por punto."""
    return _moon_frame().rotation_at(t)


def moon_radius_toward_rot(rot, moon_from_observer_km, sun_offset_km):
    """Igual que `moon_radius_toward` pero con la rotación ya calculada."""
    look, north, east = _basis(moon_from_observer_km)
    v = np.asarray(sun_offset_km, dtype=float).ravel()
    vn, ve = float(np.dot(v, north)), float(np.dot(v, east))
    D = float(np.linalg.norm(moon_from_observer_km))
    s = OFFSET_M / 1000.0 / D
    if abs(vn) < 1e-12 and abs(ve) < 1e-12:
        # centros coincidentes: el ángulo es indeterminado y manda el trozo más bajo
        theta = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False)
        l = north[None, :] * np.cos(theta)[:, None] + east[None, :] * np.sin(theta)[:, None]
        tang = l * np.sqrt(max(0.0, 1.0 - s * s)) - look[None, :] * s
        u = tang @ rot.T
        lat = np.degrees(np.arcsin(np.clip(u[:, 2], -1, 1)))
        lon = np.degrees(np.arctan2(u[:, 1], u[:, 0])) % 360.0
        return float(radius_at(lat, lon).min())
    theta = np.arctan2(ve, vn)
    l = north * np.cos(theta) + east * np.sin(theta)
    tang = l * np.sqrt(max(0.0, 1.0 - s * s)) - look * s
    u = rot @ tang
    lat = np.degrees(np.arcsin(np.clip(u[2], -1, 1)))
    lon = np.degrees(np.arctan2(u[1], u[0])) % 360.0
    return float(radius_at(lat, lon))


def moon_radius_toward(t, moon_from_observer_km, sun_offset_km):
    """Radio del limbo (km) en el ángulo de posición hacia el que se separa el Sol.

    `sun_offset_km` es el vector del centro de la Luna al centro del Sol; sólo importa
    su proyección en el plano del cielo. Si los centros coinciden exactamente el ángulo
    es indeterminado y se devuelve el mínimo del limbo, que es el criterio prudente:
    es el trozo de borde que primero deja escapar la fotosfera.
    """
    look, north, east = _basis(moon_from_observer_km)
    v = np.asarray(sun_offset_km, dtype=float)
    vn, ve = np.dot(v, north), np.dot(v, east)
    if abs(vn) < 1e-9 and abs(ve) < 1e-9:
        return float(profile(t, moon_from_observer_km)[1].min())
    theta = np.arctan2(ve, vn)
    D = np.linalg.norm(moon_from_observer_km)
    s = OFFSET_M / 1000.0 / D
    l = north * np.cos(theta) + east * np.sin(theta)
    tang = l * np.sqrt(max(0.0, 1.0 - s * s)) - look * s
    u = _moon_frame().rotation_at(t) @ tang
    lat = np.degrees(np.arcsin(np.clip(u[2], -1, 1)))
    lon = np.degrees(np.arctan2(u[1], u[0])) % 360.0
    return float(radius_at(lat, lon))
