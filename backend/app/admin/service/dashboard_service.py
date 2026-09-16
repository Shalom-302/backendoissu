"""Dashboard aggregations for the USER and ADMIN spaces (doc §11.4, §13, §14)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import Request

from backend.app.admin.schema.athlete import AthleteResponse
from backend.app.admin.schema.dashboard import (
    AdminDashboardResponse,
    BestResult,
    DisciplineStat,
    MedalCount,
    PeriodStat,
    SeasonSummary,
    UserDashboardResponse,
)
from backend.app.admin.schema.performance import (
    PerformanceListItem,
    PerformanceResponse,
    season_of,
)
from backend.app.admin.service.performance_service import PerformanceService
from backend.common.enums import MedalType
from backend.common.exception import errors
from backend.crud.crud_athlete import athlete_dao
from backend.crud.crud_performance import performance_dao
from backend.database.db_postgres import async_db_session
from backend.models import Performance
from backend.utils.translator import Translator

# Units where a *smaller* number is a better performance (races, swims).
# Everything else (metres, points) improves upward.
LOWER_IS_BETTER_UNITS = {'s', 'sec', 'ms', 'min', 'h'}

LATEST_PERFORMANCES = 5
ADMIN_LATEST_PERFORMANCES = 10
TOP_RESULTS = 5


def _is_lower_better(unit: str) -> bool:
    """Whether a lower value means a better result for this unit."""
    return (unit or '').strip().lower() in LOWER_IS_BETTER_UNITS


def _pick_best(performances: list[Performance]) -> Performance:
    """Best mark of a homogeneous group (same event, same unit)."""
    key = lambda p: p.result  # noqa: E731
    return min(performances, key=key) if _is_lower_better(performances[0].unit) else max(
        performances, key=key
    )


def _best_results(performances: list[Performance], *, with_name: bool = False) -> list[BestResult]:
    """One best mark per (discipline, event) pair."""
    groups: dict[tuple[str, str], list[Performance]] = defaultdict(list)
    for performance in performances:
        groups[(performance.discipline, performance.event)].append(performance)

    results = []
    for (discipline, event), group in groups.items():
        best = _pick_best(group)
        results.append(
            BestResult(
                discipline=discipline,
                event=event,
                result=best.result,
                unit=best.unit,
                competition_name=best.competition_name,
                competition_date=best.competition_date,
                athlete_name=best.athlete_name if with_name else None,
            )
        )
    return sorted(results, key=lambda r: (r.discipline, r.event))


def _medal_count(tally: dict[str, int]) -> MedalCount:
    """Map the raw ``{label: count}`` tally onto the response schema."""
    return MedalCount(
        gold=tally.get(MedalType.OR.value, 0),
        silver=tally.get(MedalType.ARGENT.value, 0),
        bronze=tally.get(MedalType.BRONZE.value, 0),
    )


def _season_of_period(period: str) -> str:
    """Season a ``YYYY-MM`` period belongs to."""
    year, month = (int(part) for part in period.split('-'))
    return season_of(date(year, month, 1))


class DashboardService:
    @staticmethod
    async def user_dashboard(*, request: Request) -> UserDashboardResponse:
        """Personal dashboard of the authenticated athlete (doc §13)."""
        translator = Translator(request.state.locale)
        async with async_db_session() as db:
            athlete = await athlete_dao.get_by_user_id(db, request.user.id)
            if not athlete:
                raise errors.NotFoundError(msg=translator.t('athlete.no_profile'))

            performances = await performance_dao.get_by_athlete(db, athlete.id)
            medals = _medal_count(await performance_dao.count_medals(db, athlete_id=athlete.id))
            competitions = await performance_dao.count_competitions(db, athlete_id=athlete.id)
            best_ranking = await performance_dao.best_ranking(db, athlete.id)

        return UserDashboardResponse(
            athlete=AthleteResponse.model_validate(athlete),
            total_performances=len(performances),
            total_competitions=competitions,
            best_ranking=best_ranking,
            medals=medals,
            latest_performances=[
                PerformanceResponse.model_validate(p) for p in performances[:LATEST_PERFORMANCES]
            ],
            best_results=_best_results(performances),
            evolution=PerformanceService.build_evolution(performances),
            seasons=DashboardService._seasons(performances),
        )

    @staticmethod
    async def admin_dashboard(*, request: Request) -> AdminDashboardResponse:
        """Global steering dashboard (doc §14)."""
        async with async_db_session() as db:
            total_athletes = await athlete_dao.count(db)
            active_athletes = await athlete_dao.count_active(db)

            total_performances = await performance_dao.count(db)
            total_competitions = await performance_dao.count_competitions(db)
            total_establishments = await performance_dao.count_establishments(db)
            disciplines = await athlete_dao.get_disciplines(db)
            medals = _medal_count(await performance_dao.count_medals(db))

            by_discipline_rows = await performance_dao.stats_by_discipline(db)
            athletes_per_discipline = await performance_dao.athletes_by_discipline(db)
            by_month = await performance_dao.stats_by_month(db)

            top = await performance_dao.top_results(db, limit=TOP_RESULTS)
            latest = await performance_dao.latest(db, limit=ADMIN_LATEST_PERFORMANCES)

        by_period = [
            PeriodStat(period=period, performances=perf, competitions=comp, medals=medal)
            for period, perf, comp, medal in by_month
        ]

        return AdminDashboardResponse(
            total_athletes=total_athletes,
            active_athletes=active_athletes,
            total_disciplines=len(disciplines),
            total_competitions=total_competitions,
            total_performances=total_performances,
            total_establishments=total_establishments,
            medals=medals,
            best_results=_best_results(top, with_name=True),
            latest_performances=[PerformanceListItem.model_validate(p) for p in latest],
            by_discipline=[
                DisciplineStat(
                    discipline=discipline,
                    athletes=athletes_per_discipline.get(discipline, 0),
                    performances=performances,
                    medals=medal_total,
                )
                for discipline, performances, medal_total in by_discipline_rows
            ],
            by_period=by_period,
            seasons=DashboardService._seasons_from_periods(by_period),
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _seasons(performances: list[Performance]) -> list[SeasonSummary]:
        """Season-by-season recap of one athlete's history (doc §13)."""
        groups: dict[str, list[Performance]] = defaultdict(list)
        for performance in performances:
            groups[season_of(performance.competition_date)].append(performance)

        summaries = []
        for season, group in groups.items():
            rankings = [p.ranking for p in group if p.ranking is not None]
            best = _pick_best(group)
            summaries.append(
                SeasonSummary(
                    season=season,
                    performances=len(group),
                    competitions=len({p.competition_name for p in group}),
                    medals=len([p for p in group if p.medal]),
                    best_result=Decimal(best.result),
                    average_ranking=round(sum(rankings) / len(rankings), 2) if rankings else None,
                )
            )
        return sorted(summaries, key=lambda s: s.season)

    @staticmethod
    def _seasons_from_periods(periods: list[PeriodStat]) -> list[SeasonSummary]:
        """Roll monthly activity up into seasons for the ADMIN view."""
        summaries: dict[str, SeasonSummary] = {}
        for period in periods:
            season = _season_of_period(period.period)
            summary = summaries.setdefault(season, SeasonSummary(season=season))
            summary.performances += period.performances
            summary.competitions += period.competitions
            summary.medals += period.medals
        return sorted(summaries.values(), key=lambda s: s.season)


dashboard_service = DashboardService()
