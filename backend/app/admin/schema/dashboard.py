from datetime import date
from decimal import Decimal

from backend.app.admin.schema.athlete import AthleteResponse
from backend.app.admin.schema.performance import PerformanceListItem, PerformanceResponse
from backend.common.schema import SchemaBase


class MedalCount(SchemaBase):
    """Distinctions tally."""

    gold: int = 0
    silver: int = 0
    bronze: int = 0

    @property
    def total(self) -> int:
        return self.gold + self.silver + self.bronze


class EvolutionPoint(SchemaBase):
    """One point of a progression chart (a competition day)."""

    competition_date: date
    competition_name: str
    event: str
    result: Decimal
    unit: str
    ranking: int | None = None
    season: str


class SeasonSummary(SchemaBase):
    """Aggregate of a whole season, for the season-by-season view."""

    season: str
    performances: int = 0
    competitions: int = 0
    medals: int = 0
    best_result: Decimal | None = None
    average_ranking: float | None = None


class BestResult(SchemaBase):
    """Best mark held on one event."""

    discipline: str
    event: str
    result: Decimal
    unit: str
    competition_name: str
    competition_date: date
    athlete_name: str | None = None


class UserDashboardResponse(SchemaBase):
    """Personal dashboard of the authenticated athlete (doc §13)."""

    athlete: AthleteResponse
    total_performances: int = 0
    total_competitions: int = 0
    best_ranking: int | None = None
    medals: MedalCount = MedalCount()
    latest_performances: list[PerformanceResponse] = []
    best_results: list[BestResult] = []
    evolution: list[EvolutionPoint] = []
    seasons: list[SeasonSummary] = []


class DisciplineStat(SchemaBase):
    discipline: str
    athletes: int = 0
    performances: int = 0
    medals: int = 0


class PeriodStat(SchemaBase):
    """Activity over one calendar month (``YYYY-MM``)."""

    period: str
    performances: int = 0
    competitions: int = 0
    medals: int = 0


class AdminDashboardResponse(SchemaBase):
    """Global steering dashboard (doc §14)."""

    total_athletes: int = 0
    active_athletes: int = 0
    total_disciplines: int = 0
    total_competitions: int = 0
    total_performances: int = 0
    total_establishments: int = 0
    medals: MedalCount = MedalCount()
    best_results: list[BestResult] = []
    latest_performances: list[PerformanceListItem] = []
    by_discipline: list[DisciplineStat] = []
    by_period: list[PeriodStat] = []
    seasons: list[SeasonSummary] = []
