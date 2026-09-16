"""athlete and performance

OISSU CONNECT V1 domain tables (doc §7, §8):
  User 1 --- 1 Athlete        Athlete 1 --- N Performance

Revision ID: a1c4e7b90f21
Revises: 64524c63b666
Create Date: 2026-09-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c4e7b90f21'
down_revision: Union[str, None] = '64524c63b666'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'athlete',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='Primary key id'),
        sa.Column('x_id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='Owning user account'),
        sa.Column('license_number', sa.String(length=64), nullable=False, comment='OISSU licence / identifier'),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('discipline', sa.String(length=100), nullable=False, comment='Main discipline'),
        sa.Column('speciality', sa.String(length=100), nullable=True, comment='Event / speciality'),
        sa.Column('category', sa.String(length=50), nullable=True, comment='Age category'),
        sa.Column('club_or_establishment', sa.String(length=200), nullable=True, comment='Club, school or federation'),
        sa.Column('education_level', sa.String(length=50), nullable=True),
        sa.Column('nationality', sa.String(length=100), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('photo_url', sa.String(length=500), nullable=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='Creation time'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='update time'),
        # CASCADE: deleting the account removes the profile, so no athlete can
        # survive the user it belongs to.
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('x_id'),
    )
    op.create_index(op.f('ix_athlete_id'), 'athlete', ['id'], unique=False)
    op.create_index(op.f('ix_athlete_user_id'), 'athlete', ['user_id'], unique=True)
    op.create_index(op.f('ix_athlete_license_number'), 'athlete', ['license_number'], unique=True)
    op.create_index(op.f('ix_athlete_first_name'), 'athlete', ['first_name'], unique=False)
    op.create_index(op.f('ix_athlete_last_name'), 'athlete', ['last_name'], unique=False)
    op.create_index(op.f('ix_athlete_discipline'), 'athlete', ['discipline'], unique=False)
    op.create_index(op.f('ix_athlete_category'), 'athlete', ['category'], unique=False)
    op.create_index(
        op.f('ix_athlete_club_or_establishment'), 'athlete', ['club_or_establishment'], unique=False
    )

    op.create_table(
        'performance',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='Primary key id'),
        sa.Column('x_id', sa.String(length=32), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False, comment='Owning athlete'),
        sa.Column('competition_name', sa.String(length=200), nullable=False),
        sa.Column('competition_date', sa.Date(), nullable=False),
        sa.Column('discipline', sa.String(length=100), nullable=False),
        sa.Column('event', sa.String(length=100), nullable=False, comment='Event / speciality'),
        sa.Column('result', sa.Numeric(precision=10, scale=3), nullable=False, comment='Numeric result, see `unit`'),
        sa.Column('unit', sa.String(length=20), nullable=False, comment='s, m, cm, pts…'),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('ranking', sa.Integer(), nullable=True, comment='Final ranking (1 = winner)'),
        sa.Column('medal', sa.String(length=20), nullable=True),
        sa.Column('observations', sa.Text(), nullable=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='Creation time'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='update time'),
        sa.ForeignKeyConstraint(['athlete_id'], ['athlete.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('x_id'),
    )
    op.create_index(op.f('ix_performance_id'), 'performance', ['id'], unique=False)
    op.create_index(op.f('ix_performance_athlete_id'), 'performance', ['athlete_id'], unique=False)
    op.create_index(
        op.f('ix_performance_competition_name'), 'performance', ['competition_name'], unique=False
    )
    op.create_index(
        op.f('ix_performance_competition_date'), 'performance', ['competition_date'], unique=False
    )
    op.create_index(op.f('ix_performance_discipline'), 'performance', ['discipline'], unique=False)
    op.create_index(op.f('ix_performance_medal'), 'performance', ['medal'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_performance_medal'), table_name='performance')
    op.drop_index(op.f('ix_performance_discipline'), table_name='performance')
    op.drop_index(op.f('ix_performance_competition_date'), table_name='performance')
    op.drop_index(op.f('ix_performance_competition_name'), table_name='performance')
    op.drop_index(op.f('ix_performance_athlete_id'), table_name='performance')
    op.drop_index(op.f('ix_performance_id'), table_name='performance')
    op.drop_table('performance')

    op.drop_index(op.f('ix_athlete_club_or_establishment'), table_name='athlete')
    op.drop_index(op.f('ix_athlete_category'), table_name='athlete')
    op.drop_index(op.f('ix_athlete_discipline'), table_name='athlete')
    op.drop_index(op.f('ix_athlete_last_name'), table_name='athlete')
    op.drop_index(op.f('ix_athlete_first_name'), table_name='athlete')
    op.drop_index(op.f('ix_athlete_license_number'), table_name='athlete')
    op.drop_index(op.f('ix_athlete_user_id'), table_name='athlete')
    op.drop_index(op.f('ix_athlete_id'), table_name='athlete')
    op.drop_table('athlete')
