"""The command for completely destroying a workspace."""
import logging
from dataclasses import dataclass
from typing import Final

from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.domain.workspaces.infra.workspace_notion_manager import (
    WorkspaceNotionManager,
    NotionWorkspaceNotFoundError,
)
from jupiter.domain.workspaces.infra.workspace_repository import WorkspaceNotFoundError
from jupiter.framework.storage import Connection
from jupiter.framework.use_case import (
    UseCaseArgsBase,
    MutationEmptyContextUseCase,
    EmptyContext,
    ProgressReporter,
)

LOGGER = logging.getLogger(__name__)


class NukeUseCase(MutationEmptyContextUseCase["NukeUseCase.Args", None]):
    """The command for completely destroying a workspace."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

    _connection: Final[Connection]
    _storage_engine: Final[DomainStorageEngine]
    _workspace_notion_manager: Final[WorkspaceNotionManager]

    def __init__(
        self,
        connection: Connection,
        storage_engine: DomainStorageEngine,
        workspace_notion_manager: WorkspaceNotionManager,
    ) -> None:
        """Constructor."""
        super().__init__()
        self._connection = connection
        self._storage_engine = storage_engine
        self._workspace_notion_manager = workspace_notion_manager

    def _execute(
        self, progress_reporter: ProgressReporter, context: EmptyContext, args: Args
    ) -> None:
        """Execute the command's action."""
        try:
            with progress_reporter.start_removing_entity(
                "workspace"
            ) as entity_reporter:
                with self._storage_engine.get_unit_of_work() as uow:
                    workspace = uow.workspace_repository.load()
                    entity_reporter.mark_known_entity_id(
                        workspace.ref_id
                    ).mark_known_name(str(workspace.name))
                self._workspace_notion_manager.remove_workspace(workspace.ref_id)
                entity_reporter.mark_remote_change()
        except WorkspaceNotFoundError:
            LOGGER.info("Could not find workspace to remove")
        except NotionWorkspaceNotFoundError:
            LOGGER.info("Could not find Notion workspace to remove")

        LOGGER.info("Daisy ... daisy ... daisy")
        self._connection.nuke()
