# CLAUDE.md — eclipse-viewfinder

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

## Antes de dar nada por bueno
```bash
.venv/bin/python -m eclipseview check
.venv/bin/python -m unittest discover -s tests -v
```

## Datos
Todo lo pesado en `data/` (ignorado por git): teselas DEM, mosaico, campo del eclipse,
caché del gazetteer. Se reconstruye con `eclipseview setup`.

## Estilo
- Comentarios donde el *porqué* no es obvio, no donde el *qué* ya se lee.
- Números en informes con coma decimal en español, punto en inglés (`i18n.number`).
- Commits por bloque, no un tocho al final.
