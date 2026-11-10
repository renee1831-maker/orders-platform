#!/usr/bin/env bash
# Crea/actualiza la infraestructura con CloudFormation (idempotente).
#
# CICD_MODE=github (por defecto)  -> infra/platform.yaml: S3 + DynamoDB + Elastic Beanstalk.
#                                    La CI/CD la ejecuta GitHub Actions (.github/workflows/ci-cd.yml).
# CICD_MODE=codepipeline          -> infra/pipeline.yaml: además CodeCommit + CodePipeline + CodeBuild.
#                                    Solo para cuentas donde esos servicios estén permitidos.
set -euo pipefail

CICD_MODE="${CICD_MODE:-github}"
PROJECT_NAME="${PROJECT_NAME:-orders-platform}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
PROD_ENV_TYPE="${PROD_ENV_TYPE:-SingleInstance}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

# Ruta relativa: en Git Bash (Windows) una ruta absoluta /c/... no la entiende el AWS CLI nativo.
cd "$(dirname "$0")/.."

case "$CICD_MODE" in
  github)
    STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-infra}"
    TEMPLATE="infra/platform.yaml"
    ;;
  codepipeline)
    STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-cicd}"
    TEMPLATE="infra/pipeline.yaml"
    SOURCE_PROVIDER="${SOURCE_PROVIDER:-CodeCommit}"
    BRANCH_NAME="${BRANCH_NAME:-main}"
    ;;
  *) echo "CICD_MODE debe ser github o codepipeline" >&2; exit 2 ;;
esac

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

command -v aws >/dev/null || fail "AWS CLI no está instalado."

log "Verificando credenciales (las del laboratorio expiran con la sesión)"
aws sts get-caller-identity --region "$AWS_REGION" --output table \
  || fail "Credenciales inválidas o expiradas. Copie de nuevo 'AWS Details' en ~/.aws/credentials."

if [[ -z "${SOLUTION_STACK:-}" ]]; then
  log "Resolviendo la plataforma Elastic Beanstalk más reciente para Python ${PYTHON_VERSION}"
  SOLUTION_STACK="$(aws elasticbeanstalk list-available-solution-stacks --region "$AWS_REGION" \
    --query "SolutionStacks[?contains(@, 'Amazon Linux 2023') && contains(@, 'running Python ${PYTHON_VERSION}')] | [0]" \
    --output text)"
fi
[[ -n "$SOLUTION_STACK" && "$SOLUTION_STACK" != "None" ]] \
  || fail "No se encontró plataforma EB para Python ${PYTHON_VERSION}. Pruebe PYTHON_VERSION=3.13 o 3.11."
echo "Plataforma: $SOLUTION_STACK"

PARAMS=(
  ProjectName="$PROJECT_NAME"
  SolutionStackName="$SOLUTION_STACK"
  InstanceType="$INSTANCE_TYPE"
  ProductionEnvironmentType="$PROD_ENV_TYPE"
)
if [[ "$CICD_MODE" == "codepipeline" ]]; then
  PARAMS+=(
    SourceProvider="$SOURCE_PROVIDER"
    BranchName="$BRANCH_NAME"
    GitHubConnectionArn="${GITHUB_CONNECTION_ARN:-}"
    GitHubRepository="${GITHUB_REPOSITORY:-}"
    NotificationEmail="${NOTIFICATION_EMAIL:-}"
  )
fi

log "Validando plantilla ${TEMPLATE}"
aws cloudformation validate-template --region "$AWS_REGION" \
  --template-body "file://${TEMPLATE}" >/dev/null

log "Desplegando stack ${STACK_NAME} (la primera vez tarda ~10-15 min por los entornos EB)"
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --no-fail-on-empty-changeset \
  --tags Project="$PROJECT_NAME" \
  --parameter-overrides "${PARAMS[@]}"

log "Salidas del stack"
aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table

if [[ "$CICD_MODE" == "github" ]]; then
  cat <<MSG

Siguiente paso: cargar las credenciales del laboratorio como secrets del repositorio GitHub
  (scripts/update_github_secrets.sh) y hacer git push a main para disparar el workflow.
MSG
elif [[ "$SOURCE_PROVIDER" == "CodeCommit" ]]; then
  cat <<MSG

Siguiente paso (subir el código y disparar el pipeline):
  pip install git-remote-codecommit
  git remote add aws codecommit::${AWS_REGION}://${PROJECT_NAME}-repo
  git push aws ${BRANCH_NAME}
MSG
fi
