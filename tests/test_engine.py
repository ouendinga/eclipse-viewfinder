# -*- coding: utf-8 -*-
"""Verification suite as executable tests.

Run:  python -m unittest discover -s tests -v

Tests that need elevation data skip cleanly when it is absent, so a fresh clone can
still check the parts that depend only on the ephemerides and on maths.
"""
import os
import unittest
import urllib.error

import numpy as np

from eclipseview import (events, gazetteer, i18n, obstacles, recommend,
                         sources, verify)
from eclipseview.ephem import _overlap_fraction, circumstances
from eclipseview.paths import MOSAIC_NPY, FIELD_PKL

HAS_DEM = os.path.exists(MOSAIC_NPY)
HAS_FIELD = os.path.exists(FIELD_PKL)


class TestObscurationMaths(unittest.TestCase):
    """Circle-circle overlap, checked against cases with a closed form."""

    def test_no_overlap(self):
        self.assertEqual(_overlap_fraction(1.0, 1.0, 2.5), 0.0)

    def test_total_cover(self):
        # Moon larger than Sun and concentric -> the Sun is entirely hidden
        self.assertEqual(_overlap_fraction(1.0, 1.2, 0.0), 1.0)

    def test_annular(self):
        # Moon smaller and concentric -> covered area is the ratio of the areas
        self.assertAlmostEqual(_overlap_fraction(1.0, 0.5, 0.0), 0.25, places=9)

    def test_half_way(self):
        # Equal discs whose centres coincide -> everything covered
        self.assertAlmostEqual(_overlap_fraction(1.0, 1.0, 0.0), 1.0, places=9)

    def test_monotonic_in_separation(self):
        vals = [_overlap_fraction(1.0, 1.02, d) for d in np.linspace(0, 2.02, 40)]
        self.assertTrue(all(b <= a + 1e-12 for a, b in zip(vals, vals[1:])),
                        'covering less as the discs separate')

    def test_grazing_is_continuous(self):
        just_in = _overlap_fraction(1.0, 1.02, 2.0199)
        just_out = _overlap_fraction(1.0, 1.02, 2.0201)
        self.assertLess(just_in, 1e-3)
        self.assertEqual(just_out, 0.0)


class TestEphemeris(unittest.TestCase):
    """Against NASA's published circumstances for this eclipse."""

    def test_greatest_eclipse(self):
        g = verify.check_greatest_eclipse()
        for item in g['items']:
            with self.subTest(item['what']):
                self.assertTrue(item['ok'],
                                f"{item['what']}: {item['ours']} vs "
                                f"{item['published']} {item['unit']}")

    def test_duration_bias_is_small(self):
        """Antes este test daba por bueno un sesgo POSITIVO de hasta el 5 %, porque el
        radio lunar era el medio y las duraciones salían largas. Con el radio umbral
        calibrado el sesgo ya no tiene signo esperado: lo que se exige es que sea
        pequeño en SEGUNDOS, que es lo que le importa a quien va a ver el eclipse."""
        r = sources.REFERENCE_GREATEST
        c = circumstances(r['lat'], r['lon'], 0.0)
        self.assertLessEqual(abs(c['duration_s'] - r['duration_s']),
                             sources.LUNAR_UMBRAL_RADIUS['max_dev_s'])

    def test_cities_match_ign(self):
        for g in verify.check_cities():
            for item in g['items']:
                with self.subTest(f"{g['name']} {item['what']}"):
                    self.assertTrue(item['ok'],
                                    f"{g['name']} {item['what']}: {item['ours']} vs "
                                    f"{item['published']}")

    def test_barcelona_is_not_total(self):
        """The single fact most likely to send someone to the wrong place."""
        for g in verify.check_partial():
            for item in g['items']:
                with self.subTest(f"{g['name']} {item['what']}"):
                    self.assertTrue(item['ok'])

    def test_path_edge_town(self):
        for g in verify.check_edge():
            for item in g['items']:
                with self.subTest(g['name']):
                    self.assertTrue(item['ok'],
                                    f"{g['name']}: {item['ours']} vs {item['published']}")


@unittest.skipUnless(HAS_DEM, 'sin datos de elevación (ejecuta: eclipseview setup)')
class TestTerrain(unittest.TestCase):

    def test_sea_horizon_matches_theory(self):
        """Open ocean: the skyline must equal the analytic dip. Exercises curvature,
        refraction and near-field handling together."""
        g = verify.check_sea_horizon()
        self.assertTrue(g['items'][0]['ok'],
                        f"{g['items'][0]['ours']} vs {g['items'][0]['published']}")

    def test_known_summit(self):
        g = verify.check_known_summit()
        for item in g['items']:
            with self.subTest(item['what']):
                self.assertTrue(item['ok'],
                                f"{item['ours']} vs {item['published']}")

    def test_observer_height_uses_fine_dem(self):
        """The ranking pass must not read the observer's height off the max-pooled
        mosaic: on a slope that puts you on top of the ridge in front of you.

        Regression guard for a bug that made a blocked site (-13 deg) look fine.
        """
        from eclipseview.terrain import elev_at, elev_fine
        # a steep slope in the Montseny
        lat, lon = 41.8100, 2.4200
        coarse = float(elev_at(np.array([lat]), np.array([lon]))[0])
        fine = float(elev_fine(lat, lon)[0])
        self.assertGreaterEqual(coarse, fine - 1.0,
                                'el mosaico agrupa por máximo: nunca por debajo')
        import inspect
        from eclipseview import analysis
        src = inspect.getsource(analysis.search_area)
        self.assertIn('elev_fine(LA, LO)', src,
                      'search_area debe tomar la altura del observador del DEM fino')


@unittest.skipUnless(HAS_DEM and HAS_FIELD, 'sin datos precalculados')
class TestPathGeometry(unittest.TestCase):

    def test_path_width(self):
        g = verify.check_path_width()
        if g is None:
            self.skipTest('sin limits.json')
        self.assertTrue(g['items'][0]['ok'],
                        f"{g['items'][0]['ours']} vs {g['items'][0]['published']} km")

    def test_everything_passes(self):
        s = verify.summarise(verify.run_all())
        self.assertEqual(s['failed'], [], f"fallan: {s['failed']}")


class TestCoverage(unittest.TestCase):
    """The tile set must include the ray corridor, not just the disc."""

    def test_corridor_extends_west(self):
        from eclipseview import coverage
        lat, lon = 41.0, 0.0
        disc = coverage.tiles_covering(lat - 0.1, lat + 0.1, lon - 0.1, lon + 0.1)
        need = coverage.required_tiles(lat, lon, 10.0)
        self.assertGreater(len(need), len(disc),
                           'debe pedir teselas al ONO, no solo bajo el punto')
        westmost = min(t[1] for t in need)
        self.assertLessEqual(westmost, -2,
                             'el corredor de visuales debe llegar bastante al oeste')


class TestI18n(unittest.TestCase):

    def test_locales_complete(self):
        for lang in i18n.available():
            with self.subTest(lang):
                self.assertEqual(i18n.check(lang), [], f'faltan claves en {lang}')

    def test_decimal_separator(self):
        self.assertEqual(i18n.number('es', 4.62, 2, sign=True), '+4,62')
        self.assertEqual(i18n.number('en', 4.62, 2, sign=True), '+4.62')


class TestEvents(unittest.TestCase):

    def test_default_is_ready(self):
        self.assertTrue(events.is_ready(events.DEFAULT.key))

    def test_unknown_event_raises(self):
        with self.assertRaises(KeyError):
            events.get('no-existe')


class TestSourcesIntegrity(unittest.TestCase):
    """Every claim carries a citation we can follow."""

    def test_citations_have_urls(self):
        for key, c in sources.CITATIONS.items():
            with self.subTest(key):
                self.assertTrue(c['url'].startswith('http'))
                self.assertTrue(c['label'])

    def test_reference_values_cite_a_source(self):
        for city in sources.REFERENCE_CITIES:
            self.assertIn(city['source'], sources.CITATIONS)
        self.assertIn(sources.REFERENCE_GREATEST['source'], sources.CITATIONS)
        for e in sources.REFERENCE_EDGE:
            self.assertTrue(e['source_url'].startswith('http'))

    def test_climatology_is_attributed(self):
        self.assertIn(sources.CLIMATOLOGY['source'], sources.CITATIONS)
        for r in sources.CLIMATOLOGY['regions']:
            self.assertTrue(r['label'] and r['text'])


class TestOffshoreIsNotRecommended(unittest.TestCase):
    """Sobre el mar el DEM vale 0 y el horizonte sale perfecto: si no se filtra, los
    mejores márgenes del sitio caen en mar abierto. Etiquetas reales observadas en
    Nominatim el 2026-08-05."""

    def test_country_only_is_not_land(self):
        for label in ('', 'España', ' españa ', 'Spain', 'Portugal'):
            with self.subTest(label):
                self.assertFalse(gazetteer.on_land(label))

    def test_real_places_are_land(self):
        for label in ('O Porto de Corme, Ponteceso, Bergantiños',
                      'Navas de San Antonio, Castilla y León',
                      'Asturias', 'País Vasco'):
            with self.subTest(label):
                self.assertTrue(gazetteer.on_land(label))

    def test_drop_offshore_prunes_and_renumbers(self):
        pts = [dict(i=1, place='Cuéllar, Castilla y León'),
               dict(i=2, place='España'),
               dict(i=3, place=''),
               dict(i=4, place='Soria, Castilla y León')]
        kept = recommend.drop_offshore(pts, retry=False)
        self.assertEqual([p['place'] for p in kept],
                         ['Cuéllar, Castilla y León', 'Soria, Castilla y León'])
        self.assertEqual([p['i'] for p in kept], [1, 2])

    def test_coastal_point_survives_the_finer_zoom(self):
        """Gorliz salía «España» al zoom 13 y es tierra: la segunda consulta lo salva
        y le arregla el topónimo. Sin esta red, el filtro borra costa de verdad."""
        pts = [dict(i=1, lat=43.44, lon=-2.94, place='España'),   # Gorliz, Bizkaia
               dict(i=2, lat=43.59, lon=-4.69, place='España')]   # mar cantábrico
        fine = {(43.44, -2.94): 'Gorliz, Bizkaia, Euskadi',
                (43.59, -4.69): 'España'}
        real = gazetteer.reverse
        gazetteer.reverse = lambda la, lo, **kw: fine[(la, lo)]
        try:
            kept = recommend.drop_offshore(pts)
        finally:
            gazetteer.reverse = real
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]['place'], 'Gorliz, Bizkaia, Euskadi')


class TestOpenSeaNeedsThreeSignals(unittest.TestCase):
    """Cada señal por separado tiene falsos positivos que costó encontrar; el test los
    fija para que nadie simplifique la regla creyendo que sobra una."""

    def _p(self, elev, near_m, acc_ok=True):
        return dict(lat=40.0, lon=0.0, elev=elev, acc_ok=acc_ok,
                    acc={'near': ({'m': near_m} if near_m is not None else None)})

    def test_open_sea_is_caught(self):
        # Escala d'Espanya: nivel del mar, sin vía, sin relieve
        self.assertTrue(recommend.is_at_sea(self._p(2, None), relief=7.0))

    def test_the_flat_delta_survives_because_it_has_a_road(self):
        # Delta de l'Ebre: 1 m de altitud y 2 m de relieve en 8 km, pero con carretera
        self.assertFalse(recommend.is_at_sea(self._p(1, 41), relief=2.0))

    def test_a_coastal_dwelling_survives_because_of_the_hills_behind(self):
        # Foz: 1 m, sin vía encontrada, pero 368 m de monte a 8 km
        self.assertFalse(recommend.is_at_sea(self._p(1, None), relief=368.0))

    def test_a_summit_is_never_at_sea(self):
        self.assertFalse(recommend.is_at_sea(self._p(1434, None), relief=0.0))


class TestStreetViewNeedsARoad(unittest.TestCase):
    """Street View se graba desde la vía: sin asfalto cerca el enlace abre una pantalla
    negra. Ya pasó en producción una vez, y volvió a pasar cuando enrich_obstacles
    reasignaba 'sv' a todos los puntos."""

    def _p(self, **acc):
        return dict(lat=42.5, lon=-4.3, az=285.0, **acc)

    def test_link_only_with_asphalt_close_enough(self):
        cerca = self._p(acc_ok=True, acc={'paved': {'m': 40}})
        lejos = self._p(acc_ok=True, acc={'paved': {'m': 800}})
        sin_via = self._p(acc_ok=True, acc={'paved': None})
        sin_comprobar = self._p(acc_ok=False)
        pts = [cerca, lejos, sin_via, sin_comprobar]
        self.assertEqual(recommend.apply_streetview(pts), 1)
        self.assertTrue(cerca.get('sv'))
        for p in (lejos, sin_via, sin_comprobar):
            self.assertIsNone(p.get('sv'))

    def test_a_stale_link_is_removed(self):
        # lo que hacía enrich: dejar el enlace puesto de una pasada anterior
        p = self._p(acc_ok=True, acc={'paved': {'m': 800}})
        p['sv'] = 'https://maps.google.com/…'
        recommend.apply_streetview([p])
        self.assertNotIn('sv', p)


class TestLunarLimb(unittest.TestCase):
    """El perfil real del limbo. Se salta si no están los datos (LOLA + núcleos NAIF),
    que son 34 MB y no se versionan."""

    @classmethod
    def setUpClass(cls):
        from eclipseview import limb
        if not limb.available():
            raise unittest.SkipTest('sin datos del limbo (data/moon/)')
        cls.limb = limb

    def _moon_vector(self):
        from skyfield.api import wgs84
        from eclipseview.ephem import EARTH, MOON, _ts
        t = _ts.utc(2026, 8, 12, 18, 30, 0)
        obs = EARTH + wgs84.latlon(42.537, -4.3366, elevation_m=830)
        return t, obs.at(t).observe(MOON).apparent()

    def test_libration_amplitude_matches_the_published_one(self):
        """Si la orientación estuviera mal montada, la libración no oscilaría lo que
        oscila. Es la comprobación que ata todo lo demás."""
        import numpy as np
        from eclipseview.ephem import EARTH, MOON, _ts
        lats, lons = [], []
        for d in range(30):
            t = _ts.utc(2026, 7, 20 + d)
            m = EARTH.at(t).observe(MOON).apparent()
            u = -m.position.km
            u = u / np.linalg.norm(u)
            v = self.limb.rotation_at(t) @ u
            lats.append(np.degrees(np.arcsin(v[2])))
            lons.append(np.degrees(np.arctan2(v[1], v[0])))
        self.assertGreater(max(lats) - min(lats), 10.0, 'libración en latitud muy corta')
        self.assertLess(max(lats) - min(lats), 18.0, 'libración en latitud disparada')
        self.assertGreater(max(lons) - min(lons), 10.0)
        self.assertLess(max(lons) - min(lons), 20.0)

    def test_the_profile_has_real_lunar_relief(self):
        t, m = self._moon_vector()
        _, r = self.limb.profile(t, m.position.km)
        self.assertGreater(r.max() - r.min(), 5.0, 'el borde sale demasiado liso')
        self.assertLess(r.max() - r.min(), 25.0, 'relieve imposible en la Luna')
        self.assertAlmostEqual(r.mean(), 1736.7, delta=1.5)

    def test_the_sign_convention_cancels(self):
        """El ángulo de posición y el muestreo del limbo usan la misma base, así que
        invertir el este no puede cambiar el resultado. Si lo cambia, hay un lado del
        limbo que se está leyendo al revés — y en el filo eso invierte la respuesta."""
        t, m = self._moon_vector()
        from eclipseview.ephem import SUN
        from skyfield.api import wgs84
        from eclipseview.ephem import EARTH
        obs = EARTH + wgs84.latlon(42.537, -4.3366, elevation_m=830)
        s = obs.at(t).observe(SUN).apparent()
        rot = self.limb.rotation_at(t)
        off = s.position.km - m.position.km
        a = self.limb.moon_radius_toward_rot(rot, m.position.km, off)
        real = self.limb._basis
        self.limb._basis = lambda v: (lambda r: (r[0], r[1], -r[2]))(real(v))
        try:
            b = self.limb.moon_radius_toward_rot(rot, m.position.km, off)
        finally:
            self.limb._basis = real
        self.assertAlmostEqual(a, b, places=9)

    def test_the_headline_duration_still_uses_the_sphere(self):
        """La cifra que se publica tiene que seguir cuadrando con el IGN: si alguien
        pone el limbo por defecto, este test lo caza."""
        import inspect
        from eclipseview import ephem
        sig = inspect.signature(ephem.circumstances)
        self.assertIs(sig.parameters['use_limb'].default, False)


class TestLunarRadiusCalibration(unittest.TestCase):
    """El radio umbral no se copia de ningún sitio: se ajusta a las duraciones
    publicadas (NASA e IGN). Este test rehace el ajuste, así que si alguien toca el
    valor a ojo o cambia el motor, salta."""

    def _refs(self):
        r = sources.REFERENCE_GREATEST
        out = [(r['lat'], r['lon'], 0.0, r['duration_s'])]
        for x in sources.REFERENCE_CITIES + sources.REFERENCE_EDGE:
            out.append((x['lat'], x['lon'], x['elev'], x['duration_s']))
        return out

    def _worst(self, radius_km):
        from eclipseview import ephem
        antes = ephem.R_MOON_KM
        ephem.R_MOON_KM = radius_km
        try:
            return max(abs(ephem.circumstances(la, lo, el)['duration_s'] - pub)
                       for la, lo, el, pub in self._refs())
        finally:
            ephem.R_MOON_KM = antes

    def test_shipped_radius_meets_its_own_tolerance(self):
        cal = sources.LUNAR_UMBRAL_RADIUS
        peor = self._worst(cal['km'])
        self.assertLessEqual(peor, cal['max_dev_s'],
                             f'con {cal["km"]} km el peor desvío es {peor:.2f} s')

    def test_no_neighbour_on_the_grid_is_better(self):
        """Que sea un mínimo de verdad y no un número puesto a dedo que casualmente
        cumple la tolerancia."""
        cal = sources.LUNAR_UMBRAL_RADIUS
        aqui = self._worst(cal['km'])
        for lado in (-cal['step_km'], +cal['step_km']):
            self.assertLessEqual(aqui, self._worst(cal['km'] + lado) + 1e-9,
                                 f'{cal["km"] + lado} km ajusta mejor')

    def test_it_actually_beats_the_mean_radius(self):
        """El guardia probado por el lado que importa: el radio medio (lo que había)
        tiene que fallar esta tolerancia, o el test no está midiendo nada."""
        self.assertGreater(self._worst(1737.4), sources.LUNAR_UMBRAL_RADIUS['max_dev_s'])


class TestOverpassIsPolite(unittest.TestCase):
    """Overpass es un servicio público y gratuito. El 2026-08-05 nos ganamos un
    'Connection refused' a nivel TCP tras ~1.150 peticiones en 25 minutos, y lo peor no
    fue el bloqueo: fue que el código lo tapó y dijo 'OK' al final."""

    def setUp(self):
        obstacles._healthy = None
        obstacles._cooldown.clear()

    def tearDown(self):
        obstacles._healthy = None
        obstacles._cooldown.clear()

    def test_no_endpoints_means_empty_not_all_of_them(self):
        # el fallo que lo tapó: devolvía la lista entera cuando no contestaba ninguno
        obstacles._healthy = []
        self.assertEqual(obstacles.available_endpoints(), [])

    def test_a_refusal_is_not_treated_as_busy(self):
        refused = OSError('[Errno 111] Connection refused')
        unreachable = OSError('[Errno 101] Network is unreachable')
        self.assertTrue(obstacles._is_refusal(refused))
        self.assertTrue(obstacles._is_refusal(unreachable))
        self.assertTrue(obstacles._is_refusal(
            urllib.error.HTTPError('u', 429, 'slow down', {}, None)))
        # un 504 es "estoy ocupado", no "vete": ése sí se reintenta
        self.assertFalse(obstacles._is_refusal(
            urllib.error.HTTPError('u', 504, 'busy', {}, None)))

    def test_a_refused_endpoint_goes_on_cooldown(self):
        obstacles._healthy = ['https://a', 'https://b']
        obstacles._penalise('https://a', obstacles.BAN_COOLDOWN_S)
        self.assertEqual(obstacles.available_endpoints(), ['https://b'])

    def test_server_retry_after_wins_over_our_guess(self):
        err = urllib.error.HTTPError('u', 429, 'slow', {'Retry-After': '120'}, None)
        self.assertEqual(obstacles._retry_after(err, 0), 120.0)

    def test_backoff_grows_and_is_capped(self):
        e = OSError('timeout')
        primero = obstacles._retry_after(e, 0)
        septimo = obstacles._retry_after(e, 7)
        self.assertGreater(septimo, primero)
        self.assertLessEqual(septimo, obstacles.MAX_BACKOFF_S)

    def test_a_total_outage_stops_the_run(self):
        # con todo caído no se devuelven 401 fallos: se para y se dice por qué
        obstacles._healthy = []
        with self.assertRaises(obstacles.NoEndpoints):
            obstacles.check_batch([(42.0, -4.0, 285.0, 900.0)])

    def test_a_failing_batch_is_split_before_giving_up(self):
        """Un lote de 25 que falla perdía los 25. Ahora se parte: si sólo un punto es
        problemático, se pierde uno."""
        malo = (42.5, -4.5, 285.0, 900.0)
        items = [(42.0 + i / 100.0, -4.0, 285.0, 900.0) for i in range(4)] + [malo]
        obstacles._healthy = ['https://fake']
        llamadas = []

        def fake_multi(boxes, timeout=45, tries=3):
            llamadas.append(len(boxes))
            if len(boxes) > 1:
                raise OSError('demasiado grande')      # sólo pasa de uno en uno
            return {'elements': []}

        real_multi, real_save = obstacles._query_multi, obstacles._save
        obstacles._query_multi = fake_multi
        obstacles._save = lambda: None
        obstacles._cache = {}
        try:
            out = obstacles.check_batch(items, batch=len(items))
        finally:
            obstacles._query_multi, obstacles._save = real_multi, real_save
            obstacles._cache = None
        self.assertTrue(all(r is not None for r in out), 'ningún punto sin resultado')
        self.assertTrue(all(r.get('ok') for r in out), 'se resolvieron todos al partir')
        self.assertGreater(max(llamadas), 1, 'lo intentó primero en lote')


class TestPartialNeverReadsAsHundred(unittest.TestCase):
    """Un punto sin totalidad no puede pintar «100,0% parcial»: es redondeo, pero se
    lee como una contradicción justo en los puntos del filo, que son los que más se
    miran. El JS que se publica se ejecuta de verdad aquí, no se reimplementa: una
    copia en Python aprobaría aunque el navegador hiciera otra cosa."""

    def _obsc_js(self):
        """Saca del script publicado las dos funciones que dan el texto."""
        from eclipseview import finder_ui
        src = finder_ui.script()
        trozos = []
        for nombre in ('function n(', 'function obscTxt('):
            i = src.index(nombre)          # si no está, el test peta: es lo que queremos
            j = src.index('\n  }', i) + 4 if nombre == 'function obscTxt(' \
                else src.index('\n', i) + 1
            trozos.append(src[i:j])
        return '\n'.join(trozos)

    def test_every_render_goes_through_the_guard(self):
        from eclipseview import finder_ui
        src = finder_ui.script()
        # Fuera del propio guardia no puede quedar ni una llamada cruda: si alguien
        # añade otro sitio donde se pinte la obscuración, tiene que pasar por aquí.
        i = src.index('function obscTxt(')
        fuera = src[:i] + src[src.index('\n  }', i):]
        self.assertNotIn('n(p.obsc', fuera,
                         'la obscuración se pinta con obscTxt(), nunca con n(p.obsc,…)')
        self.assertGreaterEqual(src.count('obscTxt(p,'), 5,
                                'los cinco sitios que pintan obscuración usan el guardia')

    @unittest.skipUnless(__import__('shutil').which('node'), 'sin node para ejecutar el JS')
    def test_the_shipped_js_never_prints_a_hundred_for_a_partial(self):
        import json as _json
        import subprocess
        import tempfile
        # Los valores que saturan de verdad en el dataset publicado van entre 99,951 y
        # 99,999; se añaden los extremos y un valor normal para que el guardia no se
        # coma los casos corrientes.
        casos = [99.951, 99.99, 99.999, 99.9999, 92.38, 50.0]
        harness = self._obsc_js() + '\n' + (
            'var out=[];' +
            'JSON.parse(process.argv[2]).forEach(function(v){' +
            '  out.push([obscTxt({obsc:v,total:false},1), obscTxt({obsc:v,total:false},2)]);' +
            '});' +
            'console.log(JSON.stringify(out));')
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False,
                                         encoding='utf-8') as fh:
            fh.write(harness)
            ruta = fh.name
        try:
            salida = subprocess.run(['node', ruta, _json.dumps(casos)],
                                    capture_output=True, text=True, timeout=30)
        finally:
            os.unlink(ruta)
        self.assertEqual(salida.returncode, 0, salida.stderr)
        textos = _json.loads(salida.stdout)
        for v, textos_v in zip(casos, textos):
            for t in textos_v:
                # el ">" es la salida honrada cuando ni con tres decimales baja de 100
                leido = float(t.lstrip('>').replace(',', '.'))
                self.assertLess(leido, 100.0,
                                f'{v}% sin totalidad se pinta «{t}%», y eso es un 100')
        # Y, sobre todo, la web tiene que decir lo MISMO que el informe. Que las dos
        # nunca lleguen a 100 no basta: si una trunca y la otra añade decimales, el
        # mismo punto sale como 99,9% en un sitio y 99,95% en el otro, y eso destruye
        # la confianza igual que el 100,0% que vinimos a quitar.
        for v, textos_v in zip(casos, textos):
            self.assertEqual(textos_v[0] + '%', i18n.obscuration('es', v, False),
                             f'la web y el informe discrepan en {v}%')

    def test_the_dataset_still_exercises_the_guard(self):
        """Si un día ningún punto satura, este test avisa de que el guardia dejó de
        estar probado por datos reales en vez de dejarlo ahí sin comprobar."""
        from eclipseview.paths import DATA_DIR
        ruta = os.path.join(DATA_DIR, 'points.json')
        if not os.path.exists(ruta):
            self.skipTest('sin points.json')
        import json as _json
        with open(ruta, encoding='utf-8') as fh:
            pts = _json.load(fh)['points']
        saturan = [p for p in pts
                   if not p['total'] and round(p['obsc'], 1) >= 100.0]
        self.assertTrue(saturan,
                        'ningún punto satura ya: revisa si el guardia sigue haciendo falta')


if __name__ == '__main__':
    unittest.main(verbosity=2)
