"""The command for archiving a big plan."""
import logging
from dataclasses import dataclass
from typing import Final

from jupiter.domain.big_plans.infra.big_plan_notion_manager import (
    BigPlanNotionManager,
    NotionBigPlanNotFoundError,
)
from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import (
    InboxTaskNotionManager,
)
from jupiter.domain.inbox_tasks.service.archive_service import InboxTaskArchiveService
from jupiter.domain.inbox_tasks.service.big_plan_ref_options_update_service import (
    InboxTaskBigPlanRefOptionsUpdateService,
)
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.event import EventSource
from jupiter.framework.use_case import (
    UseCaseArgsBase,
    MutationUseCaseInvocationRecorder,
    ProgressReporter,
    MarkProgressStatus,
)
from jupiter.use_cases.infra.use_cases import (
    AppUseCaseContext,
    AppMutationUseCase,
)
from jupiter.utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


class BigPlanArchiveUseCase(AppMutationUseCase["BigPlanArchiveUseCase.Args", None]):
    """The command for archiving a big plan."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        ref_id: EntityId

    _inbox_task_notion_manager: Final[InboxTaskNotionManager]
    _big_plan_notion_manager: Final[BigPlanNotionManager]

    def __init__(
        self,
        time_provider: TimeProvider,
        invocation_recorder: MutationUseCaseInvocationRecorder,
        storage_engine: DomainStorageEngine,
        inbox_task_notion_manager: InboxTaskNotionManager,
        big_plan_notion_manager: BigPlanNotionManager,
    ) -> None:
        """Constructor."""
        super().__init__(time_provider, invocation_recorder, storage_engine)
        self._inbox_task_notion_manager = inbox_task_notion_manager
        self._big_plan_notion_manager = big_plan_notion_manager

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> None:
        """Execute the command's action."""
        workspace = context.workspace

        with self._storage_engine.get_unit_of_work() as uow:
            inbox_task_collection = uow.inbox_task_collection_repository.load_by_parent(
                workspace.ref_id
            )
            inbox_tasks_for_big_plan = uow.inbox_task_repository.find_all_with_filters(
                parent_ref_id=inbox_task_collection.ref_id,
                filter_big_plan_ref_ids=[args.ref_id],
            )

        inbox_task_archive_service = InboxTaskArchiveService(
            source=EventSource.CLI,
            time_provider=self._time_provider,
            storage_engine=self._storage_engine,
            inbox_task_notion_manager=self._inbox_task_notion_manager,
        )
        for inbox_task in inbox_tasks_for_big_plan:
            inbox_task_archive_service.do_it(progress_reporter, inbox_task)

        with progress_reporter.start_archiving_entity(
            "big plan", args.ref_id
        ) as entity_reporter:
            with self._storage_engine.get_unit_of_work() as uow:
                big_plan = uow.big_plan_repository.load_by_id(args.ref_id)
                entity_reporter.mark_known_name(str(big_plan.name))
                big_plan_collection = uow.big_plan_collection_repository.load_by_id(
                    big_plan.big_plan_collection_ref_id
                )
                big_plan = big_plan.mark_archived(
                    EventSource.CLI, self._time_provider.get_current_time()
                )
                uow.big_plan_repository.save(big_plan)
                entity_reporter.mark_local_change()

            try:
                self._big_plan_notion_manager.remove_leaf(
                    big_plan.big_plan_collection_ref_id, args.ref_id
                )
                entity_reporter.mark_remote_change()
            except NotionBigPlanNotFoundError:
                LOGGER.info(
                    "Skipping removal on Notion side because big plan was not found"
                )
                entity_reporter.mark_remote_change(success=MarkProgressStatus.FAILED)

            InboxTaskBigPlanRefOptionsUpdateService(
                self._storage_engine, self._inbox_task_notion_manager
            ).sync(big_plan_collection)
            entity_reporter.mark_other_progress("inbox-task-refs")
