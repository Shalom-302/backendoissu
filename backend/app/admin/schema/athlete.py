from datetime import date, datetime

from pydantic import ConfigDict, EmailStr, Field

from backend.common.enums import AthleteCategory, Discipline, EducationLevel, Gender
from backend.common.schema import SchemaBase


class AthleteProfileBase(SchemaBase):
    """The "fiche athlète" fields, shared by create / update / read."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    license_number: str = Field(min_length=1, max_length=64, description='OISSU licence number')
    discipline: Discipline | str
    speciality: str | None = None
    category: AthleteCategory | str | None = None
    club_or_establishment: str | None = None
    education_level: EducationLevel | str | None = None
    nationality: str | None = None
    gender: Gender | str | None = None
    date_of_birth: date | None = None
    photo_url: str | None = None


class RegisterAthleteRequest(AthleteProfileBase):
    """ADMIN-only payload: creates the login account AND the profile at once."""

    email: EmailStr
    password: str = Field(min_length=8, description='Initial password, hashed before storage')


class AthleteUpdate(SchemaBase):
    """Partial update of a profile (ADMIN). Every field is optional."""

    first_name: str | None = None
    last_name: str | None = None
    license_number: str | None = None
    discipline: Discipline | str | None = None
    speciality: str | None = None
    category: AthleteCategory | str | None = None
    club_or_establishment: str | None = None
    education_level: EducationLevel | str | None = None
    nationality: str | None = None
    gender: Gender | str | None = None
    date_of_birth: date | None = None
    photo_url: str | None = None


class AthleteSelfUpdate(SchemaBase):
    """What an athlete may change on their own profile.

    Identity, licence, discipline and category stay under ADMIN control: they
    are the reference data the championships and rankings are built on.
    """

    photo_url: str | None = None
    nationality: str | None = None
    date_of_birth: date | None = None


class AthleteResponse(AthleteProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    x_id: str
    user_id: int
    created_time: datetime
    updated_time: datetime | None = None


class AthleteListItem(AthleteResponse):
    """Row of the ADMIN athlete list — carries the account state.

    ``email`` and ``is_active`` are read from the owning ``User`` through the
    model properties of the same name, so the list shows the account state
    without a second round-trip.
    """

    email: str | None = None
    is_active: bool = True


class AthleteDetail(AthleteListItem):
    """Full athlete record, performance history included."""

    performance_count: int = 0
    performances: list['PerformanceResponse'] = []


class SetAthleteStatus(SchemaBase):
    is_active: bool


from backend.app.admin.schema.performance import PerformanceResponse  # noqa: E402

AthleteDetail.model_rebuild()
