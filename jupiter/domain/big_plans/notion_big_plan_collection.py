"""A big plan collection on Notion-side."""
from dataclasses import dataclass

from jupiter.domain.big_plans.big_plan_collection import BigPlanCollection
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.notion import NotionEntity
from jupiter.framework.base.notion_id import BAD_NOTION_ID


@dataclass(frozen=True)
class NotionBigPlanCollection(NotionEntity[BigPlanCollection]):
    """A big plan collection on Notion-side."""

    @staticmethod
    def new_notion_row(aggregate_root: BigPlanCollection) -> 'NotionBigPlanCollection':
        """Construct a new Notion row from a given aggregate root."""
        return NotionBigPlanCollection(
            notion_id=BAD_NOTION_ID,
            ref_id=aggregate_root.ref_id)

    def apply_to_aggregate_root(
            self, aggregate_root: BigPlanCollection, modification_time: Timestamp) -> BigPlanCollection:
        """Obtain the aggregate root form of this, with a possible error."""
        return aggregate_root