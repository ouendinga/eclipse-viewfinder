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

- [ ] **582 puntos sin perfil de accesibilidad.** `./access.sh` completó 875 de 1.457;
      en el resto Overpass no contestó. Reanudable: la caché guarda los aciertos, así
      que una segunda pasada sólo reintenta los fallos. Se marcan «sin comprobar».
- [ ] **Puntos sin chequear contra árboles y edificios**: `./enrich.sh` los completa.
      Overpass se satura y va a rachas; es reanudable y la caché conserva lo hecho.
- [ ] **Alturas de arbolado estimadas** (18 m de pinar maduro): OSM casi nunca las trae.
      Van marcadas como estimación. Mejorable con datos de altura de dosel si aparecen.
- [ ] **Ordenación en el borde de la sombra.** Una totalidad de 6 s se lista por delante
      de un parcial del 99,4 % con mejor margen. Se avisa en el texto, pero conviene
      revisar si el orden debería penalizar las duraciones bajo ~30 s, donde el error
      del cálculo y el perfil del limbo lunar pesan mucho.
- [ ] **Perfil real del limbo lunar**: mueve los contactos algunos segundos, y justo en
      el borde de la franja es lo que decide entre 6 s y nada.
- [x] **`Sa Cuina del Bisbe` (39,16/2,92)**: confirmado que es tierra. Tiene una pista
      (`track`, firme de tierra) a 1.135 m, así que es un islote con acceso a pie, no un
      bajo submarino. Se queda.

### Hecho en esta ronda (2026-08-05, tarde)
- **Puntos en el mar fuera.** 12 de los 1.469 publicados no estaban en tierra: sobre el
  mar SRTM vale 0, el horizonte sale impecable y escalaban a lo más alto del ranking.
  Filtro en `recommend.drop_offshore`, con segunda consulta al zoom 16 antes de
  descartar — que salvó 14 puntos de costa de verdad, entre ellos Gorliz y el Monte de
  Arnela (Fisterra). **Topónimos pobres resueltos de paso**: quedan 4.
- **Índice de apartados** en el margen derecho (`minimap.py`), con el lenguaje visual de
  los panoramas: eje, marcas y el Sol como círculo.
- **Distancias relativas al lector**: «km desde Vigo» en vez de «km desde Barcelona»,
  recalculadas por el buscador. Y fuera el sesgo de origen de la prosa.
- **Secciones «Aviso» y «Fuentes»** desplegadas por fin, con la cita corregida (Overpass,
  no Nominatim, para árboles/edificios/vías) y sin la sección duplicada.
- **Analítica**: Vercel Web Analytics puesta. Ver `pending-human.md` para lo que queda.

### Hecho en esta ronda
- La ficha identifica un **punto con coordenadas**, no un municipio: el nombre del
  pueblo indujo a pensar que la recomendación era «ve a ese pueblo», cuando ir al
  centro puede tener el horizonte tapado.
- Enlace **«Cómo llegar»** que abre la navegación al punto exacto, más «ver en el mapa»,
  OpenStreetMap y Street View apuntando al azimut del Sol.
- Aviso de que son puntos del terreno: hay que comprobar acceso y finca privada.


## Estado al cerrar la sesión del 2026-08-05

**En producción**: https://eclipse.alvarosolis.dev — 1.457 miradores, 28 tests verdes.

Lo que quedó a medias de la sesión anterior está cerrado: el chequeo de accesibilidad
terminó (875/1.457), y el sitio se reconstruyó, así que el perfil de acceso y las
secciones «Aviso» y «Fuentes» **ya se ven en pantalla** por primera vez.

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
