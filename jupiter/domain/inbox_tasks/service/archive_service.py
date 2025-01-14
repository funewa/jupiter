"""Shared service for archiving an inbox task."""
import logging
from typing import Final

from jupiter.domain.inbox_tasks.inbox_task import InboxTask
from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import (
    InboxTaskNotionManager,
    NotionInboxTaskNotFoundError,
)
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.event import EventSource
from jupiter.framework.use_case import ProgressReporter, MarkProgressStatus
from jupiter.utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


class InboxTaskArchiveService:
    """Shared service for archiving an inbox task."""

    _source: Final[EventSource]
    _time_provider: Final[TimeProvider]
    _storage_engine: Final[DomainStorageEngine]
    _inbox_task_notion_manager: Final[InboxTaskNotionManager]

    def __init__(
        self,
        source: EventSource,
        time_provider: TimeProvider,
        storage_engine: DomainStorageEngine,
        inbox_task_notion_manager: InboxTaskNotionManager,
    ) -> None:
        """Constructor."""
        self._source = source
        self._time_provider = time_provider
        self._storage_engine = storage_engine
        self._inbox_task_notion_manager = inbox_task_notion_manager

    def do_it(self, progress_reporter: ProgressReporter, inbox_task: InboxTask) -> None:
        """Execute the service's action."""
        if inbox_task.archived:
            return

        with progress_reporter.start_archiving_entity(
            "inbox task", inbox_task.ref_id, str(inbox_task.name)
        ) as entity_reporter:
            inbox_task = inbox_task.mark_archived(
                self._source, self._time_provider.get_current_time()
            )

            with self._storage_engine.get_unit_of_work() as uow:
                uow.inbox_task_repository.save(inbox_task)
            entity_reporter.mark_local_change()

            # Apply Notion changes
            try:
                self._inbox_task_notion_manager.remove_leaf(
                    inbox_task.inbox_task_collection_ref_id, inbox_task.ref_id
                )
                entity_reporter.mark_remote_change()
            except NotionInboxTaskNotFoundError:
                LOGGER.info(
                    "Skipping archiving of Notion inbox task because it could not be found"
                )
                entity_reporter.mark_remote_change(MarkProgressStatus.FAILED)
