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
- [x] **Perfil real del limbo lunar**: hecho (`limb.py`, LOLA + NAIF). Es la segunda
      opinión, no el titular — ver `decisions.md` 2026-08-06.
- [ ] **Desempate cuando el margen satura.** En el oeste el **63 %** de los puntos tiene
      el margen por encima del tope de 8° de la puntuación de `select()`, así que ese
      criterio deja de distinguir y decide la geometría pura: por eso los puntos salen
      en cuadrícula en la meseta. Podría estar eligiendo un punto sin acceso teniendo
      uno igual de bueno con carretera al lado. **Cambia qué puntos se publican**: obliga
      a rehacer la selección (~40 min de horizontes) y a volver a pasar OSM por los
      puntos nuevos (una tanda de madrugada).
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


## Estado al 2026-08-06

**En producción**: https://eclipse.alvarosolis.dev — 1.456 miradores, con el perfil
real del limbo lunar publicado y el aviso del filo visible en la ficha.

Lo que cambió de fondo:

- **El acceso ya no es sólo un dato que se enseña: puede cambiar qué punto se
  recomienda.** La puntuación de `select()` recorta el margen en 8°, y por encima de
  ese tope deja de desempatar. En el 27 % de los puntos satura, y como el acceso se
  consultaba *después* de seleccionar, la selección no podía preferir un sitio al que
  se llega. Resultado medido: 880 de 1.456 puntos con acceso pobre. `rescue.py` los
  cambia por alternativas de su misma celda que también saturen, así que no se paga
  calidad por comodidad.
- **Tres familias de tests nuevas**: el rescate (que sólo pueda mejorar), la calidad
  del dataset publicado (coherencia interna) y lo que se presenta (ejecutando con
  `node` el JavaScript que se publica sobre los 1.456 puntos de verdad).
- Esos tests encontraron tres defectos que nadie miraba: seis parciales guardados con
  el 100,0 % tapado, 57 totalidades que decían «de 20:28 a 20:28» (una de 58 s), y una
  discrepancia de redondeo entre el informe y la web en las mitades exactas.

## Estado al cerrar la sesión del 2026-08-05

**En producción**: https://eclipse.alvarosolis.dev — 1.457 miradores, 28 tests verdes.

Lo que quedó a medias de la sesión anterior está cerrado: el chequeo de accesibilidad
terminó (875/1.457), y el sitio se reconstruyó, así que el perfil de acceso y las
secciones «Aviso» y «Fuentes» **ya se ven en pantalla** por primera vez.

## A dónde va esto (idea de 2026-08-06)

**De «un eclipse» a «eventos astronómicos: dónde y cómo verlos», y que la web se
entere sola.** El motor de aquí no sabe de eclipses: sabe decir si desde un punto
concreto vas a poder ver algo que está en una dirección y a una altura del cielo. Eso
vale igual para una lluvia de meteoros o para un eclipse de Luna.

Ejemplos del tipo de evento que tendría que entrar solo:

| cuándo | qué |
|---|---|
| agosto | impacto en la Luna de una etapa superior de un Falcon 9 |
| 12-13 agosto | pico de las Perseidas, con Luna nueva |
| 27-28 agosto | eclipse lunar parcial profundo |

> Las fechas y las cifras de arriba vienen de una conversación, **no de una fuente**.
> Antes de que ninguna llegue a la web hay que pasarlas por la regla del repo: o la
> calcula el código, o está en `sources.py` con su cita.

Lo que cambia respecto a hoy, por orden de dificultad:

1. **El evento deja de ser una fecha con un campo precalculado.** `events.py` ya
   parametriza, pero cada evento necesita su campo (`field.pkl`) y su región. Para una
   lluvia de meteoros no hay franja de totalidad: lo que importa es el radiante, su
   altura a lo largo de la noche y la fase de la Luna.
2. **Qué se pregunta cambia con el evento.** Un eclipse solar pregunta por el margen
   sobre el horizonte en un azimut. Las Perseidas preguntan por cielo oscuro y
   despejado en general, así que entra la contaminación lumínica, que hoy no se usa.
   Un eclipse lunar se ve desde medio planeta y casi no depende del sitio.
3. **Mantenerse al día solo.** Un catálogo de efemérides del que tirar (los eclipses
   se pueden *calcular* con DE421 sin depender de nadie; las lluvias de meteoros son
   tabulares y estables; un impacto lunar de un cohete es una noticia y necesita
   fuente). Lo automático es fácil de hacer y difícil de hacer **sin publicar una
   cifra sin comprobar**, que es justo lo que este proyecto no se puede permitir.
4. **El sitio pasa a tener varias páginas** y un índice por evento, en vez de una sola
   página con un eclipse dentro.

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
