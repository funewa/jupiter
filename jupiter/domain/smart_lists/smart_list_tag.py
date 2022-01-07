"""A smart list tag."""
from dataclasses import dataclass

from jupiter.domain.smart_lists.smart_list_tag_name import SmartListTagName
from jupiter.framework.aggregate_root import AggregateRoot, FIRST_VERSION
from jupiter.framework.base.entity_id import EntityId, BAD_REF_ID
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.event import EventSource
from jupiter.framework.update_action import UpdateAction


@dataclass()
class SmartListTag(AggregateRoot):
    """A smart list tag."""

    @dataclass(frozen=True)
    class Created(AggregateRoot.Created):
        """Created event."""

    @dataclass(frozen=True)
    class Updated(AggregateRoot.Updated):
        """Updated event."""

    smart_list_ref_id: EntityId
    tag_name: SmartListTagName

    @staticmethod
    def new_smart_list_tag(
            smart_list_ref_id: EntityId, tag_name: SmartListTagName, source: EventSource,
            created_time: Timestamp) -> 'SmartListTag':
        """Create a smart list tag."""
        smart_list_tag = SmartListTag(
            ref_id=BAD_REF_ID,
            version=FIRST_VERSION,
            archived=False,
            created_time=created_time,
            archived_time=None,
            last_modified_time=created_time,
            events=[],
            smart_list_ref_id=smart_list_ref_id,
            tag_name=tag_name)
        smart_list_tag.record_event(
            SmartListTag.Created.make_event_from_frame_args(source, smart_list_tag.version, created_time))

        return smart_list_tag

    def update(
            self, tag_name: UpdateAction[SmartListTagName], source: EventSource,
            modification_time: Timestamp) -> 'SmartListTag':
        """Change the smart list tag."""
        self.tag_name = tag_name.or_else(self.tag_name)
        self.record_event(SmartListTag.Updated.make_event_from_frame_args(source, self.version, modification_time))
        return self
