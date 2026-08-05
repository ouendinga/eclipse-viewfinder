# Roadmap

## Hecho

- Motor de eclipse (DE421) y de horizonte (SRTM 30 m), verificados contra NASA, IGN y
  cálculo analítico.
- Informe general de España e informe parametrizado por lugar y radio.
- Origen validado contra gazetteer, nunca texto libre.
- Cobertura incremental: calcula qué teselas faltan (incluido el corredor de visuales)
  y baja solo esas.
- Progreso por fases con peso real y ETA, volcable a NDJSON para un frontend.
- i18n es/en del informe de lugar.

## Siguiente

1. **Frontend web.** La capa de progreso ya está instrumentada (`jobs.py`,
   `--progress-json`). Falta el servidor y la interfaz.
2. **Precarga de los mejores sitios.** Generar por adelantado los informes de las
   poblaciones más probables para que la respuesta sea instantánea, y dejar el cálculo
   en vivo solo para lo que no esté cacheado.
3. **Caché de resultados por celda** en vez de por consulta, para que dos pueblos
   vecinos reaprovechen trabajo.


## Pendiente: mejorar la visión (lo que ve el usuario)

Lo calculado está bien; lo que falla es cómo se presenta y qué falta comprobar.

- [ ] **402 puntos (28 %) sin chequear contra árboles y edificios.** Overpass falló en
      esos durante la pasada. Es reanudable (`./enrich.sh`, ~10 min) y la caché conserva
      lo hecho. Mientras tanto se marcan «sin comprobar», nunca «limpio».
- [ ] **Alturas de arbolado estimadas** (18 m de pinar maduro): OSM casi nunca las trae.
      Van marcadas como estimación. Mejorable con datos de altura de dosel si aparecen.
- [ ] **Topónimos pobres** en unos pocos puntos («España» a secas): bajar el zoom de la
      geocodificación inversa y reintentar solo esos.
- [ ] **Ordenación en el borde de la sombra.** Una totalidad de 6 s se lista por delante
      de un parcial del 99,4 % con mejor margen. Se avisa en el texto, pero conviene
      revisar si el orden debería penalizar las duraciones bajo ~30 s, donde el error
      del cálculo y el perfil del limbo lunar pesan mucho.
- [ ] **Perfil real del limbo lunar**: mueve los contactos algunos segundos, y justo en
      el borde de la franja es lo que decide entre 6 s y nada.
- [ ] **Analítica**: sin decidir (nada / solo visitas / visitas + localidades buscadas).

### Hecho en esta ronda
- La ficha identifica un **punto con coordenadas**, no un municipio: el nombre del
  pueblo indujo a pensar que la recomendación era «ve a ese pueblo», cuando ir al
  centro puede tener el horizonte tapado.
- Enlace **«Cómo llegar»** que abre la navegación al punto exacto, más «ver en el mapa»,
  OpenStreetMap y Street View apuntando al azimut del Sol.
- Aviso de que son puntos del terreno: hay que comprobar acceso y finca privada.

## Objetivo total

**Cualquier eclipse, en cualquier parte del mundo, en varios idiomas.**

Lo que ya está preparado:

- `events.py` parametriza el evento; el motor no tiene la fecha metida a fuego.
- `coverage.py` sabe descargar elevación de cualquier parte del mundo.
- `gazetteer.py` funciona con cualquier país.
- `i18n.py` tiene la infraestructura y detecta traducciones incompletas.

Lo que falta para llegar:

- **Campo del eclipse por evento.** Hoy `field.pkl` cubre una región y un eclipse.
  Hay que generarlo por evento y region, y cachearlo.
- **Encontrar la franja automáticamente** dado un evento, en vez de partir de una
  región conocida.
- **Zonas horarias reales** en vez de un desplazamiento fijo por evento.
- **El informe general está en español y habla de España.** El de lugar ya es
  traducible; el general habría que generalizarlo o dejarlo como pieza por región.
- Climatología de nubes fuera de España (hoy solo hay datos citados para este eclipse).
