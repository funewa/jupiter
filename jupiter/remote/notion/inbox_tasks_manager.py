"""The centralised point for interacting with Notion inbox tasks."""
import copy
import hashlib
import uuid
from typing import Final, ClassVar, cast, Dict, Optional, Iterable

from jupiter.domain.difficulty import Difficulty
from jupiter.domain.eisen import Eisen
from jupiter.domain.inbox_tasks.inbox_task_source import InboxTaskSource
from jupiter.domain.inbox_tasks.inbox_task_status import InboxTaskStatus
from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import (
    InboxTaskNotionManager,
    NotionInboxTaskNotFoundError,
)
from jupiter.domain.inbox_tasks.notion_inbox_task import NotionInboxTask
from jupiter.domain.inbox_tasks.notion_inbox_task_collection import (
    NotionInboxTaskCollection,
)
from jupiter.domain.recurring_task_period import RecurringTaskPeriod
from jupiter.domain.remote.notion.field_label import NotionFieldLabel
from jupiter.domain.workspaces.notion_workspace import NotionWorkspace
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.base.notion_id import NotionId, BAD_NOTION_ID
from jupiter.framework.json import JSONDictType
from jupiter.remote.notion.common import NotionLockKey, format_name_for_option
from jupiter.remote.notion.infra.client import (
    NotionFieldProps,
    NotionFieldShow,
)
from jupiter.remote.notion.infra.client_v2 import NotionTextBlock
from jupiter.remote.notion.infra.collections_manager import (
    NotionCollectionsManager,
    NotionCollectionItemNotFoundError,
)
from jupiter.utils.global_properties import GlobalProperties
from jupiter.utils.time_provider import TimeProvider


class NotionInboxTasksManager(InboxTaskNotionManager):
    """The centralised point for interacting with Notion inbox tasks."""

    _KEY: ClassVar[str] = "inbox-tasks"
    _PAGE_NAME: ClassVar[str] = "Inbox Tasks"
    _PAGE_ICON: ClassVar[str] = "📥"

    _STATUS: ClassVar[JSONDictType] = {
        "Not Started": {
            "name": InboxTaskStatus.NOT_STARTED.for_notion(),
            "color": "gray",
            "in_board": False,
        },
        "Accepted": {
            "name": InboxTaskStatus.ACCEPTED.for_notion(),
            "color": "gray",
            "in_board": True,
        },
        "Recurring": {
            "name": InboxTaskStatus.RECURRING.for_notion(),
            "color": "gray",
            "in_board": True,
        },
        "In Progress": {
            "name": InboxTaskStatus.IN_PROGRESS.for_notion(),
            "color": "blue",
            "in_board": True,
        },
        "Blocked": {
            "name": InboxTaskStatus.BLOCKED.for_notion(),
            "color": "yellow",
            "in_board": True,
        },
        "Not Done": {
            "name": InboxTaskStatus.NOT_DONE.for_notion(),
            "color": "red",
            "in_board": True,
        },
        "Done": {
            "name": InboxTaskStatus.DONE.for_notion(),
            "color": "green",
            "in_board": True,
        },
    }

    _SOURCE: ClassVar[JSONDictType] = {
        "User": {"name": InboxTaskSource.USER.for_notion(), "color": "blue"},
        "Habit": {"name": InboxTaskSource.HABIT.for_notion(), "color": "yellow"},
        "Chore": {"name": InboxTaskSource.CHORE.for_notion(), "color": "gray"},
        "Big Plan": {"name": InboxTaskSource.BIG_PLAN.for_notion(), "color": "green"},
        "Metric": {"name": InboxTaskSource.METRIC.for_notion(), "color": "red"},
        "Person Catchup": {
            "name": InboxTaskSource.PERSON_CATCH_UP.for_notion(),
            "color": "purple",
        },
        "Person Birthday": {
            "name": InboxTaskSource.PERSON_BIRTHDAY.for_notion(),
            "color": "orange",
        },
        "Slack": {"name": InboxTaskSource.SLACK_TASK.for_notion(), "color": "green"},
        "Email": {"name": InboxTaskSource.EMAIL_TASK.for_notion(), "color": "green"},
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

    _DIFFICULTY: ClassVar[JSONDictType] = {
        "Easy": {"name": Difficulty.EASY.for_notion(), "color": "blue"},
        "Medium": {"name": Difficulty.MEDIUM.for_notion(), "color": "green"},
        "Hard": {"name": Difficulty.HARD.for_notion(), "color": "purple"},
    }

    _RECURRING_TASK_PERIOD: ClassVar[JSONDictType] = {
        "Daily": {"name": RecurringTaskPeriod.DAILY.for_notion(), "color": "orange"},
        "Weekly": {"name": RecurringTaskPeriod.WEEKLY.for_notion(), "color": "red"},
        "Monthly": {"name": RecurringTaskPeriod.MONTHLY.for_notion(), "color": "blue"},
        "Quarterly": {
            "name": RecurringTaskPeriod.QUARTERLY.for_notion(),
            "color": "green",
        },
        "Yearly": {"name": RecurringTaskPeriod.YEARLY.for_notion(), "color": "yellow"},
    }

    _SCHEMA: ClassVar[JSONDictType] = {
        "title": {"name": "Name", "type": "title"},
        "ref-id": {"name": "Ref Id", "type": "text"},
        "status": {
            "name": "Status",
            "type": "select",
            "options": [
                {
                    "color": cast(Dict[str, str], v)["color"],
                    "id": str(uuid.uuid4()),
                    "value": cast(Dict[str, str], v)["name"],
                }
                for v in _STATUS.values()
            ],
        },
        "archived": {"name": "Archived", "type": "checkbox"},
        "source": {
            "name": "Source",
            "type": "select",
            "options": [
                {
                    "color": cast(Dict[str, str], v)["color"],
                    "id": str(uuid.uuid4()),
                    "value": cast(Dict[str, str], v)["name"],
                }
                for v in _SOURCE.values()
            ],
        },
        "project-ref-id": {"name": "Project Id", "type": "text"},
        "project-name": {
            "name": "Project",
            "type": "select",
            "options": [{"color": "gray", "id": str(uuid.uuid4()), "value": "None"}],
        },
        "big-plan-ref-id": {"name": "Big Plan Id", "type": "text"},
        "bigplan2": {
            "name": "Big Plan",
            "type": "select",
            "options": [{"color": "gray", "id": str(uuid.uuid4()), "value": "None"}],
            "alt-id": "big-plan-name",
            "alt-name": "big_plan_name",
        },
        "habit-ref-id": {"name": "Habit Id", "type": "text"},
        "chore-ref-id": {"name": "Chore Id", "type": "text"},
        "metric-ref-id": {"name": "Metric Id", "type": "text"},
        "person-ref-id": {"name": "Person Id", "type": "text"},
        "slack-task-ref-id": {"name": "Slack Task Id", "type": "text"},
        "email-task-ref-id": {"name": "Email Task Id", "type": "text"},
        "actionable-date": {"name": "Actionable Date", "type": "date"},
        "due-date": {"name": "Due Date", "type": "date"},
        "eisen": {
            "name": "Eisenhower",
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
        "difficulty": {
            "name": "Difficulty",
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
        "timeline": {
            "name": "Recurring Timeline",
            "type": "text",
            "alt-id": "recurring-timeline",
            "alt-name": "recurring_timeline",
        },
        "repeat-index": {
            "name": "Recurring Repeat Index",
            "type": "number",
            "alt-id": "recurring-repeat-index",
            "alt-name": "recurring_repeat_index",
        },
        "period": {
            "name": "Recurring Period",
            "type": "select",
            "options": [
                {
                    "color": cast(Dict[str, str], v)["color"],
                    "id": str(uuid.uuid4()),
                    "value": cast(Dict[str, str], v)["name"],
                }
                for v in _RECURRING_TASK_PERIOD.values()
            ],
            "alt-id": "recurring-period",
            "alt-name": "recurring_period",
        },
        "recurring-task-gen-right-now": {
            "name": "Recurring Gen Right Now",
            "type": "date",
            "alt-id": "recurring-gen-right-now",
            "alt-name": "recurring_gen_right_now",
        },
        "last-edited-time": {"name": "Last Edited Time", "type": "last_edited_time"},
    }

    _SCHEMA_PROPERTIES = [
        NotionFieldProps(name="title", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="status", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="source", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="eisen", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="difficulty", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="actionable-date", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="due-date", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="archived", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="ref-id", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="project-ref-id", show=NotionFieldShow.HIDE),
        NotionFieldProps(name="project-name", show=NotionFieldShow.SHOW),
        NotionFieldProps(name="big-plan-ref-id", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="bigplan2", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="habit-ref-id", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="chore-ref-id", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="metric-ref-id", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="person-ref-id", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="slack-task-ref-id", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="email-task-ref-id", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="period", show=NotionFieldShow.HIDE_IF_EMPTY),
        NotionFieldProps(name="timeline", show=NotionFieldShow.HIDE),
        NotionFieldProps(name="repeat-index", show=NotionFieldShow.HIDE),
        NotionFieldProps(
            name="recurring-task-gen-right-now", show=NotionFieldShow.HIDE
        ),
        NotionFieldProps(name="last-edited-time", show=NotionFieldShow.HIDE),
    ]

    _KANBAN_BY_EISEN_SUBGROUP_FORMAT: ClassVar[JSONDictType] = {
        "board_groups": [
            {
                "property": "status",
                "type": "select",
                "value": cast(Dict[str, str], v)["name"],
                "hidden": not cast(Dict[str, bool], v)["in_board"],
            }
            for v in _STATUS.values()
        ]
        + [{"property": "status", "type": "select", "hidden": True}],
        "board_groups2": [
            {
                "property": "status",
                "value": {"type": "select", "value": cast(Dict[str, str], v)["name"]},
                "hidden": not cast(Dict[str, bool], v)["in_board"],
            }
            for v in _STATUS.values()
        ]
        + [{"property": "status", "value": {"type": "select"}, "hidden": True}],
        "board_columns_by": {
            "property": "status",
            "type": "select",
            "sort": {"type": "manual"},
            "hideEmptyGroups": False,
            "disableBoardColorColumns": False,
        },
        "collection_group_by": {
            "property": "eisen",
            "sort": {"type": "manual"},
            "type": "select",
        },
        "collection_groups": [
            {
                "property": "eisen",
                "value": {"type": "select", "value": cast(Dict[str, str], v)["name"]},
                "hidden": False,
            }
            for v in _EISENHOWER.values()
        ]
        + [{"property": "eisen", "value": {"type": "select"}, "hidden": True}],
        "board_properties": [
            {"property": "ref-id", "visible": False},
            {"property": "status", "visible": False},
            {"property": "source", "visible": True},
            {"property": "archived", "visible": False},
            {"property": "project-ref-id", "visible": False},
            {"property": "project-name", "visible": True},
            {"property": "big-plan-ref-id", "visible": False},
            {"property": "bigplan2", "visible": True},
            {"property": "habit-ref-id", "visible": False},
            {"property": "chore-ref-id", "visible": False},
            {"property": "metric-ref-id", "visible": False},
            {"property": "person-ref-id", "visible": False},
            {"property": "slack-task-ref-id", "visible": False},
            {"property": "email-task-ref-id", "visible": False},
            {"property": "actionable-date", "visible": False},
            {"property": "due-date", "visible": True},
            {"property": "eisen", "visible": False},
            {"property": "difficulty", "visible": True},
            {"property": "timeline", "visible": False},
            {"property": "repeat-index", "visible": False},
            {"property": "period", "visible": True},
            {"property": "recurring-task-gen-right-now", "visible": False},
            {"property": "last-edited-time", "visible": False},
        ],
        "board_cover_size": "small",
    }

    _KANBAN_BY_PROJECT_SUBGROUP_FORMAT: ClassVar[JSONDictType] = {
        "board_groups": [
            {
                "property": "status",
                "type": "select",
                "value": cast(Dict[str, str], v)["name"],
                "hidden": not cast(Dict[str, bool], v)["in_board"],
            }
            for v in _STATUS.values()
        ]
        + [{"property": "status", "type": "select", "hidden": True}],
        "board_groups2": [
            {
                "property": "status",
                "value": {"type": "select", "value": cast(Dict[str, str], v)["name"]},
                "hidden": not cast(Dict[str, bool], v)["in_board"],
            }
            for v in _STATUS.values()
        ]
        + [{"property": "status", "value": {"type": "select"}, "hidden": True}],
        "board_columns_by": {
            "property": "status",
            "type": "select",
            "sort": {"type": "manual"},
            "hideEmptyGroups": False,
            "disableBoardColorColumns": False,
        },
        "collection_group_by": {
            "property": "project-name",
            "sort": {"type": "manual"},
            "type": "select",
        },
        "board_properties": [
            {"property": "ref-id", "visible": False},
            {"property": "status", "visible": False},
            {"property": "source", "visible": True},
            {"property": "archived", "visible": False},
            {"property": "project-ref-id", "visible": False},
            {"property": "project-name", "visible": False},
            {"property": "big-plan-ref-id", "visible": False},
            {"property": "bigplan2", "visible": True},
            {"property": "habit-ref-id", "visible": False},
            {"property": "chore-ref-id", "visible": False},
            {"property": "metric-ref-id", "visible": False},
            {"property": "person-ref-id", "visible": False},
            {"property": "slack-task-ref-id", "visible": False},
            {"property": "email-task-ref-id", "visible": False},
            {"property": "actionable-date", "visible": False},
            {"property": "due-date", "visible": True},
            {"property": "eisen", "visible": True},
            {"property": "difficulty", "visible": True},
            {"property": "timeline", "visible": False},
            {"property": "repeat-index", "visible": False},
            {"property": "period", "visible": True},
            {"property": "recurring-task-gen-right-now", "visible": False},
            {"property": "last-edited-time", "visible": False},
        ],
        "board_cover_size": "small",
    }

    _KANBAN_FORMAT: ClassVar[JSONDictType] = {
        "board_groups": [
            {
                "property": "status",
                "type": "select",
                "value": cast(Dict[str, str], v)["name"],
                "hidden": not cast(Dict[str, bool], v)["in_board"],
            }
            for v in _STATUS.values()
        ]
        + [{"property": "status", "type": "select", "hidden": True}],
        "board_groups2": [
            {
                "property": "status",
                "value": {"type": "select", "value": cast(Dict[str, str], v)["name"]},
                "hidden": not cast(Dict[str, bool], v)["in_board"],
            }
            for v in _STATUS.values()
        ]
        + [{"property": "status", "value": {"type": "select"}, "hidden": True}],
        "board_columns_by": {
            "property": "status",
            "type": "select",
            "sort": {"type": "manual"},
            "hideEmptyGroups": False,
            "disableBoardColorColumns": False,
        },
        "board_properties": [
            {"property": "ref-id", "visible": False},
            {"property": "status", "visible": False},
            {"property": "source", "visible": True},
            {"property": "archived", "visible": False},
            {"property": "project-ref-id", "visible": False},
            {"property": "project-name", "visible": False},
            {"property": "big-plan-ref-id", "visible": False},
            {"property": "bigplan2", "visible": True},
            {"property": "habit-ref-id", "visible": False},
            {"property": "chore-ref-id", "visible": False},
            {"property": "metric-ref-id", "visible": False},
            {"property": "person-ref-id", "visible": False},
            {"property": "slack-task-ref-id", "visible": False},
            {"property": "email-task-ref-id", "visible": False},
            {"property": "actionable-date", "visible": False},
            {"property": "due-date", "visible": True},
            {"property": "eisen", "visible": True},
            {"property": "difficulty", "visible": True},
            {"property": "timeline", "visible": False},
            {"property": "repeat-index", "visible": False},
            {"property": "period", "visible": True},
            {"property": "recurring-task-gen-right-now", "visible": False},
            {"property": "last-edited-time", "visible": False},
        ],
        "board_cover_size": "small",
    }

    _KANBAN_BY_EISEN_SUBGROUPS_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban By Eisen",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "actionable-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "today"},
                                },
                            },
                            {
                                "property": "actionable-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                ],
            },
        },
        "format": _KANBAN_BY_EISEN_SUBGROUP_FORMAT,
    }

    _KANBAN_HABITS_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban Habits",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "property": "source",
                        "filter": {
                            "operator": "enum_is",
                            "value": {
                                "type": "exact",
                                "value": InboxTaskSource.HABIT.for_notion(),
                            },
                        },
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "actionable-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "today"},
                                },
                            },
                            {
                                "property": "actionable-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                ],
            },
        },
        "format": _KANBAN_FORMAT,
    }

    _KANBAN_BY_PROJECT_SUBGROUPS_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban By Project",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "actionable-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "today"},
                                },
                            },
                            {
                                "property": "actionable-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                ],
            },
        },
        "format": _KANBAN_BY_PROJECT_SUBGROUP_FORMAT,
    }

    _KANBAN_ALL_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban All",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "actionable-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "today"},
                                },
                            },
                            {
                                "property": "actionable-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                ],
            },
        },
        "format": _KANBAN_FORMAT,
    }

    _KANBAN_URGENT_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban Urgent",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "property": "status",
                        "filter": {
                            "operator": "enum_is_not",
                            "value": {"type": "exact", "value": "Done"},
                        },
                    },
                    {
                        "property": "status",
                        "filter": {
                            "operator": "enum_is_not",
                            "value": {"type": "exact", "value": "Not Done"},
                        },
                    },
                    {
                        "property": "eisen",
                        "filter": {
                            "operator": "enum_contains",
                            "value": {"type": "exact", "value": "Urgent"},
                        },
                    },
                ],
            },
        },
        "format": _KANBAN_FORMAT,
    }

    _KANBAN_DUE_TODAY_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban Due Today Or Exceeded",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "actionable-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "today"},
                                },
                            },
                            {
                                "property": "actionable-date",
                                "filter": {"operator": "today"},
                            },
                        ],
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "due-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "tomorrow"},
                                },
                            },
                            {
                                "property": "due-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                ],
            },
        },
        "format": _KANBAN_FORMAT,
    }

    _KANBAN_DUE_THIS_WEEK_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban Due This Week Or Exceeded",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "actionable-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "today"},
                                },
                            },
                            {
                                "property": "actionable-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "due-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {
                                        "type": "relative",
                                        "value": "one_week_from_now",
                                    },
                                },
                            },
                            {
                                "property": "due-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                ],
            },
        },
        "format": _KANBAN_FORMAT,
    }

    _KANBAN_DUE_THIS_MONTH_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Kanban Due This Month Or Exceeded",
        "type": "board",
        "query2": {
            "group_by": "status",
            "filter_operator": "and",
            "aggregations": [{"aggregator": "count"}],
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "actionable-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {"type": "relative", "value": "today"},
                                },
                            },
                            {
                                "property": "actionable-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                    {
                        "operator": "or",
                        "filters": [
                            {
                                "property": "due-date",
                                "filter": {
                                    "operator": "date_is_on_or_before",
                                    "value": {
                                        "type": "relative",
                                        "value": "one_month_from_now",
                                    },
                                },
                            },
                            {
                                "property": "due-date",
                                "filter": {"operator": "is_empty"},
                            },
                        ],
                    },
                ],
            },
        },
        "format": _KANBAN_FORMAT,
    }

    _CALENDAR_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Not Completed By Date",
        "type": "calendar",
        "query2": {
            "sort": [
                {"property": "due-date", "direction": "ascending"},
                {"property": "eisen", "direction": "ascending"},
                {"property": "difficulty", "direction": "ascending"},
                {"property": "period", "direction": "ascending"},
            ],
            "filter": {
                "operator": "and",
                "filters": [
                    {
                        "property": "archived",
                        "filter": {
                            "operator": "checkbox_is_not",
                            "value": {"type": "exact", "value": True},
                        },
                    },
                    {
                        "property": "status",
                        "filter": {
                            "operator": "enum_is_not",
                            "value": {"type": "exact", "value": "Done"},
                        },
                    },
                ],
            },
        },
        "format": {
            "calendar_properties": [
                {"property": "title", "visible": True},
                {
                    "property": "ref-id",
                    "visible": False,
                },
                {"property": "status", "visible": True},
                {"property": "source", "visible": True},
                {"property": "archived", "visible": False},
                {"property": "project-ref-id", "visible": False},
                {"property": "project-name", "visible": True},
                {"property": "big-plan-ref-id", "visible": False},
                {"property": "bigplan2", "visible": True},
                {"property": "habit-ref-id", "visible": False},
                {"property": "chore-ref-id", "visible": False},
                {"property": "metric-ref-id", "visible": False},
                {"property": "person-ref-id", "visible": False},
                {"property": "slack-task-ref-id", "visible": False},
                {"property": "email-task-ref-id", "visible": False},
                {"property": "actionable-date", "visible": False},
                {"property": "due-date", "visible": False},
                {"property": "eisen", "visible": True},
                {"property": "difficulty", "visible": True},
                {"property": "timeline", "visible": False},
                {"property": "repeat-index", "visible": False},
                {"property": "period", "visible": True},
                {"property": "recurring-task-gen-right-now", "visible": False},
                {"property": "last-edited-time", "visible": False},
            ]
        },
    }

    _DATABASE_VIEW_SCHEMA: ClassVar[JSONDictType] = {
        "name": "Database",
        "type": "table",
        "format": {
            "table_properties": [
                {"width": 300, "property": "title", "visible": True},
                {"width": 100, "property": "ref-id", "visible": True},
                {"width": 100, "property": "project-ref-id", "visible": True},
                {"width": 100, "property": "project-name", "visible": True},
                {"width": 100, "property": "big-plan-ref-id", "visible": True},
                {"width": 100, "property": "bigplan2", "visible": True},
                {"width": 100, "property": "habit-ref-id", "visible": True},
                {"width": 100, "property": "chore-ref-id", "visible": True},
                {"width": 100, "property": "metric-ref-id", "visible": True},
                {"width": 100, "property": "person-ref-id", "visible": True},
                {"width": 100, "property": "slack-task-ref-id", "visible": True},
                {"width": 100, "property": "email-task-ref-id", "visible": True},
                {"width": 100, "property": "archived", "visible": True},
                {"width": 100, "property": "status", "visible": True},
                {"width": 100, "property": "source", "visible": True},
                {"width": 100, "property": "actionable-date", "visible": True},
                {"width": 100, "property": "due-date", "visible": True},
                {"width": 100, "property": "eisen", "visible": True},
                {"width": 100, "property": "difficulty", "visible": True},
                {"width": 100, "property": "timeline", "visible": True},
                {"width": 100, "property": "repeat-index", "visible": True},
                {"width": 100, "property": "period", "visible": True},
                {
                    "width": 100,
                    "property": "recurring-task-gen-right-now",
                    "visible": True,
                },
                {"width": 100, "property": "archived", "visible": True},
                {"property": "last-edited-time", "visible": True},
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
        self, parent: NotionWorkspace, trunk: NotionInboxTaskCollection
    ) -> None:
        """Upsert the Notion-side inbox task."""
        self._collections_manager.upsert_collection(
            key=NotionLockKey(f"{self._KEY}:{trunk.ref_id}"),
            parent_page_notion_id=parent.notion_id,
            name=self._PAGE_NAME,
            icon=self._PAGE_ICON,
            schema=self._SCHEMA,
            schema_properties=self._SCHEMA_PROPERTIES,
            view_schemas=[
                (
                    "kanban_by_eisen_subgroup_view_id",
                    NotionInboxTasksManager._KANBAN_BY_EISEN_SUBGROUPS_VIEW_SCHEMA,
                ),
                (
                    "kanban_habits_view_id",
                    NotionInboxTasksManager._KANBAN_HABITS_VIEW_SCHEMA,
                ),
                (
                    "kanban_by_project_subgroup_view_id",
                    NotionInboxTasksManager._KANBAN_BY_PROJECT_SUBGROUPS_VIEW_SCHEMA,
                ),
                ("kanban_all_view_id", NotionInboxTasksManager._KANBAN_ALL_VIEW_SCHEMA),
                (
                    "kanban_urgent_view_id",
                    NotionInboxTasksManager._KANBAN_URGENT_VIEW_SCHEMA,
                ),
                (
                    "kanban_due_today_view_id",
                    NotionInboxTasksManager._KANBAN_DUE_TODAY_VIEW_SCHEMA,
                ),
                (
                    "kanban_due_this_week_view_id",
                    NotionInboxTasksManager._KANBAN_DUE_THIS_WEEK_VIEW_SCHEMA,
                ),
                (
                    "kanban_due_this_month_view_id",
                    NotionInboxTasksManager._KANBAN_DUE_THIS_MONTH_VIEW_SCHEMA,
                ),
                ("calendar_view_id", NotionInboxTasksManager._CALENDAR_VIEW_SCHEMA),
                ("database_view_id", NotionInboxTasksManager._DATABASE_VIEW_SCHEMA),
            ],
        )

    def upsert_inbox_tasks_big_plan_field_options(
        self, ref_id: EntityId, big_plans_labels: Iterable[NotionFieldLabel]
    ) -> None:
        """Upsert the Notion-side structure for the 'big plan' select field."""
        inbox_big_plan_options = [
            {
                "color": self._get_stable_color(str(bp.notion_link_uuid)),
                "id": str(bp.notion_link_uuid),
                "value": format_name_for_option(bp.name),
            }
            for bp in big_plans_labels
        ]

        new_schema: JSONDictType = copy.deepcopy(self._SCHEMA)
        new_schema["bigplan2"]["options"] = inbox_big_plan_options  # type: ignore

        self._collections_manager.save_collection_no_merge(
            NotionLockKey(f"{self._KEY}:{ref_id}"),
            self._PAGE_NAME,
            self._PAGE_ICON,
            new_schema,
            "bigplan2",
        )

    def upsert_inbox_tasks_project_field_options(
        self, ref_id: EntityId, project_labels: Iterable[NotionFieldLabel]
    ) -> None:
        """Upsert the Notion-side structure for the 'project' select field."""
        inbox_big_plan_options = [
            {
                "color": self._get_stable_color(str(pl.notion_link_uuid)),
                "id": str(pl.notion_link_uuid),
                "value": format_name_for_option(pl.name),
            }
            for pl in project_labels
        ]

        new_schema: JSONDictType = copy.deepcopy(self._SCHEMA)
        new_schema["project-name"]["options"] = inbox_big_plan_options  # type: ignore

        self._collections_manager.save_collection_no_merge(
            NotionLockKey(f"{self._KEY}:{ref_id}"),
            self._PAGE_NAME,
            self._PAGE_ICON,
            new_schema,
            "project-name",
        )

        new_view: JSONDictType = copy.deepcopy(
            NotionInboxTasksManager._KANBAN_BY_PROJECT_SUBGROUPS_VIEW_SCHEMA
        )
        new_view["format"]["collection_groups"] = [  # type: ignore
            {
                "property": "project-name",
                "value": {"type": "select", "value": format_name_for_option(pl.name)},
                "hidden": False,
            }
            for pl in sorted(project_labels, key=lambda x: x.created_time)
        ] + [{"property": "project-name", "value": {"type": "select"}, "hidden": True}]

        self._collections_manager.quick_update_view_for_collection(
            NotionLockKey(f"{self._KEY}:{ref_id}"),
            "kanban_by_project_subgroup_view_id",
            new_view,
        )

    def upsert_leaf(
        self, trunk_ref_id: EntityId, leaf: NotionInboxTask
    ) -> NotionInboxTask:
        """Upsert a inbox task."""
        link = self._collections_manager.upsert_collection_item(
            timezone=self._global_properties.timezone,
            schema=self._SCHEMA,
            key=NotionLockKey(f"{leaf.ref_id}"),
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            new_leaf=leaf,
            no_properties_fields=["notes"],
            content_block=NotionTextBlock(notion_id=BAD_NOTION_ID, text=leaf.notes)
            if leaf.notes
            else None,
        )
        return link.item_info

    def save_leaf(
        self,
        trunk_ref_id: EntityId,
        leaf: NotionInboxTask,
    ) -> NotionInboxTask:
        """Update the Notion-side inbox task with new data."""
        try:
            link = self._collections_manager.save_collection_item(
                timezone=self._global_properties.timezone,
                schema=self._SCHEMA,
                key=NotionLockKey(f"{leaf.ref_id}"),
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
                row=leaf,
                no_properties_fields=["notes"],
                content_block=NotionTextBlock(notion_id=BAD_NOTION_ID, text=leaf.notes)
                if leaf.notes
                else None,
            )
            return link.item_info
        except NotionCollectionItemNotFoundError as err:
            raise NotionInboxTaskNotFoundError(
                f"Notion inbox task with id {leaf.ref_id} was not found"
            ) from err

    def load_all_leaves(self, trunk_ref_id: EntityId) -> Iterable[NotionInboxTask]:
        """Retrieve all the Notion-side inbox tasks."""
        return [
            l.item_info
            for l in self._collections_manager.load_all_collection_items(
                timezone=self._global_properties.timezone,
                schema=self._SCHEMA,
                ctor=NotionInboxTask,
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
                no_properties_fields={"notes": None},
            )
        ]

    def load_leaf(
        self, trunk_ref_id: EntityId, leaf_ref_id: EntityId
    ) -> NotionInboxTask:
        """Retrieve the Notion-side inbox task associated with a particular entity."""
        try:
            link = self._collections_manager.load_collection_item(
                timezone=self._global_properties.timezone,
                schema=self._SCHEMA,
                ctor=NotionInboxTask,
                key=NotionLockKey(f"{leaf_ref_id}"),
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
                no_properties_fields={"notes": None},
            )
            return link.item_info
        except NotionCollectionItemNotFoundError as err:
            raise NotionInboxTaskNotFoundError(
                f"Notion inbox task with id {leaf_ref_id} was not found"
            ) from err

    def remove_leaf(
        self, trunk_ref_id: EntityId, leaf_ref_id: Optional[EntityId]
    ) -> None:
        """Hard remove the Notion entity associated with a local entity."""
        try:
            self._collections_manager.remove_collection_item(
                key=NotionLockKey(f"{leaf_ref_id}"),
                collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            )
        except NotionCollectionItemNotFoundError as err:
            raise NotionInboxTaskNotFoundError(
                f"Notion inbox task with id {leaf_ref_id} was not found"
            ) from err

    def drop_all_leaves(self, trunk_ref_id: EntityId) -> None:
        """Remove all inbox tasks Notion-side."""
        self._collections_manager.drop_all_collection_items(
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}")
        )

    def load_all_saved_ref_ids(self, trunk_ref_id: EntityId) -> Iterable[EntityId]:
        """Retrieve all the saved ref ids for the inbox tasks tasks."""
        return self._collections_manager.load_all_collection_items_saved_ref_ids(
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}")
        )

    def load_all_saved_notion_ids(self, trunk_ref_id: EntityId) -> Iterable[NotionId]:
        """Retrieve all the saved Notion-ids for these tasks."""
        return self._collections_manager.load_all_collection_items_saved_notion_ids(
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}")
        )

    def link_local_and_notion_leaves(
        self, trunk_ref_id: EntityId, ref_id: EntityId, notion_id: NotionId
    ) -> None:
        """Link a local entity with the Notion one, useful in syncing processes."""
        self._collections_manager.quick_link_local_and_notion_entries_for_collection_item(
            collection_key=NotionLockKey(f"{self._KEY}:{trunk_ref_id}"),
            key=NotionLockKey(f"{ref_id}"),
            ref_id=ref_id,
            notion_id=notion_id,
        )

    @staticmethod
    def _get_stable_color(option_id: str) -> str:
        """Return a random-ish yet stable color for a given name."""
        colors = [
            "gray",
            "brown",
            "orange",
            "yellow",
            "green",
            "blue",
            "purple",
            "pink",
            "red",
        ]
        return colors[
            hashlib.sha256(option_id.encode("utf-8")).digest()[0] % len(colors)
        ]
