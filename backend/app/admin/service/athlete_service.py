"""Athlete business rules (doc §11.2).

The one rule that matters most: an athlete is *one* business object made of a
login account and a profile. They are created together or not at all.
"""

from fastapi import Request
from sqlalchemy import Select

from backend.app.admin.schema.athlete import (
    AthleteDetail,
    AthleteSelfUpdate,
    AthleteUpdate,
    RegisterAthleteRequest,
)
from backend.app.admin.schema.performance import PerformanceResponse
from backend.app.admin.schema.user import UserRegister
from backend.common.enums import Role as RoleEnum
from backend.common.exception import errors
from backend.core.conf import settings
from backend.crud.crud_athlete import athlete_dao
from backend.crud.crud_user import user_dao
from backend.database.db_postgres import async_db_session
from backend.database.db_redis import redis_client
from backend.models import Athlete
from backend.utils.translator import Translator


class AthleteService:
    @staticmethod
    async def create(*, request: Request, obj: RegisterAthleteRequest) -> AthleteDetail:
        """Create the User account AND the Athlete profile in one transaction.

        ``async_db_session.begin()`` opens a single transaction: if the profile
        insert fails (duplicate licence, bad payload...), the account created a
        few lines above is rolled back with it. There is no window in which a
        login exists without its profile (doc §4.2, §8).
        """
        translator = Translator(request.state.locale)

        async with async_db_session.begin() as db:
            if await user_dao.get_by_email(db, obj.email):
                raise errors.ForbiddenError(msg=translator.t('athlete.email_exists'))
            if await athlete_dao.get_by_license_number(db, obj.license_number):
                raise errors.ForbiddenError(msg=translator.t('athlete.license_exists'))

            user = await user_dao.create_with_role(
                db,
                UserRegister(email=obj.email, password=obj.password),
                RoleEnum.USER.value,
                firstname=obj.first_name,
                lastname=obj.last_name,
            )

            profile = obj.model_dump(exclude={'email', 'password'})
            profile['user_id'] = user.id
            athlete = await athlete_dao.create(db, profile)

            return AthleteDetail(
                **{
                    **AthleteService._columns(athlete),
                    'email': user.email,
                    'is_active': bool(user.status),
                    'performance_count': 0,
                    'performances': [],
                }
            )

    @staticmethod
    def get_select(
        *,
        q: str | None = None,
        discipline: str | None = None,
        category: str | None = None,
        club_or_establishment: str | None = None,
        is_active: bool | None = None,
    ) -> Select:
        """Filtered athlete list, ready to paginate (doc §15)."""
        return athlete_dao.get_list(
            q=q,
            discipline=discipline,
            category=category,
            club_or_establishment=club_or_establishment,
            is_active=is_active,
        )

    @staticmethod
    async def get_detail(*, request: Request, pk: int) -> AthleteDetail:
        """One athlete with the full performance history."""
        translator = Translator(request.state.locale)
        async with async_db_session() as db:
            athlete = await athlete_dao.get_with_performances(db, pk)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.not_found'))
            return AthleteService._to_detail(athlete)

    @staticmethod
    async def get_me(*, request: Request) -> AthleteDetail:
        """The profile of the authenticated athlete."""
        translator = Translator(request.state.locale)
        async with async_db_session() as db:
            athlete = await athlete_dao.get_with_performances_by_user_id(db, request.user.id)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.no_profile'))
            return AthleteService._to_detail(athlete)

    @staticmethod
    async def update(*, request: Request, pk: int, obj: AthleteUpdate) -> int:
        """Partial update of a profile by an administrator."""
        translator = Translator(request.state.locale)
        async with async_db_session.begin() as db:
            athlete = await athlete_dao.get(db, pk)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.not_found'))

            data = obj.model_dump(exclude_unset=True, exclude_none=True)
            if not data:
                return 0
            new_license = data.get('license_number')
            if new_license and new_license != athlete.license_number:
                if await athlete_dao.get_by_license_number(db, new_license):
                    raise errors.ForbiddenError(msg=translator.t('athlete.license_exists'))
            return await athlete_dao.update(db, pk, data)

    @staticmethod
    async def update_me(*, request: Request, obj: AthleteSelfUpdate) -> int:
        """The limited self-service update an athlete may perform."""
        translator = Translator(request.state.locale)
        async with async_db_session.begin() as db:
            athlete = await athlete_dao.get_by_user_id(db, request.user.id)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.no_profile'))
            data = obj.model_dump(exclude_unset=True, exclude_none=True)
            if not data:
                return 0
            return await athlete_dao.update(db, athlete.id, data)

    @staticmethod
    async def set_status(*, request: Request, pk: int, is_active: bool) -> int:
        """Enable or disable an athlete.

        The flag lives on the account, so a disabled athlete can no longer log
        in - the profile and its history are kept intact.
        """
        translator = Translator(request.state.locale)
        async with async_db_session.begin() as db:
            athlete = await athlete_dao.get(db, pk)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.not_found'))
            user = await user_dao.get(db, athlete.user_id)
            user_sub = user.x_id if user else None
            count = await user_dao.set_status(db, athlete.user_id, is_active)

        await AthleteService._invalidate_sessions(user_sub)
        return count

    @staticmethod
    async def delete(*, request: Request, pk: int) -> int:
        """Delete an athlete: account, profile and history go together.

        Deleting the *account* is what cascades (``athlete.user_id`` and
        ``performance.athlete_id`` are both ``ON DELETE CASCADE``), so no row is
        left behind pointing at a user that no longer exists.
        """
        translator = Translator(request.state.locale)
        async with async_db_session.begin() as db:
            athlete = await athlete_dao.get(db, pk)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.not_found'))
            user = await user_dao.get(db, athlete.user_id)
            user_sub = user.x_id if user else None
            count = await user_dao.delete_model(db, athlete.user_id)

        await AthleteService._invalidate_sessions(user_sub)
        return count

    @staticmethod
    async def get_filters() -> dict[str, list[str]]:
        """Values available in the athlete filters (doc §15)."""
        async with async_db_session() as db:
            return {
                'disciplines': await athlete_dao.get_disciplines(db),
                'categories': await athlete_dao.get_categories(db),
                'establishments': await athlete_dao.get_establishments(db),
            }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _columns(athlete: Athlete) -> dict:
        """Mapped columns of an athlete, without SQLAlchemy internals."""
        return {k: v for k, v in athlete.__dict__.items() if not k.startswith('_')}

    @staticmethod
    def _to_detail(athlete: Athlete) -> AthleteDetail:
        performances = list(athlete.performances or [])
        return AthleteDetail(
            **{
                **AthleteService._columns(athlete),
                'email': athlete.email,
                'is_active': athlete.is_active,
                'performance_count': len(performances),
                'performances': [PerformanceResponse.model_validate(p) for p in performances],
            }
        )

    @staticmethod
    async def _invalidate_sessions(sub: str | None) -> None:
        """Drop cached tokens/identity so a status change takes effect at once."""
        if not sub:
            return
        for prefix in (
            settings.TOKEN_REDIS_PREFIX,
            settings.TOKEN_REFRESH_REDIS_PREFIX,
            settings.JWT_USER_REDIS_PREFIX,
        ):
            await redis_client.delete_prefix(f'{prefix}:{sub}')


athlete_service = AthleteService()
