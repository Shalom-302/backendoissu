"""ADMIN space: athlete management (doc §9.3, §15).

Every route here depends on ``DependsAdmin``: the role is checked on the
backend, never merely by hiding a button in the frontend (doc §17).
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.admin.schema.athlete import (
    AthleteListItem,
    AthleteUpdate,
    RegisterAthleteRequest,
    SetAthleteStatus,
)
from backend.app.admin.service.athlete_service import athlete_service
from backend.app.admin.service.performance_service import performance_service
from backend.common.pagination import DependsPagination, paging_data
from backend.common.response.response_code import CustomResponseCode
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.permission import DependsAdmin
from backend.database.db_postgres import CurrentSession

router = APIRouter(prefix="/admin/athletes", tags=["Athletes (ADMIN)"], dependencies=[DependsAdmin])


@router.post(
    "",
    summary="Register an athlete",
    description=(
        "Creates the login account AND the athlete profile in a single "
        "transaction. This is the only way an athlete account comes into "
        "existence: there is no public sign-up."
    ),
)
async def register_athlete(request: Request, obj: RegisterAthleteRequest) -> ResponseModel:
    data = await athlete_service.create(request=request, obj=obj)
    return response_base.success(request=request, res=CustomResponseCode.HTTP_201, data=data)


@router.get(
    "",
    summary="List and search athletes",
    dependencies=[DependsPagination],
)
async def list_athletes(
    request: Request,
    db: CurrentSession,
    q: Annotated[str | None, Query(description="Name, licence, establishment or email")] = None,
    discipline: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    club_or_establishment: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> ResponseModel:
    athlete_select = athlete_service.get_select(
        q=q,
        discipline=discipline,
        category=category,
        club_or_establishment=club_or_establishment,
        is_active=is_active,
    )
    page_data = await paging_data(db, athlete_select, AthleteListItem)
    return response_base.success(request=request, data=page_data)


@router.get(
    "/filters",
    summary="Values available in the athlete filters",
    description="Disciplines, categories and establishments actually present in the data.",
)
async def get_athlete_filters(request: Request) -> ResponseModel:
    data = await athlete_service.get_filters()
    return response_base.success(request=request, data=data)


@router.get("/{pk}", summary="Get one athlete with the full history")
async def get_athlete(request: Request, pk: Annotated[int, Path(...)]) -> ResponseModel:
    data = await athlete_service.get_detail(request=request, pk=pk)
    return response_base.success(request=request, data=data)


@router.get("/{pk}/performances", summary="Get the performance history of an athlete")
async def get_athlete_performances(
    request: Request, pk: Annotated[int, Path(...)]
) -> ResponseModel:
    data = await performance_service.get_history(request=request, athlete_id=pk)
    return response_base.success(request=request, data=data)


@router.patch("/{pk}", summary="Update an athlete profile")
async def update_athlete(
    request: Request, pk: Annotated[int, Path(...)], obj: AthleteUpdate
) -> ResponseModel:
    count = await athlete_service.update(request=request, pk=pk, obj=obj)
    return response_base.success(request=request, data={"updated": count})


@router.patch(
    "/{pk}/status",
    summary="Enable or disable an athlete",
    description="Disabling revokes the login; the profile and its history are kept.",
)
async def set_athlete_status(
    request: Request, pk: Annotated[int, Path(...)], obj: SetAthleteStatus
) -> ResponseModel:
    count = await athlete_service.set_status(request=request, pk=pk, is_active=obj.is_active)
    return response_base.success(request=request, data={"updated": count})


@router.delete(
    "/{pk}",
    summary="Delete an athlete",
    description="Removes the account, the profile and the performance history.",
)
async def delete_athlete(request: Request, pk: Annotated[int, Path(...)]) -> ResponseModel:
    count = await athlete_service.delete(request=request, pk=pk)
    return response_base.success(request=request, data={"deleted": count})
