#!/usr/bin/env bash
# Despliega una versión en un entorno Elastic Beanstalk y espera a que quede sana.
#
# Uso:
#   scripts/eb_deploy.sh --env orders-platform-staging --label v-abc1234 --bundle app.zip
#   scripts/eb_deploy.sh --env orders-platform-production --label v-abc1234   # promueve una versión existente
#
# Si se pasa --bundle y la versión no existe, la sube a S3 y la registra en Beanstalk.
# Sin --bundle, la versión debe existir (así producción recibe exactamente el artefacto probado en staging).
# Variables opcionales: PROJECT_NAME, STACK_NAME, AWS_REGION, DEPLOY_TIMEOUT (segundos, por defecto 1800).
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-orders-platform}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-infra}"
AWS_REGION="${AWS_REGION:-us-east-1}"
DEPLOY_TIMEOUT="${DEPLOY_TIMEOUT:-1800}"
POLL_SECONDS=15

ENV_NAME="" LABEL="" BUNDLE="" DESCRIPTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --bundle) BUNDLE="$2"; shift 2 ;;
    --description) DESCRIPTION="$2"; shift 2 ;;
    *) echo "Argumento desconocido: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$ENV_NAME" && -n "$LABEL" ]] || { echo "Faltan --env y/o --label" >&2; exit 2; }

log() { printf '\n==> %s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

output() {
  aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

APP_NAME="${APP_NAME:-$(output ApplicationName)}"
[[ -n "$APP_NAME" && "$APP_NAME" != "None" ]] || fail "No se encontró el stack ${STACK_NAME}. ¿Ejecutó scripts/deploy_infra.sh?"

version_exists() {
  [[ "$(aws elasticbeanstalk describe-application-versions --region "$AWS_REGION" \
    --application-name "$APP_NAME" --version-labels "$LABEL" \
    --query 'length(ApplicationVersions)' --output text)" != "0" ]]
}

if version_exists; then
  log "La versión ${LABEL} ya existe en ${APP_NAME}; se reutiliza"
elif [[ -n "$BUNDLE" ]]; then
  [[ -f "$BUNDLE" ]] || fail "No existe el paquete ${BUNDLE}"
  BUCKET="${ARTIFACT_BUCKET:-$(output ArtifactBucketName)}"
  KEY="releases/${LABEL}.zip"
  log "Subiendo ${BUNDLE} a s3://${BUCKET}/${KEY}"
  aws s3 cp "$BUNDLE" "s3://${BUCKET}/${KEY}" --region "$AWS_REGION" --only-show-errors
  log "Registrando versión ${LABEL}"
  aws elasticbeanstalk create-application-version --region "$AWS_REGION" \
    --application-name "$APP_NAME" --version-label "$LABEL" \
    --description "${DESCRIPTION:0:200}" \
    --source-bundle "S3Bucket=${BUCKET},S3Key=${KEY}" >/dev/null
else
  fail "La versión ${LABEL} no existe y no se indicó --bundle"
fi

env_field() {
  aws elasticbeanstalk describe-environments --region "$AWS_REGION" \
    --application-name "$APP_NAME" --environment-names "$ENV_NAME" \
    --query "Environments[0].$1" --output text
}

recent_events() {
  aws elasticbeanstalk describe-events --region "$AWS_REGION" --application-name "$APP_NAME" \
    --environment-name "$ENV_NAME" --start-time "$START_TIME" \
    --query 'reverse(Events)[].[EventDate,Severity,Message]' --output text || true
}

log "Esperando a que ${ENV_NAME} esté libre"
for _ in $(seq 1 40); do
  [[ "$(env_field Status)" == "Ready" ]] && break
  sleep "$POLL_SECONDS"
done
[[ "$(env_field Status)" == "Ready" ]] || fail "${ENV_NAME} no está en estado Ready"

START_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "Desplegando ${LABEL} en ${ENV_NAME}"
aws elasticbeanstalk update-environment --region "$AWS_REGION" \
  --environment-name "$ENV_NAME" --version-label "$LABEL" >/dev/null

deadline=$(( $(date +%s) + DEPLOY_TIMEOUT ))
sleep "$POLL_SECONDS"
while true; do
  status="$(env_field Status)"
  health="$(env_field Health)"
  printf '  estado=%s salud=%s\n' "$status" "$health"
  if [[ "$status" == "Ready" ]]; then break; fi
  (( $(date +%s) < deadline )) || { recent_events; fail "Tiempo de espera agotado (${DEPLOY_TIMEOUT}s)"; }
  sleep "$POLL_SECONDS"
done

deployed="$(env_field VersionLabel)"
log "Eventos del despliegue"
recent_events

# Beanstalk revierte a la versión anterior si el despliegue falla: hay que comprobarlo explícitamente.
[[ "$deployed" == "$LABEL" ]] || fail "El entorno quedó con la versión ${deployed}, no con ${LABEL} (despliegue revertido)"
[[ "$health" != "Red" ]] || fail "El entorno quedó con salud Red"

CNAME="$(env_field CNAME)"
log "Versión ${LABEL} activa en http://${CNAME}"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "url=http://${CNAME}" >> "$GITHUB_OUTPUT"
fi
