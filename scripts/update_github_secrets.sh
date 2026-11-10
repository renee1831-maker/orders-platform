#!/usr/bin/env bash
# Copia las credenciales temporales del laboratorio (~/.aws/credentials, perfil [default])
# a los secrets del repositorio GitHub. Ejecútelo cada vez que reinicie el laboratorio.
#
# Requiere GitHub CLI autenticado (gh auth login). Uso:
#   bash scripts/update_github_secrets.sh                 # repositorio del remoto "origin"
#   bash scripts/update_github_secrets.sh usuario/repo
set -euo pipefail

CREDENTIALS_FILE="${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}"
PROFILE="${AWS_PROFILE:-default}"
REPO_ARGS=()
[[ $# -ge 1 ]] && REPO_ARGS=(--repo "$1")

command -v gh >/dev/null || {
  echo "GitHub CLI (gh) no está instalado. Instálelo (winget install GitHub.cli) o cargue los secrets" >&2
  echo "a mano en GitHub → Settings → Secrets and variables → Actions." >&2
  exit 1
}
[[ -f "$CREDENTIALS_FILE" ]] || { echo "No existe ${CREDENTIALS_FILE}" >&2; exit 1; }

read_key() {
  awk -v profile="[$PROFILE]" -v key="$1" '
    /^\[/ { in_profile = ($0 == profile) }
    in_profile {
      split($0, kv, "=")
      k = kv[1]; gsub(/[ \t\r]/, "", k)
      if (k == key) { v = substr($0, index($0, "=") + 1); gsub(/^[ \t]+|[ \t\r]+$/, "", v); print v; exit }
    }' "$CREDENTIALS_FILE"
}

for pair in AWS_ACCESS_KEY_ID:aws_access_key_id AWS_SECRET_ACCESS_KEY:aws_secret_access_key AWS_SESSION_TOKEN:aws_session_token; do
  secret="${pair%%:*}"
  value="$(read_key "${pair#*:}")"
  [[ -n "$value" ]] || { echo "Falta ${pair#*:} en el perfil [$PROFILE] de ${CREDENTIALS_FILE}" >&2; exit 1; }
  # Por stdin: el valor no aparece en la línea de comandos ni en el historial.
  printf '%s' "$value" | gh secret set "$secret" "${REPO_ARGS[@]}"
done
echo "Secrets actualizados. Si un job falló por credenciales vencidas, use 'Re-run failed jobs' en GitHub."
