"""The centralised point for interacting with the Notion persons database."""
import uuid
from typing import Iterable, ClassVar, cast, Dict, Final

from jupiter.domain.difficulty import Difficulty
from jupiter.domain.eisen import Eisen
from jupiter.domain.persons.infra.person_notion_manager import (
    PersonNotionManager,
    NotionPersonNotFoundError,
)
from jupiter.domain.persons.notion_person import NotionPerson
from jupiter.domain.persons.notion_person_collection import NotionPersonCollection
from jupiter.domain.persons.person_relationship import PersonRelationship
from jupiter.domain.recurring_task_period import RecurringTaskPeriod
from jupiter.domain.workspaces.notion_workspace import NotionWorkspace
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.base.notion_id import NotionId
from jupiter.framework.json import JSONDictType
from jupiter.remote.notion.common import NotionLockKey
from jupiter.remote.notion.infra.client import (
    NotionFieldProps,
    NotionFieldShow,
)
from jupiter.remote.notion.infra.collections_manager import (
    NotionCollectionsManager,
    NotionCollectionItemNotFoundError,
)
from jupiter.utils.global_properties import GlobalProperties
from jupiter.utils.time_provider import TimeProvider


class NotionPersonsManager(PersonNotionManager):
    """The centralised point for interacting with the Notion persons database."""

    _KEY: ClassVar[str] = "persons"
    _PAGE_NAME: ClassVar[str] = "Persons"
    _PAGE_ICON: ClassVar[str] = "👨"

    _RELATIONSHIP: ClassVar[JSONDictType] = {
        "Family": {
            "name": PersonRelationship.FAMILY.for_notion(),
            "color": "orange",
            "in_board": True,
        },
        "Friend": {
            "name": PersonRelationship.FRIEND.for_notion(),
            "color": "blue",
            "in_board": True,
        },
        "Acquaintance": {
            "name": PersonRelationship.ACQUAINTANCE.for_notion(),
            "color": "yellow",
            "in_board": True,
        },
        "School Buddy": {
            "name": PersonRelationship.SCHOOL_BUDDY.for_notion(),
            "color": "red",
            "in_board": True,
        },
        "Work Buddy": {
            "name": PersonRelationship.WORK_BUDDY.for_notion(),
            "color": "orange",
            "in_board": True,
        },
        "Colleague": {
            "name": PersonRelationship.COLLEAGUE.for_notion(),
            "color": "green",
            "in_board": True,
        },
        "Other": {
            "name": PersonRelationship.OTHER.for_notion(),
            "color": "gray",
            "in_board": True,
        },
    }

    _PERIOD: ClassVar[JSONDictType] = {
        "Daily": {
            "name": RecurringTaskPeriod.DAILY.for_notion(),
            "color": "orange",
            "in_board": True,
        },
        "Weekly": {
            "name": RecurringTaskPeriod.WEEKLY.for_notion(),
            "color": "green",
            "in_board": True,
        },
        "Monthly": {
            "name": RecurringTaskPeriod.MONTHLY.for_notion(),
            "color": "yellow",
            "in_board": True,
        },
        "Quarterly": {
            "name": RecurringTaskPeriod.QUARTERLY.for_notion(),
            "color": "blue",
            "in_board": True,
        },
        "Yearly": {
            "name": RecurringTaskPeriod.YEARLY.for_notion(),
            "color": "red",
            "in_board": True,
        },
    }

    _EISENHOWER: ClassVar[JSONDictType] = {
        "Important-And-Urgent": {
            "name": Eisen.IMPORTANT_AND_URGENT.for_notion(),
            "color": "green",
        },
        "Urgent": {"name": Eisen.URGENT.for_notion(), "color": "red"},
        "Important": {"name": Eisen.IMPORTANT.for_notion(), "color": "blue"},
        "Regular": {"name": Eisen.REGULAR.for_notion(), "color": "orange"},
    }

    _DIFFICULTY = {
        "Easy": {"name": Difficulty.EASY.for_notion(), "color": "blue"},
        "Medium": {"name": Difficulty.MEDIUM.for_notion(), "color": "green"},
        "Hard": {"name": Difficulty.HARD.for_notion(), "color": "purple"},
    }

    _SCHEMA: ClassVar[JSONDictType] = {
        "title": {"name": "Name", "type": "title"},
        "archived": {"name": "Archived", "type": "checkbox"},
        "relationship": {
            "name": "Relationship",
            "type": "select",
            "options": [
                {
                    "color": cast(Dict[str, str], v)["color"],
                    "id": str(uuid.uuid4()),
                    "value": cast(Dict[str, str], v)["name"],
                }
                for v in _RELATIONSHIP.values()
            ],
        },
        "catch-up-period": {
            "name": "Catch Up Period",
            "type": "select",
            "options": [
                {
                    "color": cast(Dict[str, str], v)["color"],
                    "id": str(uuid.uuid4()),
                    "value": cast(Dict[str, str], v)["name"],
                }
                for v in _PERIOD.values()
            ],
        },
        "catch-up-eisen": {
            "name": "Catch Up Eisenhower",
            "type": "select",
            "options": [
                {
                    "color": cast(Dict[str, str], v)["color"],
                    "id": str(uuid.uuid4()),
                    "value": cast(Dict[str, str], v)["name"],
                }
                for v in _EISENHOWER.values()
            ],
        },
        "catch-up-difficulty": {
            "name": "Catch Up Difficulty",
            "type": "select",
            "options": [
                {
                    "color": cast(Dict[str, str], v)["color"],
                    "id": str(uuid.uuid4()),
                    "value": cast(Dict[str, str], v)["name"],
                }
                for v in _DIFFICULTY.values()
            ],
        },
        "catch-up-actionable-from-day": {
            "name": "Catch Up Actionable From Day",
            "type": "number",
        },
        "catch-up-actionable-from-month": {
            "name": "Catch Up Actionable From Month",
            "type": "number",
        },
        "catch-up-due-at-time": {
            "name": "Catch Up Due At Time",
            "type": "text",
        },
        "catch-up-due-at-day": {
            "name": "Catch Up Due At Day",
            "type": "number",
        },
        "catch-up-due-at-month": {
            "name": "Catch Up Due At Month",
            "type": "number",
        },
        "birthday": {"name": "Birthday", "type": "text"},
        "last-edited-time": {"name": "Last Edited Time", "type": "last_edited_time"},
        "ref-id": {"name": "Ref Id", "type": "text"},
    }

    _SCHEMA_PROPERTIES = [
        NotionFieldProps(name="title", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="relationship", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="birthday", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="catch-up-period", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="catch-up-eisen", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(
            name="catch-up-difficulty", show=NotionFieldShow.HIDE_IF_EMPTY
        ),
        NotionFieldProps(
            name="catch-up-actionable-from-month", show=NotionFieldShow.HIDE_IF_EMPTY
        ),
        NotionFieldProps(
            name="catch-up-actionable-from-day", show=NotionFieldShow.HIDE_IF_EMPTY
        ),
        NotionFieldProps(
            name="catch-up-due-at-month", show=NotionFieldShow.HIDE_IF_EMPTY
        ),
        NotionFieldProps(
            name="catch-up-due-at-day", show=NotionFieldShow.HIDE_IF_EMPTY
        ),
        NotionFieldProps(
            name="catch-up-due-at-time", show=NotionFieldShow.HIDE_IF_EMPTY
        ),
        NotionFieldProps(name="archived", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="ref-id", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="last-edited-time", show=NotionFieldShow.SHOW),
    ]

    _DATABASE_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Database",
        "type": "table",
        "format": {
            "table_properties": [
                {"width": 300, "property": "title", "visible": True},
                {"width": 100, "property": "relationship", "visible": True},
                {"width": 100, "property": "birthday", "visible": True},
                {"width": 100, "property": "catch-up-period", "visible": True},
                {"width": 100, "property": "catch-up-eisen", "visible": True},
                {"width": 100, "property": "catch-up-difficulty", "visible": True},
                {
                    "width": 100,
                    "property": "catch-up-actionable-from-day",
                    "visible": False,
                },
                {
                    "width": 100,
                    "property": "catch-up-actionable-from-month",
                    "visible": False,
                },
                {"width": 100, "property": "catch-up-due-at-time", "visible": False},
                {"width": 100, "property": "catch-up-due-at-day", "visible": False},
                {"width": 100, "property": "catch-up-due-at-month", "visible": False},
                {"width": 100, "property": "archived", "visible": True},
                {"width": 100, "property": "last-edited-time", "visible": True},
                {"width": 100, "property": "ref-id", "visible": True},
            ]
        },
    }

    _global_properties: Final[GlobalProperties]
    _time_provider: Final[TimeProvider]
    _collections_manager: Final[NotionCollectionsManager]

    def __init__(
        self,
        global_properties: GlobalProperties,
        time_provider: TimeProvider,
        collections_manager: NotionCollectionsManager,
    ) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._time_provider = time_provider
        self._collections_manager = collections_manager

    def upsert_trunk(
        self, parent: NotionWorkspace, trunk: NotionPersonCollection
    ) -> None:
        """Upsert the root Notion structure."""
        self._collections_manager.upsert_collection(
            key=NotionLockKey(f"{self._KEY}:{trunk.ref_id}"),
            parent_page_notion_id=parent.notion_id,
            name=self._PAGE_NAME,
            icon=self._PAGE_ICON,
            schema=self._SCHEMA,
            schema_properties=self._SCHEMA_PROPERTIES,
            view_schemas=[("database_view_id", self._DATABASE_VIEW_SCHEMA)],
        )

    def upsert_leaf(self, trunk_ref_id: EntityId, leaf: NotionPerson) -> NotionPerson:
        """Upsert a person on Notion-side."""
        link = self._collections_manager.upsert_collection_item(
            timezone=self._global_properties.timezone,
            schema=self._SCHEMA,
            key=NotionLockKey(f"{leaf.ref_id}"),
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            new_leaf=leaf,
        )
        return link.item_info

    def save_leaf(
        self,
        trunk_ref_id: EntityId,
        leaf: NotionPerson,
    ) -> NotionPerson:
        """Save an already existing person on Notion-side."""
        try:
            link = self._collections_manager.save_collection_item(
                timezone=self._global_properties.timezone,
                schema=self._SCHEMA,
                key=NotionLockKey(f"{leaf.ref_id}"),
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
                row=leaf,
            )
            return link.item_info
        except NotionCollectionItemNotFoundError as err:
            raise NotionPersonNotFoundError(
                f"Person with id {leaf.ref_id} could not be found"
            ) from err

    def load_leaf(self, trunk_ref_id: EntityId, leaf_ref_id: EntityId) -> NotionPerson:
        """Retrieve a person from Notion-side."""
        try:
            link = self._collections_manager.load_collection_item(
                timezone=self._global_properties.timezone,
                schema=self._SCHEMA,
                ctor=NotionPerson,
                key=NotionLockKey(f"{leaf_ref_id}"),
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            )
            return link.item_info
        except NotionCollectionItemNotFoundError as err:
            raise NotionPersonNotFoundError(
                f"Person with id {leaf_ref_id} could not be found"
            ) from err

    def load_all_leaves(self, trunk_ref_id: EntityId) -> Iterable[NotionPerson]:
        """Retrieve all persons from Notion-side."""
        return [
            l.item_info
            for l in self._collections_manager.load_all_collection_items(
                timezone=self._global_properties.timezone,
                schema=self._SCHEMA,
                ctor=NotionPerson,
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            )
        ]

    def remove_leaf(self, trunk_ref_id: EntityId, leaf_ref_id: EntityId) -> None:
        """Remove a person on Notion-side."""
        try:
            self._collections_manager.remove_collection_item(
                key=NotionLockKey(f"{leaf_ref_id}"),
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            )
        except NotionCollectionItemNotFoundError as err:
            raise NotionPersonNotFoundError(
                f"Person with id {leaf_ref_id} could not be found"
            ) from err

    def drop_all_leaves(self, trunk_ref_id: EntityId) -> None:
        """Drop all persons on Notion-side."""
        self._collections_manager.drop_all_collection_items(
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}")
        )

    def link_local_and_notion_leaves(
        self, trunk_ref_id: EntityId, ref_id: EntityId, notion_id: NotionId
    ) -> None:
        """Link a local and Notion version of the entities."""
        self._collections_manager.quick_link_local_and_notion_entries_for_collection_item(
            key=NotionLockKey(f"{ref_id}"),
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            ref_id=ref_id,
            notion_id=notion_id,
        )

    def load_all_saved_ref_ids(self, trunk_ref_id: EntityId) -> Iterable[EntityId]:
        """Load ids of all persons we know about from Notion side."""
        return self._collections_manager.load_all_collection_items_saved_ref_ids(
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}")
        )

    def load_all_saved_notion_ids(self, trunk_ref_id: EntityId) -> Iterable[NotionId]:
        """Load ids of all persons we know about from Notion side."""
        return self._collections_manager.load_all_collection_items_saved_notion_ids(
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}")
        )
