"""multi login by default

`user.is_multi_login` shipped with contradictory defaults: `False` on the Python
side, `'1'` (true) on the server side. Because SQLAlchemy always sends the value
explicitly, every account was created single-session, and signing in anywhere
revoked every other session of that account.

Several live sessions per account is the wanted behaviour — the same person on a
phone and a laptop, an administrator demonstrating on two screens. This aligns
the column default and flips the accounts created before the change; an account
that must be limited to one session is set back to false individually.

Revision ID: c7d2f04a91e8
Revises: a1c4e7b90f21
Create Date: 2026-09-16 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2f04a91e8'
down_revision: Union[str, None] = 'a1c4e7b90f21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'user',
        'is_multi_login',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text('true'),
    )
    op.execute('UPDATE "user" SET is_multi_login = true WHERE is_multi_login = false')


def downgrade() -> None:
    op.alter_column(
        'user',
        'is_multi_login',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text('false'),
    )
    # Deliberately not reverting the rows: which accounts were single-session
    # before the upgrade is not recorded, and guessing would lock people out.
