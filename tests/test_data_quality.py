# -*- coding: utf-8 -*-
"""Invariantes del dataset que se publica.

Los tests del motor comprueban que la geometría es correcta. Estos comprueban otra
cosa: que lo que sale por la puerta es coherente consigo mismo. Un fallo de motor lo
caza el contraste con el IGN; un punto en el mar, una duración negativa o un `t3`
anterior a `t2` no los caza nadie, porque cada número por separado parece razonable.

Se ejecutan contra `data/points.json` si existe, y contra `site/points.json` si está
construido: el segundo es literalmente el fichero que descarga el navegador, y entre
uno y otro hay un paso de filtrado donde ya se coló un fallo una vez.
"""
import json
import os
import unittest

from eclipseview import recommend
from eclipseview.panorama import AZ_LO, AZ_HI
from eclipseview.paths import DATA_DIR

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = {
    'data/points.json': os.path.join(DATA_DIR, 'points.json'),
    'site/points.json': os.path.join(REPO, 'site', 'points.json'),
}

# La región que cubren los datos precalculados de este evento.
LAT_S, LAT_N, LON_W, LON_E = 35.0, 45.0, -10.0, 5.0


def cargar(ruta):
    with open(ruta, encoding='utf-8') as fh:
        return json.load(fh)


class BaseDataset(unittest.TestCase):
    """Cada comprobación se hace sobre todas las copias del dataset que existan."""

    def datasets(self):
        hubo = False
        for nombre, ruta in FUENTES.items():
            if os.path.exists(ruta):
                hubo = True
                yield nombre, cargar(ruta)['points']
        if not hubo:
            self.skipTest('no hay ningún points.json construido')

    def fallo(self, nombre, p, motivo):
        return (f'{nombre}: punto {p.get("i")} en {p.get("lat")},{p.get("lon")} '
                f'({p.get("place")}) — {motivo}')


class TestShape(BaseDataset):

    CLAVES = ('i', 'lat', 'lon', 'elev', 'total', 'dur', 'obsc', 'alt', 'az',
              'hz', 'clear', 't', 'prof', 'sun', 'moon')

    def test_every_point_has_every_field(self):
        for nombre, pts in self.datasets():
            for p in pts:
                faltan = [k for k in self.CLAVES if k not in p]
                self.assertFalse(faltan, self.fallo(nombre, p, f'sin {faltan}'))

    def test_identifiers_are_unique(self):
        for nombre, pts in self.datasets():
            ids = [p['i'] for p in pts]
            self.assertEqual(len(ids), len(set(ids)), f'{nombre}: hay «i» repetidos')

    def test_no_two_points_are_the_same_place(self):
        """Dos puntos en la misma coordenada ocupan dos huecos de la lista de ocho y
        le quitan al usuario una alternativa de verdad."""
        for nombre, pts in self.datasets():
            coords = [(p['lat'], p['lon']) for p in pts]
            self.assertEqual(len(coords), len(set(coords)),
                             f'{nombre}: hay coordenadas repetidas')


class TestGeometryIsSelfConsistent(BaseDataset):

    def test_points_are_inside_the_covered_region(self):
        for nombre, pts in self.datasets():
            for p in pts:
                self.assertTrue(LAT_S <= p['lat'] <= LAT_N and LON_W <= p['lon'] <= LON_E,
                                self.fallo(nombre, p, 'fuera de la región cubierta'))

    def test_elevation_is_never_negative(self):
        for nombre, pts in self.datasets():
            for p in pts:
                self.assertGreaterEqual(p['elev'], 0,
                                        self.fallo(nombre, p, 'altitud negativa'))

    def test_the_sun_is_in_the_drawn_window(self):
        """Si el azimut se sale de la ventana, el panorama dibuja el Sol fuera del
        recuadro y la ficha enseña un gráfico sin Sol."""
        for nombre, pts in self.datasets():
            for p in pts:
                self.assertTrue(AZ_LO <= p['az'] <= AZ_HI,
                                self.fallo(nombre, p, f'azimut {p["az"]} fuera de '
                                                      f'[{AZ_LO}, {AZ_HI}]'))

    def test_the_margin_is_the_sun_minus_the_terrain(self):
        """`clear` no es un número suelto: tiene que salir de `alt` y `hz`, que son los
        dos que se enseñan al lado. Si se separan, la ficha se contradice a sí misma
        delante del usuario."""
        for nombre, pts in self.datasets():
            for p in pts:
                if p['total']:
                    continue          # con totalidad manda el peor de C2 y C3
                self.assertAlmostEqual(
                    p['clear'], p['alt'] - p['hz'], delta=0.02,
                    msg=self.fallo(nombre, p,
                                   f'clear={p["clear"]} pero alt-hz='
                                   f'{p["alt"] - p["hz"]:.2f}'))

    def test_the_horizon_profile_matches_the_azimuth_grid(self):
        n = len(recommend.AZIMUTHS)
        for nombre, pts in self.datasets():
            for p in pts:
                self.assertEqual(len(p['prof']), n,
                                 self.fallo(nombre, p, 'perfil de otro tamaño'))

    def test_obstacles_can_only_take_margin_away(self):
        """El margen neto nunca puede ser MAYOR que el del terreno pelado: un árbol no
        despeja un horizonte."""
        for nombre, pts in self.datasets():
            for p in pts:
                if p.get('clear_net') is None:
                    continue
                self.assertLessEqual(p['clear_net'], p['clear'] + 1e-6,
                                     self.fallo(nombre, p, 'el obstáculo SUMA margen'))


class TestTotalityIsCoherent(BaseDataset):

    def test_totality_means_seconds_and_two_contacts(self):
        for nombre, pts in self.datasets():
            for p in pts:
                if not p['total']:
                    continue
                self.assertGreater(p['dur'], 0, self.fallo(nombre, p, 'totalidad de 0 s'))
                self.assertIsNotNone(p['t2'], self.fallo(nombre, p, 'sin C2'))
                self.assertIsNotNone(p['t3'], self.fallo(nombre, p, 'sin C3'))
                self.assertLess(p['t2'], p['t3'],
                                self.fallo(nombre, p, f'C3 {p["t3"]} antes que C2 {p["t2"]}'))

    def test_a_partial_has_no_contacts_and_no_seconds(self):
        for nombre, pts in self.datasets():
            for p in pts:
                if p['total']:
                    continue
                self.assertEqual(p['dur'], 0, self.fallo(nombre, p, 'parcial con segundos'))
                self.assertIsNone(p['t2'], self.fallo(nombre, p, 'parcial con C2'))
                self.assertIsNone(p['t3'], self.fallo(nombre, p, 'parcial con C3'))

    def test_obscuration_is_a_percentage_and_totality_is_a_hundred(self):
        for nombre, pts in self.datasets():
            for p in pts:
                self.assertTrue(0 < p['obsc'] <= 100,
                                self.fallo(nombre, p, f'obscuración {p["obsc"]}'))
                if p['total']:
                    self.assertAlmostEqual(p['obsc'], 100.0, places=3,
                                           msg=self.fallo(nombre, p,
                                                          'totalidad sin 100 % tapado'))
                else:
                    self.assertLess(p['obsc'], 100.0,
                                    self.fallo(nombre, p, 'parcial con el 100 % tapado'))

    def test_the_limb_model_answers_for_every_point_or_for_none(self):
        """Media respuesta es lo peor: la lista ordenaría unos puntos con el criterio
        de los dos modelos y otros con el de uno solo, sin decirlo."""
        for nombre, pts in self.datasets():
            con = sum(1 for p in pts if p.get('dur_limb') is not None)
            self.assertIn(con, (0, len(pts)),
                          f'{nombre}: {con} de {len(pts)} con limbo, o todos o ninguno')

    def test_a_point_the_limb_saves_has_seconds_to_show(self):
        """Si se va a enseñar «puede haber unos segundos», que haya segundos."""
        for nombre, pts in self.datasets():
            for p in pts:
                if p.get('total_limb') and not p['total']:
                    self.assertGreater(p.get('dur_limb', 0), 0,
                                       self.fallo(nombre, p,
                                                  'el limbo da totalidad de 0 s'))


class TestWhatWeClaimAboutTheGround(BaseDataset):

    def test_every_point_says_where_it_is(self):
        """Un punto sin topónimo es un punto que no pasó el filtro de tierra firme."""
        for nombre, pts in self.datasets():
            for p in pts:
                self.assertTrue(p.get('place'),
                                self.fallo(nombre, p, 'sin topónimo: ¿está en el mar?'))

    def test_street_view_is_only_promised_where_there_is_a_road(self):
        """El enlace manda a una foto que sólo existe si hay carretera cerca. Sin esta
        regla se publicaron 1.422 enlaces rotos."""
        from eclipseview import obstacles
        for nombre, pts in self.datasets():
            for p in pts:
                if not p.get('sv'):
                    continue
                paved = (p.get('acc') or {}).get('paved')
                self.assertTrue(paved and paved['m'] <= obstacles.SV_MAX_ROAD_M,
                                self.fallo(nombre, p, 'Street View sin asfalto cerca'))

    def test_an_unchecked_point_never_carries_a_verdict(self):
        """`acc_ok=False` significa «no se sabe». Si además viniera con datos de acceso,
        la interfaz los pintaría como si se supieran."""
        for nombre, pts in self.datasets():
            for p in pts:
                if p.get('acc_ok'):
                    continue
                self.assertFalse(p.get('acc'),
                                 self.fallo(nombre, p, 'sin comprobar pero con acceso'))
                self.assertFalse(p.get('sv'),
                                 self.fallo(nombre, p, 'sin comprobar pero con foto'))

    def test_the_published_copy_matches_the_working_one(self):
        """El fallo que este test existe para cazar: construir el sitio con un
        `points.json` viejo y desplegar datos que no son los que se calcularon."""
        rutas = {k: v for k, v in FUENTES.items() if os.path.exists(v)}
        if len(rutas) < 2:
            self.skipTest('sólo hay una copia del dataset')
        cargados = {k: cargar(v)['points'] for k, v in rutas.items()}
        (n1, a), (n2, b) = list(cargados.items())
        self.assertEqual(len(a), len(b), f'{n1} tiene {len(a)} puntos y {n2} {len(b)}')
        for p, q in zip(a, b):
            self.assertEqual((p['lat'], p['lon'], p['total'], p['dur']),
                             (q['lat'], q['lon'], q['total'], q['dur']),
                             f'{n1} y {n2} discrepan en el punto {p["i"]}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
