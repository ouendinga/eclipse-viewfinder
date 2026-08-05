#!/usr/bin/env bash
# Completa lo que falta de OpenStreetMap de madrugada, muy despacio.
#
# Por qué de madrugada y despacio: Overpass es un servicio público y gratuito, y
# limita por COSTE de consulta, no por número. Nuestras consultas son uniones de
# decenas de corredores, así que con menos de cien peticiones ya nos devolvió
# "429 Too Many Requests" y "Connection refused" (2026-08-05). El trabajo pendiente
# son ~16 peticiones de árboles y ~39 de accesibilidad: a una por minuto es menos de
# una hora, que de madrugada no le molesta a nadie.
#
# Uso:  ./night.sh            (una pasada)
#       OVERPASS_MIN_INTERVAL=90 ./night.sh
# Programarlo:  ./night.sh --programar 03:30
set -uo pipefail
cd "$(dirname "$0")"

export OVERPASS_MIN_INTERVAL="${OVERPASS_MIN_INTERVAL:-60}"
LOG="${LOG:-$PWD/reports/night-$(date +%Y%m%d-%H%M).log}"

MARCA="# eclipse-viewfinder-night"

if [ "${1:-}" = "--programar" ]; then
  # cron y no 'at' porque atd no está instalado. Una entrada diaria es inofensiva
  # porque el script sale solo cuando no queda nada pendiente (ver abajo).
  MIN="${3:-30}"; HORA="${2:-3}"
  ( crontab -l 2>/dev/null | grep -v "$MARCA";
    echo "$MIN $HORA * * * cd $PWD && ./night.sh $MARCA" ) | crontab -
  echo "programado a las $HORA:$MIN cada día. Entradas actuales:"; crontab -l
  echo "para quitarlo:  ./night.sh --desprogramar"
  exit 0
fi

if [ "${1:-}" = "--desprogramar" ]; then
  crontab -l 2>/dev/null | grep -v "$MARCA" | crontab -
  echo "quitado. Entradas actuales:"; crontab -l
  exit 0
fi

# Nada que hacer: se sale sin molestar a Overpass. Esto es lo que permite dejar una
# entrada diaria en cron y olvidarse: el día que esté todo completo, no hace nada.
PEND=$(.venv/bin/python - <<'PY'
import json, os
from eclipseview.paths import DATA_DIR
P = json.load(open(os.path.join(DATA_DIR, 'points.json')))['points']
print(sum(1 for p in P if not p.get('obs_ok')) + sum(1 for p in P if not p.get('acc_ok')))
PY
)
if [ "${PEND:-0}" -eq 0 ]; then
  echo "$(date '+%F %T') nada pendiente, no se consulta nada."
  exit 0
fi

mkdir -p reports
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') · una consulta cada ${OVERPASS_MIN_INTERVAL}s ==="

# Los reintentos van muy espaciados a propósito: si Overpass nos tiene en la lista
# negra, volver a los dos minutos sólo alarga el castigo.
for intento in 1 2 3; do
  echo "--- intento $intento: árboles y edificios ---"
  ./enrich.sh; rc_enrich=$?
  echo "--- intento $intento: vías de acceso ---"
  ./access.sh; rc_access=$?
  if [ $rc_enrich -eq 0 ] && [ $rc_access -eq 0 ]; then
    echo "todo completado en el intento $intento"
    break
  fi
  [ $intento -lt 3 ] && { echo "esperando 30 min antes de reintentar"; sleep 1800; }
done

echo "=== $(date '+%Y-%m-%d %H:%M:%S') · resumen ==="
.venv/bin/python - <<'PY'
import json, os
from eclipseview.paths import DATA_DIR
m = json.load(open(os.path.join(DATA_DIR, 'points.json')))['meta']
n = m['n']
print(f"puntos: {n}")
print(f"  árboles/edificios: {m['n_obs_checked']}  ({n - m['n_obs_checked']} sin comprobar)")
print(f"  accesibilidad:     {m['n_access_checked']}  ({n - m['n_access_checked']} sin comprobar)")
PY
echo "log: $LOG"
echo "SI HAY PUNTOS NUEVOS: ./redeploy.sh para publicarlos."
