"""Basic model types and validators for them."""

import enum
import re
from typing import Dict, Iterable, Optional, NewType, Final, FrozenSet, Tuple

import pendulum
import pendulum.parsing.exceptions


class ModelValidationError(Exception):
    """An exception raised when validating some model type."""


@enum.unique
class SyncPrefer(enum.Enum):
    """The source of data to prefer for a sync operation."""
    LOCAL = "local"
    NOTION = "notion"


EntityId = NewType("EntityId", str)


EntityName = NewType("EntityName", str)


WorkspaceSpaceId = NewType("WorkspaceSpaceId", str)


WorkspaceToken = NewType("WorkspaceToken", str)


ProjectKey = NewType("ProjectKey", str)


@enum.unique
class Eisen(enum.Enum):
    """The Eisenhower status of a particular task."""
    IMPORTANT = "important"
    URGENT = "urgent"

    def for_notion(self) -> str:
        """A prettier version of the value for Notion."""
        return str(self.value).capitalize()


@enum.unique
class Difficulty(enum.Enum):
    """The difficulty of a particular task."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    def for_notion(self) -> str:
        """A prettier version of the value for Notion."""
        return str(self.value).capitalize()


@enum.unique
class InboxTaskStatus(enum.Enum):
    """The status of an inbox task."""
    NOT_STARTED = "not-started"
    ACCEPTED = "accepted"
    RECURRING = "recurring"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    NOT_DONE = "not-done"
    DONE = "done"

    def for_notion(self) -> str:
        """A prettier version of the value for Notion."""
        return " ".join(s.capitalize() for s in str(self.value).split("-"))


@enum.unique
class RecurringTaskPeriod(enum.Enum):
    """A period for a particular task."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

    def for_notion(self) -> str:
        """A prettier version of the value for Notion."""
        return str(self.value).capitalize()


@enum.unique
class BigPlanStatus(enum.Enum):
    """The status of a big plan."""
    NOT_STARTED = "not-started"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    NOT_DONE = "not-done"
    DONE = "done"

    def for_notion(self) -> str:
        """A prettier version of the value for Notion."""
        return " ".join(s.capitalize() for s in str(self.value).split("-"))


class BasicValidator:
    """A validator class for various basic model types."""

    _sync_prefer_values: Final[FrozenSet[str]] = frozenset(sp.value for sp in SyncPrefer)
    _entity_id_re: Final[re.Pattern] = re.compile(r"^\d+$")
    _entity_name_re: Final[re.Pattern] = re.compile(r"^.+$")
    _workspace_space_id_re: Final[re.Pattern] = re.compile(r"^[0-9a-z-]{36}$")
    _workspace_token_re: Final[re.Pattern] = re.compile(r"^[0-9a-f]+$")
    _project_key_re: Final[re.Pattern] = re.compile(r"^[a-z0-9]([a-z0-9]*-?)*$")
    _default_tz: Final[str] = "UTC"
    _eisen_values: Final[FrozenSet[str]] = frozenset(e.value for e in Eisen)
    _difficulty_values: Final[FrozenSet[str]] = frozenset(d.value for d in Difficulty)
    _inbox_task_status_values: Final[FrozenSet[str]] = frozenset(its.value for its in InboxTaskStatus)
    _recurring_task_period_values: Final[FrozenSet[str]] = frozenset(rtp.value for rtp in RecurringTaskPeriod)
    _recurring_task_due_at_time_re: Final[re.Pattern] = re.compile(r"^[0-9][0-9]:[0-9][0-9]$")
    _recurring_task_due_at_day_bounds: Final[Dict[RecurringTaskPeriod, Tuple[int, int]]] = {
        RecurringTaskPeriod.DAILY: (0, 0),
        RecurringTaskPeriod.WEEKLY: (0, 6),
        RecurringTaskPeriod.MONTHLY: (0, 31),
        RecurringTaskPeriod.QUARTERLY: (0, 31),
        RecurringTaskPeriod.YEARLY: (0, 31)
    }
    _recurring_task_due_at_month_bounds: Final[Dict[RecurringTaskPeriod, Tuple[int, int]]] = {
        RecurringTaskPeriod.DAILY: (0, 0),
        RecurringTaskPeriod.WEEKLY: (0, 0),
        RecurringTaskPeriod.MONTHLY: (0, 0),
        RecurringTaskPeriod.QUARTERLY: (0, 2),
        RecurringTaskPeriod.YEARLY: (0, 12)
    }
    _big_plan_status_values: Final[FrozenSet[str]] = frozenset(bps.value for bps in BigPlanStatus)

    def sync_prefer_validate_and_clean(self, sync_prefer_raw: Optional[str]) -> SyncPrefer:
        """Validate and clean the big plan status."""
        if not sync_prefer_raw:
            raise ModelValidationError("Expected sync prefer to be non-null")

        sync_prefer_str: str = sync_prefer_raw.strip().lower()

        if sync_prefer_str not in self._sync_prefer_values:
            raise ModelValidationError(
                f"Expected sync prefer '{sync_prefer_raw}' for be one of '{','.join(self._sync_prefer_values)}'")

        return SyncPrefer(sync_prefer_str)

    @staticmethod
    def sync_prefer_values() -> Iterable[str]:
        """The possible values for sync prefer."""
        return BasicValidator._sync_prefer_values

    def entity_id_validate_and_clean(self, entity_id_raw: Optional[str]) -> EntityId:
        """Validate and clean an entity id."""
        if not entity_id_raw:
            raise ModelValidationError("Expected entity id to be non-null")

        entity_id: str = entity_id_raw.strip()

        if len(entity_id) == 0:
            raise ModelValidationError("Expected entity id to be non-empty")

        if not self._entity_id_re.match(entity_id):
            raise ModelValidationError(f"Expected entity id '{entity_id_raw}' to match '{self._entity_id_re.pattern}")

        return EntityId(entity_id)

    def entity_name_validate_and_clean(self, entity_name_raw: Optional[str]) -> EntityName:
        """Validate and clean an entity name."""
        if not entity_name_raw:
            raise ModelValidationError("Expected entity name to be non-null")

        entity_name: str = " ".join(word for word in entity_name_raw.strip().split(" ") if len(word) > 0)

        if len(entity_name) == 0:
            raise ModelValidationError("Expected entity name to be non-empty")

        if not self._entity_name_re.match(entity_name):
            raise ModelValidationError(
                f"Expected entity id '{entity_name_raw}' to match '{self._entity_name_re.pattern}")

        return EntityName(entity_name)

    def workspace_space_id_validate_and_clean(self, workspace_space_id_raw: Optional[str]) -> WorkspaceSpaceId:
        """Validate and clean a workspace space id."""
        if not workspace_space_id_raw:
            raise ModelValidationError("Expected workspace space id to be non-null")

        workspace_space_id: str = workspace_space_id_raw.strip().lower()

        if len(workspace_space_id) == 0:
            raise ModelValidationError("Expected workspace space id to be non-empty")

        if not self._workspace_space_id_re.match(workspace_space_id):
            raise ModelValidationError(
                f"Expected workspace space id '{workspace_space_id}' to match '{self._workspace_space_id_re.pattern}")

        return WorkspaceSpaceId(workspace_space_id)

    def workspace_token_validate_and_clean(self, workspace_token_raw: Optional[str]) -> WorkspaceToken:
        """Validate and clean a workspace token."""
        if not workspace_token_raw:
            raise ModelValidationError("Expected workspace token to be non-null")

        workspace_token: str = workspace_token_raw.strip().lower()

        if len(workspace_token) == 0:
            raise ModelValidationError("Expected workspace token to be non-empty")

        if not self._workspace_token_re.match(workspace_token):
            raise ModelValidationError(
                f"Expected workspace token '{workspace_token}' to match '{self._workspace_token_re.pattern}")

        return WorkspaceToken(workspace_token)

    def project_key_validate_and_clean(self, project_key_raw: Optional[str]) -> ProjectKey:
        """Validate and clean a project key."""
        if not project_key_raw:
            raise ModelValidationError("Expected project key to be non-null")

        project_key_str: str = project_key_raw.strip().lower()

        if len(project_key_str) == 0:
            raise ModelValidationError("Expected project key to be non-empty")

        if not self._project_key_re.match(project_key_str):
            raise ModelValidationError(
                f"Expected project key '{project_key_raw}' to match '{self._project_key_re.pattern}'")

        return ProjectKey(project_key_str)

    def datetime_validate_and_clean(self, datetime_raw: Optional[str]) -> pendulum.DateTime:
        """Validate and clean an optional datetime."""
        if not datetime_raw:
            raise ModelValidationError("Expected datetime to be non-null")

        try:
            the_datetime = pendulum.parse(datetime_raw, tz=self._default_tz)

            if not isinstance(the_datetime, pendulum.DateTime):
                raise ModelValidationError(f"Expected datetime '{datetime_raw}' to be in a proper datetime format")

            return the_datetime
        except pendulum.parsing.exceptions.ParserError as error:
            raise ModelValidationError(f"Expected datetime '{datetime_raw}' to be in a proper format") from error

    def date_validate_and_clean(self, date_raw: Optional[str]) -> pendulum.DateTime:
        """Validate and clean an optional date."""
        if not date_raw:
            raise ModelValidationError("Expected date to be non-null")

        try:
            the_datetime = pendulum.parse(date_raw, tz=self._default_tz)

            if not isinstance(the_datetime, pendulum.DateTime):
                raise ModelValidationError(f"Expected datetime '{date_raw}' to be in a proper datetime format")

            return the_datetime.end_of("day")
        except pendulum.parsing.exceptions.ParserError as error:
            raise ModelValidationError(f"Expected datetime '{date_raw}' to be in a proper format") from error

    def eisen_validate_and_clean(self, eisen_raw: Optional[str]) -> Eisen:
        """Validate and clean the Eisenhower status."""
        if not eisen_raw:
            raise ModelValidationError("Expected Eisenhower status to be non-null")

        eisen_str: str = eisen_raw.strip().lower()

        if eisen_str not in self._eisen_values:
            raise ModelValidationError(
                f"Expected Eisenhower status '{eisen_raw}' for be one of '{','.join(self._eisen_values)}'")

        return Eisen(eisen_str)

    @staticmethod
    def eisen_values() -> Iterable[str]:
        """The possible values for Eisenhower statues."""
        return BasicValidator._eisen_values

    def difficulty_validate_and_clean(self, difficulty_raw: Optional[str]) -> Difficulty:
        """Validate and clean the difficulty."""
        if not difficulty_raw:
            raise ModelValidationError("Expected difficulty to be non-null")

        difficulty_str: str = difficulty_raw.strip().lower()

        if difficulty_str not in self._difficulty_values:
            raise ModelValidationError(
                f"Expected difficulty '{difficulty_raw}' for be one of '{','.join(self._difficulty_values)}'")

        return Difficulty(difficulty_str)

    @staticmethod
    def difficulty_values() -> Iterable[str]:
        """The possible values for difficulty."""
        return BasicValidator._difficulty_values

    def inbox_task_status_validate_and_clean(self, inbox_task_status_raw: Optional[str]) -> BigPlanStatus:
        """Validate and clean the big plan status."""
        if not inbox_task_status_raw:
            raise ModelValidationError("Expected inbox task status to be non-null")

        inbox_task_status_str: str = inbox_task_status_raw.strip().lower()

        if inbox_task_status_str not in self._inbox_task_status_values:
            raise ModelValidationError(
                f"Expected inbox task status '{inbox_task_status_raw}' for be " +
                "one of '{','.join(self._inbox_task_status_values)}'")

        return BigPlanStatus(inbox_task_status_str)

    @staticmethod
    def inbox_task_status_values() -> Iterable[str]:
        """The possible values for inbox task statues."""
        return BasicValidator._inbox_task_status_values

    def recurring_task_period_validate_and_clean(self, recurring_task_period_raw: Optional[str]) -> RecurringTaskPeriod:
        """Validate and clean the big plan status."""
        if not recurring_task_period_raw:
            raise ModelValidationError("Expected big plan status to be non-null")

        recurring_task_period_str: str = recurring_task_period_raw.strip().lower()

        if recurring_task_period_str not in self._recurring_task_period_values:
            raise ModelValidationError(
                f"Expected big plan status '{recurring_task_period_raw}' for be " +
                "one of '{','.join(self._recurring_task_period_values)}'")

        return RecurringTaskPeriod(recurring_task_period_str)

    @staticmethod
    def recurring_task_period_values() -> Iterable[str]:
        """The possible values for big plan statues."""
        return BasicValidator._recurring_task_period_values

    def recurring_task_due_at_time_validate_and_clean(self, recurring_task_due_at_time_raw: Optional[str]) -> str:
        """Validate and clean the due at time info."""
        if not recurring_task_due_at_time_raw:
            raise ModelValidationError("Expected the due time info to be non-null")

        recurring_task_due_at_time_str: str = recurring_task_due_at_time_raw.strip().lower()

        if len(recurring_task_due_at_time_str) == 0:
            raise ModelValidationError("Expected due time info to be non-empty")

        if not self._recurring_task_due_at_time_re.match(recurring_task_due_at_time_str):
            raise ModelValidationError(
                f"Expected due time info '{recurring_task_due_at_time_raw}' to " +
                "match '{self._recurring_task_due_at_time_re.pattern}'")

        return recurring_task_due_at_time_str

    def recurring_task_due_at_day_validate_and_clean(
            self, period: RecurringTaskPeriod, recurring_task_due_at_day_raw: Optional[int]) -> int:
        """Validate and clean the recurring task due at day info."""
        if not recurring_task_due_at_day_raw:
            raise ModelValidationError("Expected the due day info to be non-null")

        bounds = self._recurring_task_due_at_day_bounds[period]

        if recurring_task_due_at_day_raw < bounds[0] or recurring_task_due_at_day_raw > bounds[1]:
            raise ModelValidationError(
                f"Expected the due day info for {period} period to be a value between {bounds[0]} and {bounds[1]}")

        return recurring_task_due_at_day_raw

    def recurring_task_due_at_month_validate_and_clean(
            self, period: RecurringTaskPeriod, recurring_task_due_at_month_raw: Optional[int]) -> int:
        """Validate and clean the recurring task due at day info."""
        if not recurring_task_due_at_month_raw:
            raise ModelValidationError("Expected the due month info to be non-null")

        bounds = self._recurring_task_due_at_month_bounds[period]

        if recurring_task_due_at_month_raw < bounds[0] or recurring_task_due_at_month_raw > bounds[1]:
            raise ModelValidationError(
                f"Expected the due month info for {period} period to be a value between {bounds[0]} and {bounds[1]}")

        return recurring_task_due_at_month_raw

    @staticmethod
    def recurring_task_skip_rule_validate_and_clean(recurring_task_skip_rule_raw: Optional[str]) -> str:
        """Validate and clean the recurring task skip rule."""
        if not recurring_task_skip_rule_raw:
            raise ModelValidationError("Expected the skip rule info to be non-null")

        return recurring_task_skip_rule_raw.strip().lower()

    def big_plan_status_validate_and_clean(self, big_plan_status_raw: Optional[str]) -> BigPlanStatus:
        """Validate and clean the big plan status."""
        if not big_plan_status_raw:
            raise ModelValidationError("Expected big plan status to be non-null")

        big_plan_status_str: str = big_plan_status_raw.strip().lower()

        if big_plan_status_str not in self._big_plan_status_values:
            raise ModelValidationError(
                f"Expected big plan status '{big_plan_status_raw}' for be " +
                "one of '{','.join(self._big_plan_status_values)}'")

        return BigPlanStatus(big_plan_status_str)

    @staticmethod
    def big_plan_status_values() -> Iterable[str]:
        """The possible values for big plan statues."""
        return BasicValidator._big_plan_status_values