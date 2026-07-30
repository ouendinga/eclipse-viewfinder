# eclipse-viewfinder

**Desde dónde ver un eclipse, teniendo en cuenta el terreno de verdad.**

Los mapas de eclipse te dicen *dónde cae la sombra*. No te dicen si desde ese punto
vas a poder ver el Sol. Cuando el Sol está bajo —y en el eclipse del **12 de agosto
de 2026** sobre España está entre 2° y 12°— el sitio no lo decide el pueblo: lo decide
si tienes una loma a 3 km o una sierra a 80 km delante.

Esta herramienta calcula la geometría del eclipse con efemérides JPL y traza rayos
sobre el modelo de elevación del terreno para responder a la única pregunta que
importa: **¿me va a tapar algo el Sol?**

```
                     Sol a 3,7°
  altura                  ○
    ▲            ·  ·  ·  ╲
    │      ·  ·           ╲  margen = -1,04°  ← el Sol se pone ANTES del máximo
  0°┤▁▁▁▁▂▄▆███████████████▆▄▂▁▁   ← perfil real del terreno hacia el ONO
    └────────────────────────────▶ azimut
```

## Qué hace

Dos informes, el mismo motor:

| | |
|---|---|
| **`overview`** | Análisis de toda la franja de totalidad sobre España: dónde ir, qué perdona cada zona, dónde están las trampas. |
| **`place`** | Le das un pueblo y un radio, y te saca los mejores miradores de esa zona, con la silueta real del horizonte y la trayectoria del Sol dibujada encima. |

En cada panorama el Sol y la Luna van **a tamaño y posición angulares reales**: el
creciente que ves en el gráfico es el que verías con los ojos.

## Uso

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. buscar el sitio (siempre eliges de una lista, nunca texto libre)
.venv/bin/python -m eclipseview places "Malgrat de Mar"

# 2. los mejores miradores a 45 km
.venv/bin/python -m eclipseview place "Malgrat de Mar" --pick 1 -r 45

# añadiendo puntos tuyos
.venv/bin/python -m eclipseview place "Soria" --pick 1 -r 60 \
    --also "41.6459,2.7414,el pueblo" \
    --peak "41.7767,2.4272,Turó de l'Home"

# el informe general de España
.venv/bin/python -m eclipseview overview

# ¿tengo datos para esta zona?
.venv/bin/python -m eclipseview coverage "Lisboa" -r 40 --fetch

# ¿me puedo fiar del motor?
.venv/bin/python -m eclipseview check
```

- `--also "lat,lon,nombre"` incluye ese punto exacto.
- `--peak "lat,lon,nombre"` igual, pero lo ajusta a la cima real más cercana: los
  geocodificadores fallan con las cumbres (buscando "Turó de l'Home" salen **cuatro**
  candidatos y el bueno es el segundo).
- `--min-clear` margen mínimo exigido. Por debajo de 1,5° no me fiaría: el modelo de
  elevación no sabe de árboles, naves ni casas.
- `--lang es|en`, `--progress-json fichero.ndjson` para consumir el progreso desde un
  frontend.

## Los números que da

- **margen libre** — grados entre el Sol y el terreno real durante el evento. Es el
  número que decide. Negativo = el Sol se pone detrás del monte antes de tiempo.
- **zona apta** — qué porcentaje del entorno mantiene margen suficiente. Distingue un
  buen sitio de un píxel con suerte, y es lo que más reordena los rankings ingenuos.
- **obscuración** — fracción del **área** del disco solar tapada, que es la que se
  corresponde con cuánto oscurece (no confundir con la magnitud, que es de diámetros).

## Cómo sé que no me lo estoy inventando

`eclipseview check` compara el motor con valores publicados y con cálculos analíticos,
**cada vez**, y el informe incluye esa tabla recién calculada:

| comprobación | calculado | publicado | fuente |
|---|---|---|---|
| Máximo eclipse: duración | 141,3 s | 138,2 s | NASA GSFC |
| Máximo eclipse: instante | 17:46:03 | 17:46:01 UTC | NASA GSFC |
| A Coruña: duración / altura | 79,4 s / 12,0° | 76 s / 12° | IGN |
| Burgos: duración / altura | 106,4 s / 8,3° | 104 s / 8° | IGN |
| Tarragona: duración | 64,2 s | 62 s | Diari de Tarragona |
| Barcelona: ¿totalidad? | no | no | IGN |
| Horizonte marino (cabo Vilán) | −0,127° | −0,127° | analítico |
| Moncayo desde Zaragoza | +1,16° a 79 km | +1,20° a 80 km | cálculo a mano |
| Anchura de la sombra | 300 km | 294 km | NASA GSFC |

**Sesgo conocido y documentado:** las duraciones salen un 2–3 % largas frente al IGN
por el convenio de radio lunar. Cuéntalas como ±3 s; para horarios oficiales, el IGN.
Hay un test que vigila que ese sesgo siga siendo pequeño y positivo.

```bash
.venv/bin/python -m unittest discover -s tests -v     # 24 tests
```

## Datos

Se descargan solos y solo los que falten. Una consulta necesita elevación **no solo
bajo el punto**, sino en todo el corredor hacia el Sol hasta 150 km: con el Sol a 4°,
una sierra a 80 km te tapa. `coverage` calcula ese corredor, dice cuántas teselas
faltan y cuántos MB son, y `--fetch` las baja.

- Relieve: SRTM 1″ (~30 m) vía [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/)
- Efemérides: [JPL DE421](https://ssd.jpl.nasa.gov/planets/eph_export.html) vía Skyfield
- Topónimos: [Nominatim / OpenStreetMap](https://nominatim.openstreetmap.org/)
- Climatología de nubes: [Eclipsophile, Jay Anderson](https://eclipsophile.com/tse2026/)
  — el único dato del informe que **no** calculo yo, y va siempre citado

Nada de esto se guarda en el repo: `data/` está en `.gitignore`.

## Estado

Funciona de punta a punta para el eclipse del **12 de agosto de 2026** sobre España,
en español e inglés. El motor ya está parametrizado por evento (`events.py`), pero
solo este tiene datos precalculados.

Lo que viene, en [docs/roadmap.md](docs/roadmap.md): frontend web con el progreso ya
instrumentado, precarga de los mejores sitios, y el resto de eclipses y regiones.

## Documentación

- [docs/metodologia.md](docs/metodologia.md) — cómo se calcula, y por qué así
- [docs/verificacion.md](docs/verificacion.md) — contra qué se contrasta
- [docs/fuentes.md](docs/fuentes.md) — de dónde sale cada dato
- [docs/roadmap.md](docs/roadmap.md) — qué falta
- [CLAUDE.md](CLAUDE.md) — contexto para trabajar en el repo

## Licencia

MIT. Los datos de origen tienen sus propias licencias (OpenStreetMap ODbL, SRTM
dominio público).
