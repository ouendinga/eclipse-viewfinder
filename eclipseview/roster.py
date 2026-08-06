# -*- coding: utf-8 -*-
"""Los sitios que salen en el informe general.

Aquí sólo viven coordenadas y texto editorial *cualitativo*. Cada número del informe
se calcula al pintarlo a partir de estas coordenadas, así que la lista no puede
desincronizarse de las cifras que salen a su lado.

Las coordenadas las eligió la propia cadena de proceso (barrido -> robustez ->
refinado) y no un dedo sobre el mapa: cada una es el mejor sitio encontrado en su
zona.
"""

TIERS = [
    dict(key='sensata', eyebrow='Recomendación principal',
         title='La apuesta sensata: la meseta',
         intro='Palencia y Soria juntan las tres cosas a la vez: están sobre la línea '
               'central, el Sol todavía está lo bastante alto para que la corona no se '
               'coma la bruma y, sobre todo, el horizonte al ONO es bajo en casi toda '
               'la comarca, no solo en un punto afortunado.'),
    dict(key='clima', eyebrow='Si lo que te preocupa son las nubes',
         title='El valle del Ebro',
         intro='La mejor climatología de toda la franja, a cambio de perder segundos '
               'de totalidad y algo de altura del Sol, porque la línea central pasa '
               'bastante al sur.'),
    dict(key='cerca', eyebrow='El extremo oriental de la franja',
         title='Lo más cerca del Mediterráneo que funciona',
         intro='La franja roza el sur de Catalunya: es lo único que da totalidad sin '
               'alejarse del Mediterráneo. El problema es que casi todo el sur de '
               'Catalunya mira al ONO contra montaña, con una excepción clara.'),
    dict(key='techo', eyebrow='La mejor vista posible — y la más arriesgada',
         title='La costa de Asturias',
         intro='Geométricamente no hay nada mejor en España: la línea central toca el '
               'mar justo aquí, con la totalidad más larga, el Sol más alto y un '
               'horizonte marino. Y es también la zona con peor pronóstico de nubes.'),
    dict(key='trampa', eyebrow='Lo que parece buena idea y no lo es',
         title='Dos trampas',
         intro='Los dos destinos que más aparecen en las listas de "dónde ver el '
               'eclipse" y que, mirando el terreno, no aguantan el análisis.'),
]

SITES = [
    dict(key='palencia', tier='sensata', hero=True,
         label='Meseta de Boedo (Palencia)',
         lat=42.5370, lon=-4.3366, zone=(42.51, -4.30, 9.0),
         role='De todas las comarcas que analicé, es la más a prueba de errores: '
              'aquí no necesitas acertar con la piedra exacta.'),
    dict(key='aguilar', tier='sensata',
         label='Aguilar de Campoo (Palencia / Burgos)',
         lat=42.6995, lon=-4.1933, zone=(42.74, -4.23, 9.0),
         role='Un poco más al norte y algo más alto, con el mejor margen de la meseta. '
              'A cambio, sube el riesgo de nubes de evolución diurna por la cercanía '
              'de la cordillera Cantábrica.'),
    dict(key='soria_n', tier='sensata',
         label='Golmayo / alto Duero (Soria)',
         lat=41.6760, lon=-2.7003, zone=(41.73, -2.61, 9.0),
         role='La opción de compromiso si no quieres cruzar media España: bastante '
              'más cerca del Mediterráneo y casi el mismo margen.'),
    dict(key='soria_c', tier='sensata',
         label='Tardelcuende / Matamala (Soria)',
         lat=41.5674, lon=-2.5840, zone=(41.50, -2.62, 9.0),
         role='Prácticamente sobre la línea central, en terreno igual de indulgente.'),
    dict(key='ebro', tier='clima',
         label='Jaulín / muelas del Ebro (Zaragoza)',
         lat=41.4140, lon=-0.9302, zone=(41.45, -1.05, 12.0),
         role='Ojo: Zaragoza capital y el fondo de los barrancos no sirven. Hay que '
              'salir a las plataformas y muelas del sur.'),
    dict(key='delta', tier='cerca',
         label="Delta de l'Ebre (Riumar)",
         lat=40.7250, lon=0.8600, zone=(40.72, 0.78, 9.0),
         role='El delta es la respuesta, y precisamente porque es plano: no hay nada '
              'que levante el horizonte, así que el margen aguanta en toda la zona.'),
    dict(key='tarragona', tier='cerca',
         label='Tarragona capital',
         lat=41.1190, lon=1.2450, zone=(41.15, 1.10, 10.0),
         role='Entra en la totalidad, pero muy cerca del borde de la sombra: la corona '
              'se ve poco tiempo y asimétrica. Si el plan es no conducir, sirve.'),
    dict(key='busto', tier='techo', hero=True,
         label='Cabo Busto (Luarca, Asturias)',
         lat=43.5680, lon=-6.4790, zone=(43.545, -6.52, 7.0),
         role='El techo de lo alcanzable en España. Pero la costa se dobla y en muchos '
              'tramos acabas mirando al ONO contra tierra: aquí hay que ir al cabo '
              'correcto, no a la playa más próxima.'),
    dict(key='penisc', tier='trampa', warn=True,
         label='Peñíscola (Castellón)',
         lat=40.3585, lon=0.4065, zone=(40.38, 0.39, 9.0),
         role='Sale en todas las listas porque la línea central pasa muy cerca. '
              'Mirando al ONO desde el casco antiguo tienes el Maestrat delante, y en '
              'la playa mirarías al Sol contra la sierra: el Mediterráneo queda a tu '
              'espalda.'),
    dict(key='mallorca', tier='trampa', warn=True,
         label='Serra de Tramuntana (Mallorca)',
         lat=39.7405, lon=2.6651, zone=(39.70, 2.56, 9.0),
         role='Buena climatología y totalidad, pero la Tramuntana tapa justo el ONO en '
              'casi toda la isla. Este punto funciona solo porque estás muy alto y '
              'miras por encima de todo hacia el mar.'),
]

# Los sitios de la escalera «qué te da cada hora de coche», del más cercano al más
# lejano.
LADDER = ['tarragona', 'delta', 'ebro', 'soria_n', 'palencia', 'busto']

# Origen de referencia para la columna de distancias del informe general.
LADDER_ORIGIN = dict(name='Barcelona', lat=41.3874, lon=2.1686)
