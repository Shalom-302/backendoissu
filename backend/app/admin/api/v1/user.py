from typing import Annotated, Union

from fastapi import APIRouter, Query, Request

from backend.app.admin.schema.user import (
    GetCurrentUserInfoDetail,
    GetUserInfoListDetails,
    UpdateUserParam,
)
from backend.app.admin.service.user_service import user_service
from backend.common.enums import Role
from backend.common.pagination import DependsPagination, paging_data
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.permission import DependsAdmin, DependsAuth
from backend.database.db_postgres import CurrentSession

router = APIRouter(prefix="/users", tags=["User"])


@router.get(
    "/me",
    summary="Get the authenticated user account",
    dependencies=[DependsAuth],
    response_model_exclude={"password"},
)
async def get_my_account(request: Request) -> ResponseModel:
    data = GetCurrentUserInfoDetail(**request.user.model_dump())
    return response_base.success(request=request, data=data)


@router.patch(
    "/me",
    summary="Update the authenticated user account",
    dependencies=[DependsAuth],
)
async def update_my_account(request: Request, obj: UpdateUserParam) -> ResponseModel:
    count = await user_service.update(id=request.user.id, obj=obj)
    return response_base.success(request=request, data={"updated": count})


@router.get(
    "/",
    summary="Get users pagination",
    description="Reserved to administrators: the account list is a back-office view.",
    dependencies=[
        DependsAdmin,
        DependsPagination,
    ],
)
async def get_pagination_users(
    request: Request,
    db: CurrentSession,
    query: Annotated[str | None, Query()] = None,
    role: Annotated[Union[Role, str] | None, Query()] = None,
    status: Annotated[bool | None, Query()] = None,
) -> ResponseModel:
    user_select = await user_service.get_select(q=query, role=role, status=status)
    page_data = await paging_data(db, user_select, GetUserInfoListDetails)
    return response_base.success(request=request, data=page_data)
