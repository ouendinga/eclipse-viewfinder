# Metodología

Cómo se calcula cada número, y por qué está hecho así. Las decisiones que parecen
detalles menores son justo las que hacen que el resultado sea correcto o basura.

## 1. Geometría del eclipse

Posición topocéntrica **aparente** del Sol y de la Luna con efemérides JPL DE421
(Skyfield), para el observador exacto (lat, lon, altitud).

- **Totalidad** mientras `separación < radio_luna − radio_sol`.
- **Contactos** (C2, C3) por bisección sobre esa función, con tolerancia de 0,02 s.
- **Magnitud** = fracción del *diámetro* solar tapada.
- **Obscuración** = fracción del *área* del disco tapada, por la fórmula de
  intersección de dos círculos. Es la que se corresponde con cuánto oscurece.

  Ojo con una intuición falsa: la obscuración **no** siempre es menor que la magnitud.
  Justo fuera del límite de la sombra la Luna es angularmente mayor que el Sol, y el
  área tapada va por delante del diámetro tapado. En Malgrat: magnitud 0,992,
  obscuración 0,9943.

- **Refracción**: se ignora para los contactos (desplaza al Sol y a la Luna casi
  igual a la misma altura) y se aplica a la altura/azimut que se reportan, que es lo
  que de verdad ves.

### Sesgo conocido

Las duraciones salen un **2–3 % largas** frente al IGN. La causa es el convenio de
radio lunar: la condición umbral depende de `r_luna − r_sol`, una resta de dos
números casi iguales, así que un 0,08 % en el radio lunar mueve la duración un 4 %.
No se "ajusta" el radio para cuadrar con tres puntos de referencia ruidosos: se
documenta el sesgo, se acota (±3 s) y hay un test que vigila que siga siendo pequeño
y positivo.

Las **alturas del Sol** no tienen ese problema y coinciden exactamente con el IGN.

## 2. Horizonte real

Desde cada punto se trazan rayos hacia el azimut del Sol y se busca el ángulo aparente
máximo del terreno:

```
ángulo = atan2( h_objetivo − h_observador − caída,  d )
caída  = d² (1 − k) / (2R)      R = 6.371.000 m,  k = 0,13
```

`k` es el coeficiente estándar de refracción terrestre; levanta ligeramente el terreno
lejano. El resultado es directamente comparable con la altura **refractada** del Sol,
porque ambos están en las mismas coordenadas.

Muestreo: cada 180 m hasta 25 km (nunca más que el tamaño de celda, para no saltarse
una cresta) y cada 500–800 m hasta 150 km.

### Dos resoluciones, a propósito

| | resolución | por qué |
|---|---|---|
| **Ordenar** miles de puntos | mosaico agrupado a ~185 m tomando el **máximo** de cada celda | conservador con las crestas: si hay un filo, no quiero promediarlo |
| **Confirmar** los finalistas | SRTM 1″ (~30 m) con interpolación bilineal | el máximo agrupado exagera; los ganadores hay que verlos de verdad |

Dos errores reales que salieron de aquí y que el código ahora evita:

1. **La altura del observador debe venir del DEM fino.** Si se toma del mosaico
   agrupado por máximo, en una ladera el cálculo cree que estás encima de la cresta
   que en realidad tienes delante. Un sitio pasó de "apto" a **−13,2°** al
   recomprobarlo. Hay un test que lo vigila.
2. **El campo cercano no se muestrea con el mosaico agrupado.** La propia celda del
   observador contiene el punto más alto de sus 185 m, lo que fabrica un muro a
   metros de ti (daba +7,6° falsos en el cabo Vilán). Los rayos empiezan a 400 m en
   la pasada rápida, y a 60 m con datos finos en la definitiva.

## 3. Margen libre

```
margen = altura aparente del Sol − altura aparente del terreno en ESE azimut
```

Evaluado en C2, máximo y C3, y se toma **el peor**: el Sol tiene que estar despejado
durante todo el evento, y va bajando mientras tanto.

Se exige un mínimo (1,5° por defecto) porque el modelo de elevación **no ve árboles,
edificios ni naves industriales**. Un margen de +0,7° es 1,4 veces el diámetro del
Sol: cualquier pino lo tapa.

## 4. Zona apta

Para cada sitio se reevalúa una malla de 13×13 a 30 m alrededor y se mide qué
porcentaje del entorno mantiene más de 2° de margen.

Es la métrica que más reordena los resultados: la costa asturiana tiene el mejor
margen de España (+10,7°) pero solo un 65 % de zona apta, porque la costa se dobla y
en muchos tramos acabas mirando al ONO contra tierra. La meseta de Palencia da +8,5°
con un **99,4 %** de zona apta: no necesitas acertar con la piedra exacta.

## 5. Cobertura de datos

Analizar un punto no necesita elevación solo debajo: los rayos van hasta 150 km hacia
el Sol. El conjunto de teselas necesario es el disco de búsqueda **barrido** a lo
largo del azimut solar. Equivocarse aquí es silencioso y peligroso: una tesela que
falta se lee como nivel del mar, y convertiría un horizonte tapado en uno despejado.

Las teselas que devuelven 404 son océano y se registran como tal, para no reintentarlas
ni confundirlas con un hueco.

## 6. Origen validado

El usuario **nunca escribe texto libre que se convierta en una coordenada**. Elige de
una lista de poblaciones o accidentes geográficos reales, cada uno con su
identificador OSM, su jerarquía administrativa y su población. Si no hay
coincidencias, falla con un error, no con un punto inventado.
