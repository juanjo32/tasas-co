#!/usr/bin/env bash
# Hace commit y push de los datos si cambiaron. Uso: scripts/guardar.sh "mensaje"
set -euo pipefail
git config user.name "tasas-co-bot"
git config user.email "tasas-co-bot@users.noreply.github.com"
git add data MOVIMIENTOS.md site/public/data 2>/dev/null || true
if git diff --cached --quiet; then
  echo "Sin cambios: $1"
  exit 0
fi
git commit -q -m "datos: $1 ($(TZ=America/Bogota date +'%Y-%m-%d %H:%M'))"
for intento in 1 2 3; do
  git pull -q --rebase --autostash && git push -q && exit 0
  sleep 5
done
echo "::error::No se pudo hacer push de los datos"
exit 1
