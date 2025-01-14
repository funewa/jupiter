"""Service for archiving a Slack task and associated entities."""
import logging
from typing import Final

from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import (
    InboxTaskNotionManager,
    NotionInboxTaskNotFoundError,
)
from jupiter.domain.push_integrations.slack.infra.slack_task_notion_manager import (
    SlackTaskNotionManager,
    NotionSlackTaskNotFoundError,
)
from jupiter.domain.push_integrations.slack.slack_task import SlackTask
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.event import EventSource
from jupiter.framework.use_case import ProgressReporter, MarkProgressStatus
from jupiter.utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


class SlackTaskArchiveService:
    """Shared service for archiving a slack task."""

    _source: Final[EventSource]
    _time_provider: Final[TimeProvider]
    _storage_engine: Final[DomainStorageEngine]
    _inbox_task_notion_manager: Final[InboxTaskNotionManager]
    _slack_task_notion_manager: Final[SlackTaskNotionManager]

    def __init__(
        self,
        source: EventSource,
        time_provider: TimeProvider,
        storage_engine: DomainStorageEngine,
        inbox_task_notion_manager: InboxTaskNotionManager,
        slack_task_notion_manager: SlackTaskNotionManager,
    ) -> None:
        """Constructor."""
        self._source = source
        self._time_provider = time_provider
        self._storage_engine = storage_engine
        self._inbox_task_notion_manager = inbox_task_notion_manager
        self._slack_task_notion_manager = slack_task_notion_manager

    def do_it(self, progress_reporter: ProgressReporter, slack_task: SlackTask) -> None:
        """Execute the service's action."""
        if slack_task.archived:
            return

        with self._storage_engine.get_unit_of_work() as uow:
            slack_task_collection = uow.slack_task_collection_repository.load_by_id(
                slack_task.slack_task_collection_ref_id
            )
            push_integration_group = uow.push_integration_group_repository.load_by_id(
                slack_task_collection.push_integration_group_ref_id
            )
            inbox_task_collection = uow.inbox_task_collection_repository.load_by_parent(
                push_integration_group.workspace_ref_id
            )

            inbox_tasks_to_archive = uow.inbox_task_repository.find_all_with_filters(
                parent_ref_id=inbox_task_collection.ref_id,
                allow_archived=False,
                filter_slack_task_ref_ids=[slack_task.ref_id],
            )

        for inbox_task in inbox_tasks_to_archive:
            with progress_reporter.start_archiving_entity(
                "inbox task", inbox_task.ref_id, str(inbox_task.name)
            ) as entity_reporter:
                with self._storage_engine.get_unit_of_work() as uow:
                    inbox_task = inbox_task.mark_archived(
                        self._source, self._time_provider.get_current_time()
                    )
                    uow.inbox_task_repository.save(inbox_task)
                    entity_reporter.mark_local_change()

                try:
                    self._inbox_task_notion_manager.remove_leaf(
                        inbox_task.inbox_task_collection_ref_id, inbox_task.ref_id
                    )
                    entity_reporter.mark_remote_change()
                except NotionInboxTaskNotFoundError:
                    # If we can't find this locally it means it's already gone
                    LOGGER.info(
                        "Skipping archival on Notion side because inbox task was not found"
                    )
                    entity_reporter.mark_remote_change(MarkProgressStatus.FAILED)

        with progress_reporter.start_archiving_entity(
            "Slack task", slack_task.ref_id, str(slack_task.simple_name)
        ) as entity_reporter:
            with self._storage_engine.get_unit_of_work() as uow:
                slack_task = slack_task.mark_archived(
                    self._source, self._time_provider.get_current_time()
                )
                uow.slack_task_repository.save(slack_task)
                entity_reporter.mark_local_change()

            try:
                self._slack_task_notion_manager.remove_leaf(
                    slack_task.slack_task_collection_ref_id, slack_task.ref_id
                )
                entity_reporter.mark_remote_change()
            except NotionSlackTaskNotFoundError:
                # If we can't find this locally it means it's already gone
                LOGGER.info(
                    "Skipping archival on Notion side because Slack task was not found"
                )
                entity_reporter.mark_remote_change(MarkProgressStatus.FAILED)
