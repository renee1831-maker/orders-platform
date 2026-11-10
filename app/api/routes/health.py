from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.dependencies import OrderServiceDep, SettingsDep
from app.core.build_info import get_build_info

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness: el proceso responde")
def health(settings: SettingsDep) -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "build": get_build_info(),
    }


@router.get("/health/ready", summary="Readiness: dependencias disponibles")
def readiness(service: OrderServiceDep) -> JSONResponse:
    if service.is_healthy():
        return JSONResponse({"status": "ready"})
    return JSONResponse({"status": "unavailable"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
