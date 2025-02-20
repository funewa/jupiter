"""The Eisenhower status of a particular task."""
import enum
from functools import lru_cache, total_ordering
from typing import Optional, Iterable, List, cast

from jupiter.framework.errors import InputValidationError


@enum.unique
@total_ordering
class Eisen(enum.Enum):
    """The Eisenhower status of a particular task."""

    IMPORTANT_AND_URGENT = "important-and-urgent"
    IMPORTANT = "important"
    URGENT = "urgent"
    REGULAR = "regular"

    def for_notion(self) -> str:
        """A prettier version of the value for Notion."""
        return str(self.value).capitalize()

    @staticmethod
    def from_raw(eisen_raw: Optional[str]) -> "Eisen":
        """Validate and clean a raw person relationship value."""
        if not eisen_raw:
            raise InputValidationError("Expected Eisenhower status to be non-null")

        eisen_str: str = eisen_raw.strip().lower()

        if eisen_str not in Eisen.all_values():
            raise InputValidationError(
                f"Expected Eisenhower status '{eisen_raw}' to be one of '{','.join(Eisen.all_values())}'"
            )

        return Eisen(eisen_str)

    @staticmethod
    @lru_cache(maxsize=1)
    def all_values() -> Iterable[str]:
        """The possible values for eisen."""
        return list(st.value for st in Eisen)

    def __lt__(self, other: object) -> bool:
        """Compare this with another."""
        if not isinstance(other, Eisen):
            raise Exception(
                f"Cannot compare an entity id with {other.__class__.__name__}"
            )

        all_values = cast(List[str], self.all_values())

        return all_values.index(self.value) < all_values.index(other.value)

    def __str__(self) -> str:
        """String form."""
        return str(self.value)
