# Fuentes

Regla del proyecto: **cada cifra tiene origen computado o cita**. Lo que no es ninguna
de las dos cosas no entra.

## Calculado por este proyecto

Geometría del eclipse (duración, contactos, magnitud, obscuración, altura y azimut del
Sol), perfil del horizonte, margen libre, zona apta, límites y anchura de la franja.

Todo sale de las efemérides y del modelo de elevación. Reproducible: mismo commit y
mismos datos, mismos números.

## Datos externos

| dato | fuente | licencia |
|---|---|---|
| Efemérides planetarias | [JPL DE421](https://ssd.jpl.nasa.gov/planets/eph_export.html) vía Skyfield | dominio público |
| Relieve SRTM 1″ (~30 m) | [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) | dominio público |
| Topónimos y geocodificación | [Nominatim / OpenStreetMap](https://nominatim.openstreetmap.org/) | ODbL |
| Climatología de nubes de agosto | [Eclipsophile — Jay Anderson](https://eclipsophile.com/tse2026/) | citada, no redistribuida |
| Circunstancias publicadas (contraste) | [IGN](https://eclipses.ign.es/eclipse-total-sol-de-12-de-agosto-2026.html), [NASA GSFC](https://eclipse.gsfc.nasa.gov/) | citadas |
| Duración en Tarragona (contraste) | [Diari de Tarragona](https://www.diaridetarragona.com/tarragona/258007/mapa-podras-ver-eclipse-sol-casa-provincia-tarragona.html) | citada |
| Eclipses de 2027 y 2028 | [IGN 2027](https://eclipses.ign.es/eclipse-total-sol-de-2-de-agosto-2027.html), [IGN 2028](https://eclipses.ign.es/eclipse-anular-sol-de-26-de-enero-2028.html) | citadas |

Todo esto vive en `eclipseview/sources.py`, separado del código de cálculo a propósito:
la frontera entre "lo que deduce el programa" y "lo que publicó otro" se ve en el
código, no solo en la prosa. Un test comprueba que cada valor de referencia tiene su
cita y que cada cita tiene URL.

## Uso de Nominatim

Se respeta su política: 1 petición por segundo, `User-Agent` identificable y caché en
disco de todas las respuestas (`data/gazetteer_cache.json`). Para un uso intensivo
habría que montar una instancia propia o pasar a GeoNames.
