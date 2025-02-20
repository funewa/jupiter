"""The command for archiving a slack task."""
from dataclasses import dataclass
from typing import Final

from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import (
    InboxTaskNotionManager,
)
from jupiter.domain.push_integrations.slack.infra.slack_task_notion_manager import (
    SlackTaskNotionManager,
)
from jupiter.domain.push_integrations.slack.service.archive_service import (
    SlackTaskArchiveService,
)
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.event import EventSource
from jupiter.framework.use_case import (
    UseCaseArgsBase,
    MutationUseCaseInvocationRecorder,
    ProgressReporter,
)
from jupiter.use_cases.infra.use_cases import (
    AppUseCaseContext,
    AppMutationUseCase,
)
from jupiter.utils.time_provider import TimeProvider


class SlackTaskArchiveUseCase(AppMutationUseCase["SlackTaskArchiveUseCase.Args", None]):
    """The command for archiving a slack task."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        ref_id: EntityId

    _inbox_task_notion_manager: Final[InboxTaskNotionManager]
    _slack_task_notion_manager: Final[SlackTaskNotionManager]

    def __init__(
        self,
        time_provider: TimeProvider,
        invocation_recorder: MutationUseCaseInvocationRecorder,
        storage_engine: DomainStorageEngine,
        inbox_task_notion_manager: InboxTaskNotionManager,
        slack_task_notion_manager: SlackTaskNotionManager,
    ) -> None:
        """Constructor."""
        super().__init__(time_provider, invocation_recorder, storage_engine)
        self._inbox_task_notion_manager = inbox_task_notion_manager
        self._slack_task_notion_manager = slack_task_notion_manager

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> None:
        """Execute the command's action."""
        with self._storage_engine.get_unit_of_work() as uow:
            slack_task = uow.slack_task_repository.load_by_id(ref_id=args.ref_id)

        slack_task_archive_service = SlackTaskArchiveService(
            EventSource.CLI,
            self._time_provider,
            self._storage_engine,
            self._inbox_task_notion_manager,
            self._slack_task_notion_manager,
        )

        slack_task_archive_service.do_it(progress_reporter, slack_task)
