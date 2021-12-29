"""The command for creating a project."""
import logging
from dataclasses import dataclass
from typing import Final

from jupiter.domain.big_plans.big_plan_collection import BigPlanCollection
from jupiter.domain.big_plans.infra.big_plan_notion_manager import BigPlanNotionManager
from jupiter.domain.big_plans.notion_big_plan_collection import NotionBigPlanCollection
from jupiter.domain.entity_name import EntityName
from jupiter.domain.inbox_tasks.inbox_task_collection import InboxTaskCollection
from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import InboxTaskNotionManager
from jupiter.domain.inbox_tasks.notion_inbox_task_collection import NotionInboxTaskCollection
from jupiter.domain.projects.infra.project_notion_manager import ProjectNotionManager
from jupiter.domain.projects.notion_project import NotionProject
from jupiter.domain.projects.project import Project
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.domain.recurring_tasks.infra.recurring_task_notion_manager import RecurringTaskNotionManager
from jupiter.domain.recurring_tasks.notion_recurring_task_collection import NotionRecurringTaskCollection
from jupiter.domain.recurring_tasks.recurring_task_collection import RecurringTaskCollection
from jupiter.domain.storage_engine import StorageEngine
from jupiter.framework.use_case import UseCase
from jupiter.utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


class ProjectCreateUseCase(UseCase['ProjectCreateUseCase.Args', None]):
    """The command for creating a project."""

    @dataclass()
    class Args:
        """Args."""
        key: ProjectKey
        name: EntityName

    _time_provider: Final[TimeProvider]
    _storage_engine: Final[StorageEngine]
    _project_notion_manager: Final[ProjectNotionManager]
    _inbox_task_notion_manager: Final[InboxTaskNotionManager]
    _recurring_task_notion_manager: Final[RecurringTaskNotionManager]
    _big_plan_notion_manager: Final[BigPlanNotionManager]

    def __init__(
            self, time_provider: TimeProvider, storage_engine: StorageEngine,
            project_notion_manager: ProjectNotionManager, inbox_task_notion_manager: InboxTaskNotionManager,
            recurring_task_notion_manager: RecurringTaskNotionManager,
            big_plan_notion_manager: BigPlanNotionManager) -> None:
        """Constructor."""
        self._time_provider = time_provider
        self._storage_engine = storage_engine
        self._project_notion_manager = project_notion_manager
        self._inbox_task_notion_manager = inbox_task_notion_manager
        self._recurring_task_notion_manager = recurring_task_notion_manager
        self._big_plan_notion_manager = big_plan_notion_manager

    def execute(self, args: Args) -> None:
        """Execute the command's action."""
        new_project = Project.new_project(args.key, args.name, self._time_provider.get_current_time())

        with self._storage_engine.get_unit_of_work() as uow:
            new_project = uow.project_repository.create(new_project)

            new_inbox_task_collection = InboxTaskCollection.new_inbox_task_collection(
                new_project.ref_id, self._time_provider.get_current_time())
            new_inbox_task_collection = uow.inbox_task_collection_repository.create(new_inbox_task_collection)

            new_recurring_task_collection = RecurringTaskCollection.new_recurring_task_collection(
                new_project.ref_id, self._time_provider.get_current_time())
            new_recurring_task_collection = \
                uow.recurring_task_collection_repository.create(new_recurring_task_collection)

            new_big_plan_collection = BigPlanCollection.new_big_plan_collection(
                new_project.ref_id, self._time_provider.get_current_time())
            new_big_plan_collection = uow.big_plan_collection_repository.create(new_big_plan_collection)

        LOGGER.info("Applied local changes")

        new_notion_project = NotionProject.new_notion_row(new_project)
        new_notion_project = self._project_notion_manager.upsert_project(new_notion_project)

        new_notion_inbox_task_collection = \
            NotionInboxTaskCollection.new_notion_row(new_inbox_task_collection)
        self._inbox_task_notion_manager.upsert_inbox_task_collection(
            new_notion_project, new_notion_inbox_task_collection)

        new_notion_recurring_task_collection = \
            NotionRecurringTaskCollection.new_notion_row(new_recurring_task_collection)
        self._recurring_task_notion_manager.upsert_recurring_task_collection(
            new_notion_project, new_notion_recurring_task_collection)

        new_notion_big_plan_collection = NotionBigPlanCollection.new_notion_row(new_big_plan_collection)
        self._big_plan_notion_manager.upsert_big_plan_collection(
            new_notion_project, new_notion_big_plan_collection)
        LOGGER.info("Applied Notion changes")