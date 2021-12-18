"""What exactly to sync."""
import enum
from functools import lru_cache
from typing import Iterable, Optional

from models.errors import ModelValidationError
from models.frame.value import Value


@enum.unique
class SyncTarget(Value, enum.Enum):
    """What exactly to sync."""
    STRUCTURE = "structure"
    WORKSPACE = "workspace"
    VACATIONS = "vacations"
    PROJECTS = "projects"
    INBOX_TASKS = "inbox-tasks"
    RECURRING_TASKS = "recurring-tasks"
    BIG_PLANS = "big-plans"
    SMART_LISTS = "smart-lists"
    METRICS = "metrics"
    PRM = "prm"

    @staticmethod
    def from_raw(sync_target_raw: Optional[str]) -> 'SyncTarget':
        """Validate and clean the big plan status."""
        if not sync_target_raw:
            raise ModelValidationError("Expected sync target to be non-null")

        sync_target_str: str = sync_target_raw.strip().lower()

        if sync_target_str not in SyncTarget.all_values():
            raise ModelValidationError(
                f"Expected sync prefer '{sync_target_raw}' to be one of '{','.join(SyncTarget.all_values())}'")

        return SyncTarget(sync_target_str)

    @staticmethod
    @lru_cache(maxsize=1)
    def all_values() -> Iterable[str]:
        """The possible values for difficulties."""
        return frozenset(st.value for st in SyncTarget)