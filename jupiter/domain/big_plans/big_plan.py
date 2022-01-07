"""A big plan."""
import uuid
from dataclasses import dataclass
from typing import Optional

from jupiter.domain.adate import ADate
from jupiter.domain.big_plans.big_plan_name import BigPlanName
from jupiter.domain.big_plans.big_plan_status import BigPlanStatus
from jupiter.framework.aggregate_root import AggregateRoot, FIRST_VERSION
from jupiter.framework.base.entity_id import EntityId, BAD_REF_ID
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.event import EventSource
from jupiter.framework.update_action import UpdateAction


@dataclass()
class BigPlan(AggregateRoot):
    """A big plan."""

    @dataclass(frozen=True)
    class Created(AggregateRoot.Created):
        """Created event."""

    @dataclass(frozen=True)
    class Updated(AggregateRoot.Updated):
        """Updated event."""

    big_plan_collection_ref_id: EntityId
    name: BigPlanName
    status: BigPlanStatus
    actionable_date: Optional[ADate]
    due_date: Optional[ADate]
    notion_link_uuid: uuid.UUID
    accepted_time: Optional[Timestamp]
    working_time: Optional[Timestamp]
    completed_time: Optional[Timestamp]

    @staticmethod
    def new_big_plan(
            archived: bool, big_plan_collection_ref_id: EntityId, name: BigPlanName, status: BigPlanStatus,
            actionable_date: Optional[ADate], due_date: Optional[ADate], source: EventSource,
            created_time: Timestamp) -> 'BigPlan':
        """Create a big plan."""
        big_plan = BigPlan(
            ref_id=BAD_REF_ID,
            version=FIRST_VERSION,
            archived=archived,
            created_time=created_time,
            archived_time=created_time if archived else None,
            last_modified_time=created_time,
            events=[],
            big_plan_collection_ref_id=big_plan_collection_ref_id,
            name=name,
            status=status,
            actionable_date=actionable_date,
            due_date=due_date,
            notion_link_uuid=uuid.uuid4(),
            accepted_time=created_time if status.is_accepted_or_more else None,
            working_time=created_time if status.is_working_or_more else None,
            completed_time=created_time if status.is_completed else None)

        big_plan.record_event(
            BigPlan.Created.make_event_from_frame_args(
                source, big_plan.version, created_time, notion_link_uuid=big_plan.notion_link_uuid,
                accepted_time=big_plan.accepted_time, working_time=big_plan.working_time,
                completed_time=big_plan.completed_time))

        return big_plan

    def update(
            self, name: UpdateAction[BigPlanName], status: UpdateAction[BigPlanStatus],
            actionable_date: UpdateAction[Optional[ADate]], due_date: UpdateAction[Optional[ADate]],
            source: EventSource, modification_time: Timestamp) -> 'BigPlan':
        """Update the big plan."""
        self.name = name.or_else(self.name)

        if status.should_change:
            updated_accepted_time: UpdateAction[Optional[Timestamp]]
            if not self.status.is_accepted_or_more and status.value.is_accepted_or_more:
                self.accepted_time = modification_time
                updated_accepted_time = UpdateAction.change_to(modification_time)
            elif self.status.is_accepted_or_more and not status.value.is_accepted_or_more:
                self.accepted_time = None
                updated_accepted_time = UpdateAction.change_to(None)
            else:
                updated_accepted_time = UpdateAction.do_nothing()

            updated_working_time: UpdateAction[Optional[Timestamp]]
            if not self.status.is_working_or_more and status.value.is_working_or_more:
                self.working_time = modification_time
                updated_working_time = UpdateAction.change_to(modification_time)
            elif self.status.is_working_or_more and not status.value.is_working_or_more:
                self.working_time = None
                updated_working_time = UpdateAction.change_to(None)
            else:
                updated_working_time = UpdateAction.do_nothing()

            updated_completed_time: UpdateAction[Optional[Timestamp]]
            if not self.status.is_completed and status.value.is_completed:
                self.completed_time = modification_time
                updated_completed_time = UpdateAction.change_to(modification_time)
            elif self.status.is_completed and not status.value.is_completed:
                self.completed_time = None
                updated_completed_time = UpdateAction.change_to(None)
            else:
                updated_completed_time = UpdateAction.do_nothing()
            self.status = status.value

            event_kwargs = {
                "updated_accepted_time": updated_accepted_time,
                "updated_working_time": updated_working_time,
                "updated_completed_time":  updated_completed_time
            }
        else:
            event_kwargs = {}

        self.actionable_date = actionable_date.or_else(self.actionable_date)
        self.due_date = due_date.or_else(self.due_date)

        self.record_event(
            BigPlan.Updated.make_event_from_frame_args(source, self.version, modification_time, **event_kwargs))

        return self

    @property
    def project_ref_id(self) -> EntityId:
        """The id of the project this big plan belongs to."""
        # TODO(horia141): fix this uglyness
        return self.big_plan_collection_ref_id
