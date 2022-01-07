"""A metric entry."""
from dataclasses import dataclass
from typing import Optional

from jupiter.domain.adate import ADate
from jupiter.framework.aggregate_root import AggregateRoot, FIRST_VERSION
from jupiter.framework.base.entity_id import EntityId, BAD_REF_ID
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.event import EventSource
from jupiter.framework.update_action import UpdateAction


@dataclass()
class MetricEntry(AggregateRoot):
    """A metric entry."""

    @dataclass(frozen=True)
    class Created(AggregateRoot.Created):
        """Created event."""

    @dataclass(frozen=True)
    class Updated(AggregateRoot.Updated):
        """Updated event."""

    metric_ref_id: EntityId
    collection_time: ADate
    value: float
    notes: Optional[str]

    @staticmethod
    def new_metric_entry(
            archived: bool, metric_ref_id: EntityId, collection_time: ADate, value: float, notes: Optional[str],
            source: EventSource, created_time: Timestamp) -> 'MetricEntry':
        """Create a metric entry."""
        metric_entry = MetricEntry(
            ref_id=BAD_REF_ID,
            version=FIRST_VERSION,
            archived=archived,
            created_time=created_time,
            archived_time=created_time if archived else None,
            last_modified_time=created_time,
            events=[],
            metric_ref_id=metric_ref_id,
            collection_time=collection_time,
            value=value,
            notes=notes)
        metric_entry.record_event(
            MetricEntry.Created.make_event_from_frame_args(source, metric_entry.version, created_time))
        return metric_entry

    def update(
            self, collection_time: UpdateAction[ADate], value: UpdateAction[float], notes: UpdateAction[Optional[str]],
            source: EventSource, modification_time: Timestamp) -> 'MetricEntry':
        """Change the metric entry."""
        self.collection_time = collection_time.or_else(self.collection_time)
        self.value = value.or_else(self.value)
        self.notes = notes.or_else(self.notes)
        self.record_event(MetricEntry.Updated.make_event_from_frame_args(source, self.version, modification_time))
        return self
