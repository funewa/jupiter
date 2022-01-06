"""The personal relationship database."""
from dataclasses import dataclass

from jupiter.framework.aggregate_root import AggregateRoot, FIRST_VERSION
from jupiter.framework.base.entity_id import EntityId, BAD_REF_ID
from jupiter.framework.base.timestamp import Timestamp


@dataclass()
class PrmDatabase(AggregateRoot):
    """The personal relationship database."""

    @dataclass(frozen=True)
    class Created(AggregateRoot.Created):
        """Create event."""

    @dataclass(frozen=True)
    class ChangeCatchUpProjectRefId(AggregateRoot.Updated):
        """Change catch up project ref id."""

    catch_up_project_ref_id: EntityId

    @staticmethod
    def new_prm_database(catch_up_project_ref_id: EntityId, created_time: Timestamp) -> 'PrmDatabase':
        """Create a new personal database."""
        person = PrmDatabase(
            ref_id=BAD_REF_ID,
            version=FIRST_VERSION,
            archived=False,
            created_time=created_time,
            archived_time=None,
            last_modified_time=created_time,
            events=[],
            catch_up_project_ref_id=catch_up_project_ref_id)
        person.record_event(PrmDatabase.Created.make_event_from_frame_args(created_time))
        return person

    def change_catch_up_project(
            self, catch_up_project_ref_id: EntityId, modified_time: Timestamp) -> 'PrmDatabase':
        """Change the catch up project."""
        if self.catch_up_project_ref_id == catch_up_project_ref_id:
            return self
        self.catch_up_project_ref_id = catch_up_project_ref_id
        self.record_event(PrmDatabase.ChangeCatchUpProjectRefId.make_event_from_frame_args(modified_time))
        return self
