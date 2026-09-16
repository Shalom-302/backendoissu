"""USER space: what an athlete can see and change about themselves (doc §9.2)."""

from fastapi import APIRouter, Request

from backend.app.admin.schema.athlete import AthleteSelfUpdate
from backend.app.admin.service.athlete_service import athlete_service
from backend.app.admin.service.performance_service import performance_service
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.permission import DependsAthlete

router = APIRouter(prefix="/athletes", tags=["Athlete (USER space)"])


@router.get("/me", summary="Get my athlete profile", dependencies=[DependsAthlete])
async def get_my_profile(request: Request) -> ResponseModel:
    data = await athlete_service.get_me(request=request)
    return response_base.success(request=request, data=data)


@router.patch("/me", summary="Update my athlete profile", dependencies=[DependsAthlete])
async def update_my_profile(request: Request, obj: AthleteSelfUpdate) -> ResponseModel:
    count = await athlete_service.update_me(request=request, obj=obj)
    return response_base.success(request=request, data={"updated": count})


@router.get(
    "/me/performances",
    summary="Get my performance history",
    description="Most recent competition first.",
    dependencies=[DependsAthlete],
)
async def get_my_performances(request: Request) -> ResponseModel:
    data = await performance_service.get_my_history(request=request)
    return response_base.success(request=request, data=data)
