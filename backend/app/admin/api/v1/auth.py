from fastapi import APIRouter, Depends, Request, Response
from fastapi_limiter.depends import RateLimiter
from starlette.background import BackgroundTasks

from backend.app.admin.schema.user import (
    GetCurrentUserInfoDetail,
    UserLoginSchema,
)
from backend.app.admin.service.auth_service import auth_service
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.permission import DependsAuth

router = APIRouter(prefix="/auth", tags=["User Auth"])

# NOTE — no public POST /auth/register.
# OISSU CONNECT V1 exposes a single login screen and no public sign-up: athlete
# accounts are created by an administrator through POST /api/v1/admin/athletes,
# which creates the account and the profile together (doc §4.1, §4.2).
# The first administrator is created out of band with `shaapi auth init`.


@router.post(
    '/login',
    summary='user login',
    description='json format, only supports debugging in third-party api tools, e.g. postman.',
    dependencies=[Depends(RateLimiter(times=5, minutes=1))],  # brute-force guard
)
async def user_login(
    request: Request, response: Response, obj: UserLoginSchema, background_tasks: BackgroundTasks
) -> ResponseModel:
    data = await auth_service.login(request=request, response=response, obj=obj, background_tasks=background_tasks)
    return response_base.success(request=request, data=data)


@router.post('/token/new', summary='Create a new token', dependencies=[DependsAuth])
async def create_new_token(request: Request, response: Response) -> ResponseModel:
    data = await auth_service.new_token(request=request, response=response)
    return response_base.success(request=request, data=data)


@router.post('/logout', summary='user logout', dependencies=[DependsAuth])
async def user_logout(request: Request, response: Response) -> ResponseModel:
    await auth_service.logout(request=request, response=response)
    return response_base.success(request=request)


@router.get('/me', summary='Get connected user profile', dependencies=[DependsAuth], response_model_exclude={'password'})
async def get_current_user(request: Request) -> ResponseModel:
    data = GetCurrentUserInfoDetail(**request.user.model_dump())
    return response_base.success(request=request, data=data)






