# Verificación

El motor se contrasta **en cada ejecución**, no una vez y a fiarse. `eclipseview check`
y el informe general muestran la misma tabla, recién calculada.

```bash
.venv/bin/python -m eclipseview check
.venv/bin/python -m unittest discover -s tests -v
```

## Contra qué se contrasta

**Valores publicados**

| qué | fuente |
|---|---|
| Punto de máximo eclipse: duración e instante | NASA GSFC |
| A Coruña y Burgos: duración y altura del Sol | IGN |
| Tarragona: duración en el borde de la franja | Diari de Tarragona |
| Barcelona: debe quedar **fuera** de la totalidad | IGN |
| Anchura de la sombra sobre España | NASA GSFC |

**Verdad analítica** (no depende de que nadie haya publicado nada)

- *Horizonte marino*: mirando al Atlántico abierto desde el cabo Vilán, el resultado
  debe ser exactamente la depresión teórica del horizonte,
  `−√(2h(1−k)/R)`. Ejercita curvatura, refracción y campo cercano a la vez: no hay
  terreno donde esconder un error.
- *Cumbre conocida*: desde Zaragoza, el horizonte al ONO es el Moncayo. Se compara
  con el cálculo a mano usando la altitud publicada de la cumbre.
- *Fórmula de obscuración*: casos con forma cerrada (discos concéntricos, sin solape,
  anular) y monotonía respecto a la separación.

## Regresiones vigiladas

Cada uno de estos tests existe porque el fallo **ocurrió de verdad** durante el
desarrollo:

1. **Bisección de C3 con el intervalo al revés.** Devolvía el punto medio del muestreo
   grueso sin refinar, inflando las duraciones hasta 15 s. Se detectó contrastando con
   la NASA. Ahora la bisección valida que el intervalo contiene un cambio de signo y
   revienta si no.
2. **Altura del observador tomada del mosaico agrupado por máximo.** En ladera te
   sitúa sobre la cresta que tienes delante; un sitio pasó de "apto" a −13,2° al
   recomprobarlo a 30 m. Hay un test que inspecciona el código de `search_area` para
   asegurar que usa el DEM fino.
3. **Corredor de visuales.** Si el conjunto de teselas solo cubriera el disco de
   búsqueda, las que faltan se leerían como nivel del mar y un horizonte tapado
   parecería despejado. Un test comprueba que se piden teselas muy al oeste.
4. **Sesgo de duración.** Un test asegura que sigue siendo pequeño (<5 %) y positivo,
   para que una regresión que lo invierta o lo dispare se vea.
5. **El limbo lunar no puede colarse en la cifra que se publica.** Un test comprueba
   que `circumstances(use_limb=False)` sigue siendo el defecto: el IGN y la NASA
   publican con limbo medio y la gente contrasta con ellos.
6. **«100,0% parcial».** 97 de los 1.456 puntos tienen entre 99,951 % y 99,999 % del
   disco oculto, y redondeados a una decimal se pintaban como `100,0% parcial`, que
   leído en frío es una contradicción justo en los puntos del filo. Ahora, y sólo
   cuando el redondeo satura, se trunca hacia abajo. El test **ejecuta el JS que se
   publica** con `node`, no una copia en Python: una reimplementación aprobaría
   aunque el navegador hiciera otra cosa.

## Lo que sí se comprueba ya (y antes no)

- **El perfil real del limbo lunar** (`limb.py`): topografía LOLA/LRO más la libración
  del día, sacada de los núcleos NAIF. No manda sobre la cifra publicada —es la
  segunda opinión— pero decide el aviso del filo. Contrastado por tres vías: la
  amplitud de la libración cuadra con la publicada, invertir el convenio de signos da
  el mismo resultado, y el radio medio del borde cae sobre la esfera calibrada.
- **Árboles y edificios**: los 1.456 puntos publicados están comprobados contra
  OpenStreetMap, y el margen que manda es el neto.

## Lo que NO está verificado

- El relieve de base es SRTM a 30 m: la silueta lejana no lleva vegetación. Los
  árboles y edificios se añaden aparte, desde OSM, y sólo donde OSM los tiene.
- Las **alturas** de arbolado casi nunca vienen en OSM: se estiman.
- La refracción cerca del horizonte varía con la temperatura; puede mover el terreno
  lejano una o dos décimas de grado.
- El limbo está medido a unos 2 km de resolución: en el borde de la sombra eso son
  segundos, y no hay ninguna referencia publicada con limbo corregido contra la que
  validarlo.
- La climatología de nubes es estadística publicada, **no un pronóstico**. El
  pronóstico en vivo (Open-Meteo) es otra cosa y se marca como tal.
- **Nadie ha ido a un punto a mirarlo.** Es lo único que ningún modelo cierra.
