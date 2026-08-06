# -*- coding: utf-8 -*-
"""Datos externos y valores de referencia, cada uno con su cita.

Nada de este fichero lo calcula el proyecto. Va aparte a propósito para que la
frontera entre «lo que deduce el código» y «lo que publicó otro» se vea en el código,
y no sólo en la prosa.

Dos clases de entradas:
  * REFERENCE_* -- valores publicados que sirven para VERIFICAR el motor (ver tests/).
  * CLIMATOLOGY -- estadística de nubes de agosto, que no se puede sacar de las
    efemérides ni del terreno y que por tanto el informe tiene que atribuir.
"""

EVENT = {
    'date': '2026-08-12',
    'name': 'Eclipse total de Sol del 12 de agosto de 2026',
    'tz_offset_h': 2,          # hora peninsular en agosto = UTC+2 (CEST)
}

CITATIONS = {
    'nasa_gsfc': {
        'label': 'NASA GSFC Eclipse Web Site',
        'url': 'https://eclipse.gsfc.nasa.gov/SEsearch/SEsearchmap.php?Ecl=20260812',
    },
    'ign': {
        'label': 'Instituto Geográfico Nacional (IGN)',
        'url': 'https://eclipses.ign.es/eclipse-total-sol-de-12-de-agosto-2026.html',
    },
    'eclipsophile': {
        'label': 'Eclipsophile — Jay Anderson',
        'url': 'https://eclipsophile.com/tse2026/',
    },
    'ign_2027': {
        'label': 'IGN — eclipse total del 2 de agosto de 2027',
        'url': 'https://eclipses.ign.es/eclipse-total-sol-de-2-de-agosto-2027.html',
    },
    'ign_2028': {
        'label': 'IGN — eclipse anular del 26 de enero de 2028',
        'url': 'https://eclipses.ign.es/eclipse-anular-sol-de-26-de-enero-2028.html',
    },
    'srtm': {
        'label': 'SRTM 1 arcsec vía AWS Terrain Tiles',
        'url': 'https://registry.opendata.aws/terrain-tiles/',
    },
    'de421': {
        'label': 'JPL DE421 (Skyfield)',
        'url': 'https://ssd.jpl.nasa.gov/planets/eph_export.html',
    },
    'osm': {
        'label': 'Nominatim / OpenStreetMap',
        'url': 'https://nominatim.openstreetmap.org/',
    },
    # Árboles, edificios y vías NO salen de Nominatim (geocodificador): salen de
    # Overpass, que consulta la base de datos de OSM. Citar la fuente correcta.
    'overpass': {
        'label': 'Overpass API / OpenStreetMap',
        'url': 'https://overpass-api.de/',
    },
    'open_meteo': {
        'label': 'Open-Meteo',
        'url': 'https://open-meteo.com/',
    },
    'lola': {
        'label': 'LOLA / LRO — topografía lunar (NASA PDS)',
        'url': 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/',
    },
    'naif': {
        'label': 'NAIF/JPL — orientación de la Luna (moon_pa_de421)',
        'url': 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/',
    },
}

# --------------------------------------------------------------- verification

# Punto de máximo eclipse y sus circunstancias publicadas (NASA GSFC).
REFERENCE_GREATEST = {
    'lat': 65 + 10.0 / 60, 'lon': -(25 + 14.4 / 60),
    'duration_s': 138.2,            # 2m18.2s
    'utc': '2026-08-12 17:46:01',
    'source': 'nasa_gsfc',
    'tolerance_s': 6.0,             # our lunar-radius convention runs ~2-3% long
    'tolerance_time_s': 30.0,
}

# Circunstancias de ciudades publicadas por el IGN. Las coordenadas son en las que
# evaluamos; la duración publicada depende de en qué punto exacto del municipio te
# pongas, así que la tolerancia es holgada a propósito. La comprobación estricta es
# la ALTURA del Sol.
REFERENCE_CITIES = [
    {'name': 'A Coruña', 'lat': 43.3623, 'lon': -8.4115, 'elev': 20,
     'duration_s': 76, 'sun_alt_deg': 12, 'source': 'ign'},
    {'name': 'Burgos', 'lat': 42.3439, 'lon': -3.6969, 'elev': 860,
     'duration_s': 104, 'sun_alt_deg': 8, 'source': 'ign'},
]

# Publicado por su cuenta para el borde norte de la franja, y es una afirmación que
# cambia decisiones: es lo que hace que la totalidad sea alcanzable desde el área de
# Barcelona.
# Antes citaba al Diari de Tarragona "1 m 02 s". Comprobado el 2026-08-05 abriendo el
# artículo: dice "alrededor de 55 segundos". O sea, la cita no sostenía la cifra, y con
# una tolerancia de 8 s ninguna de las dos versiones hacía saltar el aviso. Se sustituye
# por la ficha oficial del IGN para el municipio, que además trae las coordenadas y la
# altitud exactas a las que están calculadas sus cifras -- compararlas en otro punto
# era otra fuente de error escondida.
REFERENCE_EDGE = [
    {'name': 'Tarragona', 'lat': 41.11910, 'lon': 1.25842, 'elev': 69,
     'duration_s': 59, 'tolerance_s': 8,
     'sun_alt_deg': 4.2, 'sun_az_deg': 286.0, 'tolerance_alt_deg': 0.5,
     'source_label': 'IGN — ficha de Tarragona (totalidad 0 m 59 s, Sol a 4,2°)',
     'source_url': 'https://eclipses.ign.es/src/img/eclipse-26/infografia/'
                   '43148_Tarragona_Tarragona.jpg'},
]

# Barcelona queda fuera de la umbra. Merece un test porque es el dato con más
# papeletas para mandar a alguien al sitio equivocado.
REFERENCE_PARTIAL = [
    {'name': 'Barcelona', 'lat': 41.3874, 'lon': 2.1686, 'elev': 20},
]

# Published umbral width, for a sanity check on our bisected limits.
REFERENCE_PATH_WIDTH_KM = {'value': 294, 'tolerance': 25, 'source': 'nasa_gsfc'}

# ------------------------------------------------- radio lunar umbral calibrado
#
# El radio con el que se calcula la totalidad NO es el radio medio de la Luna. El limbo
# real tiene montañas y valles, y la sombra la define el perfil, no una esfera. Las
# predicciones publicadas usan por eso un radio efectivo algo menor para los contactos
# umbrales.
#
# Aquí no se adopta una constante de fuera —se buscó la de NASA GSFC y su página no
# publica el valor en texto, y una cita que no sostiene su cifra es peor que ninguna—,
# sino que se CALIBRA contra las cifras publicadas que ya están citadas arriba:
# REFERENCE_GREATEST (NASA) y las fichas municipales del IGN (REFERENCE_CITIES y
# REFERENCE_EDGE). O sea, lo calcula el código a partir de datos citados, y hay un test
# que rehace el ajuste y comprueba que el valor publicado aquí sigue siendo el mejor.
#
# Medido el 2026-08-05 con las cuatro referencias (59 s a 138 s de totalidad):
#   1737,4 km (lo que había, sin convenio declarado) -> +3,39 s de media, 4,70 s el peor
#   1736,65 km (k=0,272281, convenio umbral usado por Espenak) -> +1,53 s / 2,45 s
#   1736,0 km (este ajuste) -> -0,08 s de media, 0,59 s el peor
LUNAR_UMBRAL_RADIUS = {
    'km': 1736.0,
    'step_km': 0.2,          # la rejilla con la que se buscó; el test la reusa
    'max_dev_s': 1.0,        # desviación máxima admitida contra las referencias
    'method': ('ajustado a las duraciones publicadas por NASA GSFC y el IGN; '
               'ver tests/test_engine.py::TestLunarRadiusCalibration'),
}

# --------------------------------------------------------------- climatology

# Perspectivas de nubes de agosto a lo largo de la franja española. Están CITADAS, no
# calculadas: hay que mantener la redacción cerca de la fuente y pintar siempre la
# atribución junto a ellas.
CLIMATOLOGY = {
    'source': 'eclipsophile',
    'note': ('Climatología de agosto publicada por Jay Anderson (Eclipsophile). '
             'Son estadísticas de años anteriores, no un pronóstico para el día.'),
    'regions': [
        {'key': 'cantabrico', 'label': 'Costa cantábrica y Galicia',
         'rating': 'malo',
         'text': 'nubosidad media cercana al 60 %, con estratos costeros que entran '
                 'al atardecer'},
        {'key': 'meseta_norte', 'label': 'Meseta norte (León, Burgos, Valladolid, Palencia)',
         'rating': 'bueno',
         'text': '68–78 % de insolación en agosto; eclipse visible 17 de cada 21 años '
                 'según el análisis diario de satélite'},
        {'key': 'soria', 'label': 'Soria y La Rioja',
         'rating': 'bueno',
         'text': 'Soria 73 % de insolación; el Sistema Ibérico sube a 35–45 % de nubosidad'},
        {'key': 'ebro', 'label': 'Valle del Ebro (Zaragoza, Huesca)',
         'rating': 'el mejor',
         'text': 'nubosidad por debajo del 30 %; habría estado despejado 18 de los '
                 'últimos 21 años en esta fecha'},
        {'key': 'iberico_sur', 'label': 'Teruel y Maestrazgo',
         'rating': 'medio',
         'text': '35–45 % de nubosidad, con convección de tarde sobre las sierras'},
        {'key': 'baleares', 'label': 'Baleares',
         'rating': 'bueno',
         'text': 'en torno al 75 % de probabilidad de éxito desde la costa oeste; el '
                 'interior se llena de cúmulos por la tarde'},
    ],
    'low_sun_warning': (
        'Con el Sol tan bajo, la línea de visión atraviesa cientos de kilómetros de '
        'atmósfera hacia el ONO: no basta con que esté despejado sobre tu cabeza, '
        'tiene que estarlo sobre el horizonte. Eclipsophile insiste en que la '
        'movilidad es la mayor ventaja para este eclipse.'),
}

# Los otros dos eclipses sobre España, para dar contexto. Cifras publicadas.
OTHER_ECLIPSES = [
    {'date': '2027-08-02', 'kind': 'total',
     'where': 'Andalucía (Cádiz, Málaga, Granada, Almería) y Ceuta',
     'headline': 'hasta 4 m 48 s en Ceuta, por la mañana y con el Sol alto (~38°)',
     'source': 'ign_2027'},
    {'date': '2028-01-26', 'kind': 'anular',
     'where': 'del suroeste peninsular al noreste',
     'headline': 'anularidad de ~7 m; Sol de 8° en Huelva a 0,4° en Tarragona',
     'source': 'ign_2028'},
]


def cite(key):
    c = CITATIONS[key]
    return f'<a href="{c["url"]}">{c["label"]}</a>'
