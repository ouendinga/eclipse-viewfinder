"""Render a horizon panorama: the real terrain skyline in the WNW, with the Sun's
track for 2026-08-12 drawn across it, so you can see exactly where the eclipsed Sun
falls against the landscape.

x axis = true azimuth (deg), y axis = apparent altitude (deg). Both the terrain and
the Sun are in *apparent* (refracted) coordinates, so they are directly comparable.
"""
import numpy as np
from skyfield.api import load
from .ephem import circumstances, sun_track, moon_offset
from .terrain import horizon_fine, elev_fine

_ts = load.timescale()


def build(lat, lon, az_lo=262.0, az_hi=300.0, az_step=0.25, name=''):
    """Compute everything needed for one panorama."""
    c = circumstances(lat, lon, float(elev_fine(lat, lon)[0]))
    az = np.arange(az_lo, az_hi + 1e-9, az_step)
    hz, bd, obs_elev = horizon_fine(lat, lon, az, return_distance=True)

    # Sun track from an hour before C2 through sunset
    t0 = _ts.utc(2026, 8, 12, 17, 20, 0)
    t1 = _ts.utc(2026, 8, 12, 19, 20, 0)
    saz, salt_g, salt_r, tt = sun_track(lat, lon, obs_elev, t0, t1, step_s=20.0)

    # Interpolate terrain altitude at the Sun's azimuth along the track
    hz_at_sun = np.interp(saz, az, hz)
    visible = salt_r > hz_at_sun
    # Sunset behind the real skyline = last moment the disc centre is above terrain
    idx = np.where(visible)[0]
    set_az = float(saz[idx[-1]]) if idx.size else float('nan')
    set_utc = tt[idx[-1]].utc_iso(' ') if idx.size else None

    keys = (('c2_utc', 'C2'), ('max_utc', 'max'), ('c3_utc', 'C3')) if c['total'] \
        else (('max_utc', 'max'),)
    marks = []
    for key, label in keys:
        iso = c[key]
        h, m, s = int(iso[11:13]), int(iso[14:16]), float(iso[17:19])
        tm = _ts.utc(2026, 8, 12, h, m, s)
        a, ag, ar, _ = sun_track(lat, lon, obs_elev, tm, tm, step_s=1.0)
        marks.append(dict(label=label, utc=iso, az=float(a[0]), alt=float(ar[0]),
                          terrain=float(np.interp(a[0], az, hz)),
                          local=f'{(h+2)%24:02d}:{m:02d}:{int(s):02d}'))

    # Moon position relative to the Sun at maximum, for drawing the true crescent
    iso = c['max_utc']
    tmax = _ts.utc(2026, 8, 12, int(iso[11:13]), int(iso[14:16]), float(iso[17:19]))
    d_az, d_alt, r_sun, r_moon = moon_offset(lat, lon, obs_elev, tmax)

    return dict(name=name, lat=lat, lon=lon, obs_elev=obs_elev, circ=c,
                az=az, hz=hz, bd=bd, sun_az=saz, sun_alt=salt_r,
                marks=marks, set_az=set_az, set_utc=set_utc,
                hz_at_sun=hz_at_sun, visible=visible,
                moon=dict(d_az=d_az, d_alt=d_alt, r_sun=r_sun, r_moon=r_moon))


AZ_LO, AZ_HI = 262.0, 300.0
ALT_LO = -1.6


def svg(p, width=820, height=352, pad_l=44, pad_b=32, pad_t=12, pad_r=10):
    """Render the panorama as a self-contained SVG string.

    Both axes share the SAME angular scale, and every site is drawn on the same
    window, so the panoramas are directly comparable and the Sun can be drawn at
    its true angular diameter (0.53 deg).
    """
    az, hz = p['az'], p['hz']
    iw = width - pad_l - pad_r
    ih = height - pad_t - pad_b
    deg_px = iw / (AZ_HI - AZ_LO)          # px per degree, identical on both axes
    alt_hi = ALT_LO + ih / deg_px

    def X(a):
        return pad_l + (np.asarray(a) - AZ_LO) * deg_px

    def Y(v):
        return pad_t + (alt_hi - np.asarray(v)) * deg_px

    def Yc(v):                              # clamped to the plot box
        return np.clip(Y(v), pad_t, pad_t + ih)

    o = [f'<svg viewBox="0 0 {width} {height}" class="pano" '
         f'xmlns="http://www.w3.org/2000/svg" role="img">']
    o.append('<title>Perfil real del horizonte hacia el ONO y trayectoria del Sol '
             f'el 12 de agosto de 2026 desde {p["name"]}</title>')
    o.append(f'<clipPath id="cp{id(p)%99999}"><rect x="{pad_l}" y="{pad_t}" '
             f'width="{iw}" height="{ih}"/></clipPath>')
    o.append(f'<rect class="sky" x="{pad_l}" y="{pad_t}" width="{iw}" height="{ih}"/>')

    # altitude gridlines
    v = 0
    while v <= alt_hi:
        y = float(Y(v))
        o.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+iw}" y2="{y:.1f}" '
                 f'class="grid{" zero" if v == 0 else ""}"/>')
        o.append(f'<text x="{pad_l-7}" y="{y+3.5:.1f}" class="ylab">{v}&#176;</text>')
        v += 2
    # azimuth gridlines
    a = int(np.ceil(AZ_LO / 5.0) * 5)
    while a <= AZ_HI:
        x = float(X(a))
        o.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+ih}" '
                 f'class="grid"/>')
        lab = {270: 'O', 275: '', 280: '', 285: '', 290: '', 295: '', 300: 'ONO'}
        o.append(f'<text x="{x:.1f}" y="{pad_t+ih+14}" class="xlab">{a}&#176;</text>')
        a += 5

    g = f' clip-path="url(#cp{id(p)%99999})"'
    # terrain silhouette
    pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in zip(X(az), Yc(hz)))
    o.append(f'<polygon class="terrain"{g} points="{pad_l},{pad_t+ih} {pts} '
             f'{pad_l+iw},{pad_t+ih}"/>')

    # the Sun's path, as a faint trail plus discs every 10 minutes (true size)
    sr = 0.2665 * deg_px
    m = (p['sun_az'] >= AZ_LO) & (p['sun_az'] <= AZ_HI)
    if m.any():
        tp = ' '.join(f'{x:.1f},{y:.1f}'
                      for x, y in zip(X(p['sun_az'][m]), Y(p['sun_alt'][m])))
        o.append(f'<polyline class="track"{g} points="{tp}"/>')
    step = max(1, int(round(600 / 20)))     # track sampled every 20 s -> 10 min
    idx = np.arange(0, p['sun_az'].size, step)
    for i in idx:
        aa, vv = float(p['sun_az'][i]), float(p['sun_alt'][i])
        if not (AZ_LO <= aa <= AZ_HI) or vv < ALT_LO:
            continue
        buried = vv < float(np.interp(aa, az, hz))
        o.append(f'<circle class="sunstep{" buried" if buried else ""}"{g} '
                 f'cx="{X(aa):.1f}" cy="{Y(vv):.1f}" r="{sr:.1f}"/>')

    # The Sun at maximum eclipse, drawn at true angular size with the Moon's disc in
    # its real relative position -- so the crescent you see here is the crescent you
    # would actually see from this spot.
    if p['marks']:
        mk = p['marks'][1] if len(p['marks']) > 1 else p['marks'][0]
        total = p['circ']['total']
        x, y = float(X(mk['az'])), float(Y(mk['alt']))
        mo = p['moon']
        rs = mo['r_sun'] * deg_px
        rm = mo['r_moon'] * deg_px
        mx = x + mo['d_az'] * deg_px
        my = y - mo['d_alt'] * deg_px
        if total:
            o.append(f'<circle class="corona"{g} cx="{x:.1f}" cy="{y:.1f}" '
                     f'r="{rs*2.6:.1f}"/>')
        # If the skyline is above the Sun at this instant, the disc is drawn where it
        # *would* be, dimmed, so it is obvious that the ground is in the way.
        hidden = mk['alt'] < mk['terrain']
        hc = ' hidden' if hidden else ''
        o.append(f'<circle class="sundisc{" tot" if total else ""}{hc}"{g} '
                 f'cx="{x:.1f}" cy="{y:.1f}" r="{rs:.2f}"/>')
        o.append(f'<circle class="moondisc{hc}"{g} cx="{mx:.2f}" cy="{my:.2f}" '
                 f'r="{rm:.2f}"/>')
        if hidden:
            o.append(f'<circle class="hidering"{g} cx="{x:.1f}" cy="{y:.1f}" '
                     f'r="{rs*1.9:.2f}"/>')
        pct = p['circ']['obscuration'] * 100.0
        lab = f'TOTALIDAD {mk["local"]}' if total else \
              f'{pct:.1f}% oculto &#183; {mk["local"]}'
        halo = rs * 2.6 if total else rs * 1.6
        ly = max(y - halo - 8, pad_t + 11)
        o.append(f'<line class="callout" x1="{x:.1f}" y1="{ly+3:.1f}" '
                 f'x2="{x:.1f}" y2="{y-halo:.1f}"/>')
        o.append(f'<text x="{x:.1f}" y="{ly:.1f}" class="mlab">{lab}</text>')

        # Magnified inset: at true scale the uncovered sliver is sub-pixel, so show
        # the same Sun-Moon geometry blown up. Same numbers, readable shape.
        R = 44.0
        mag = R / rs
        cx, cy = pad_l + R + 16, pad_t + R + 16
        o.append(f'<circle class="insetbg" cx="{cx:.1f}" cy="{cy:.1f}" '
                 f'r="{R*1.5:.1f}"/>')
        if total:
            o.append(f'<circle class="corona" cx="{cx:.1f}" cy="{cy:.1f}" '
                     f'r="{R*1.45:.1f}"/>')
        o.append(f'<circle class="sundisc" cx="{cx:.1f}" cy="{cy:.1f}" r="{R:.1f}"/>')
        o.append(f'<circle class="moondisc" cx="{cx + mo["d_az"]*deg_px*mag:.2f}" '
                 f'cy="{cy - mo["d_alt"]*deg_px*mag:.2f}" r="{rm*mag:.2f}"/>')
        o.append(f'<text x="{cx:.1f}" y="{cy + R*1.5 + 12:.1f}" class="ilab">'
                 f'&#215;{mag:.0f} aumentos</text>')
    return ''.join(o) + '</svg>'


def summary(p):
    c = p['circ']
    out = {
        'name': p['name'], 'lat': p['lat'], 'lon': p['lon'],
        'elev': round(p['obs_elev']),
        'total': c['total'],
        'dur': round(c.get('duration_s', 0.0), 1),
    }
    if c['total']:
        cl = [m['alt'] - m['terrain'] for m in p['marks']]
        out.update(
            c2_local=p['marks'][0]['local'], c3_local=p['marks'][2]['local'],
            alt_c2=round(c['c2_alt_app'], 2), alt_c3=round(c['c3_alt_app'], 2),
            az_c2=round(c['c2_az'], 2), az_c3=round(c['c3_az'], 2),
            terrain_c2=round(p['marks'][0]['terrain'], 2),
            terrain_c3=round(p['marks'][2]['terrain'], 2),
            clearance=round(min(cl), 2),
            blocker_km=round(float(np.interp(c['c3_az'], p['az'], p['bd'])) / 1000, 1),
            set_az=round(p['set_az'], 1),
            set_utc=p['set_utc'],
        )
    return out
