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
