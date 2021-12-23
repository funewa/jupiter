"""A period for a particular task."""
import enum
from functools import lru_cache
from typing import Iterable, Optional

from framework.errors import ModelValidationError
from framework.value import Value


@enum.unique
class RecurringTaskPeriod(Value, enum.Enum):
    """A period for a particular task."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

    def for_notion(self) -> str:
        """A prettier version of the value for Notion."""
        return str(self.value).capitalize()

    @staticmethod
    def from_raw(recurring_task_period_raw: Optional[str]) -> 'RecurringTaskPeriod':
        """Validate and clean the recurring task period."""
        if not recurring_task_period_raw:
            raise ModelValidationError("Expected recurring task period to be non-null")

        recurring_task_period_str: str = recurring_task_period_raw.strip().lower()

        if recurring_task_period_str not in RecurringTaskPeriod.all_values():
            raise ModelValidationError(
                f"Expected recurring task period '{recurring_task_period_raw}' to be " +
                f"one of '{','.join(RecurringTaskPeriod.all_values())}'")

        return RecurringTaskPeriod(recurring_task_period_str)

    @staticmethod
    @lru_cache(maxsize=1)
    def all_values() -> Iterable[str]:
        """The possible values for difficulties."""
        return frozenset(st.value for st in RecurringTaskPeriod)
