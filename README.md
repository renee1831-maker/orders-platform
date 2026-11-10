# Plataforma de Gestión de Pedidos — API REST + CI/CD en AWS

API REST en **Python (FastAPI)** para crear, consultar, filtrar y actualizar el estado de pedidos,
desplegada automáticamente en AWS con **GitHub → GitHub Actions → Elastic Beanstalk**,
persistencia en **DynamoDB** y observabilidad en **CloudWatch**. La infraestructura está definida
como código en `infra/platform.yaml` (CloudFormation) y el flujo CI/CD en `.github/workflows/ci-cd.yml`.

> El laboratorio AWS Academy 19174 bloquea CodePipeline, CodeBuild y CodeCommit, por eso la CI/CD
> corre en GitHub Actions. La variante 100 % AWS (CodeCommit → CodePipeline → CodeBuild) se conserva en
> `infra/pipeline.yaml` y se despliega con `CICD_MODE=codepipeline ./scripts/deploy_infra.sh`.

| Documento | Contenido |
|---|---|
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Diagrama, decisiones técnicas y alternativas evaluadas |
| [docs/DESPLIEGUE_SANDBOX.md](docs/DESPLIEGUE_SANDBOX.md) | Paso a paso en el laboratorio AWS Academy |
| [docs/ENTREGABLES.md](docs/ENTREGABLES.md) | Capturas para el informe PDF y guion del video |
| [docs/requests.http](docs/requests.http) | Peticiones de ejemplo |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/orders` | Crear pedido (cliente, productos, cantidades, dirección) |
| `GET` | `/api/v1/orders` | Listar con filtros `status`, `created_from`, `created_to`; orden `sort=created_at\|-created_at`; paginación `limit` + `cursor` |
| `GET` | `/api/v1/orders/{id}` | Consultar un pedido |
| `PATCH` | `/api/v1/orders/{id}/status` | Cambiar estado (valida la máquina de estados) |
| `GET` | `/health`, `/health/ready` | Liveness (incluye el commit desplegado) y readiness |
| `GET` | `/docs` | Swagger UI (deshabilitado en producción) |

Estados: `PENDING` (Pendiente) → `IN_PROCESS` (En proceso) → `SHIPPED` (Enviado) → `DELIVERED` (Entregado).
Cualquier otra transición responde **409**. Los importes se devuelven como *string* decimal
(`"125.50"`) para no perder precisión.

## Ejecución local

```bash
make install && . .venv/bin/activate
make check          # ruff + cfn-lint + mypy --strict + pytest (cobertura ≥ 85 %)
make run            # http://localhost:8000/docs  (repositorio en memoria)
make up             # Docker: API + DynamoDB Local en http://localhost:8080/docs
```

## Despliegue en AWS (resumen)

```bash
bash scripts/deploy_infra.sh                    # S3 + DynamoDB + Elastic Beanstalk (staging y producción)
git remote add origin https://github.com/<usuario>/orders-platform.git
bash scripts/update_github_secrets.sh           # credenciales del laboratorio como secrets (cada sesión)
git push -u origin main                         # dispara GitHub Actions: CI → staging → aprobación → producción
```

## Estructura

```
app/
  domain/          Entidad Order, máquina de estados, errores de dominio (sin dependencias externas)
  services/        Casos de uso (OrderService) — depende de la abstracción OrderRepository
  repositories/    Puerto + adaptadores: DynamoDB (producción) y memoria (pruebas/local)
  api/             Controladores FastAPI, esquemas de validación, errores, middleware
  core/            Configuración 12-factor, logging JSON, metadatos de build
tests/             unit/ · api/ · integration/ (DynamoDB simulado con moto)
infra/             CloudFormation: platform.yaml (EB, DynamoDB, S3) · pipeline.yaml (variante CodePipeline)
.github/workflows/ CI/CD con GitHub Actions
scripts/           deploy/destroy de infraestructura, eb_deploy.sh, secrets de GitHub, smoke test
buildspec.yml      (variante CodePipeline) CI: lint, tipado, IaC lint, pruebas, empaquetado
buildspec-smoke.yml Verificación funcional contra el entorno desplegado
```
