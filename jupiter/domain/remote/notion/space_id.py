"""The id of a Notion space."""
import re
from dataclasses import dataclass
from typing import Optional, Final, Pattern

from jupiter.framework.errors import InputValidationError
from jupiter.framework.value import Value

_NOTION_SPACE_ID_RE: Final[Pattern[str]] = re.compile(r"^[0-9a-z-]{36}$")


@dataclass(frozen=True)
class NotionSpaceId(Value):
    """The id of a Notion space."""

    _the_id: str

    @staticmethod
    def from_raw(notion_space_id_raw: Optional[str]) -> "NotionSpaceId":
        """Validate and clean a Notion space id."""
        if not notion_space_id_raw:
            raise InputValidationError("Expected Notion space id to be non-null")

        notion_space_id: str = notion_space_id_raw.strip().lower()

        if len(notion_space_id) == 0:
            raise InputValidationError("Expected Notion space id to be non-empty")

        if not _NOTION_SPACE_ID_RE.match(notion_space_id):
            raise InputValidationError(
                f"Expected workspace space id '{notion_space_id}' to match '{_NOTION_SPACE_ID_RE.pattern}"
            )

        return NotionSpaceId(notion_space_id)

    def __str__(self) -> str:
        """Transform this to a string version."""
        return self._the_id
