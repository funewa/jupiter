"""The command for associating a inbox task with a big plan."""
from dataclasses import dataclass
from typing import Optional, Final

from jupiter.domain.inbox_tasks.inbox_task import CannotModifyGeneratedTaskError
from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import (
    InboxTaskNotionManager,
)
from jupiter.domain.inbox_tasks.notion_inbox_task import NotionInboxTask
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.errors import InputValidationError
from jupiter.framework.event import EventSource
from jupiter.framework.use_case import (
    MutationUseCaseInvocationRecorder,
    UseCaseArgsBase,
    ProgressReporter,
)
from jupiter.use_cases.infra.use_cases import (
    AppUseCaseContext,
    AppMutationUseCase,
)
from jupiter.utils.time_provider import TimeProvider


class InboxTaskAssociateWithBigPlanUseCase(
    AppMutationUseCase["InboxTaskAssociateWithBigPlanUseCase.Args", None]
):
    """The command for associating a inbox task with a big plan."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        ref_id: EntityId
        big_plan_ref_id: Optional[EntityId]

    _inbox_task_notion_manager: Final[InboxTaskNotionManager]

    def __init__(
        self,
        time_provider: TimeProvider,
        invocation_recorder: MutationUseCaseInvocationRecorder,
        storage_engine: DomainStorageEngine,
        inbox_task_notion_manager: InboxTaskNotionManager,
    ) -> None:
        """Constructor."""
        super().__init__(time_provider, invocation_recorder, storage_engine)
        self._inbox_task_notion_manager = inbox_task_notion_manager

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> None:
        """Execute the command's action."""
        with progress_reporter.start_updating_entity(
            "inbox task", args.ref_id
        ) as entity_reporter:
            with self._storage_engine.get_unit_of_work() as uow:
                inbox_task = uow.inbox_task_repository.load_by_id(args.ref_id)
                entity_reporter.mark_known_name(str(inbox_task.name))

                try:
                    if args.big_plan_ref_id:
                        big_plan = uow.big_plan_repository.load_by_id(
                            args.big_plan_ref_id
                        )
                        project = uow.project_repository.load_by_id(
                            big_plan.project_ref_id
                        )
                        inbox_task = inbox_task.associate_with_big_plan(
                            project_ref_id=big_plan.project_ref_id,
                            big_plan_ref_id=args.big_plan_ref_id,
                            source=EventSource.CLI,
                            modification_time=self._time_provider.get_current_time(),
                        )
                        all_big_plans = {big_plan.ref_id: big_plan}
                    else:
                        project = uow.project_repository.load_by_id(
                            inbox_task.project_ref_id
                        )
                        inbox_task = inbox_task.release_from_big_plan(
                            source=EventSource.CLI,
                            modification_time=self._time_provider.get_current_time(),
                        )
                        all_big_plans = {}
                except CannotModifyGeneratedTaskError as err:
                    raise InputValidationError(
                        f"Modifying a generated task's field {err.field} is not possible"
                    ) from err

                uow.inbox_task_repository.save(inbox_task)
                entity_reporter.mark_local_change()

            direct_info = NotionInboxTask.DirectInfo(
                all_projects_map={project.ref_id: project},
                all_big_plans_map=all_big_plans,
            )
            notion_inbox_task = self._inbox_task_notion_manager.load_leaf(
                inbox_task.inbox_task_collection_ref_id, inbox_task.ref_id
            )
            notion_inbox_task = notion_inbox_task.join_with_entity(
                inbox_task, direct_info
            )
            self._inbox_task_notion_manager.save_leaf(
                inbox_task.inbox_task_collection_ref_id, notion_inbox_task
            )
            entity_reporter.mark_remote_change()
