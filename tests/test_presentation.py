# -*- coding: utf-8 -*-
"""Lo que la ficha ENSEÑA, ejecutado sobre el dataset entero.

Los tests de datos comprueban que `points.json` es coherente. Estos comprueban el paso
siguiente, que es donde el usuario se juega el viaje: que las reglas de la interfaz no
puedan pintar una contradicción a partir de un dato correcto.

Se ejecuta con `node` el JavaScript que se publica, no una traducción a Python. Una
reimplementación aprobaría aunque el navegador hiciera otra cosa, que es justo el fallo
que estos tests tendrían que cazar.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from eclipseview import finder_ui, i18n
from eclipseview.paths import DATA_DIR

PUNTOS = os.path.join(DATA_DIR, 'points.json')
HAY_NODE = shutil.which('node')


def _cuerpo(src, i):
    """Desde `function` en `i`, devuelve hasta su llave de cierre emparejada.

    Cortar por indentación no vale: las funciones de una línea cierran en la misma
    línea, y buscar el siguiente "  }" se tragaba entera la función de al lado. Se
    cuentan llaves saltando las que van dentro de una cadena.
    """
    j = src.index('{', i)
    nivel, k, comilla = 0, j, None
    while k < len(src):
        c = src[k]
        if comilla:
            if c == '\\':
                k += 2
                continue
            if c == comilla:
                comilla = None
        elif c in '"\'':
            comilla = c
        elif c == '{':
            nivel += 1
        elif c == '}':
            nivel -= 1
            if nivel == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError('llaves sin emparejar al extraer el JS')


def extraer(nombres):
    """Saca del script publicado las funciones pedidas, tal cual se publican."""
    src = finder_ui.script()
    return '\n'.join(_cuerpo(src, src.index(f'function {n}(')) for n in nombres)


def correr(js, puntos):
    """Ejecuta `js` con los puntos en `PTS` y devuelve lo que imprima como JSON."""
    # los puntos se declaran ANTES: `var` iza la declaración pero no el valor, así que
    # ponerlos al final dejaba PTS a undefined justo cuando se usa
    harness = 'var PTS=JSON.parse(require("fs").readFileSync(process.argv[2]));\n' + js
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False,
                                     encoding='utf-8') as fh:
        fh.write(harness)
        script = fh.name
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                     encoding='utf-8') as fh:
        json.dump(puntos, fh)
        datos = fh.name
    try:
        out = subprocess.run(['node', script, datos], capture_output=True, text=True,
                             timeout=180)
    finally:
        os.unlink(script)
        os.unlink(datos)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


@unittest.skipUnless(HAY_NODE, 'sin node para ejecutar el JS publicado')
@unittest.skipUnless(os.path.exists(PUNTOS), 'sin points.json')
class TestTheCardCannotContradictItself(unittest.TestCase):
    """Sobre los 1.456 puntos de verdad, no sobre tres casos inventados: los casos que
    rompen cosas son siempre los del filo, y esos no se le ocurren a nadie."""

    @classmethod
    def setUpClass(cls):
        with open(PUNTOS, encoding='utf-8') as fh:
            cls.puntos = json.load(fh)['points']

    def _mapa(self, funciones, expresion):
        js = extraer(funciones) + (
            '\nvar out=PTS.map(function(p){return ' + expresion + ';});'
            'console.log(JSON.stringify(out));')
        return correr(js, self.puntos)

    def test_a_partial_never_reads_as_a_hundred_percent(self):
        """El fallo que abrió todo esto: 99,951 % redondeado salía «100,0% parcial»."""
        textos = self._mapa(['n', 'obscTxt'], 'obscTxt(p,1)')
        for p, t in zip(self.puntos, textos):
            if p['total']:
                continue
            self.assertLess(float(t.lstrip('>').replace(',', '.')), 100.0,
                            f'{p["place"]} ({p["obsc"]}%) se pinta «{t}% parcial»')

    def test_the_web_and_the_report_say_the_same_number(self):
        """Dos reglas distintas para el mismo dato dejarían al informe diciendo 99,95 %
        y a la web 99,9 % del mismo sitio."""
        textos = self._mapa(['n', 'obscTxt'], 'obscTxt(p,1)')
        for p, t in zip(self.puntos, textos):
            if p['total']:
                continue      # con totalidad la ficha escribe «100%» directamente
            self.assertEqual(t + '%', i18n.obscuration('es', p['obsc'], False),
                             f'discrepan en {p["place"]}')

    def test_only_one_warning_chip_can_ever_show(self):
        """Los tres avisos del filo son excluyentes. Si dos pudieran salir a la vez, la
        ficha diría «sin totalidad segura» y «puede haber unos segundos» pegados."""
        js = extraer(['n', 'durLo', 'durHi']) + """
var out=PTS.map(function(p){
  var a = (p.total && p.total_limb===false) ? 1 : 0;
  var b = (!p.total && p.total_limb) ? 1 : 0;
  var c = (p.total && durLo(p) < 30) ? 1 : 0;
  return [a,b,c];
});console.log(JSON.stringify(out));"""
        for p, (a, b, c) in zip(self.puntos, correr(js, self.puntos)):
            self.assertLessEqual(a + b + c, 1,
                                 f'{p["place"]} enseñaría más de un aviso a la vez')

    def test_solid_totality_is_the_one_both_models_confirm(self):
        """El orden de la lista lo decide `solida`. Un punto que sólo ve un modelo no
        puede encabezarla: es la regla que evita mandar a alguien a por una corona que
        puede no estar."""
        vals = self._mapa(['solida'], 'solida(p)')
        for p, v in zip(self.puntos, vals):
            esperado = 1 if (p['total'] and p.get('total_limb')) else 0
            self.assertEqual(v, esperado, f'{p["place"]}')

    def test_the_duration_range_always_contains_both_models(self):
        """La chapa enseña «TOTALIDAD 13-24 s». Si el rango no contuviera las dos
        cifras, estaría escondiendo justo la que no gusta."""
        js = extraer(['n', 'durLo', 'durHi']) + (
            '\nvar out=PTS.map(function(p){return [durLo(p), durHi(p)];});'
            'console.log(JSON.stringify(out));')
        for p, (lo, hi) in zip(self.puntos, correr(js, self.puntos)):
            self.assertLessEqual(lo, hi, f'{p["place"]}: rango invertido')
            if p['total']:
                self.assertLessEqual(lo, p['dur'], f'{p["place"]}')
                self.assertGreaterEqual(hi, p['dur'], f'{p["place"]}')

    def test_the_access_label_never_promises_a_road_that_is_not_there(self):
        """«asfalto a 40 m» tiene que salir de una vía asfaltada a 40 m. Es la frase que
        decide si alguien va con el coche de calle o no va."""
        etiquetas = self._mapa(['n', 'acc_label'], 'acc_label(p)')
        # Sólo las frases que AFIRMAN algo llevan distancia («asfalto a 40 m»). Las que
        # niegan («sin vía en 1,2 km») también contienen la palabra, así que hay que
        # mirar la afirmación y no la palabra suelta.
        for p, txt in zip(self.puntos, etiquetas):
            acc = p.get('acc') or {}
            if txt == 'sin comprobar':
                self.assertFalse(p.get('acc_ok') and acc,
                                 f'{p["place"]}: dice sin comprobar y sí lo está')
                continue
            if txt.startswith('sin ') or txt == 'solo sendero':
                continue
            self.assertIn(' a ', txt, f'{p["place"]}: etiqueta inesperada «{txt}»')
            if txt.startswith('asfalto'):
                self.assertTrue(acc.get('paved'),
                                f'{p["place"]}: «{txt}» sin vía asfaltada en los datos')
            else:
                self.assertTrue(acc.get('drive') or acc.get('paved'),
                                f'{p["place"]}: «{txt}» sin vía en los datos')

    def test_the_card_says_estimated_when_it_is_estimated(self):
        """Los 18 m de un pinar son una suposición, no un dato: OSM casi nunca etiqueta
        la altura del arbolado. La ficha tiene que escribir «altura estimada», porque es
        lo único que este proyecto se inventa y venderlo como medido sería lo peor que
        podría hacer."""
        js = 'function esc(s){return String(s==null?"":s);}\n'   # el real usa el DOM
        js += extraer(['n', 'deg', 'obscTxt', 'why'])
        js += ('\nvar out=PTS.map(function(p){return why(p, 10);});'
               'console.log(JSON.stringify(out));')
        textos = correr(js, self.puntos)
        vistos = 0
        for p, t in zip(self.puntos, textos):
            if p.get('obs_ok') and p.get('obs', 0) > 0 and p.get('obs_what'):
                esperado = 'altura del mapa' if p.get('obs_meas') else 'altura estimada'
                self.assertIn(esperado, t, f'{p["place"]}')
                vistos += 1
        self.assertGreater(vistos, 0, 'ningún punto ejercita la frase del obstáculo')

    def test_an_unchecked_point_is_never_painted_as_good(self):
        """`acc_class` decide el color. Un dato que falta no puede salir en verde."""
        clases = self._mapa(['acc_class'], 'acc_class(p)')
        for p, c in zip(self.puntos, clases):
            if not p.get('acc_ok'):
                self.assertEqual(c, 'no', f'{p["place"]}: sin comprobar pero pintado {c}')


@unittest.skipUnless(os.path.exists(PUNTOS), 'sin points.json')
class TestTheHeadlineNumbersAreReachable(unittest.TestCase):
    """La lista sólo pinta los ocho primeros. Una función que sólo se dispara en el
    noveno es código muerto que nadie ve, y da la falsa sensación de estar cubierto."""

    @classmethod
    def setUpClass(cls):
        with open(PUNTOS, encoding='utf-8') as fh:
            cls.puntos = json.load(fh)['points']

    def test_the_limb_warning_is_reachable_from_somewhere(self):
        import math

        def km(a, b, c, d):
            x = (a - c) * 111.2
            y = (b - d) * 111.32 * math.cos(math.radians((a + c) / 2))
            return math.hypot(x, y)

        def net(p):
            return (p['clear_net'] if p.get('clear_net') is not None and p.get('obs_ok')
                    else p['clear'])

        def solida(p):
            return 1 if (p['total'] and p.get('total_limb')) else 0

        avisan = {p['i'] for p in self.puntos
                  if p.get('total_limb') and not p['total']}
        if not avisan:
            self.skipTest('ningún punto activa el aviso del limbo')
        visto = set()
        for o in self.puntos:
            cerca = [q for q in self.puntos
                     if km(o['lat'], o['lon'], q['lat'], q['lon']) <= 60]
            cerca.sort(key=lambda q: (-solida(q), -net(q)))
            for q in cerca[:8]:
                if q['i'] in avisan:
                    visto.add(q['i'])
        self.assertTrue(visto,
                        'el aviso «puede haber unos segundos» está escrito pero ningún '
                        'punto lo alcanza nunca en la lista de ocho')


class TestTheCountdownPointsAtTheRightInstant(unittest.TestCase):
    """La cuenta atrás la resta el navegador desde un instante UTC. Si ese instante
    está mal, engaña a todo el que la mire y no hay forma de que salte un test de
    geometría: el número es perfectamente plausible."""

    def setUp(self):
        from eclipseview import countdown, events
        self.countdown = countdown
        self.ev = events.DEFAULT

    def test_it_accepts_the_contact_format_with_seconds(self):
        """Los contactos del dataset llevan segundos. Antes esto reventaba."""
        self.assertEqual(self.countdown._utc_iso(self.ev, '20:26:14'),
                         '2026-08-12T18:26:14Z')

    def test_it_still_accepts_plain_minutes(self):
        self.assertEqual(self.countdown._utc_iso(self.ev, '20:26'),
                         '2026-08-12T18:26:00Z')

    def test_crossing_midnight_moves_the_day_too(self):
        """Restar el huso puede cambiar la fecha. Ajustar sólo la hora dejaría una
        cuenta atrás con 24 h de error y con toda la pinta de estar bien."""
        self.assertEqual(self.countdown._utc_iso(self.ev, '00:00:30'),
                         '2026-08-11T22:00:30Z')

    @unittest.skipUnless(os.path.exists(PUNTOS), 'sin points.json')
    def test_the_instant_comes_from_the_dataset_and_is_the_earliest(self):
        """No puede haber una hora escrita a mano: si se recalculan los puntos y el
        minuto cambia, la cuenta atrás tiene que cambiar sola."""
        with open(PUNTOS, encoding='utf-8') as fh:
            pts = json.load(fh)['points']
        contactos = [p['t2'] for p in pts if p['total'] and p['t2']]
        if not contactos:
            self.skipTest('ningún punto con totalidad')
        primero = min(contactos)
        html = self.countdown.html(primero, self.ev)
        self.assertIn(self.countdown._utc_iso(self.ev, primero), html)
        for t in contactos:
            self.assertGreaterEqual(t, primero,
                                    'hay una totalidad antes de la que se anuncia')


if __name__ == '__main__':
    unittest.main(verbosity=2)
