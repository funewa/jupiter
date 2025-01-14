"""The command for archiving a vacation."""
import logging
from dataclasses import dataclass
from typing import Final

from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.domain.vacations.infra.vacation_notion_manager import (
    VacationNotionManager,
    NotionVacationNotFoundError,
)
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.event import EventSource
from jupiter.framework.use_case import (
    MutationUseCaseInvocationRecorder,
    UseCaseArgsBase,
    ProgressReporter,
    MarkProgressStatus,
)
from jupiter.use_cases.infra.use_cases import (
    AppUseCaseContext,
    AppMutationUseCase,
)
from jupiter.utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


class VacationArchiveUseCase(AppMutationUseCase["VacationArchiveUseCase.Args", None]):
    """The command for archiving a vacation."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        ref_id: EntityId

    _vacation_notion_manager: Final[VacationNotionManager]

    def __init__(
        self,
        time_provider: TimeProvider,
        invocation_recorder: MutationUseCaseInvocationRecorder,
        storage_engine: DomainStorageEngine,
        vacation_notion_manager: VacationNotionManager,
    ) -> None:
        """Constructor."""
        super().__init__(time_provider, invocation_recorder, storage_engine)
        self._vacation_notion_manager = vacation_notion_manager

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> None:
        """Execute the command's action."""
        workspace = context.workspace

        with progress_reporter.start_archiving_entity(
            "vacation", args.ref_id
        ) as entity_reporter:
            with self._storage_engine.get_unit_of_work() as uow:
                vacation_collection = uow.vacation_collection_repository.load_by_parent(
                    workspace.ref_id
                )
                vacation = uow.vacation_repository.load_by_id(args.ref_id)
                entity_reporter.mark_known_name(str(vacation.name))

                vacation = vacation.mark_archived(
                    EventSource.CLI, self._time_provider.get_current_time()
                )
                uow.vacation_repository.save(vacation)
                entity_reporter.mark_local_change()

            try:
                self._vacation_notion_manager.remove_leaf(
                    vacation_collection.ref_id, vacation.ref_id
                )
                entity_reporter.mark_remote_change()
            except NotionVacationNotFoundError:
                LOGGER.info(
                    "Skipping archival on Notion side because vacation was not found"
                )
                entity_reporter.mark_remote_change(MarkProgressStatus.FAILED)
