# Guía para el informe PDF y el video

## Capturas para el informe (requisito → evidencia)

| # | Requisito | Captura sugerida |
|---|---|---|
| 1 | Control de versiones | GitHub: repositorio con archivos (`app/`, `infra/`, `.github/workflows/`) e historial de commits |
| 2 | Infraestructura como código | CloudFormation: stack `orders-platform-infra` en `CREATE_COMPLETE` y pestaña *Resources* |
| 3 | CI se activa con cada commit | GitHub → *Actions*: ejecución iniciada por el push con el mensaje y hash del commit |
| 4 | Compilación y pruebas | Log del job *Build and test* mostrando `ruff`, `mypy`, `cfn-lint` y `55 passed` |
| 5 | Pruebas unitarias / reportes | *Summary* de la ejecución: pruebas aprobadas y % de cobertura; artefacto `test-reports` |
| 6 | Caché de dependencias | Paso *setup-python* con caché restaurada en la segunda ejecución (más rápida) |
| 7 | Artefactos generados | Artefacto `app-bundle` en GitHub + ZIP en el bucket S3 + *Application versions* en Beanstalk |
| 8 | CD a pruebas | Job *Deploy staging* exitoso + log del smoke test con todas las ✔ |
| 9 | Paso controlado a producción | *Review deployments* pendiente y luego aprobado |
| 10 | CD a producción | Job *Deploy production* exitoso; Beanstalk con dos entornos en verde |
| 11 | Crear pedidos | Swagger (`/docs` en staging): POST con respuesta 201 |
| 12 | Visualizar, filtrar y ordenar | GET con `status=...` y `sort=created_at` |
| 13 | Actualizar estado | PATCH con 200 y un intento inválido con 409 |
| 14 | Persistencia | DynamoDB → tabla → *Explore items* con los pedidos |
| 15 | Monitoreo | CloudWatch Logs con logs JSON (`order_created`) y salud *enhanced* de Beanstalk |
| 16 | Arquitectura | Diagrama de `docs/ARQUITECTURA.md` (GitHub lo renderiza; o exportar en mermaid.live) |
| 17 | Restricción del laboratorio | Error `AccessDeniedException` de CodePipeline/CodeBuild que justifica GitHub Actions |

Para cada captura basta una explicación de 2–3 líneas: qué muestra y qué requisito cumple.

## Guion del video (≤ 10 minutos)

Grabe por segmentos: una ejecución completa del workflow tarda ~10–15 minutos, así que corte o
acelere las esperas y dígalo en voz alta.

| Tiempo | Contenido |
|---|---|
| 0:00–1:00 | Problema, objetivo y diagrama de arquitectura |
| 1:00–2:00 | Recorrido del código: capas, máquina de estados, `.github/workflows/ci-cd.yml`, plantilla CloudFormation; por qué GitHub Actions (restricción del laboratorio) |
| 2:00–3:30 | API funcionando en staging desde Swagger: crear, listar con filtro, cambiar estado, transición inválida (409) |
| 3:30–4:00 | Mostrar `/health` de producción con el **commit actual** |
| 4:00–4:45 | Hacer un cambio visible (p. ej. `description` en `app/main.py`), `git commit` y `git push` |
| 4:45–7:00 | GitHub Actions arranca solo: Build and test (lint, tipos, pruebas), resumen de cobertura, despliegue a staging, smoke test |
| 7:00–8:00 | Aprobación manual (*Review deployments*) y despliegue *Immutable* a producción |
| 8:00–9:00 | `/health` de producción muestra el **nuevo commit**; CloudWatch Logs y tabla DynamoDB |
| 9:00–10:00 | Cierre: qué se automatizó, riesgos y mejoras futuras |

**Plus recomendado (si el tiempo alcanza):** subir un commit con una prueba rota y mostrar que el
workflow se detiene en *Build and test* sin tocar staging ni producción. Es la evidencia más clara
de que la integración continua protege los entornos.
