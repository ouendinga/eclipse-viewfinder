# -*- coding: utf-8 -*-
"""Traducciones del informe de lugar.

Van como diccionarios normales y no con gettext para que el repo no arrastre
dependencias y para que quien traduzca vea todas las cadenas de golpe. Las claves que
falten caen al español y `check()` las saca, así que un idioma a medio traducir se ve
en vez de pasar en silencio.

El informe general de España es sólo en español a propósito: es un ensayo sobre el
terreno de un país, no una plantilla. El que generaliza es el informe de *lugar*.
"""
import decimal

DEFAULT = 'es'

STRINGS = {
    'es': {
        'lang_name': 'español',
        'report_title': 'Mejores miradores del eclipse cerca de {place}',
        'eyebrow': '{event} · búsqueda de miradores',
        'h1': 'Los mejores sitios a {radius:.0f} km de {place}',
        'lede': ('Ordenados por <b>margen libre</b>: los grados que separan al Sol '
                 'del terreno real en el momento clave. Exijo al menos '
                 '<b>{min_clear}</b>, porque el modelo del terreno no sabe de '
                 'árboles ni de edificios.'),
        'summary': 'Resumen',
        'col_site': 'sitio', 'col_coords': 'lat, lon', 'col_elev': 'm',
        'col_dist': 'km', 'col_obsc': 'sol oculto', 'col_alt': 'altura sol',
        'col_horizon': 'horizonte', 'col_margin': 'margen', 'col_dur': 'totalidad',
        'n_coords': 'coordenadas', 'n_elev': 'altitud', 'n_dist': 'distancia',
        'n_obsc': 'sol oculto', 'n_alt': 'altura del sol', 'n_az': 'azimut',
        'n_horizon': 'horizonte real', 'n_margin': 'margen libre',
        'n_max': 'máximo ({tz})', 'n_blocker': 'obstáculo a', 'n_dur': 'totalidad',
        'badge_total': 'TOTALIDAD', 'badge_partial': '{pct} parcial',
        'origin_note': ('Origen: {place} ({lat:.4f}, {lon:.4f}), según '
                        '{gazetteer}. <b>Margen</b> negativo = el Sol se pone '
                        'detrás del terreno antes del momento clave. En los '
                        'panoramas, el Sol y la Luna están dibujados a tamaño y '
                        'posición reales: el creciente que ves es el que verás.'),
        'no_results': ('No he encontrado ningún sitio con al menos {min_clear} de '
                       'margen en {radius:.0f} km. Prueba a ampliar el radio o a '
                       'bajar el mínimo exigido.'),
        'note_blocked': ('<b>No sirve.</b> El Sol se esconde tras el terreno hacia '
                         'las {set_time}, y el momento clave es a las {max_time}. '
                         'La silueta se levanta {horizon} y el Sol solo llega a '
                         '{alt}.'),
        'note_tight': ('<b>Justo.</b> Solo <b>{margin}</b> por encima de la '
                       'silueta, unas {times:.1f} veces el diámetro del Sol. El '
                       'obstáculo está a {blocker}; a esa distancia un árbol o una '
                       'nave no salen en el modelo y sí en la foto. Ve a verlo '
                       'antes.'),
        'note_ok': ('<b>Margen cómodo:</b> {margin} libres, unas {times:.0f} veces '
                    'el diámetro del Sol. Lo más alto en esa dirección está a '
                    '{blocker} y se queda en {horizon}.'),
        'note_total': ' Aquí hay <b>totalidad: {dur}</b>.',
        'note_total_edge': (' Ojo: entra en la franja pero solo por <b>{dur}</b>, '
                            'o sea justo en el borde de la sombra: el margen de '
                            'error es alto.'),
        'note_partial': (' Eclipse <b>parcial</b>: {obsc} del disco oculto, pero '
                         'no hay corona.'),
        'how_title': 'Cómo se lee un panorama',
        'how_1': ('La silueta oscura es el terreno real hacia el ONO, con la '
                  'curvatura de la Tierra y la refracción incluidas.'),
        'how_2': ('Los círculos naranjas son el Sol cada 10 minutos, a su tamaño '
                  'angular real. Donde se apagan, ya se ha puesto tras el terreno.'),
        'how_3': ('El recuadro ampliado enseña la forma exacta del Sol en el '
                  'momento clave, con la Luna en su posición real.'),
        'how_4': ('El <b>margen libre</b> es lo que decide. Por debajo de '
                  '{min_clear} no me fiaría.'),
        'footer': ('Efemérides {de421} · relieve {srtm} · topónimos {osm} · '
                   'curvatura y refracción incluidas (k = 0,13). Hora local: {tz}.'),
        'verified': 'Motor verificado: {passed}/{total} comprobaciones contra '
                    'valores publicados y cálculos analíticos.',
    },
    'en': {
        'lang_name': 'English',
        'report_title': 'Best eclipse viewpoints near {place}',
        'eyebrow': '{event} · viewpoint search',
        'h1': 'The best spots within {radius:.0f} km of {place}',
        'lede': ('Ranked by <b>clearance</b>: the degrees between the Sun and the '
                 'real skyline at the key moment. I require at least '
                 '<b>{min_clear}</b>, because an elevation model knows nothing '
                 'about trees or buildings.'),
        'summary': 'Summary',
        'col_site': 'site', 'col_coords': 'lat, lon', 'col_elev': 'm',
        'col_dist': 'km', 'col_obsc': 'sun covered', 'col_alt': 'sun altitude',
        'col_horizon': 'skyline', 'col_margin': 'clearance', 'col_dur': 'totality',
        'n_coords': 'coordinates', 'n_elev': 'elevation', 'n_dist': 'distance',
        'n_obsc': 'sun covered', 'n_alt': 'sun altitude', 'n_az': 'azimuth',
        'n_horizon': 'real skyline', 'n_margin': 'clearance',
        'n_max': 'maximum ({tz})', 'n_blocker': 'obstacle at', 'n_dur': 'totality',
        'badge_total': 'TOTALITY', 'badge_partial': '{pct} partial',
        'origin_note': ('Origin: {place} ({lat:.4f}, {lon:.4f}), per {gazetteer}. '
                        'A negative <b>clearance</b> means the Sun sets behind the '
                        'terrain before the key moment. In the panoramas the Sun '
                        'and Moon are drawn at true size and position: the '
                        'crescent shown is the crescent you would see.'),
        'no_results': ('No spot within {radius:.0f} km has at least {min_clear} of '
                       'clearance. Try a wider radius or a lower minimum.'),
        'note_blocked': ('<b>No good.</b> The Sun disappears behind the terrain at '
                         'about {set_time}, and the key moment is {max_time}. The '
                         'skyline rises to {horizon} and the Sun only reaches '
                         '{alt}.'),
        'note_tight': ('<b>Tight.</b> Only <b>{margin}</b> above the skyline, about '
                       '{times:.1f} times the Sun\'s diameter. The obstacle is '
                       '{blocker} away; at that range a tree or a shed is invisible '
                       'to the model and very visible in the photo. Go and look '
                       'first.'),
        'note_ok': ('<b>Comfortable:</b> {margin} clear, about {times:.0f} times '
                    'the Sun\'s diameter. The highest thing in that direction is '
                    '{blocker} away and stays at {horizon}.'),
        'note_total': ' There is <b>totality here: {dur}</b>.',
        'note_total_edge': (' Careful: inside the path but only for <b>{dur}</b>, '
                            'i.e. right at the shadow edge, so the error margin is '
                            'large.'),
        'note_partial': (' <b>Partial</b> eclipse: {obsc} of the disc covered, but '
                         'no corona.'),
        'how_title': 'How to read a panorama',
        'how_1': ('The dark silhouette is the real terrain toward the WNW, '
                  'including Earth curvature and atmospheric refraction.'),
        'how_2': ('The orange circles are the Sun every 10 minutes at true angular '
                  'size. Where they fade, it has already set behind the ground.'),
        'how_3': ('The magnified inset shows the exact shape of the Sun at the key '
                  'moment, with the Moon in its real position.'),
        'how_4': ('<b>Clearance</b> is what decides. Below {min_clear} I would not '
                  'trust it.'),
        'footer': ('Ephemerides {de421} · terrain {srtm} · place names {osm} · '
                   'curvature and refraction included (k = 0.13). Local time: {tz}.'),
        'verified': 'Engine verified: {passed}/{total} checks against published '
                    'values and analytic results.',
    },
}


def available():
    return sorted(STRINGS)


def t(lang, key, **kw):
    d = STRINGS.get(lang) or STRINGS[DEFAULT]
    s = d.get(key)
    if s is None:
        s = STRINGS[DEFAULT].get(key, key)
    return s.format(**kw) if kw else s


def number(lang, value, decimals=2, sign=False):
    """El español lleva coma decimal y el inglés punto. Pasa por aquí toda cifra que se
    imprime, así que un informe no puede mezclar convenios.

    Y redondea las mitades exactas HACIA ARRIBA, no a la par. No es una manía: el
    buscador de la web formatea con `toFixed`, que redondea hacia arriba, mientras que
    Python formatea a la par. Con 99,25 % el informe decía 99,2 % y la web 99,3 % del
    mismo punto. Son seis puntos del dataset, pero un lector que compare las dos cifras
    no tiene forma de saber cuál creer.
    """
    q = decimal.Decimal(1).scaleb(-decimals)
    # Decimal(float) toma el valor binario EXACTO, que es sobre el que opera toFixed.
    # Pasar por repr() daría 1,01 donde el navegador da 1,00.
    v = decimal.Decimal(float(value)).quantize(q, rounding=decimal.ROUND_HALF_UP)
    s = f'{v:+f}' if sign else f'{v:f}'
    return s.replace('.', ',') if (lang or DEFAULT).startswith('es') else s


def deg(lang, value, decimals=2, sign=False):
    return number(lang, value, decimals, sign) + '°'


def obscuration(lang, pct, total):
    """Formatea un porcentaje de obscuración sin mentir por redondeo.

    Un parcial del 99,994 % no puede salir como «100,0% parcial»: se lee como una
    contradicción y se lleva por delante la credibilidad del resto de números de la
    página. Se añaden decimales hasta que el valor se queda por debajo de 100, y si nunca
    lo consigue se cae a un «>» explícito.
    """
    if total:
        return '100%'
    for decimals in (1, 2, 3):
        s = number(lang, pct, decimals)
        if float(s.replace(',', '.')) < 100.0:
            return s + '%'
    return '>' + number(lang, 99.999, 3) + '%'


def check(lang):
    """Las claves que le faltan a un idioma, para que una traducción incompleta se vea."""
    base = set(STRINGS[DEFAULT])
    return sorted(base - set(STRINGS.get(lang, {})))
