#!/usr/bin/env bash
# Despliega el sitio estático en Vercel y deja el subdominio apuntando.
# El token sale de projects/services.md, nunca del repo.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SERVICES="${SERVICES_MD:-/home/alvaro/projects/services.md}"
DOMAIN="${DOMAIN:-eclipse.alvarosolis.dev}"
PROJECT="${PROJECT:-eclipse-viewfinder}"

TOKEN="$(grep -oE 'vcp_[A-Za-z0-9]+' "$SERVICES" | head -1)"
TEAM="$(grep -oE 'team_[A-Za-z0-9]+' "$SERVICES" | head -1)"
[ -n "$TOKEN" ] || { echo "No encuentro el token de Vercel en $SERVICES"; exit 1; }

cd "$HERE/site"
echo "→ desplegando $(ls *.html | wc -l) páginas a producción..."
URL="$(npx --yes vercel@latest deploy --prod --yes \
        --token "$TOKEN" --scope "$TEAM" --name "$PROJECT" 2>&1 | tail -1)"
echo "→ desplegado: $URL"
echo "→ asociando $DOMAIN..."
npx --yes vercel@latest domains add "$DOMAIN" "$PROJECT" \
    --token "$TOKEN" --scope "$TEAM" 2>&1 | tail -3 || true
echo "listo. Comprueba https://$DOMAIN"
