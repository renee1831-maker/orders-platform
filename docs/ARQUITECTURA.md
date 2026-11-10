# Arquitectura de la solución

## Diagrama

```mermaid
flowchart LR
  dev([Desarrollador]) -- git push --> repo[(GitHub<br/>orders-platform)]
  repo -- evento push a main --> gha

  subgraph gha[GitHub Actions · workflow CI/CD]
    direction LR
    j1[Build and test<br/>ruff · mypy · cfn-lint · pytest] --> j2[Deploy staging<br/>EB + smoke test full]
    j2 --> j3{Aprobación manual<br/>entorno production}
    j3 --> j4[Deploy production<br/>EB Immutable + smoke read-only]
  end

  j1 -. reportes JUnit / cobertura / app-bundle.zip .-> art[Artefactos de GitHub]
  j2 -- ZIP de la versión --> s3[(S3 artefactos)]
  s3 --> ver[EB Application Versions]

  subgraph aws[AWS Academy Sandbox · us-east-1 · stack orders-platform-infra]
    subgraph stg[Entorno staging]
      ebs[Elastic Beanstalk<br/>EC2 t3.micro · gunicorn+uvicorn] --> ddbs[(DynamoDB<br/>orders-staging)]
    end
    subgraph prd[Entorno producción]
      ebp[Elastic Beanstalk<br/>Single o ALB + ASG 2-4] --> ddbp[(DynamoDB<br/>orders-production · PITR)]
    end
    cw[Amazon CloudWatch<br/>Logs + salud enhanced]
  end

  ver --> ebs
  ver --> ebp
  ebs & ebp -- logs JSON / health --> cw
  usr([Cliente API]) -- HTTP REST --> ebp
```

## Decisiones y alternativas evaluadas

**Despliegue: Elastic Beanstalk (elegido) frente a ECS Fargate y EC2 manual.** Beanstalk tiene una
acción nativa en CodePipeline, gestiona EC2, Auto Scaling, balanceador, logs a CloudWatch y
despliegues *Immutable* sin escribir esa infraestructura, y funciona con `LabRole`/`LabInstanceProfile`
del laboratorio. ECS Fargate es la opción natural a escala (contenedores, despliegues blue/green
con CodeDeploy), pero exige VPC, ALB, ECR, task definitions y roles adicionales: más superficie y
más puntos de fallo en un sandbox con IAM restringido. EC2 manual con CodeDeploy obliga a mantener
AppSpec, agente y scripts de ciclo de vida. Migrar a ECS es directo: el `Dockerfile` ya existe.

**Persistencia: DynamoDB (elegido) frente a RDS PostgreSQL.** El acceso es por clave y por dos
patrones de consulta conocidos (todos por fecha; por estado y fecha), que se resuelven con dos GSI
sin *Scan*. Es serverless, no requiere VPC ni credenciales (usa el rol de la instancia), cuesta
prácticamente cero en reposo y se aprovisiona en segundos. RDS aportaría SQL ad hoc y joins, pero
tarda 10–15 minutos en crearse, consume presupuesto del laboratorio aunque no se use y exige
gestionar secretos. El repositorio está detrás de una interfaz, así que cambiarlo no toca el dominio.

**Framework: FastAPI** por validación declarativa con Pydantic, OpenAPI/Swagger automático (útil para
la demostración) y tipado estático verificable con `mypy --strict`. Los *endpoints* son síncronos a
propósito: boto3 es bloqueante y FastAPI los ejecuta en un *threadpool*, evitando bloquear el *event loop*.

**CI/CD: GitHub + GitHub Actions (elegido) frente a CodeCommit + CodePipeline + CodeBuild.**
El diseño original usaba los servicios de AWS (sigue en `infra/pipeline.yaml`). En el laboratorio
19174 el rol `voclabs` no tiene permisos para CodePipeline, CodeBuild, CodeCommit ni CodeConnections,
y `LabRole` no puede ser asumido por esos servicios; como no se pueden crear roles, el pipeline de AWS
no es desplegable allí. El enunciado admite un repositorio externo como GitHub, y GitHub Actions
cubre las mismas etapas: disparo por commit, build y pruebas con caché de dependencias, reportes,
artefactos versionados, despliegue a staging, aprobación manual mediante *environments* protegidos y
promoción del **mismo artefacto** a producción. El despliegue usa las APIs de Elastic Beanstalk, que
el laboratorio sí permite. Costo: las credenciales del laboratorio son temporales, así que los
secrets se renuevan en cada sesión (`scripts/update_github_secrets.sh`). En una cuenta real se usaría
OIDC (`aws-actions/configure-aws-credentials` con un rol federado) en lugar de claves.

## Patrones aplicados

La aplicación sigue una arquitectura por capas al estilo Clean Architecture, equivalente a MVC en
la capa web: los **modelos** son las entidades de dominio inmutables (`Order`), los **controladores**
son los *routers* de FastAPI y la **vista** es la representación JSON definida por los esquemas de
salida. `OrderService` depende del protocolo `OrderRepository` (inversión de dependencias); la
implementación concreta se inyecta en `create_app`, lo que permite probar con un repositorio en
memoria y un reloj determinista.

La máquina de estados vive en el dominio, no en el controlador, de modo que ninguna ruta puede
saltarse una transición. Las actualizaciones usan **bloqueo optimista** (`version` + escritura
condicional en DynamoDB): dos operadores que cambien el mismo pedido a la vez no se pisan; el
segundo recibe 409.

## Flujo CI/CD: qué valida cada etapa

| Job (GitHub Actions) | Equivalente AWS | Qué hace | Si falla |
|---|---|---|---|
| Disparo `on: push` a `main` | Source + EventBridge | Inicia el workflow con cada commit | — |
| Build and test | CodeBuild (`buildspec.yml`) | `ruff`, `mypy --strict`, `cfn-lint`, 55+ pruebas con cobertura ≥ 85 %, `build_info.json`, `app-bundle.zip` | El código no llega a ningún entorno |
| Deploy staging | Acción Deploy de EB + smoke test | Sube el ZIP a S3, crea la versión en EB, despliega, comprueba salud y crea un pedido real recorriendo todos los estados | Se detiene antes de producción |
| Aprobación | Manual approval | Entorno `production` con revisores obligatorios | Se rechaza y no se promueve |
| Deploy production | Acción Deploy de EB + smoke test | Promueve la misma versión con despliegue *Immutable* y verifica en solo lectura | EB conserva la versión anterior sirviendo tráfico |

`scripts/eb_deploy.sh` verifica que el entorno termine con la versión solicitada: si Beanstalk
revierte el despliegue, el job falla en lugar de reportar un falso éxito.
