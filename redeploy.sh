#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
.venv/bin/python -c "
from eclipseview import site
out, data = site.build(out_dir='site', progress=lambda m: print(' ', m, flush=True))
print('sitio ->', out, '| verificación', data['summary']['passed'], '/', data['summary']['total'])
" || exit 1
TOKEN="$(grep -oE 'vcp_[A-Za-z0-9]+' /home/alvaro/projects/services.md | head -1)"
cd site && npx --yes vercel@latest deploy --prod --yes --token "$TOKEN" --name eclipse-viewfinder 2>&1 | tail -1
echo "== redesplegado =="
