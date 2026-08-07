# -*- coding: utf-8 -*-
"""El rescate de accesos sólo puede mejorar un punto, nunca empeorarlo.

Cambiar qué puntos se publican es la operación más peligrosa del proyecto: si se cuela
un cambio malo, la web manda a alguien a un sitio peor y nadie se entera hasta el día
del eclipse. Estos tests fijan las condiciones bajo las que un cambio es aceptable.
"""
import unittest

from eclipseview import recommend, rescue


def punto(**kw):
    """Un punto publicado con los valores que hagan falta y el resto por defecto."""
    p = dict(i=1, lat=41.0, lon=-3.0, clear=12.0, clear_net=12.0, obs_ok=True,
             total=True, dur=60.0, obsc=100.0, acc_ok=True, acc={})
    p.update(kw)
    return p


def con_asfalto(m):
    return dict(acc_ok=True, acc={'paved': {'m': m}})


def con_pista(m, dura=False):
    return dict(acc_ok=True, acc={'drive': {'m': m, 'hard': ['grade4'] if dura else []}})


class TestAccessRank(unittest.TestCase):
    """El orden de accesos tiene que ser total y sin empates ambiguos: es lo que
    permite decir «estrictamente mejor» sin discutir cada caso."""

    def test_paved_close_is_the_best(self):
        self.assertEqual(rescue.access_rank(punto(**con_asfalto(50))), 3)

    def test_soft_track_close_beats_far_asphalt(self):
        pista = rescue.access_rank(punto(**con_pista(100)))
        lejos = rescue.access_rank(punto(**con_asfalto(900)))
        self.assertGreater(pista, lejos)

    def test_a_hard_track_is_not_a_good_access(self):
        """OSM marca 4x4/grade4 y eso no es «se llega en coche»."""
        self.assertLess(rescue.access_rank(punto(**con_pista(100, dura=True))), 2)

    def test_silence_is_never_treated_as_easy(self):
        """Sin comprobar tiene que valer lo mismo que lo peor, nunca más."""
        sin = rescue.access_rank(punto(acc_ok=False, acc=None))
        self.assertEqual(sin, 0)
        self.assertLessEqual(sin, rescue.access_rank(punto(**con_pista(1100))))


class TestNeedsRescue(unittest.TestCase):

    def test_only_fires_when_the_margin_saturates(self):
        """Si el margen no satura, el criterio SÍ desempata y no hay nada que arreglar:
        tocar ese punto sería cambiar calidad por comodidad."""
        justo = recommend.CLEAR_SATURATION - 0.1
        self.assertFalse(rescue.needs_rescue(
            punto(clear=justo, clear_net=justo, **con_pista(1100))))

    def test_fires_on_saturated_and_badly_reached(self):
        self.assertTrue(rescue.needs_rescue(
            punto(clear=14.0, clear_net=14.0, **con_pista(1100))))

    def test_a_good_access_is_left_alone(self):
        self.assertFalse(rescue.needs_rescue(
            punto(clear=14.0, clear_net=14.0, **con_asfalto(40))))

    def test_it_is_the_NET_margin_that_decides(self):
        """Un punto con 12° de terreno pero un pinar que se come 5° NO satura de
        verdad. Mirar `clear` en vez de `clear_net` lo metería en el rescate."""
        p = punto(clear=12.0, clear_net=7.0, obs_ok=True, **con_pista(1100))
        self.assertFalse(rescue.needs_rescue(p))


class TestBetterRefusesToDowngrade(unittest.TestCase):
    """Cada uno de estos tests es una forma de que el rescate estropee el dataset."""

    def setUp(self):
        self.orig = punto(clear=14.0, clear_net=14.0, total=True, dur=60.0,
                          **con_pista(1100))

    def test_never_trades_totality_for_a_partial(self):
        cand = punto(clear=20.0, clear_net=20.0, total=False, dur=0.0,
                     **con_asfalto(20))
        self.assertFalse(rescue.better(self.orig, cand))

    def test_never_gives_away_seconds_of_corona(self):
        cand = punto(clear=20.0, clear_net=20.0, total=True, dur=40.0,
                     **con_asfalto(20))
        self.assertFalse(rescue.better(self.orig, cand))

    def test_a_candidate_that_does_not_saturate_is_not_equally_good(self):
        flojo = recommend.CLEAR_SATURATION - 0.5
        cand = punto(clear=flojo, clear_net=flojo, total=True, dur=60.0,
                     **con_asfalto(20))
        self.assertFalse(rescue.better(self.orig, cand))

    def test_the_same_access_is_not_a_reason_to_move(self):
        cand = punto(clear=20.0, clear_net=20.0, total=True, dur=60.0,
                     **con_pista(1100))
        self.assertFalse(rescue.better(self.orig, cand))

    def test_never_moves_a_point_onto_water(self):
        """Sobre el mar el modelo de elevación vale 0 y el horizonte sale impecable, así
        que un punto en el agua gana en margen y en acceso a la vez. Un reverse que sólo
        acierta el país («España») es la señal. Pasó de verdad: un candidato en la ría de
        Vigo llegó hasta el guardia final y tiró una pasada de dos horas."""
        cand = punto(clear=20.0, clear_net=20.0, total=True, dur=61.0,
                     place='España', **con_asfalto(20))
        self.assertFalse(rescue.better(self.orig, cand))

    def test_a_named_municipality_is_accepted(self):
        cand = punto(clear=14.0, clear_net=14.0, total=True, dur=61.0,
                     place='Lalín, Deza, Galicia', **con_asfalto(30))
        self.assertTrue(rescue.better(self.orig, cand))

    def test_a_real_improvement_is_accepted(self):
        cand = punto(clear=14.0, clear_net=14.0, total=True, dur=61.0,
                     **con_asfalto(30))
        self.assertTrue(rescue.better(self.orig, cand))

    def test_a_couple_of_seconds_of_noise_do_not_block_it(self):
        """Exigir dur exacto sería tan estricto que no rescataría nada: el cálculo
        tiene décimas de ruido entre dos puntos a un kilómetro."""
        cand = punto(clear=14.0, clear_net=14.0, total=True,
                     dur=60.0 - rescue.DUR_TOLERANCE_S + 0.1, **con_asfalto(30))
        self.assertTrue(rescue.better(self.orig, cand))


class TestNoTwoPointsEndUpInTheSameSpot(unittest.TestCase):
    """Los candidatos salen de la celda, y una celda puede tener varios puntos
    publicados dentro. Sin reservar el sitio, todos se quedan con la mejor alternativa:
    la primera pasada real dejó CUATRO puntos en la misma coordenada de Silleda. Dos
    puntos idénticos ocupan dos huecos de la lista de ocho."""

    def test_two_points_sharing_candidates_do_not_collide(self):
        a = punto(i=1, lat=42.0, lon=-8.0, clear=14.0, clear_net=14.0,
                  **con_pista(1100))
        b = punto(i=2, lat=42.05, lon=-8.05, clear=14.0, clear_net=14.0,
                  **con_pista(1100))
        mejor = punto(i=0, lat=42.10, lon=-8.10, clear=15.0, clear_net=15.0,
                      place='Silleda, Deza, Galicia', **con_asfalto(20))
        segundo = punto(i=0, lat=42.20, lon=-8.20, clear=15.0, clear_net=15.0,
                        place='Lalín, Deza, Galicia', **con_asfalto(60))
        # los dos reciben la MISMA lista, como pasa de verdad
        finos = {1: [dict(mejor), dict(segundo)], 2: [dict(mejor), dict(segundo)]}
        cambios = rescue.choose_swaps([a, b], finos)
        self.assertEqual(len(cambios), 2, 'los dos deberían mejorar')
        destinos = [(q['lat'], q['lon']) for _, q in cambios]
        self.assertEqual(len(destinos), len(set(destinos)),
                         'dos puntos han acabado en la misma coordenada')

    def test_a_candidate_on_an_existing_point_is_refused(self):
        """Y tampoco puede mudarse encima de un punto que ya está publicado."""
        a = punto(i=1, lat=42.0, lon=-8.0, clear=14.0, clear_net=14.0,
                  **con_pista(1100))
        ocupado = punto(i=2, lat=42.10, lon=-8.10, clear=14.0, clear_net=14.0,
                        **con_asfalto(20))
        encima = punto(i=0, lat=42.10, lon=-8.10, clear=15.0, clear_net=15.0,
                       place='Silleda, Deza, Galicia', **con_asfalto(20))
        cambios = rescue.choose_swaps([a, ocupado], {1: [encima]})
        self.assertEqual(cambios, [], 'se ha mudado encima de otro punto')

    def test_the_spot_it_leaves_becomes_free_again(self):
        """Si A se va de X, otro puede ocupar X: reservarlo para siempre bloquearía
        cambios buenos sin motivo."""
        a = punto(i=1, lat=42.0, lon=-8.0, clear=14.0, clear_net=14.0,
                  **con_pista(1100))
        b = punto(i=2, lat=42.5, lon=-8.5, clear=14.0, clear_net=14.0,
                  **con_pista(1100))
        lejos = punto(i=0, lat=43.0, lon=-9.0, clear=15.0, clear_net=15.0,
                      place='Dumbría, Fisterra, Galicia', **con_asfalto(20))
        alsitio_de_a = punto(i=0, lat=42.0, lon=-8.0, clear=15.0, clear_net=15.0,
                             place='Lalín, Deza, Galicia', **con_asfalto(20))
        cambios = rescue.choose_swaps([a, b], {1: [lejos], 2: [alsitio_de_a]})
        self.assertEqual(len(cambios), 2)


class TestTheCellIsTheSameOneSelectUsed(unittest.TestCase):
    """El rescate busca alternativas en «la celda del punto». Si esa definición se
    separa de la de `select()`, busca en el sitio equivocado y no encuentra nada -- o
    peor, encuentra algo a cien kilómetros y lo da por vecino."""

    def test_select_does_not_recompute_the_cell_on_its_own(self):
        import inspect
        src = inspect.getsource(recommend.select)
        self.assertIn('cell_key(', src, 'select() usa la definición compartida')
        self.assertNotIn('/ 111.2', src, 'y no se fabrica otra por su cuenta')

    def test_two_points_far_apart_are_never_the_same_cell(self):
        a = recommend.cell_key(41.0, -3.0, True)
        b = recommend.cell_key(41.0, -3.0 + 1.0, True)     # ~84 km al este
        self.assertNotEqual(a, b)

    def test_partial_cells_are_coarser_than_total_ones(self):
        self.assertGreater(recommend.SEP_KM_PARTIAL, recommend.SEP_KM)


class TestSaturationIsOneNumber(unittest.TestCase):

    def test_select_clips_at_the_declared_saturation(self):
        """Si alguien cambia el 8.0 del score y no la constante, el rescate creería que
        satura donde ya no satura y empezaría a mover puntos que sí se distinguían."""
        import inspect
        src = inspect.getsource(recommend.select)
        self.assertIn('CLEAR_SATURATION', src)
        self.assertNotIn('8.0)', src, 'el tope no se escribe a mano en el score')


class TestAnAssumedHeightIsNeverMeasured(unittest.TestCase):
    """La altura del arbolado es lo ÚNICO que este proyecto se inventa: OSM casi nunca
    la trae. Vale inventarla —suponer cero sería peor, porque un cero se lee como «aquí
    no hay nada»— pero no vale presentarla como medida."""

    def test_a_default_never_comes_back_as_measured(self):
        from eclipseview import obstacles
        for clave in ('wood', 'forest', 'scrub', 'orchard', 'vineyard'):
            alto, medida = obstacles._height({'landuse': clave})
            self.assertEqual(alto, obstacles.DEFAULT_HEIGHTS[clave])
            self.assertFalse(medida, f'{clave}: valor por defecto marcado como medido')
        alto, medida = obstacles._height({'building': 'yes'})
        self.assertFalse(medida, 'edificio sin altura marcado como medido')

    def test_a_real_tag_does_come_back_as_measured(self):
        """Y al revés: una altura etiquetada de verdad no puede quedarse en estimada, o
        la ficha estaría rebajando un dato bueno."""
        from eclipseview import obstacles
        self.assertEqual(obstacles._height({'height': '24'}), (24.0, True))
        self.assertEqual(obstacles._height({'building:levels': '4'}),
                         (4 * obstacles.LEVEL_HEIGHT_M, True))

    def test_a_measurement_that_equals_the_default_is_still_a_measurement(self):
        """3 m es el valor supuesto para el matorral y también una altura etiquetada
        perfectamente posible. Distinguirlas por la cifra es imposible; por eso la
        marca viaja aparte y este test existe."""
        from eclipseview import obstacles
        alto, medida = obstacles._height({'height': '3', 'landuse': 'scrub'})
        self.assertEqual(alto, 3.0)
        self.assertTrue(medida)


if __name__ == '__main__':
    unittest.main(verbosity=2)
