"""Repository for workspaces."""
import logging
import typing
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Final, ClassVar, Optional

from domain.entity_name import EntityName
from domain.timestamp import Timestamp
from domain.timezone import Timezone
from domain.workspaces.infra.workspace_engine import WorkspaceUnitOfWork, WorkspaceEngine
from domain.workspaces.infra.workspace_repository import WorkspaceRepository
from domain.workspaces.workspace import Workspace
from models.errors import RepositoryError
from models.framework import EntityId, JSONDictType, BAD_REF_ID
from utils.storage import StructuredIndividualStorage
from utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


class MissingWorkspaceRepositoryError(RepositoryError):
    """Error raised when there isn't a workspace defined."""


@dataclass()
class _WorkspaceRow:
    """A workspace."""

    name: EntityName
    timezone: Timezone
    default_project_ref_id: EntityId
    created_time: Timestamp
    last_modified_time: Timestamp


class YamlWorkspaceRepository(WorkspaceRepository):
    """A repository for workspaces."""

    _WORKSPACE_FILE_PATH: ClassVar[Path] = Path("./workspaces.yaml")

    _time_provider: Final[TimeProvider]
    _structured_storage: Final[StructuredIndividualStorage[_WorkspaceRow]]

    def __init__(self, time_provider: TimeProvider) -> None:
        """Constructor."""
        self._time_provider = time_provider
        self._structured_storage = StructuredIndividualStorage(self._WORKSPACE_FILE_PATH, self)

    def initialize(self) -> None:
        """Initialise the workspace repository."""

    def create(self, workspace: Workspace) -> Workspace:
        """Create a new workspace."""
        new_workspace_row = _WorkspaceRow(
            name=workspace.name,
            timezone=workspace.timezone,
            default_project_ref_id=workspace.default_project_ref_id,
            created_time=workspace.created_time,
            last_modified_time=workspace.last_modified_time)
        self._structured_storage.save(new_workspace_row)
        return workspace

    def save(self, workspace: Workspace) -> Workspace:
        """Save the workspace."""
        new_workspace_row = _WorkspaceRow(
            name=workspace.name,
            timezone=workspace.timezone,
            default_project_ref_id=workspace.default_project_ref_id,
            created_time=workspace.created_time,
            last_modified_time=workspace.last_modified_time)
        self._structured_storage.save(new_workspace_row)
        return workspace

    def find(self) -> Workspace:
        """Find the workspace."""
        workspace_row = self._structured_storage.load_optional()
        if workspace_row is None:
            raise MissingWorkspaceRepositoryError()
        return Workspace(
            _ref_id=BAD_REF_ID,
            _archived=False,
            _created_time=workspace_row.created_time,
            _archived_time=None,
            _last_modified_time=workspace_row.last_modified_time,
            _events=[],
            _name=workspace_row.name,
            _timezone=workspace_row.timezone,
            _default_project_ref_id=workspace_row.default_project_ref_id)

    @staticmethod
    def storage_schema() -> JSONDictType:
        """The schema for the data."""
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "timezone": {"type": "string"},
                "default_project_ref_id": {"type": "string"},
                "created_time": {"type": "string"},
                "last_modified_time": {"type": "string"}
            }
        }

    @staticmethod
    def storage_to_live(storage_form: JSONDictType) -> _WorkspaceRow:
        """Transform the data reconstructed from basic storage into something useful for the live system."""
        return _WorkspaceRow(
            name=EntityName.from_raw(typing.cast(str, storage_form["name"])),
            timezone=Timezone.from_raw(typing.cast(str, storage_form["timezone"])),
            default_project_ref_id=EntityId.from_raw(typing.cast(str, storage_form["default_project_ref_id"])),
            created_time=Timestamp.from_str(typing.cast(str, storage_form["created_time"])),
            last_modified_time=Timestamp.from_str(typing.cast(str, storage_form["last_modified_time"])))

    @staticmethod
    def live_to_storage(live_form: _WorkspaceRow) -> JSONDictType:
        """Transform the live system data to something suitable for basic storage."""
        return {
            "name": str(live_form.name),
            "timezone": str(live_form.timezone),
            "default_project_ref_id": str(live_form.default_project_ref_id),
            "created_time": str(live_form.created_time),
            "last_modified_time": str(live_form.last_modified_time)
        }


class YamlWorkspaceUnitOfWork(WorkspaceUnitOfWork):
    """The YAML storage workspace unit of work."""

    _workspace_repository: Final[YamlWorkspaceRepository]

    def __init__(self, time_provider: TimeProvider) -> None:
        """Constructor."""
        self._workspace_repository = YamlWorkspaceRepository(time_provider)

    def __enter__(self) -> 'YamlWorkspaceUnitOfWork':
        """Enter the context."""
        self._workspace_repository.initialize()
        return self

    def __exit__(
            self, exc_type: Optional[typing.Type[BaseException]], _exc_val: Optional[BaseException],
            _exc_tb: Optional[TracebackType]) -> None:
        """Exit context."""

    @property
    def workspace_repository(self) -> WorkspaceRepository:
        """The workspace repository."""
        return self._workspace_repository


class YamlWorkspaceEngine(WorkspaceEngine):
    """The YAML storage workspace engine."""

    _time_provider: Final[TimeProvider]

    def __init__(self, time_provider: TimeProvider) -> None:
        """Constructor."""
        self._time_provider = time_provider

    @contextmanager
    def get_unit_of_work(self) -> typing.Iterator[WorkspaceUnitOfWork]:
        """Get the unit of work."""
        yield YamlWorkspaceUnitOfWork(self._time_provider)