"""Pitchable demonstration dataset for OISSU CONNECT V1 (doc §12).

Everything this script writes is FICTIONAL. Names, schools, licences,
competitions and results are generated only so the dashboards, lists and charts
look credible during a presentation. None of it represents real OISSU data.

Two conventions make the demo data removable in one command when the real data
arrives (doc §18):

* every demo account uses the ``@oissu-demo.ci`` email domain;
* every demo licence starts with ``OISSU-DEMO-``.

``purge()`` deletes exactly those accounts; the profiles and performances follow
through ``ON DELETE CASCADE``.

Usage (inside the api container)::

    python -m backend.cli seed-demo
    python -m backend.cli seed-demo --purge
"""

from __future__ import annotations

import asyncio
import os
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, or_, select

from backend.common.enums import (
    AthleteCategory,
    Discipline,
    EducationLevel,
    Gender,
    MedalType,
)
from backend.common.enums import Role as RoleEnum
from backend.common.security.jwt import get_hash_password
from backend.core.conf import settings
from backend.database.db_postgres import async_db_session
from backend.models import Athlete, Performance, Role, User

# --- demo markers ---------------------------------------------------------
# The design document writes the demo addresses as `@oissu.local`, but `.local`
# is a reserved special-use name: `EmailStr` refuses it, so those accounts could
# be created and never logged into. `.ci` keeps the addresses obviously Ivorian
# and obviously fictional while staying a valid email domain.
DEMO_EMAIL_DOMAIN = 'oissu-demo.ci'

# Purged as well, so a database seeded before that fix is cleaned up too.
LEGACY_DEMO_EMAIL_DOMAINS = ('oissu.local',)

DEMO_LICENSE_PREFIX = 'OISSU-DEMO-'

DEFAULT_ADMIN_EMAIL = f'admin.demo@{DEMO_EMAIL_DOMAIN}'
DEFAULT_ADMIN_PASSWORD = 'OissuDemo2026!'
DEFAULT_ATHLETE_PASSWORD = 'AthleteDemo2026!'

ATHLETE_COUNT = 60
# A fixed seed keeps the demo reproducible: the same pitch, twice in a row.
RANDOM_SEED = 20260916

FIRST_NAMES_M = [
    'Koffi', 'Yao', 'Kouadio', 'Konan', 'Aboubacar', 'Ismaël', 'Sékou', 'Bakary',
    'Mamadou', 'Adama', 'Serge', 'Arsène', 'Didier', 'Franck', 'Wilfried',
    'Cheick', 'Ibrahim', 'Zié', 'Gnamien', 'Assoumane',
]
FIRST_NAMES_F = [
    'Aya', 'Adjoua', 'Affoué', 'Mariam', 'Fatoumata', 'Aminata', 'Rokia',
    'Nadège', 'Prisca', 'Ange', 'Djeneba', 'Salimata', 'Christelle', 'Emmanuella',
    'Naomi', 'Maimouna', 'Akissi', 'Grâce', 'Chantal', 'Sarah',
]
LAST_NAMES = [
    "N'Guessan", 'Koné', 'Traoré', 'Ouattara', 'Bamba', 'Diomandé', 'Kouassi',
    'Yapi', 'Gbagbo', 'Zadi', 'Sangaré', 'Cissé', 'Doumbia', 'Touré', 'Silué',
    'Adou', 'Brou', 'Kacou', 'Loba', 'Tanoh', 'Dosso', 'Fofana', 'Gnahoré',
]

ESTABLISHMENTS = [
    'Lycée Moderne Exemple',
    'Collège National Démonstration',
    'Université Ivoire Sport',
    'Établissement Pilote OISSU',
    'Lycée Municipal Fictif',
    'Collège Sainte-Démo',
    'Institut Sportif Témoin',
    'Université Modèle Abidjan',
]

CITIES = [
    'Abidjan', 'Yamoussoukro', 'Bouaké', 'Daloa', 'San-Pédro',
    'Korhogo', 'Man', 'Gagnoa',
]

# (event, unit, best plausible value, worst plausible value)
# A time unit means lower is better; metres and points improve upward.
EVENTS: dict[str, list[tuple[str, str, float, float]]] = {
    Discipline.ATHLETISME.value: [
        ('100 m', 's', 10.6, 13.8),
        ('200 m', 's', 21.4, 28.0),
        ('400 m', 's', 47.5, 62.0),
        ('800 m', 's', 112.0, 145.0),
        ('Saut en longueur', 'm', 7.9, 4.8),
        ('Saut en hauteur', 'm', 2.15, 1.40),
        ('Lancer de poids', 'm', 17.5, 8.5),
    ],
    Discipline.NATATION.value: [
        ('50 m nage libre', 's', 23.8, 34.0),
        ('100 m nage libre', 's', 52.6, 76.0),
        ('100 m brasse', 's', 64.0, 96.0),
    ],
    Discipline.FOOTBALL.value: [('Buts marqués', 'pts', 5.0, 0.0)],
    Discipline.BASKETBALL.value: [('Points marqués', 'pts', 34.0, 4.0)],
    Discipline.HANDBALL.value: [('Buts marqués', 'pts', 13.0, 1.0)],
    Discipline.VOLLEYBALL.value: [('Points marqués', 'pts', 26.0, 3.0)],
}

# name, level; dates are drawn per season so the charts span several years.
COMPETITIONS = [
    ('Championnat scolaire régional', 'régional'),
    ('Tournoi inter-établissements', 'départemental'),
    ('Finale nationale OISSU', 'national'),
    ('Meeting universitaire de printemps', 'universitaire'),
    ('Coupe du sport scolaire', 'régional'),
    ('Journée de détection OISSU', 'départemental'),
    ('Challenge inter-régions', 'national'),
    ('Grand prix scolaire de la Lagune', 'régional'),
]

# Three full seasons, so "évolution par saison" has something to show.
SEASONS = [(2023, 2024), (2024, 2025), (2025, 2026)]


def _is_time(unit: str) -> bool:
    return unit == 's'


def _draw_result(best: float, worst: float, talent: float, progress: float, rng: random.Random) -> Decimal:
    """Draw one plausible result.

    ``talent`` (0 = modest, 1 = excellent) places the athlete on the range,
    ``progress`` (0 = first season, 1 = latest) nudges them towards their best
    over time, and a little noise keeps the curve from looking synthetic.
    """
    skill = min(1.0, max(0.0, talent * 0.75 + progress * 0.25 + rng.uniform(-0.08, 0.08)))
    value = worst + (best - worst) * skill
    return Decimal(f'{value:.2f}')


def _season_dates(start_year: int, rng: random.Random) -> list[date]:
    """A handful of competition days spread over one school season."""
    anchors = [
        date(start_year, 10, 14),
        date(start_year, 12, 9),
        date(start_year + 1, 2, 17),
        date(start_year + 1, 4, 13),
        date(start_year + 1, 6, 8),
    ]
    return [day + timedelta(days=rng.randint(-6, 6)) for day in anchors]


def _medal_for(ranking: int) -> str | None:
    return {1: MedalType.OR.value, 2: MedalType.ARGENT.value, 3: MedalType.BRONZE.value}.get(ranking)


async def _get_or_create_role(db, name: str) -> Role:
    role = (await db.execute(select(Role).where(Role.name == name))).scalars().first()
    if role is None:
        role = Role(name=name)
        db.add(role)
        await db.flush()
    return role


async def seed() -> int:
    """Create the full demonstration dataset. Idempotent: purges first."""
    if settings.ENVIRONMENT != 'dev' and not os.getenv('OISSU_SEED_FORCE'):
        print(
            f'[abort] ENVIRONMENT={settings.ENVIRONMENT!r}. The demo seed is for '
            'development databases only (doc §17). Set OISSU_SEED_FORCE=1 to '
            'override on a throwaway environment.'
        )
        return 1

    rng = random.Random(RANDOM_SEED)
    admin_email = os.getenv('ADMIN_EMAIL', DEFAULT_ADMIN_EMAIL)
    admin_password = os.getenv('ADMIN_PASSWORD', DEFAULT_ADMIN_PASSWORD)
    athlete_password = os.getenv('DEMO_ATHLETE_PASSWORD', DEFAULT_ATHLETE_PASSWORD)

    await purge(quiet=True)

    # bcrypt is deliberately slow. Every demo athlete shares one password, so
    # hashing it once and reusing the digest turns a ~20s seed into an instant
    # one without weakening anything: these accounts are throwaway by design.
    athlete_salt = 'demo0'
    athlete_hash = get_hash_password(f'{athlete_password}{athlete_salt}')
    admin_salt = 'demo1'
    admin_hash = get_hash_password(f'{admin_password}{admin_salt}')

    disciplines = [d.value for d in Discipline]
    categories = [c.value for c in AthleteCategory]
    education_levels = [e.value for e in EducationLevel]

    async with async_db_session.begin() as db:
        admin_role = await _get_or_create_role(db, RoleEnum.ADMIN.value)
        user_role = await _get_or_create_role(db, RoleEnum.USER.value)

        admin = User(email=admin_email, password=admin_hash, salt=admin_salt)
        admin.roles.append(admin_role)
        db.add(admin)

        performance_total = 0
        for index in range(1, ATHLETE_COUNT + 1):
            gender = rng.choice([Gender.MALE.value, Gender.FEMALE.value])
            first_name = rng.choice(FIRST_NAMES_M if gender == Gender.MALE.value else FIRST_NAMES_F)
            last_name = rng.choice(LAST_NAMES)
            discipline = rng.choice(disciplines)
            event_name, unit, best, worst = rng.choice(EVENTS[discipline])
            category = rng.choice(categories)

            license_number = f'{DEMO_LICENSE_PREFIX}{index:04d}'
            email = f'athlete{index:03d}@{DEMO_EMAIL_DOMAIN}'

            user = User(email=email, password=athlete_hash, salt=athlete_salt)
            user.firstname = first_name
            user.lastname = last_name
            user.roles.append(user_role)
            # A few inactive accounts so "athlètes actifs" is not just the total.
            user.status = index % 17 != 0
            db.add(user)
            await db.flush()

            birth_year = {
                AthleteCategory.MINIME.value: 2011,
                AthleteCategory.CADET.value: 2009,
                AthleteCategory.JUNIOR.value: 2007,
                AthleteCategory.SENIOR.value: 2003,
            }[category]

            athlete = Athlete(
                user_id=user.id,
                license_number=license_number,
                first_name=first_name,
                last_name=last_name,
                discipline=discipline,
                speciality=event_name,
                category=category,
                club_or_establishment=rng.choice(ESTABLISHMENTS),
                education_level=rng.choice(education_levels),
                nationality='Ivoirienne',
                gender=gender,
                date_of_birth=date(birth_year, rng.randint(1, 12), rng.randint(1, 28)),
            )
            db.add(athlete)
            await db.flush()

            talent = rng.random()
            for season_index, (start_year, _) in enumerate(SEASONS):
                progress = season_index / max(1, len(SEASONS) - 1)
                days = _season_dates(start_year, rng)
                for day in rng.sample(days, rng.randint(1, 3)):
                    competition_name, level = rng.choice(COMPETITIONS)
                    ranking = rng.choices(
                        [1, 2, 3, 4, 5, 6, 8, 11], weights=[6, 6, 6, 5, 5, 4, 3, 3]
                    )[0]
                    db.add(
                        Performance(
                            athlete_id=athlete.id,
                            competition_name=f'{competition_name} {start_year}',
                            competition_date=day,
                            discipline=discipline,
                            event=event_name,
                            result=_draw_result(best, worst, talent, progress, rng),
                            unit=unit,
                            location=rng.choice(CITIES),
                            ranking=ranking,
                            medal=_medal_for(ranking),
                            observations=(
                                f'Épreuve {level} — données de démonstration, non officielles.'
                            ),
                        )
                    )
                    performance_total += 1

    print(f'[ok] Demo dataset created: 1 admin, {ATHLETE_COUNT} athletes, {performance_total} performances.')
    print()
    print(f'  ADMIN    {admin_email} / {admin_password}')
    print(f'  ATHLETES athlete001@{DEMO_EMAIL_DOMAIN} ... '
          f'athlete{ATHLETE_COUNT:03d}@{DEMO_EMAIL_DOMAIN}')
    print(f'           all of them share the password {athlete_password}')
    print()
    print('  Every athlete owns a real account: their own login, their own profile')
    print('  and their own performances. Sign in as any of them to see the USER space.')
    print('  All identities, schools, competitions and results are FICTIONAL (doc §12).')
    return 0


async def purge(*, quiet: bool = False) -> int:
    """Remove every demo record.

    Only the accounts are deleted: ``athlete.user_id`` and
    ``performance.athlete_id`` are ``ON DELETE CASCADE``, so the profiles and
    the history go with them and nothing is orphaned (doc §18).
    """
    domains = (DEMO_EMAIL_DOMAIN, *LEGACY_DEMO_EMAIL_DOMAINS)
    patterns = [User.email.like(f'%@{domain}') for domain in domains]

    async with async_db_session.begin() as db:
        before = (
            await db.execute(select(func.count(User.id)).where(or_(*patterns)))
        ).scalar_one()
        await db.execute(delete(User).where(or_(*patterns)))
        # Defensive: a licence left behind by a partial import is demo data too.
        await db.execute(
            delete(Athlete).where(Athlete.license_number.like(f'{DEMO_LICENSE_PREFIX}%'))
        )

    if not quiet:
        print(f'[ok] Removed {before} demo accounts and everything attached to them.')
    return 0


if __name__ == '__main__':
    import sys

    raise SystemExit(
        asyncio.run(purge() if '--purge' in sys.argv else seed())
    )
