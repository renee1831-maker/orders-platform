#!/usr/bin/env bash
# Elimina el stack. La tabla de producción (y el repositorio CodeCommit, si existe) se conservan (Retain).
# CICD_MODE=github (por defecto) borra orders-platform-infra; CICD_MODE=codepipeline borra orders-platform-cicd.
set -euo pipefail

CICD_MODE="${CICD_MODE:-github}"
PROJECT_NAME="${PROJECT_NAME:-orders-platform}"
AWS_REGION="${AWS_REGION:-us-east-1}"
if [[ "$CICD_MODE" == "codepipeline" ]]; then
  STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-cicd}"
else
  STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-infra}"
fi

read -r -p "Se eliminará el stack '${STACK_NAME}' en ${AWS_REGION}. Escriba el nombre para confirmar: " answer
[[ "$answer" == "$STACK_NAME" ]] || { echo "Cancelado."; exit 1; }

BUCKET="$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)"
if [[ -n "$BUCKET" && "$BUCKET" != "None" ]]; then
  echo "Vaciando bucket de artefactos ${BUCKET}"
  aws s3 rm "s3://${BUCKET}" --recursive --region "$AWS_REGION"
fi

aws cloudformation delete-stack --region "$AWS_REGION" --stack-name "$STACK_NAME"
echo "Esperando eliminación..."
aws cloudformation wait stack-delete-complete --region "$AWS_REGION" --stack-name "$STACK_NAME"

cat <<MSG
Stack eliminado. Recursos conservados a propósito (bórrelos manualmente si ya no los necesita):
  aws dynamodb delete-table --table-name ${PROJECT_NAME}-orders-production --region ${AWS_REGION}
MSG
if [[ "$CICD_MODE" == "codepipeline" ]]; then
  echo "  aws codecommit delete-repository --repository-name ${PROJECT_NAME}-repo --region ${AWS_REGION}"
fi
