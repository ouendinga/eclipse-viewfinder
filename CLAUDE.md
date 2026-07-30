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
