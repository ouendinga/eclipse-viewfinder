# Notas de ingeniería

Lo que hay que saber antes de tocar el motor: por qué está montado así y qué fallos
ya se pagaron. Los detalles de cada módulo van en su propio código.

## Qué es
Herramienta que decide **desde dónde ver un eclipse** cruzando la geometría del evento
(efemérides JPL DE421) con el perfil real del terreno (SRTM 30 m). El número que manda
es el **margen libre**: grados entre el Sol y la silueta del terreno en su azimut.

## Regla de oro del repo
**Ninguna cifra inventada.** Cada número o lo calcula el código, o está en
`eclipseview/sources.py` con su cita. En la prosa de los informes no se escribe un
número a mano: se interpola desde los resultados. Si añades una afirmación cuantitativa,
o la calculas o la citas.

## Arquitectura
```
eclipseview/
  ephem.py      geometría del eclipse (contactos, magnitud, obscuración)
  terrain.py    horizonte por trazado de rayos (curvatura + refracción)
  analysis.py   evaluate() / search_area() / zone_stats()  ← el núcleo
  panorama.py   SVG del horizonte + Sol y Luna a escala real
  report.py     informe de lugar (traducible)
  overview.py   informe general de España (solo es, es un ensayo)
  gazetteer.py  origen validado contra OSM; NUNCA texto libre
  coverage.py   qué teselas hacen falta y descarga incremental
  jobs.py       progreso por fases con peso real
  sources.py    datos externos y valores de referencia, con cita
  verify.py     comprobaciones; alimentan tests E informes
  events.py     el evento parametrizado
  rescue.py     cambia un mirador mal comunicado por otro igual de bueno
```

## Trampas que ya costaron caro (no las repitas)
1. **La altura del observador sale del DEM fino**, nunca del mosaico agrupado por
   máximo: en ladera te sitúa sobre la cresta que tienes delante. Hay test.
2. **El campo cercano no se muestrea con el mosaico agrupado**: la celda del propio
   observador fabrica un muro a metros. Los rayos empiezan lejos en la pasada rápida.
3. **La bisección valida el intervalo.** Al revés devolvía el punto medio sin refinar
   e inflaba duraciones hasta 15 s.
4. **`field_build.py` usa `spawn`**: las efemérides van mapeadas en memoria de forma
   perezosa y un hijo por `fork` hereda el mapeo a medias y revienta en jplephem.
5. **La cobertura incluye el corredor hacia el Sol hasta 150 km**, no solo el disco.
   Una tesela que falta se lee como nivel del mar → horizonte tapado que parece limpio.
6. **El radio lunar de los contactos umbrales NO es el medio.** Con 1737,4 km las
   duraciones salían +2,4 a +4,7 s largas. Está calibrado en `sources.py` contra NASA
   e IGN, con tests que rehacen el ajuste. Si tocas el motor y esos tests fallan, el
   problema es el motor, no el valor.
7. **Una cita tiene que sostener su cifra.** Que la URL responda 200 no basta: hay que
   leer si dice lo que decimos que dice. Una cita citaba «1 m 02 s» y el artículo decía
   «alrededor de 55 segundos», y la tolerancia era tan ancha que nunca saltó.
8. **Overpass limita por coste, no por número.** Con menos de cien consultas pesadas ya
   devuelve 429 y «Connection refused». `healthy_endpoints()` devuelve lista vacía si no
   contesta nadie, y los scripts abortan con código 2 en vez de fabricar fallos: una
   comprobación que nunca puede decir «no» no comprueba nada.
9. **El intervalo por defecto de Overpass (6 s) NO sirve para una tanda.** `night.sh`
   exporta `OVERPASS_MIN_INTERVAL=60` y por eso funciona; cualquier script nuevo que
   consulte en lote y se olvide de exportarlo se come un 429 a los ~75 puntos. Pasó
   con `rescue.sh` el 2026-08-06, sabiendo la trampa y sin aplicar la mitigación. Si
   un script hace lotes contra Overpass, lo primero que tiene que llevar es el
   intervalo.
10. **Un criterio que satura deja de desempatar, y no se nota.** El score de `select()`
   recorta el margen en `CLEAR_SATURATION` (8°, quince veces el diámetro del Sol). Por
   encima de ahí, quien decide es la geometría pura — y como el acceso se consulta a
   OSM *después* de seleccionar, la selección no podía preferir un sitio al que se
   llega aunque lo tuviera al lado. Salían 880 de 1.456 puntos con acceso pobre y la
   herramienta parecía funcionar perfectamente. Lo arregla `rescue.py`, sin rehacer la
   selección entera: cambia sólo donde satura Y el acceso es malo, y sólo por
   candidatos que también saturan.
11. **Un punto que se mueve NO se lleva su topónimo.** La celda mide hasta 25 km, así
   que el sustituto puede caer en otro municipio. Heredar el «en el término de X» es
   una mentira que ningún test de geometría puede ver.
12. **Python redondea las mitades a la par y `toFixed` hacia arriba.** Con 99,25 % el
   informe decía 99,2 % y la web 99,3 % del mismo punto. `i18n.number` redondea ahora
   hacia arriba usando el valor binario exacto, que es sobre el que opera el navegador.

## Antes de dar nada por bueno
```bash
.venv/bin/python -m eclipseview check
.venv/bin/python -m unittest discover -s tests -v
```

## Datos
Todo lo pesado en `data/` (ignorado por git): teselas DEM, mosaico, campo del eclipse,
caché del gazetteer. Se reconstruye con `eclipseview setup`.

## Estilo
- **Comentarios en español, código en inglés.** Nombres, cadenas internas y mensajes
  de error del motor, en inglés; la explicación de por qué algo está así, en español.
- Comentarios donde el *porqué* no es obvio, no donde el *qué* ya se lee.
- Números en informes con coma decimal en español, punto en inglés (`i18n.number`).
- Commits por bloque, no un tocho al final.
