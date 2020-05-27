"""The collection for recurring tasks."""
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
import typing
from typing import Final, Optional, Dict, ClassVar, Iterable, List, cast

from notion.collection import CollectionRowBlock

from models.basic import EntityId, Eisen, Difficulty, RecurringTaskPeriod
from remote.notion import common
from remote.notion.client import NotionClient
from remote.notion.collection import NotionCollection, BasicRowType, NotionCollectionKWArgsType
from remote.notion.common import NotionId, NotionPageLink, NotionCollectionLink
from remote.notion.connection import NotionConnection
from utils.storage import JSONDictType

LOGGER = logging.getLogger(__name__)


@dataclass()
class RecurringTaskRow(BasicRowType):
    """A recurring task on Notion side."""

    name: str
    archived: bool
    period: Optional[str]
    group: Optional[str]
    eisen: Optional[List[str]]
    difficulty: Optional[str]
    due_at_time: Optional[str]
    due_at_day: Optional[int]
    due_at_month: Optional[int]
    suspended: bool
    skip_rule: Optional[str]
    must_do: bool


class RecurringTasksCollection:
    """A collection on Notion side for recurring tasks."""

    _LOCK_FILE_PATH: ClassVar[Path] = Path("/data/recurring-tasks.lock.yaml")

    _PAGE_NAME: ClassVar[str] = "Recurring Tasks"

    _PERIOD: ClassVar[JSONDictType] = {
        "Daily": {
            "name": RecurringTaskPeriod.DAILY.for_notion(),
            "color": "orange",
            "in_board": True
        },
        "Weekly": {
            "name": RecurringTaskPeriod.WEEKLY.for_notion(),
            "color": "green",
            "in_board": True
        },
        "Monthly": {
            "name": RecurringTaskPeriod.MONTHLY.for_notion(),
            "color": "yellow",
            "in_board": True
        },
        "Quarterly": {
            "name": RecurringTaskPeriod.QUARTERLY.for_notion(),
            "color": "blue",
            "in_board": True
        },
        "Yearly": {
            "name": RecurringTaskPeriod.YEARLY.for_notion(),
            "color": "red",
            "in_board": True
        }
    }

    _EISENHOWER: ClassVar[JSONDictType] = {
        "Urgent": {
            "name": Eisen.URGENT.for_notion(),
            "color": "red"
        },
        "Important": {
            "name": Eisen.IMPORTANT.for_notion(),
            "color": "blue"
        }
    }

    _DIFFICULTY = {
        "Easy": {
            "name": Difficulty.EASY.for_notion(),
            "color": "blue"
        },
        "Medium": {
            "name": Difficulty.MEDIUM.for_notion(),
            "color": "green"
        },
        "Hard": {
            "name": Difficulty.HARD.for_notion(),
            "color": "purple"
        }
    }

    _SCHEMA: ClassVar[JSONDictType] = {
        "title": {
            "name": "Name",
            "type": "title"
        },
        "period": {
            "name": "Period",
            "type": "select",
            "options": [{
                "color": cast(Dict[str, str], v)["color"],
                "id": str(uuid.uuid4()),
                "value": cast(Dict[str, str], v)["name"]
            } for v in _PERIOD.values()]
        },
        "group": {
            "name": "Group",
            "type": "text"
        },
        "archived": {
            "name": "Archived",
            "type": "checkbox"
        },
        "eisen": {
            "name": "Eisenhower",
            "type": "multi_select",
            "options": [{
                "color": cast(Dict[str, str], v)["color"],
                "id": str(uuid.uuid4()),
                "value": cast(Dict[str, str], v)["name"]
            } for v in _EISENHOWER.values()]
        },
        "difficulty": {
            "name": "Difficulty",
            "type": "select",
            "options": [{
                "color": cast(Dict[str, str], v)["color"],
                "id": str(uuid.uuid4()),
                "value": cast(Dict[str, str], v)["name"]
            } for v in _DIFFICULTY.values()]
        },
        "due-at-time": {
            "name": "Due At Time",
            "type": "text",
        },
        "due-at-day": {
            "name": "Due At Day",
            "type": "number",
        },
        "due-at-month": {
            "name": "Due At Month",
            "type": "number",
        },
        "suspended": {
            "name": "Suspended",
            "type": "checkbox",
        },
        "must-do": {
            "name": "Must Do",
            "type": "checkbox"
        },
        "skip-rule": {
            "name": "Skip Rule",
            "type": "text"
        },
        "ref-id": {
            "name": "Ref Id",
            "type": "text"
        }
    }

    _KANBAN_ALL_VIEW_SCHEMA: JSONDictType = {
        "name": "Kanban",
        "type": "board",
        "query2": {
            "group_by": "period",
            "filter_operator": "and",
            "aggregations": [{
                "aggregator": "count"
            }],
            "sort": [{
                "property": "suspended",
                "direction": "ascending"
            }, {
                "property": "group",
                "direction": "ascending"
            }, {
                "property": "eisen",
                "direction": "ascending"
            }, {
                "property": "difficulty",
                "direction": "ascending"
            }, {
                "property": "due-at-month",
                "direction": "ascending"
            }, {
                "property": "due-at-day",
                "direction": "ascending"
            }, {
                "property": "due-at-time",
                "direction": "ascending"
            }],
            "filter": {
                "operator": "and",
                "filters": [{
                    "property": "archived",
                    "filter": {
                        "operator": "checkbox_is_not",
                        "value": {
                            "type": "exact",
                            "value": "True"
                        }
                    }
                }]
            }
        },
        "format": {
            "board_groups": [{
                "property": "period",
                "type": "select",
                "value": cast(Dict[str, str], v)["name"],
                "hidden": not cast(Dict[str, bool], v)["in_board"]
            } for v in _PERIOD.values()],
            "board_groups2": [{
                "property": "period",
                "value": {
                    "type": "select",
                    "value": cast(Dict[str, str], v)["name"]
                },
                "hidden": not cast(Dict[str, bool], v)["in_board"]
            } for v in _PERIOD.values()],
            "board_properties": [{
                "property": "period",
                "visible": False
            }, {
                "property": "group",
                "visible": True
            }, {
                "property": "archived",
                "visible": False,
            }, {
                "property": "eisen",
                "visible": True
            }, {
                "property": "difficulty",
                "visible": True
            }, {
                "property": "due-at-time",
                "visible": True
            }, {
                "property": "due-at-day",
                "visible": True
            }, {
                "property": "due-at-month",
                "visible": True
            }, {
                "property": "suspended",
                "visible": True
            }, {
                "property": "must-do",
                "visible": False
            }, {
                "property": "skip-rule",
                "visible": False
            }, {
                "property": "ref-id",
                "visible": False
            }],
            "board_cover_size": "small"
        }
    }

    _DATABASE_VIEW_SCHEMA: JSONDictType = {
        "name": "Database",
        "type": "table",
        "format": {
            "table_properties": [{
                "width": 300,
                "property": "title",
                "visible": True
            }, {
                "width": 100,
                "property": "archived",
                "visible": True
            }, {
                "width": 100,
                "property": "period",
                "visible": True
            }, {
                "width": 100,
                "property": "group",
                "visible": True
            }, {
                "width": 100,
                "property": "eisen",
                "visible": True
            }, {
                "width": 100,
                "property": "difficulty",
                "visible": True
            }, {
                "width": 100,
                "property": "due-at-time",
                "visible": True
            }, {
                "width": 100,
                "property": "due-at-day",
                "visible": True
            }, {
                "width": 100,
                "property": "due-at-month",
                "visible": True
            }, {
                "width": 100,
                "property": "suspended",
                "visible": True
            }, {
                "width": 100,
                "property": "must-do",
                "visible": True
            }, {
                "width": 100,
                "property": "skip-rule",
                "visible": True
            }, {
                "width": 100,
                "property": "ref-id",
                "visible": False
            }]
        }
    }

    _collection: Final[NotionCollection[RecurringTaskRow]]

    def __init__(self, connection: NotionConnection):
        """Constructor."""
        self._collection = NotionCollection[RecurringTaskRow](connection, self._LOCK_FILE_PATH, self)

    def __enter__(self) -> 'RecurringTasksCollection':
        """Enter context."""
        self._collection.initialize()
        return self

    def __exit__(
            self, exc_type: Optional[typing.Type[BaseException]], _exc_val: Optional[BaseException],
            _exc_tb: Optional[TracebackType]) -> None:
        """Exit context."""
        if exc_type is not None:
            return
        self._collection.exit_save()

    def upsert_recurring_tasks_structure(
            self, project_ref_id: EntityId, parent_page: NotionPageLink) -> NotionCollectionLink:
        """Create the Notion-side structure for this collection."""
        return self._collection.upsert_structure(project_ref_id, parent_page)

    def remove_recurring_tasks_structure(self, project_ref_id: EntityId) -> None:
        """Remove the Notion-side structure for this collection."""
        return self._collection.remove_structure(project_ref_id)

    def create_recurring_task(
            self, project_ref_id: EntityId, inbox_collection_link: NotionCollectionLink, name: str, period: str,
            group: str, eisen: List[str], difficulty: Optional[str], due_at_time: Optional[str],
            due_at_day: Optional[int], due_at_month: Optional[int], suspended: bool, skip_rule: Optional[str],
            must_do: bool, ref_id: EntityId) -> RecurringTaskRow:
        """Create a recurring task."""
        new_recurring_task_row = RecurringTaskRow(
            notion_id=NotionId("FAKE-FAKE-FAKE"),
            name=name,
            archived=False,
            period=period,
            group=group,
            eisen=eisen,
            difficulty=difficulty,
            due_at_time=due_at_time,
            due_at_day=due_at_day,
            due_at_month=due_at_month,
            suspended=suspended,
            skip_rule=skip_rule,
            must_do=must_do,
            ref_id=ref_id)
        return cast(RecurringTaskRow, self._collection.create(
            project_ref_id, new_recurring_task_row, inbox_collection_link=inbox_collection_link))

    def link_local_and_notion_entries(self, project_ref_id: EntityId, ref_id: EntityId, notion_id: NotionId) -> None:
        """Link a local entity with the Notio none, useful in syncing processes."""
        self._collection.link_local_and_notion_entries(project_ref_id, ref_id, notion_id)

    def archive_recurring_task(self, project_ref_id: EntityId, ref_id: EntityId) -> None:
        """Remove a particular recurring task."""
        self._collection.archive(project_ref_id, ref_id)

    def load_all_recurring_tasks(self, project_ref_id: EntityId) -> Iterable[RecurringTaskRow]:
        """Retrieve all the Notion-side recurring tasks."""
        return cast(Iterable[RecurringTaskRow], self._collection.load_all(project_ref_id))

    def load_recurring_task(self, project_ref_id: EntityId, ref_id: EntityId) -> RecurringTaskRow:
        """Retrieve the Notion-side recurring task associated with a particular entity."""
        return cast(RecurringTaskRow, self._collection.load(project_ref_id, ref_id))

    def save_recurring_task(
            self, project_ref_id: EntityId, new_recurring_task_row: RecurringTaskRow,
            inbox_collection_link: Optional[NotionCollectionLink] = None) -> None:
        """Update the Notion-side recurring task with new data."""
        self._collection.save(project_ref_id, new_recurring_task_row, inbox_collection_link=inbox_collection_link)

    def hard_remove_recurring_task(self, project_ref_id: EntityId, ref_id: EntityId) -> None:
        """Hard remove the Notion entity associated with a local entity."""
        self._collection.hard_remove(project_ref_id, ref_id)

    @staticmethod
    def get_page_name() -> str:
        """Get the name for the page."""
        return RecurringTasksCollection._PAGE_NAME

    @staticmethod
    def get_notion_schema() -> JSONDictType:
        """Get the Notion schema for the collection."""
        return RecurringTasksCollection._SCHEMA

    @staticmethod
    def get_view_schemas() -> Dict[str, JSONDictType]:
        """Get the Notion view schemas for the collection."""
        return {
            "kanban_all_view_id": RecurringTasksCollection._KANBAN_ALL_VIEW_SCHEMA,
            "database_view_id": RecurringTasksCollection._DATABASE_VIEW_SCHEMA
        }

    @staticmethod
    @typing.no_type_check
    def merge_notion_schemas(old_schema: JSONDictType, new_schema: JSONDictType) -> JSONDictType:
        """Merge an old and new schema for the collection."""
        combined_schema = {}

        # Merging schema is limited right now. Basically we assume the new schema takes
        # precedence over the old one, except for select and multi_select, which have a set
        # of options for them which are identified by "id"s. We wanna keep these stable
        # across schema updates.
        # As a special case, the big plan item is left to whatever value it had before
        # since this thing is managed via the big plan syncing flow!
        # As another special case, the recurring tasks group key is left to whatever value it had
        # before since this thing is managed by the other flows!
        for (schema_item_name, schema_item) in new_schema.items():
            if schema_item_name in ("bigplan2", "group"):
                combined_schema[schema_item_name] = old_schema[schema_item_name] \
                    if (schema_item_name in old_schema and old_schema[schema_item_name]["type"] == "select") \
                    else schema_item
            elif schema_item["type"] == "select" or schema_item["type"] == "multi_select":
                if schema_item_name in old_schema:
                    old_v = old_schema[schema_item_name]

                    combined_schema[schema_item_name] = {
                        "name": schema_item["name"],
                        "type": schema_item["type"],
                        "options": []
                    }

                    for option in schema_item["options"]:
                        old_option = next((old_o for old_o in old_v["options"] if old_o["value"] == option["value"]),
                                          None)
                        if old_option is not None:
                            combined_schema[schema_item_name]["options"].append({
                                "color": option["color"],
                                "value": option["value"],
                                "id": old_option["id"]
                            })
                        else:
                            combined_schema[schema_item_name]["options"].append(option)
                else:
                    combined_schema[schema_item_name] = schema_item
            else:
                combined_schema[schema_item_name] = schema_item

        return combined_schema

    @staticmethod
    def copy_row_to_notion_row(
            client: NotionClient, row: RecurringTaskRow, notion_row: CollectionRowBlock,
            **kwargs: NotionCollectionKWArgsType) -> CollectionRowBlock:
        """Copy the fields of the local row to the actual Notion structure."""
        if row.ref_id is None:
            raise Exception(f"Recurring task row '{row.name}' which is synced must have a ref id")

        inbox_collection_link = cast(NotionCollectionLink, kwargs.get("inbox_collection_link", None))

        notion_row.title = row.name
        notion_row.archived = row.archived
        notion_row.period = row.period
        notion_row.group = row.group
        notion_row.eisenhower = row.eisen
        notion_row.difficulty = row.difficulty
        notion_row.due_at_time = row.due_at_time
        notion_row.due_at_day = row.due_at_day
        notion_row.due_at_month = row.due_at_month
        notion_row.suspended = row.suspended
        notion_row.skip_rule = row.skip_rule
        notion_row.must_do = row.must_do
        notion_row.ref_id = row.ref_id

        if inbox_collection_link:
            LOGGER.info(f"Creating views structure for recurring task {notion_row}")

            client.attach_view_block_as_child_of_block(
                notion_row, 0, inbox_collection_link.collection_id,
                RecurringTasksCollection._get_view_schema_for_recurring_task_desc(row.ref_id))

        return notion_row

    @staticmethod
    def copy_notion_row_to_row(inbox_task_notion_row: CollectionRowBlock) -> RecurringTaskRow:
        """Transform the live system data to something suitable for basic storage."""
        return RecurringTaskRow(
            notion_id=inbox_task_notion_row.id,
            name=inbox_task_notion_row.title,
            archived=inbox_task_notion_row.archived,
            period=inbox_task_notion_row.period,
            group=inbox_task_notion_row.group,
            eisen=common.clean_eisenhower(inbox_task_notion_row.eisenhower),
            difficulty=inbox_task_notion_row.difficulty,
            due_at_time=inbox_task_notion_row.due_at_time,
            due_at_day=inbox_task_notion_row.due_at_day,
            due_at_month=inbox_task_notion_row.due_at_month,
            suspended=inbox_task_notion_row.suspended,
            skip_rule=inbox_task_notion_row.skip_rule,
            must_do=inbox_task_notion_row.must_do,
            ref_id=inbox_task_notion_row.ref_id)

    @staticmethod
    def _get_view_schema_for_recurring_task_desc(recurring_task_ref_id: str) -> JSONDictType:
        """Get the view schema for a recurring tasks details view."""
        return {
            "name": "Inbox Tasks",
            "query2": {
                "filter_operator": "and",
                "sort": [{
                    "property": "status",
                    "direction": "ascending"
                }, {
                    "property": "due-date",
                    "direction": "ascending"
                }],
                "filter": {
                    "operator": "and",
                    "filters": [{
                        "property": "recurring-task-ref-id",
                        "filter": {
                            "operator": "string_is",
                            "value": {
                                "type": "exact",
                                "value": recurring_task_ref_id
                            }
                        }
                    }]
                }
            },
            "format": {
                "table_properties": [{
                    "width": 300,
                    "property": "title",
                    "visible": True
                }, {
                    "width": 100,
                    "property": "status",
                    "visible": True
                }, {
                    "width": 100,
                    "property": "bigplan2",
                    "visible": False
                }, {
                    "width": 100,
                    "property": "due-date",
                    "visible": True
                }, {
                    "width": 100,
                    "property": "eisen",
                    "visible": True
                }, {
                    "width": 100,
                    "property": "difficulty",
                    "visible": True
                }, {
                    "width": 100,
                    "property": "fromscript",
                    "visible": False
                }, {
                    "width": 100,
                    "property": "period",
                    "visible": False
                }, {
                    "width": 100,
                    "property": "timeline",
                    "visible": False
                }]
            }
        }