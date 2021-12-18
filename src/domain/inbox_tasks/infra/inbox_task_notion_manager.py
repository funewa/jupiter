"""A manager of Notion-side inbox tasks."""
import abc
from typing import Optional, Iterable

from domain.inbox_task_big_plan_label import InboxTaskBigPlanLabel
from domain.inbox_tasks.inbox_task_collection import InboxTaskCollection
from domain.inbox_tasks.notion_inbox_task import NotionInboxTask
from domain.inbox_tasks.notion_inbox_task_collection import NotionInboxTaskCollection
from domain.projects.notion_project import NotionProject
from domain.projects.project import Project
from models.framework import EntityId, NotionId


class InboxTaskNotionManager(abc.ABC):
    """A manager of Notion-side inbox tasks."""

    @abc.abstractmethod
    def upsert_inbox_task_collection(
            self, project: Project, notion_project: NotionProject,
            inbox_task_collection: InboxTaskCollection) -> NotionInboxTaskCollection:
        """Upsert the Notion-side inbox task."""

    @abc.abstractmethod
    def remove_inbox_tasks_collection(self, inbox_task_collection: InboxTaskCollection) -> None:
        """Remove the Notion-side structure for this collection."""

    @abc.abstractmethod
    def get_inbox_task_collection(self, inbox_task_collection: InboxTaskCollection) -> NotionInboxTaskCollection:
        """Retrieve the Notion-side inbox task collection."""

    @abc.abstractmethod
    def upsert_inbox_tasks_big_plan_field_options(
            self, project_ref_id: EntityId, big_plans_labels: Iterable[InboxTaskBigPlanLabel]) -> None:
        """Upsert the Notion-side structure for the 'big plan' select field."""

    @abc.abstractmethod
    def upsert_inbox_task(
            self, inbox_task_collection: InboxTaskCollection, inbox_task: NotionInboxTask) -> NotionInboxTask:
        """Upsert a inbox task."""

    @abc.abstractmethod
    def link_local_and_notion_inbox_task(self, project_ref_id: EntityId, ref_id: EntityId, notion_id: NotionId) -> None:
        """Link a local entity with the Notion one, useful in syncing processes."""

    @abc.abstractmethod
    def load_all_inbox_tasks(self, inbox_task_collection: InboxTaskCollection) -> Iterable[NotionInboxTask]:
        """Retrieve all the Notion-side inbox tasks."""

    @abc.abstractmethod
    def load_inbox_task(self, project_ref_id: EntityId, ref_id: EntityId) -> NotionInboxTask:
        """Retrieve the Notion-side inbox task associated with a particular entity."""

    @abc.abstractmethod
    def remove_inbox_task(self, project_ref_id: EntityId, ref_id: EntityId) -> None:
        """Remove a particular inbox tasks."""

    @abc.abstractmethod
    def save_inbox_task(self, project_ref_id: EntityId, inbox_task: NotionInboxTask) -> NotionInboxTask:
        """Update the Notion-side inbox task with new data."""

    @abc.abstractmethod
    def load_all_saved_inbox_tasks_notion_ids(self, project_ref_id: EntityId) -> Iterable[NotionId]:
        """Retrieve all the saved Notion-ids for these tasks."""

    @abc.abstractmethod
    def load_all_saved_inbox_tasks_ref_ids(self, project_ref_id: EntityId) -> Iterable[EntityId]:
        """Retrieve all the saved ref ids for the inbox tasks tasks."""

    @abc.abstractmethod
    def drop_all_inbox_tasks(self, project_ref_id: EntityId) -> None:
        """Remove all inbox tasks Notion-side."""

    @abc.abstractmethod
    def hard_remove_inbox_task(self, project_ref_id: EntityId, ref_id: Optional[EntityId]) -> None:
        """Hard remove the Notion entity associated with a local entity."""