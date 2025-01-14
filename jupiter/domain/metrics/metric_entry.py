"""A metric entry."""
from dataclasses import dataclass
from typing import Optional

from jupiter.domain.adate import ADate
from jupiter.domain.entity_name import EntityName
from jupiter.framework.base.entity_id import EntityId, BAD_REF_ID
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.entity import Entity, FIRST_VERSION, LeafEntity
from jupiter.framework.event import EventSource
from jupiter.framework.update_action import UpdateAction


@dataclass(frozen=True)
class MetricEntry(LeafEntity):
    """A metric entry."""

    @dataclass(frozen=True)
    class Created(Entity.Created):
        """Created event."""

    @dataclass(frozen=True)
    class Updated(Entity.Updated):
        """Updated event."""

    metric_ref_id: EntityId
    collection_time: ADate
    value: float
    notes: Optional[str]

    @staticmethod
    def new_metric_entry(
        archived: bool,
        metric_ref_id: EntityId,
        collection_time: ADate,
        value: float,
        notes: Optional[str],
        source: EventSource,
        created_time: Timestamp,
    ) -> "MetricEntry":
        """Create a metric entry."""
        metric_entry = MetricEntry(
            ref_id=BAD_REF_ID,
            version=FIRST_VERSION,
            archived=archived,
            created_time=created_time,
            archived_time=created_time if archived else None,
            last_modified_time=created_time,
            events=[
                MetricEntry.Created.make_event_from_frame_args(
                    source, FIRST_VERSION, created_time
                )
            ],
            metric_ref_id=metric_ref_id,
            collection_time=collection_time,
            value=value,
            notes=notes,
        )
        return metric_entry

    def update(
        self,
        collection_time: UpdateAction[ADate],
        value: UpdateAction[float],
        notes: UpdateAction[Optional[str]],
        source: EventSource,
        modification_time: Timestamp,
    ) -> "MetricEntry":
        """Change the metric entry."""
        return self._new_version(
            collection_time=collection_time.or_else(self.collection_time),
            value=value.or_else(self.value),
            notes=notes.or_else(self.notes),
            new_event=MetricEntry.Updated.make_event_from_frame_args(
                source, self.version, modification_time
            ),
        )

    @property
    def parent_ref_id(self) -> EntityId:
        """The parent."""
        return self.metric_ref_id

    @property
    def simple_name(self) -> EntityName:
        """A simple name for the metric entry."""
        return EntityName(
            f"Entry for {ADate.to_user_date_str(self.collection_time)} value={self.value}"
            + (f"notes={self.notes}" if self.notes else "")
        )
