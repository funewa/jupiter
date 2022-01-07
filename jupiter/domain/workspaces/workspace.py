"""The workspace where everything happens."""
from dataclasses import dataclass

from jupiter.domain.timezone import Timezone
from jupiter.domain.workspaces.workspace_name import WorkspaceName
from jupiter.framework.aggregate_root import AggregateRoot, FIRST_VERSION
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.event import EventSource
from jupiter.framework.update_action import UpdateAction


@dataclass()
class Workspace(AggregateRoot):
    """The workspace where everything happens."""

    @dataclass(frozen=True)
    class Created(AggregateRoot.Created):
        """Created event."""

    @dataclass(frozen=True)
    class Updated(AggregateRoot.Updated):
        """Updated event."""

    @dataclass(frozen=True)
    class ChangedDefaultProject(AggregateRoot.Updated):
        """Change the default project."""

    name: WorkspaceName
    timezone: Timezone
    default_project_ref_id: EntityId

    @staticmethod
    def new_workspace(
            name: WorkspaceName, timezone: Timezone, default_project_ref_id: EntityId,
            source: EventSource, created_time: Timestamp) -> 'Workspace':
        """Create a new workspace."""
        workspace = Workspace(
            ref_id=EntityId.from_raw('0'),
            version=FIRST_VERSION,
            archived=False,
            created_time=created_time,
            archived_time=None,
            last_modified_time=created_time,
            events=[],
            name=name,
            timezone=timezone,
            default_project_ref_id=default_project_ref_id)
        workspace.record_event(
            Workspace.Created.make_event_from_frame_args(source, workspace.version, created_time))
        return workspace

    def update(
            self, name: UpdateAction[WorkspaceName], timezone: UpdateAction[Timezone],
            source: EventSource, modification_time: Timestamp) -> 'Workspace':
        """Update properties of the workspace."""
        self.name = name.or_else(self.name)
        self.timezone = timezone.or_else(self.timezone)
        self.record_event(Workspace.Updated.make_event_from_frame_args(source, self.version, modification_time))
        return self

    def change_default_project(
            self, default_project_ref_id: EntityId, source: EventSource, modification_time: Timestamp) -> 'Workspace':
        """Change the default project of the workspace."""
        self.default_project_ref_id = default_project_ref_id
        self.record_event(
            Workspace.ChangedDefaultProject.make_event_from_frame_args(source, self.version, modification_time))
        return self
