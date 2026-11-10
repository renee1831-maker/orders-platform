# Despliegue paso a paso en el laboratorio AWS Academy (Sandbox 19174)

> **Por qué GitHub Actions y no CodePipeline.** En este laboratorio el rol `voclabs` no tiene permiso
> para CodePipeline, CodeBuild, CodeCommit, CodeConnections ni ECS (`AccessDeniedException ... no
> identity-based policy allows the codepipeline:ListPipelines action`), y `LabRole` no confía en
> `codepipeline.amazonaws.com` ni `codebuild.amazonaws.com`. Sí están permitidos Elastic Beanstalk,
> DynamoDB, CloudFormation, S3 y ECR. Por eso el repositorio es **GitHub** (permitido por el enunciado)
> y la CI/CD la ejecuta **GitHub Actions**, que despliega en Elastic Beanstalk con las credenciales del
> laboratorio. La versión con CodePipeline sigue disponible en `infra/pipeline.yaml`
> (`CICD_MODE=codepipeline`) para cuentas donde esos servicios estén habilitados.

## 0. Requisitos locales

Git, Python 3.12, AWS CLI v2, una cuenta de GitHub. Opcional: GitHub CLI (`winget install GitHub.cli`)
para actualizar los secrets con un comando.

En Windows use **Git Bash** y entre siempre a la carpeta del proyecto con comillas (la ruta tiene espacios):

```bash
cd "/c/Users/User/Documents/Laboratorios/Ordenes de Compras/orders-platform"
source .venv/Scripts/activate
```

## 1. Iniciar el laboratorio y cargar credenciales

1. Pulse **Start Lab** y espere el indicador verde.
2. **AWS Details → AWS CLI: Show**: copie el bloque completo en `~/.aws/credentials` (perfil `[default]`).
3. Verifique: `aws sts get-caller-identity`.

Las credenciales caducan al terminar la sesión (≈4 h). Al reiniciar el laboratorio repita este paso
**y el paso 4.3** (secrets de GitHub). Al cerrar la sesión el laboratorio detiene las instancias EC2;
al reiniciarlo, Beanstalk tarda unos minutos en volver a estado *Ok*.

## 2. Comprobaciones previas

```bash
aws iam get-role --role-name LabRole --query Role.Arn
aws iam get-instance-profile --instance-profile-name LabInstanceProfile --query InstanceProfile.Arn
aws iam get-role --role-name LabRole \
  --query "Role.AssumeRolePolicyDocument.Statement[].Principal.Service" --output text \
  | tr '\t' '\n' | grep -E "elasticbeanstalk|ec2"
```

Deben aparecer los dos ARN y los servicios `elasticbeanstalk` y `ec2`.

## 3. Crear la infraestructura (S3 + DynamoDB + Elastic Beanstalk)

```bash
bash scripts/deploy_infra.sh
```

Crea el stack `orders-platform-infra` en 10–15 minutos. Al final imprime `StagingUrl`,
`ProductionUrl` y el bucket de artefactos. Los entornos arrancan con la aplicación de ejemplo de AWS;
la API real llega con el primer *push*.

## 4. Repositorio GitHub y secrets

1. En GitHub cree un repositorio vacío, por ejemplo `orders-platform` (sin README ni .gitignore).
   Si es **público**, las aprobaciones manuales de entornos funcionan en el plan gratuito.
   Si es privado, se necesita GitHub Pro (gratis con GitHub Student Developer Pack).
2. Suba el código:
   ```bash
   git init -b main
   git add . && git commit -m "feat: API de pedidos y CI/CD con GitHub Actions"
   git remote add origin https://github.com/<usuario>/orders-platform.git
   git push -u origin main
   ```
   Este primer push ya ejecuta el workflow; el despliegue fallará hasta cargar los secrets (paso 3):
   es normal. Después use **Re-run all jobs**.
3. Cargue las credenciales del laboratorio como secrets del repositorio:
   - Con GitHub CLI: `gh auth login` una vez y luego `bash scripts/update_github_secrets.sh`.
   - A mano: GitHub → *Settings → Secrets and variables → Actions → New repository secret*:
     `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_SESSION_TOKEN` (valores de AWS Details).
4. Configure la aprobación manual: *Settings → Environments → New environment* `production` →
   marque **Required reviewers**, agréguese como revisor y guarde. Cree también el entorno `staging`
   (sin reglas) si no se creó solo.

## 5. Ejecutar el flujo CI/CD

Cada `git push` a `main` dispara *Actions → CI/CD*:

| Job | Qué hace |
|---|---|
| **Build and test** | `ruff`, `mypy --strict`, `cfn-lint`, 55 pruebas con cobertura ≥ 85 %, `build_info.json` con el commit y empaquetado `app-bundle.zip` (artefacto) |
| **Deploy staging** | Sube el ZIP a S3, registra la versión en Beanstalk, despliega en staging, espera salud y ejecuta el smoke test completo |
| **Deploy production** | Espera la **aprobación manual** (*Review deployments → Approve and deploy*), promueve la **misma versión** con despliegue *Immutable* y ejecuta el smoke test de solo lectura |

Los *pull requests* solo ejecutan la CI.

## 6. Verificar

```bash
STAGING=$(aws cloudformation describe-stacks --stack-name orders-platform-infra \
  --query "Stacks[0].Outputs[?OutputKey=='StagingUrl'].OutputValue" --output text)
curl -s "$STAGING/health"                         # muestra el commit desplegado
python scripts/smoke_test.py --url "$STAGING" --mode full
```

Evidencias: GitHub → *Actions* (ejecución, resumen de pruebas y cobertura, artefactos), Beanstalk →
*Application versions* y *Events*, CloudWatch → *Log groups* `/aws/elasticbeanstalk/orders-platform-*`.

Despliegue manual de una versión (sin GitHub), útil para diagnosticar:

```bash
bash scripts/eb_deploy.sh --env orders-platform-staging --label manual-1 --bundle app-bundle.zip
```

## 7. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ExpiredToken` / `InvalidClientTokenId` en local | Sesión del laboratorio vencida | Repetir paso 1 |
| Job de deploy falla en *Credenciales AWS* o con `ExpiredToken` | Secrets de GitHub con credenciales viejas | Paso 4.3 y *Re-run failed jobs* |
| `No se encontró el stack orders-platform-infra` | Infraestructura no creada o borrada | Paso 3 |
| `despliegue revertido` / salud `Red` | La app no arrancó en EB | Beanstalk → *Logs → Request logs* o CloudWatch; revisar `/health/ready` |
| *Deploy production* no espera aprobación | Falta la regla del entorno `production` | Paso 4.4 |
| `No se encontró plataforma EB` | Versión de Python no publicada en la región | `PYTHON_VERSION=3.13 bash scripts/deploy_infra.sh` |
| `CNAME ... is not available` | Prefijo ocupado | `PROJECT_NAME=orders-<iniciales> bash scripts/deploy_infra.sh` (y ajuste `PROJECT_NAME` en el workflow) |
| Error de *Launch Configuration* en EB | Cuentas nuevas solo admiten *Launch Templates* | Ya mitigado con `DisableIMDSv1` + `gp3`; no quitar esas opciones |
| `ROLLBACK_COMPLETE` en el stack | Error de permisos en algún recurso | Ver pestaña *Events*, eliminar el stack y reintentar |

## 8. Limpieza (cuidar el presupuesto del laboratorio)

```bash
bash scripts/destroy_infra.sh
```

La tabla de producción se conserva por diseño; el script imprime el comando para borrarla.
