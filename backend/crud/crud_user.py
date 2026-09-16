from fast_captcha import text_captcha
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from backend.models import Role, User
from backend.crud.crud_role import role_dao
from backend.app.admin.schema.user import (
    UserRegister,
    UserUpdate
)
from backend.common.security.jwt import get_hash_password
from backend.common.enums import Role as Role_enum
from backend.utils.timezone import timezone
from backend.crud.crud_base import CRUDBase


class CRUDUser(CRUDBase[User]):
    async def get(self, db: AsyncSession, admin_id: int) -> User | None:
        """
        Getting admin

        :param db:
        :param admin_id:
        :return:
        """
        return await self.select_model(db, admin_id)
    
    async def get_by_x_id(self, db: AsyncSession, x_id: str, populates: list = []) -> User | None:
        """
        Get admin by email

        :param db:
        :param email:
        :return:
        """
        return await self.select_model_by_column(db, x_id=x_id, populates=populates)

    async def get_by_email(self, db: AsyncSession, email: str, populates: list = []) -> User | None:
        """
        Get admin by email

        :param db:
        :param email:
        :return:
        """
        return await self.select_model_by_column(db, email=email, populates=populates)

    async def get_by_phone(self, db: AsyncSession, phone: str) -> User | None:
        """
        Get admin by phone

        :param db:
        :param phone:
        :return:
        """
        return await self.select_model_by_column(db, phone=phone, populates=['roles'])

    async def get_by_pseudo(self, db: AsyncSession, pseudo: str) -> User | None:
        """
        Get admin by pseudo

        :param db:
        :param pseudo:
        :return:
        """
        return await self.select_model_by_column(db, pseudo=pseudo, populates=['roles'])

    async def update_login_time(self, db: AsyncSession, email: str) -> int:
        """
        Update login time

        :param db:
        :param email:
        :return:
        """
        return await self.update_model_by_column(db, {'last_login_time': timezone.now()}, email=email)

    async def create(self, db: AsyncSession, obj: UserRegister, *, social: bool = False) -> None:
        """
        Create User

        :param db:
        :param obj:
        :param social: Social admins, adapted to oauth 2.0
        :return:
        """
        if not social:
            salt = text_captcha(5)
            obj.password = get_hash_password(f'{obj.password}{salt}')
            dict_obj = obj.model_dump()
            dict_obj.update({'salt': salt})
        else:
            dict_obj = obj.model_dump()
            dict_obj.update({'salt': None})
    
        new_admin = self.model(**dict_obj)
        await db.add(db, new_admin)

    async def add(self, db: AsyncSession, obj: UserRegister) -> User:
        """
        Add admin

        :param db:
        :param obj:
        :return:
        """
        salt = text_captcha(5)
        obj.password = get_hash_password(f'{obj.password}{salt}')
        dict_obj = obj.model_dump(exclude={'roles'})
        
        dict_obj.update({'salt': salt})

        
        new_admin = self.model(**dict_obj)

        
        role = await role_dao.get_by_name(db, Role_enum.ADMIN.value)
        
        role_list = []
        if role is not None:
            role_list.append(role)
        new_admin.roles.extend(role_list)
        db.add(new_admin)
        await db.flush()
        await db.refresh(new_admin)
        return new_admin

    async def create_with_role(
        self,
        db: AsyncSession,
        obj: UserRegister,
        role_name: str,
        *,
        firstname: str | None = None,
        lastname: str | None = None,
    ) -> User:
        """Create an account and attach one role, by name.

        ``add()`` above always grants the ADMIN role — that is the boilerplate
        bootstrap path used by ``shaapi auth init``. OISSU CONNECT also creates
        USER (athlete) accounts, so the role is a parameter here. The missing
        role row is created on the fly, which keeps a fresh database working
        without a separate seeding step.

        The caller owns the transaction: nothing is committed here, so an
        athlete profile that fails to insert rolls the account back with it.
        """
        salt = text_captcha(5)
        dict_obj = obj.model_dump(exclude={'roles'})
        dict_obj['password'] = get_hash_password(f'{obj.password}{salt}')
        dict_obj['salt'] = salt

        new_user = self.model(**dict_obj)
        # Kept on the account as well as on the profile: the signed-in header
        # reads the account, and an admin has no athlete profile to read from.
        new_user.firstname = firstname
        new_user.lastname = lastname

        role = await role_dao.get_by_name(db, role_name)
        if role is None:
            role = Role(name=role_name)
            db.add(role)
            await db.flush()
        new_user.roles.append(role)

        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)
        return new_user

    async def update_admin_info(self, db: AsyncSession, input_admin: int, obj: UserUpdate) -> int:
        """
        Updating admin information

        :param db:
        :param input_admin:
        :param obj:
        :return:
        """
        return await self.update_model(db, input_admin, obj)

    async def update_profile_image(self, db: AsyncSession, input_admin: int, profile_image: dict) -> int:
        """
        Update admin profile image

        :param db:
        :param input_admin:
        :param avatar:
        :return:
        """
        return await self.update_model(db, input_admin, {'profile_image': dict})

    async def check_email(self, db: AsyncSession, email: str) -> User | None:
        """
        Check admin email

        :param db:
        :param email:
        :return:
        """
        return await self.select_model_by_column(db, email=email)

    async def reset_password(self, db: AsyncSession, pk: int, new_pwd: str) -> int:
        """
        Reset admin password

        :param db:
        :param pk:
        :param new_pwd:
        :return:
        """
        return await self.update_model(db, pk, {'password': new_pwd})

    async def get_list(self, email: str = None, phone: str = None, status: bool = None, role: str | None = None) -> Select:
        """
        Get admin list

        :param dept:
        :param adminname:
        :param phone:
        :param status:
        :return:
        """
        stmt = (
            select(self.model)
            .order_by(desc(self.model.join_time))
        )
        where_list = []
        if email:
            where_list.append(self.model.email.like(f'%{email}%'))
        if phone:
            where_list.append(self.model.phone.like(f'%{phone}%'))
        if status is not None:
            where_list.append(self.model.status == status)
        if where_list:
            stmt = stmt.where(and_(*where_list))
        return stmt

    async def get_status(self, db: AsyncSession, admin_id: int) -> int:
        """
        Get admin status 

        :param db:
        :param admin_id:
        :return:
        """
        admin = await self.get(db, admin_id)
        return admin.status

    async def get_multi_login(self, db: AsyncSession, admin_id: int) -> bool:
        """
        Get admin multipoint login status

        :param db:
        :param admin_id:
        :return:
        """
        admin = await self.get(db, admin_id)
        return admin.is_multi_login

    async def set_status(self, db: AsyncSession, admin_id: int, status: bool) -> int:
        """
        Set admin account status

        :param db:
        :param admin_id:
        :param status:
        :return:
        """
        return await self.update_model(db, admin_id, {'status': status})

    async def set_multi_login(self, db: AsyncSession, admin_id: int, multi_login: bool) -> int:
        """
        Set multi login

        :param db:
        :param admin_id:
        :param multi_login:
        :return:
        """
        return await self.update_model(db, admin_id, {'is_multi_login': multi_login})

    async def get_with_relation(self, db: AsyncSession, *, id: int = None, x_id: str = None, email: str = None, populates: list = []) -> User | None:
        """
        Get admin and (roles)

        :param db:
        :param admin_id:
        :param email:
        :return:
        """
        stmt = (
            select(self.model)
        )
            
        filters = []
        if id:
            filters.append(self.model.id == id)
        if email:
            filters.append(self.model.email == email)
        if x_id:
            filters.append(self.model.x_id == x_id)
            
        stmt = self.get_with_relationship(stmt, populates=populates)
        admin = await db.execute(stmt.where(*filters))
        return admin.scalars().first()


user_dao: CRUDUser = CRUDUser(User)
