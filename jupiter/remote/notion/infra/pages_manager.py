"""The handler of ad-hoc pages on Notion side."""
from typing import Final, Optional

from jupiter.framework.base.notion_id import NotionId
from jupiter.remote.notion.common import NotionLockKey
from jupiter.remote.notion.infra.client import NotionPageBlockNotFound
from jupiter.remote.notion.infra.client_builder import NotionClientBuilder
from jupiter.remote.notion.infra.client_v2 import NotionRegularPage
from jupiter.remote.notion.infra.page_link import NotionPageLink, NotionPageLinkExtra
from jupiter.remote.notion.infra.page_link_repository import NotionPageLinkNotFoundError
from jupiter.remote.notion.infra.storage_engine import NotionStorageEngine
from jupiter.utils.time_provider import TimeProvider


class NotionPageNotFoundError(Exception):
    """Error raised when a Notion page does not exist."""


class NotionPagesManager:
    """The handler of ad-hoc pages on Notion side."""

    _time_provider: Final[TimeProvider]
    _client_builder: Final[NotionClientBuilder]
    _storage_engine: Final[NotionStorageEngine]

    def __init__(
        self,
        time_provider: TimeProvider,
        client_builder: NotionClientBuilder,
        storage_engine: NotionStorageEngine,
    ) -> None:
        """Constructor."""
        self._time_provider = time_provider
        self._client_builder = client_builder
        self._storage_engine = storage_engine

    def upsert_page(
        self,
        key: NotionLockKey,
        name: str,
        parent_page_notion_id: NotionId,
        icon: Optional[str],
    ) -> NotionPageLink:
        """Create a page with a given name."""
        notion_client = self._client_builder.get_notion_client_v2()

        with self._storage_engine.get_unit_of_work() as uow:
            found_notion_page_link = uow.notion_page_link_repository.load_optional(key)

        if found_notion_page_link:
            new_page = NotionRegularPage(
                notion_id=found_notion_page_link.notion_id,
                parent_page_notion_id=parent_page_notion_id,
                name=name,
                icon=icon,
            )
            notion_client.update_regular_page(new_page)

            with self._storage_engine.get_unit_of_work() as uow:
                new_notion_page_link = found_notion_page_link.mark_update(
                    self._time_provider.get_current_time()
                )
                uow.notion_page_link_repository.save(new_notion_page_link)

            return new_notion_page_link
        else:
            new_page = NotionRegularPage.new(
                parent_page_notion_id=parent_page_notion_id, name=name, icon=icon
            )
            new_page = notion_client.create_regular_page(new_page)

            with self._storage_engine.get_unit_of_work() as uow:
                new_notion_page_link = NotionPageLink.new_notion_page_link(
                    key=key,
                    notion_id=new_page.notion_id,
                    creation_time=self._time_provider.get_current_time(),
                )
                uow.notion_page_link_repository.create(new_notion_page_link)

            return new_notion_page_link

    def save_page(
        self,
        key: NotionLockKey,
        name: str,
        parent_page_notion_id: NotionId,
        icon: Optional[str],
    ) -> NotionPageLink:
        """Save a page with a given name."""
        notion_client = self._client_builder.get_notion_client_v2()

        try:
            with self._storage_engine.get_unit_of_work() as uow:
                notion_page_link = uow.notion_page_link_repository.load(key)

            new_page = NotionRegularPage(
                notion_id=notion_page_link.notion_id,
                parent_page_notion_id=parent_page_notion_id,
                name=name,
                icon=icon,
            )
        except (NotionPageLinkNotFoundError, NotionPageBlockNotFound) as err:
            raise NotionPageNotFoundError(
                f"The Notion page identified by {key} does not exist"
            ) from err

        notion_client.update_regular_page(new_page)

        with self._storage_engine.get_unit_of_work() as uow:
            new_notion_page_link = notion_page_link.mark_update(
                self._time_provider.get_current_time()
            )
            uow.notion_page_link_repository.save(new_notion_page_link)

        return new_notion_page_link

    def get_page(self, key: NotionLockKey) -> NotionPageLink:
        """Get a page with a given key."""
        try:
            with self._storage_engine.get_unit_of_work() as uow:
                return uow.notion_page_link_repository.load(key)
        except NotionPageLinkNotFoundError as err:
            raise NotionPageNotFoundError(
                f"The Notion page identified by {key} does not exist"
            ) from err

    def get_page_extra(self, key: NotionLockKey) -> NotionPageLinkExtra:
        """Get a page with a given key."""
        notion_client = self._client_builder.get_notion_client_v2()

        try:
            with self._storage_engine.get_unit_of_work() as uow:
                notion_page_link = uow.notion_page_link_repository.load(key)
            page_block = notion_client.get_root_page(notion_page_link.notion_id)
        except (NotionPageLinkNotFoundError, NotionPageBlockNotFound) as err:
            raise NotionPageNotFoundError(
                f"The Notion page identified by {key} does not exist"
            ) from err

        return notion_page_link.with_extra(page_block.name, page_block.icon)

    def remove_page(self, key: NotionLockKey) -> None:
        """Remove a page with a given key."""
        notion_client = self._client_builder.get_notion_client_v2()

        try:
            with self._storage_engine.get_unit_of_work() as uow:
                notion_page_link = uow.notion_page_link_repository.load(key)
            notion_client.remove_regular_page(notion_page_link.notion_id)
        except (NotionPageLinkNotFoundError, NotionPageBlockNotFound) as err:
            raise NotionPageNotFoundError(
                f"The Notion page identified by {key} does not exist"
            ) from err
