# -*- coding: utf-8 -*-
"""Verification suite as executable tests.

Run:  python -m unittest discover -s tests -v

Tests that need elevation data skip cleanly when it is absent, so a fresh clone can
still check the parts that depend only on the ephemerides and on maths.
"""
import os
import unittest

import numpy as np

from eclipseview import events, gazetteer, i18n, recommend, sources, verify
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

    def test_duration_bias_is_documented(self):
        """Our lunar-radius convention runs long. Assert the bias stays SMALL and
        POSITIVE, so a regression that flips or inflates it is caught."""
        r = sources.REFERENCE_GREATEST
        c = circumstances(r['lat'], r['lon'], 0.0)
        bias = (c['duration_s'] - r['duration_s']) / r['duration_s']
        self.assertGreater(bias, 0.0)
        self.assertLess(bias, 0.05, 'el sesgo de duración se ha disparado')

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
