#!/usr/bin/env bash
# Espera a que acabe la generación de puntos, reconstruye el sitio y lo redespliega.
# Espera sobre un marcador del log, no sobre pgrep: un patrón que aparece en la propia
# línea de comandos del vigilante hace que pgrep se encuentre a sí mismo y se bloquee.
set -uo pipefail
cd "$(dirname "$0")"
LOG=/tmp/pts2.log
until grep -q '^OK ' "$LOG" 2>/dev/null; do
  if ! grep -qE '^\[' "$LOG" 2>/dev/null && [ ! -s "$LOG" ]; then sleep 20; continue; fi
  grep -qiE 'Traceback|Error' "$LOG" && { echo "FALLO en la generación"; tail -5 "$LOG"; exit 1; }
  sleep 30
done
echo "== dataset listo =="; tail -1 "$LOG"
.venv/bin/python -c "
from eclipseview import site
out, data = site.build(out_dir='site', progress=lambda m: print(' ', m, flush=True))
print('sitio ->', out, 'verificación', data['summary']['passed'], '/', data['summary']['total'])
" || exit 1
TOKEN="$(grep -oE 'vcp_[A-Za-z0-9]+' /home/alvaro/projects/services.md | head -1)"
cd site && npx --yes vercel@latest deploy --prod --yes --token "$TOKEN" --name eclipse-viewfinder 2>&1 | tail -2
echo "== redesplegado =="
curl -s -o /dev/null -w "https://eclipse.alvarosolis.dev -> %{http_code}\n" https://eclipse.alvarosolis.dev/
