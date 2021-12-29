"""A repository for inbox task collections."""
import abc
from typing import Optional, Iterable

from jupiter.domain.inbox_tasks.inbox_task_collection import InboxTaskCollection
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.storage import Repository


class InboxTaskCollectionAlreadyExistsError(Exception):
    """Error raised when trying to create an inbox task collection and it already exists."""


class InboxTaskCollectionNotFoundError(Exception):
    """Error raised when an inbox task collection does not exist."""


class InboxTaskCollectionRepository(Repository, abc.ABC):
    """A repository of inbox task collections."""

    @abc.abstractmethod
    def create(self, inbox_task_collection: InboxTaskCollection) -> InboxTaskCollection:
        """Create a inbox task collection."""

    @abc.abstractmethod
    def load_by_id(self, ref_id: EntityId) -> InboxTaskCollection:
        """Retrieve a inbox task collection by its id."""

    @abc.abstractmethod
    def load_by_project(self, project_ref_id: EntityId) -> InboxTaskCollection:
        """Retrieve a inbox task collection by its owning project id."""

    @abc.abstractmethod
    def find_all(
            self, allow_archived: bool = False, filter_ref_ids: Optional[Iterable[EntityId]] = None,
            filter_project_ref_ids: Optional[Iterable[EntityId]] = None) -> Iterable[InboxTaskCollection]:
        """Retrieve inbox task collections."""

    @abc.abstractmethod
    def remove(self, ref_id: EntityId) -> InboxTaskCollection:
        """Hard remove a inbox task collection."""