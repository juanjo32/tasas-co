#!/usr/bin/env bash
# Hace commit y push de los datos si cambiaron. Uso: scripts/guardar.sh "mensaje"
set -euo pipefail
git config user.name "tasas-co-bot"
git config user.email "tasas-co-bot@users.noreply.github.com"
for ruta in data MOVIMIENTOS.md site/public/data; do
  [ -e "$ruta" ] && git add "$ruta"
done
if git diff --cached --quiet; then
  echo "Sin cambios: $1"
  exit 0
fi
git commit -q -m "datos: $1 ($(TZ=America/Bogota date +'%Y-%m-%d %H:%M'))"
# El checkout no deja credenciales en .git/config: el token llega solo a este script por GH_TOKEN
: "${GH_TOKEN:?Falta GH_TOKEN}"
auth="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
echo "::add-mask::$auth"
gitauth() { git -c "http.https://github.com/.extraheader=$auth" "$@"; }
for intento in 1 2 3; do
  gitauth pull -q --rebase --autostash && gitauth push -q && exit 0
  sleep 5
done
echo "::error::No se pudo hacer push de los datos"
exit 1
