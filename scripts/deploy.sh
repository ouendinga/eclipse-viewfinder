#!/usr/bin/env bash
# Despliega el sitio estático en Vercel y deja el subdominio apuntando.
#
# Las credenciales se pasan por entorno y no se leen de ningún fichero: una ruta
# escrita aquí le diría a cualquiera dónde ir a buscarlas.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${DOMAIN:-eclipse.alvarosolis.dev}"
PROJECT="${PROJECT:-eclipse-viewfinder}"

TOKEN="${VERCEL_TOKEN:?exporta VERCEL_TOKEN}"
TEAM="${VERCEL_TEAM:?exporta VERCEL_TEAM}"

cd "$HERE/site"
echo "→ desplegando $(ls *.html | wc -l) páginas a producción..."
URL="$(npx --yes vercel@latest deploy --prod --yes \
        --token "$TOKEN" --scope "$TEAM" --name "$PROJECT" 2>&1 | tail -1)"
echo "→ desplegado: $URL"
echo "→ asociando $DOMAIN..."
npx --yes vercel@latest domains add "$DOMAIN" "$PROJECT" \
    --token "$TOKEN" --scope "$TEAM" 2>&1 | tail -3 || true
echo "listo. Comprueba https://$DOMAIN"
