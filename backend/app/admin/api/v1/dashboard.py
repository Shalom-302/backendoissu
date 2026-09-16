"""Dashboards for both spaces (doc §13, §14).

Two routes, one per audience: an athlete gets their own indicators, an
administrator gets the global picture. Each is guarded by its own role.
"""

from fastapi import APIRouter, Request

from backend.app.admin.service.dashboard_service import dashboard_service
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.permission import DependsAdmin, DependsAthlete

router = APIRouter(tags=["Dashboard"])


@router.get(
    "/dashboard",
    summary="Personal dashboard of the authenticated athlete",
    dependencies=[DependsAthlete],
)
async def get_user_dashboard(request: Request) -> ResponseModel:
    data = await dashboard_service.user_dashboard(request=request)
    return response_base.success(request=request, data=data)


@router.get(
    "/admin/dashboard",
    summary="Global steering dashboard",
    dependencies=[DependsAdmin],
)
async def get_admin_dashboard(request: Request) -> ResponseModel:
    data = await dashboard_service.admin_dashboard(request=request)
    return response_base.success(request=request, data=data)
