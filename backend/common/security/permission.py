"""Role-based guards for the OISSU CONNECT V1.

V1 has exactly two roles — ``USER`` (an athlete) and ``ADMIN`` — so it does not
need the Casbin policy engine that ships with the boilerplate (see
``backend.common.security.rbac``, still available for the V2 workflows). These
dependencies keep the check where the doc requires it: **on the backend**, not
only in the frontend routing (doc §17).
"""

from fastapi import Depends, Request

from backend.common.enums import Role as RoleEnum
from backend.common.exception.errors import AuthorizationError, TokenError
from backend.common.security.jwt import DependsJwtAuth


def _role_names(request: Request) -> set[str]:
    """Role names carried by the authenticated user, lowercased."""
    roles = getattr(request.user, 'roles', None) or []
    names = set()
    for role in roles:
        name = role.get('name') if isinstance(role, dict) else getattr(role, 'name', None)
        if name:
            names.add(str(name).lower())
    return names


def require_authenticated(request: Request, _token: str = DependsJwtAuth) -> None:
    """Reject anything the JWT middleware did not authenticate."""
    if not request.auth.scopes:
        raise TokenError


def require_admin(request: Request, _token: str = DependsJwtAuth) -> None:
    """Allow only accounts holding the ADMIN role.

    Every ``/admin/*`` route depends on this (doc §9.3).
    """
    require_authenticated(request)
    if RoleEnum.ADMIN.value not in _role_names(request):
        raise AuthorizationError(msg='This action is restricted to administrators')


def require_athlete(request: Request, _token: str = DependsJwtAuth) -> None:
    """Allow only accounts holding the USER (athlete) role."""
    require_authenticated(request)
    if RoleEnum.USER.value not in _role_names(request):
        raise AuthorizationError(msg='This action is restricted to athletes')


def is_admin(request: Request) -> bool:
    """Whether the current request is made by an administrator."""
    return RoleEnum.ADMIN.value in _role_names(request)


DependsAuth = Depends(require_authenticated)
DependsAdmin = Depends(require_admin)
DependsAthlete = Depends(require_athlete)
