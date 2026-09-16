"""ADMIN space: performance management (doc §9.3)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.admin.schema.performance import (
    PerformanceCreate,
    PerformanceListItem,
    PerformanceUpdate,
)
from backend.app.admin.service.performance_service import performance_service
from backend.common.pagination import DependsPagination, paging_data
from backend.common.response.response_code import CustomResponseCode
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.permission import DependsAdmin
from backend.database.db_postgres import CurrentSession

router = APIRouter(
    prefix="/admin/performances", tags=["Performances (ADMIN)"], dependencies=[DependsAdmin]
)


@router.post("", summary="Record a performance")
async def create_performance(request: Request, obj: PerformanceCreate) -> ResponseModel:
    data = await performance_service.create(request=request, obj=obj)
    return response_base.success(request=request, res=CustomResponseCode.HTTP_201, data=data)


@router.get("", summary="List and filter performances", dependencies=[DependsPagination])
async def list_performances(
    request: Request,
    db: CurrentSession,
    athlete_id: Annotated[int | None, Query()] = None,
    discipline: Annotated[str | None, Query()] = None,
    competition_name: Annotated[str | None, Query()] = None,
    medal: Annotated[str | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> ResponseModel:
    performance_select = performance_service.get_select(
        athlete_id=athlete_id,
        discipline=discipline,
        competition_name=competition_name,
        medal=medal,
        date_from=date_from,
        date_to=date_to,
    )
    page_data = await paging_data(db, performance_select, PerformanceListItem)
    return response_base.success(request=request, data=page_data)


@router.get("/{pk}", summary="Get one performance")
async def get_performance(request: Request, pk: Annotated[int, Path(...)]) -> ResponseModel:
    data = await performance_service.get(request=request, pk=pk)
    return response_base.success(request=request, data=data)


@router.patch("/{pk}", summary="Update a performance")
async def update_performance(
    request: Request, pk: Annotated[int, Path(...)], obj: PerformanceUpdate
) -> ResponseModel:
    count = await performance_service.update(request=request, pk=pk, obj=obj)
    return response_base.success(request=request, data={"updated": count})


@router.delete("/{pk}", summary="Delete a performance")
async def delete_performance(request: Request, pk: Annotated[int, Path(...)]) -> ResponseModel:
    count = await performance_service.delete(request=request, pk=pk)
    return response_base.success(request=request, data={"deleted": count})
