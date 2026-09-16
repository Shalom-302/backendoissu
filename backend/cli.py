"""Project management commands that run *inside* the api container.

The host ``shaapi`` wrapper invokes these over ``docker compose exec``. For
example ``shaapi auth init`` runs, inside the container::

    python -m backend.cli create-admin --email you@example.com --password ...

Kept on argparse + asyncio (stdlib only) so it has no extra dependency beyond
the backend itself.
"""
from __future__ import annotations

import argparse
import asyncio


async def create_admin(email: str, password: str) -> int:
    """Create an admin user (idempotent) so you can log into Swagger."""
    from backend.app.admin.schema.user import UserRegister
    from backend.common.enums import Role as RoleEnum
    from backend.crud.crud_role import role_dao
    from backend.crud.crud_user import user_dao
    from backend.database.db_postgres import async_db_session
    from backend.models import Role

    async with async_db_session() as db:
        if await user_dao.get_by_email(db, email) is not None:
            print(f"[skip] A user with email {email} already exists.")
            return 0

        # user_dao.add() attaches the admin role *by name*, so make sure it
        # exists first. The Role model has no data_scope column, so we build it
        # directly rather than through CreateRoleParam.
        if await role_dao.get_by_name(db, RoleEnum.ADMIN.value) is None:
            db.add(Role(name=RoleEnum.ADMIN.value))
            await db.flush()

        await user_dao.add(db, UserRegister(email=email, password=password))
        await db.commit()

    print(f"[ok] Admin user created: {email}")
    print("     Log in at /api/v1/docs with this email and password.")
    return 0


def storage_init() -> int:
    """Ensure the configured object-storage bucket exists."""
    # Importing the singleton constructs the client, which creates the bucket
    # if it is missing (see MinioStorage.__init__).
    from backend.common.cloud_storage import mstorage
    from backend.core.conf import settings

    bucket = settings.MINIO_BUCKET_NAME
    if not mstorage.client.bucket_exists(bucket):
        mstorage.create_bucket()
        print(f"[ok] Created bucket: {bucket}")
    else:
        print(f"[skip] Bucket already exists: {bucket}")
    return 0


async def seed_demo(purge_only: bool) -> int:
    """Load (or remove) the pitchable demonstration dataset — doc §12.

    Refuses to run outside ``ENVIRONMENT=dev`` unless ``OISSU_SEED_FORCE`` is
    set: the demo data must never land in a production database (doc §17).
    """
    from backend.seeder.demo_seed import purge, seed

    return await (purge() if purge_only else seed())


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="backend.cli", description="OISSU CONNECT project management commands"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ca = sub.add_parser("create-admin", help="Create an admin user")
    ca.add_argument("--email", required=True, help="Admin email (login).")
    ca.add_argument("--password", required=True, help="Admin password.")

    sub.add_parser("storage-init", help="Ensure the object-storage bucket exists")

    sd = sub.add_parser("seed-demo", help="Load the demonstration dataset (dev only)")
    sd.add_argument(
        "--purge",
        action="store_true",
        help="Remove the demo dataset instead of creating it.",
    )

    args = parser.parse_args()
    if args.command == "create-admin":
        return asyncio.run(create_admin(args.email, args.password))
    if args.command == "storage-init":
        return storage_init()
    if args.command == "seed-demo":
        return asyncio.run(seed_demo(args.purge))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
