"""Local circumstances of the 2026-08-12 total solar eclipse, computed from JPL DE421.

For a given (lat, lon, h) we find:
  - C2 (start of totality), max eclipse, C3 (end of totality)
  - duration of totality
  - apparent (refracted) altitude and azimuth of the Sun at each instant

Method: topocentric apparent separation of Sun and Moon centres compared with their
angular radii. Totality while  sep < R_moon - R_sun  (umbral condition).
Refraction is ignored for the contact times (it shifts Sun and Moon almost equally at
the same altitude) but applied for the reported alt/az, which is what you actually see.
"""
import numpy as np
from skyfield.api import Loader, wgs84
from skyfield.framelib import ecliptic_frame  # noqa: F401  (ensures full install)
from .paths import EPHEM_DIR

R_SUN_KM = 695700.0
# Radio lunar efectivo para los contactos umbrales. NO es el radio medio (1737,4 km,
# que además era lo que había con un comentario equivocado: decía k = 0,2725076, que
# son 1738,09 km). El limbo real tiene montañas y valles, así que la totalidad dura
# menos de lo que da una esfera media. El valor y su calibración están en sources.py.
from .sources import LUNAR_UMBRAL_RADIUS      # noqa: E402
R_MOON_KM = LUNAR_UMBRAL_RADIUS['km']

_loader = Loader(EPHEM_DIR)
_eph = _loader('de421.bsp')
_ts = _loader.timescale()
EARTH, SUN, MOON = _eph['earth'], _eph['sun'], _eph['moon']


def _radii_and_sep(observer, t, limb_rot=None):
    """Return (separation_deg, r_sun_deg, r_moon_deg) as arrays.

    Con `limb_rot` (una matriz de rotación de la Luna, ver `limb_rotation`) el radio
    lunar deja de ser una esfera y sale del PERFIL REAL del limbo, leído en el ángulo
    de posición hacia el que se separa el Sol: es por ahí por donde asoma la fotosfera,
    así que es ese trozo de borde el que decide si hay totalidad.
    """
    obs = observer.at(t)
    s = obs.observe(SUN).apparent()
    m = obs.observe(MOON).apparent()
    sep = s.separation_from(m).degrees
    d_sun = s.distance().km
    d_moon = m.distance().km
    r_sun = np.degrees(np.arcsin(R_SUN_KM / d_sun))
    if limb_rot is None:
        r_moon = np.degrees(np.arcsin(R_MOON_KM / d_moon))
    else:
        from . import limb
        # el vector del centro de la Luna al centro del Sol, en el plano del cielo
        offset = s.position.km - m.position.km
        rk = limb.moon_radius_toward_rot(limb_rot, m.position.km, offset)
        r_moon = np.degrees(np.arcsin(rk / d_moon))
    return np.atleast_1d(sep), np.atleast_1d(r_sun), np.atleast_1d(r_moon)


def limb_rotation(t):
    """Orientación de la Luna en `t`, o None si no están los datos de LOLA/NAIF.

    Se calcula UNA vez por punto y se reutiliza en toda la bisección: la Luna gira medio
    grado por hora, así que dentro del minuto que dura la totalidad la cara que enseña
    es la misma, y recalcular la matriz en cada iteración multiplicaría por veinte el
    coste sin mover un metro el resultado.
    """
    from . import limb
    if not limb.available():
        return None
    try:
        return limb.rotation_at(t)
    except Exception:
        return None


def _g_total(observer, t, limb_rot=None):
    """>0 while the observer is inside the umbra (total eclipse)."""
    sep, r_sun, r_moon = _radii_and_sep(observer, t, limb_rot)
    return (r_moon - r_sun) - sep


def _g_partial(observer, t):
    """>0 while any part of the Sun is covered."""
    sep, r_sun, r_moon = _radii_and_sep(observer, t)
    return (r_moon + r_sun) - sep


def _overlap_fraction(r_sun, r_moon, sep):
    """Fraction of the solar disc area hidden by the lunar disc (circle-circle overlap)."""
    if sep >= r_sun + r_moon:
        return 0.0
    if sep <= abs(r_moon - r_sun):
        return 1.0 if r_moon >= r_sun else (r_moon / r_sun) ** 2
    d, a, b = float(sep), float(r_sun), float(r_moon)
    t1 = a * a * np.arccos(np.clip((d * d + a * a - b * b) / (2 * d * a), -1, 1))
    t2 = b * b * np.arccos(np.clip((d * d + b * b - a * a) / (2 * d * b), -1, 1))
    t3 = 0.5 * np.sqrt(max(0.0, (-d + a + b) * (d + a - b) * (d - a + b) * (d + a + b)))
    return float((t1 + t2 - t3) / (np.pi * a * a))


def moon_offset(lat, lon, elev_m, t):
    """Apparent (d_az, d_alt) of the Moon's centre relative to the Sun's, in degrees,
    plus both angular radii. Used to draw the eclipsed Sun at true shape and scale."""
    observer = EARTH + wgs84.latlon(lat, lon, elevation_m=elev_m)
    obs = observer.at(t)
    s = obs.observe(SUN).apparent()
    m = obs.observe(MOON).apparent()
    alt_s, az_s, _ = s.altaz('standard')
    alt_m, az_m, _ = m.altaz('standard')
    r_sun = np.degrees(np.arcsin(R_SUN_KM / s.distance().km))
    r_moon = np.degrees(np.arcsin(R_MOON_KM / m.distance().km))
    d_az = (az_m.degrees - az_s.degrees) * np.cos(np.radians(alt_s.degrees))
    return float(d_az), float(alt_m.degrees - alt_s.degrees), float(r_sun), float(r_moon)


def _bisect(observer, f, tjd_a, tjd_b, tol_s=0.02):
    """Root-find in TT Julian date. Accepts the bracket in either order and
    verifies that it really does contain a sign change."""
    tjd_lo, tjd_hi = (tjd_a, tjd_b) if tjd_a < tjd_b else (tjd_b, tjd_a)
    tol = tol_s / 86400.0
    flo = f(observer, _ts.tt_jd(tjd_lo))[0]
    fhi = f(observer, _ts.tt_jd(tjd_hi))[0]
    if (flo > 0) == (fhi > 0):
        raise ValueError(f'bracket does not straddle a root: f={flo:.3e},{fhi:.3e}')
    while tjd_hi - tjd_lo > tol:
        mid = 0.5 * (tjd_lo + tjd_hi)
        fm = f(observer, _ts.tt_jd(mid))[0]
        if (fm > 0) == (flo > 0):
            tjd_lo, flo = mid, fm
        else:
            tjd_hi = mid
    return 0.5 * (tjd_lo + tjd_hi)


def circumstances(lat, lon, elev_m=0.0, coarse_step_s=30.0, use_limb=False):
    """Full local circumstances. Returns dict (or partial-only / no-eclipse info).

    `use_limb=False` por defecto, y no es pereza: el IGN y la NASA publican sus
    duraciones con limbo MEDIO por convenio, y quien mire esta web va a contrastar con
    el IGN. Cambiar el número de portada por otro que no cuadra con el suyo sería peor
    servicio aunque el modelo sea más fino — y además la verificación del proyecto se
    apoya justo en esa comparación.

    Con `use_limb=True` se usa el perfil real del limbo (ver `limb.py`). Eso es la
    segunda opinión que decide la pregunta del filo: ¿hay corona o no la hay?
    """
    observer = EARTH + wgs84.latlon(lat, lon, elevation_m=elev_m)

    # Coarse scan of the window that covers Spain: 17:30-19:30 UTC
    t0 = _ts.utc(2026, 8, 12, 17, 30, 0)
    n = int(2 * 3600 / coarse_step_s) + 1
    tt_grid = t0.tt + np.arange(n) * (coarse_step_s / 86400.0)
    t = _ts.tt_jd(tt_grid)

    sep, r_sun, r_moon = _radii_and_sep(observer, t)
    g_tot = (r_moon - r_sun) - sep
    g_par = (r_moon + r_sun) - sep

    # Maximum eclipse = minimum of (sep - r_moon - r_sun) normalised; use max of g_par
    i_max = int(np.argmax(g_par))
    lo = max(i_max - 2, 0)
    hi = min(i_max + 2, n - 1)
    # Golden-section-ish refinement of the maximum on g_par
    a, b = tt_grid[lo], tt_grid[hi]
    for _ in range(60):
        m1 = a + (b - a) / 3.0
        m2 = b - (b - a) / 3.0
        if _g_partial(observer, _ts.tt_jd(m1))[0] < _g_partial(observer, _ts.tt_jd(m2))[0]:
            a = m1
        else:
            b = m2
    tt_max = 0.5 * (a + b)

    sep_m, rs_m, rm_m = _radii_and_sep(observer, _ts.tt_jd(tt_max))
    sep_m, rs_m, rm_m = sep_m[0], rs_m[0], rm_m[0]
    # Eclipse magnitude = fraction of solar *diameter* covered
    magnitude = (rs_m + rm_m - sep_m) / (2.0 * rs_m)
    # Obscuration = fraction of the solar *disc area* covered -- the number that tracks
    # how dark it gets. Note it is NOT always below the magnitude: just outside the
    # umbral limit the Moon is angularly larger than the Sun, and the area covered runs
    # slightly ahead of the covered fraction of the diameter.
    obscuration = _overlap_fraction(rs_m, rm_m, sep_m)

    out = {
        'lat': lat, 'lon': lon, 'elev_m': elev_m,
        'magnitude': magnitude, 'obscuration': obscuration,
        'total': False, 'duration_s': 0.0,
    }

    def altaz(tt):
        tt_ = _ts.tt_jd(tt)
        app = observer.at(tt_).observe(SUN).apparent()
        alt_g, az, _ = app.altaz()                       # geometric
        alt_r, _, _ = app.altaz('standard')              # with standard refraction
        return alt_g.degrees, alt_r.degrees, az.degrees, tt_

    alt_g, alt_r, az, t_max = altaz(tt_max)
    out.update({
        'max_utc': t_max.utc_iso(' '),
        'max_alt_geom': alt_g, 'max_alt_app': alt_r, 'max_az': az,
    })

    # Totality is decided at the instant of maximum eclipse (minimum separation),
    # not from the coarse grid -- near the path edges totality can last only a few
    # seconds and would fall between coarse samples.
    # El limbo REAL decide los contactos. La orientación de la Luna se calcula una sola
    # vez, en el máximo: dentro del par de minutos que dura esto la cara que enseña no
    # cambia, y recalcularla en cada iteración de la bisección multiplicaría el coste
    # sin mover el resultado.
    rot = limb_rotation(_ts.tt_jd(tt_max)) if use_limb else None
    gt = (lambda o, tt: _g_total(o, tt, rot)) if rot is not None else _g_total

    if gt(observer, _ts.tt_jd(tt_max))[0] <= 0:
        out['limb'] = rot is not None
        return out  # partial only at this site

    # C2 and C3 must lie within +/-3 min of maximum for any eclipse on Earth.
    half = 180.0 / 86400.0
    try:
        tt_c2 = _bisect(observer, gt, tt_max - half, tt_max)
        tt_c3 = _bisect(observer, gt, tt_max, tt_max + half)
    except ValueError:
        # Con el limbo real, justo en el filo puede haber totalidad en el máximo y no
        # llegar a haber contacto limpio: son las perlas de Baily, no una totalidad.
        out['limb'] = rot is not None
        return out
    dur = (tt_c3 - tt_c2) * 86400.0

    a2g, a2r, az2, t2 = altaz(tt_c2)
    a3g, a3r, az3, t3 = altaz(tt_c3)
    out.update({
        'total': True, 'duration_s': dur,
        'c2_utc': t2.utc_iso(' '), 'c3_utc': t3.utc_iso(' '),
        'c2_alt_geom': a2g, 'c2_alt_app': a2r, 'c2_az': az2,
        'c3_alt_geom': a3g, 'c3_alt_app': a3r, 'c3_az': az3,
    })
    return out


def sun_track(lat, lon, elev_m, tt_start_utc, tt_end_utc, step_s=30.0):
    """Apparent Sun track (az, alt) between two skyfield Times, for horizon plots."""
    observer = EARTH + wgs84.latlon(lat, lon, elevation_m=elev_m)
    n = int((tt_end_utc.tt - tt_start_utc.tt) * 86400 / step_s) + 1
    tt = tt_start_utc.tt + np.arange(n) * (step_s / 86400.0)
    t = _ts.tt_jd(tt)
    app = observer.at(t).observe(SUN).apparent()
    alt_g, az, _ = app.altaz()
    alt_r, _, _ = app.altaz('standard')
    return az.degrees, alt_g.degrees, alt_r.degrees, t


if __name__ == '__main__':
    for name, la, lo, h in [
        ('A Coruna', 43.3623, -8.4115, 20),
        ('Oviedo', 43.3619, -5.8494, 230),
        ('Burgos', 42.3439, -3.6969, 860),
        ('Soria', 41.7665, -2.4790, 1065),
        ('Zaragoza', 41.6488, -0.8891, 210),
        ('Castellon', 39.9864, -0.0513, 30),
        ('Palma', 39.5696, 2.6502, 10),
        ('Valencia', 39.4699, -0.3763, 15),
        ('Madrid', 40.4168, -3.7038, 660),
        ('Barcelona', 41.3874, 2.1686, 20),
    ]:
        c = circumstances(la, lo, h)
        if c['total']:
            print(f"{name:10s} tot {c['duration_s']:5.1f}s  C2 {c['c2_utc'][11:19]}  "
                  f"alt(app) {c['c2_alt_app']:5.2f}->{c['c3_alt_app']:5.2f}  "
                  f"az {c['c2_az']:6.2f}->{c['c3_az']:6.2f}  mag {c['magnitude']:.4f}")
        else:
            print(f"{name:10s} PARTIAL mag {c['magnitude']:.4f}  "
                  f"max {c['max_utc'][11:19]} alt(app) {c['max_alt_app']:5.2f} az {c['max_az']:6.2f}")
