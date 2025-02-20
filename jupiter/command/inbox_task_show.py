"""UseCase for showing the inbox tasks."""
from argparse import ArgumentParser, Namespace
from typing import Final

from rich.console import Console
from rich.text import Text
from rich.tree import Tree

from jupiter.command import command
from jupiter.command.rendering import (
    entity_id_to_rich_text,
    source_to_rich_text,
    inbox_task_status_to_rich_text,
    parent_entity_name_to_rich_text,
    actionable_date_to_rich_text,
    due_date_to_rich_text,
    eisen_to_rich_text,
    difficulty_to_rich_text,
    project_to_rich_text,
    RichConsoleProgressReporter,
)
from jupiter.domain.adate import ADate
from jupiter.domain.difficulty import Difficulty
from jupiter.domain.inbox_tasks.inbox_task_source import InboxTaskSource
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.framework.base.entity_id import EntityId
from jupiter.use_cases.inbox_tasks.find import InboxTaskFindUseCase
from jupiter.utils.global_properties import GlobalProperties


class InboxTaskShow(command.ReadonlyCommand):
    """UseCase class for showing the inbox tasks."""

    _global_properties: Final[GlobalProperties]
    _command: Final[InboxTaskFindUseCase]

    def __init__(
        self, global_properties: GlobalProperties, the_command: InboxTaskFindUseCase
    ) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "inbox-task-show"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Show the list of inbox tasks"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--show-archived",
            dest="show_archived",
            default=False,
            action="store_true",
            help="Whether to show archived vacations or not",
        )
        parser.add_argument(
            "--id",
            type=str,
            dest="ref_ids",
            default=[],
            action="append",
            help="Show only tasks selected by this id",
        )
        parser.add_argument(
            "--project",
            dest="project_keys",
            default=[],
            action="append",
            help="Allow only tasks from this project",
        )
        parser.add_argument(
            "--source",
            dest="sources",
            default=[],
            action="append",
            choices=InboxTaskSource.all_values(),
            help="Allow only inbox tasks form this particular source. Defaults to all",
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        # Parse arguments
        show_archived = args.show_archived
        ref_ids = (
            [EntityId.from_raw(rid) for rid in args.ref_ids]
            if len(args.ref_ids) > 0
            else None
        )
        project_keys = (
            [ProjectKey.from_raw(p) for p in args.project_keys]
            if len(args.project_keys) > 0
            else None
        )
        sources = (
            [InboxTaskSource.from_raw(s) for s in args.sources]
            if len(args.sources) > 0
            else None
        )

        response = self._command.execute(
            progress_reporter,
            InboxTaskFindUseCase.Args(
                allow_archived=show_archived,
                filter_ref_ids=ref_ids,
                filter_project_keys=project_keys,
                filter_sources=sources,
            ),
        )

        sorted_inbox_tasks = sorted(
            response.inbox_tasks,
            key=lambda it: (
                it.inbox_task.archived,
                it.inbox_task.eisen,
                it.inbox_task.status,
                it.inbox_task.due_date or ADate.from_str("2100-01-01"),
                it.inbox_task.difficulty or Difficulty.EASY,
            ),
        )

        rich_tree = Tree("📥 Inbox Tasks", guide_style="bold bright_blue")

        for inbox_task_entry in sorted_inbox_tasks:
            inbox_task = inbox_task_entry.inbox_task
            project = inbox_task_entry.project
            habit = inbox_task_entry.habit
            chore = inbox_task_entry.chore
            big_plan = inbox_task_entry.big_plan
            metric = inbox_task_entry.metric
            person = inbox_task_entry.person
            slack_task = inbox_task_entry.slack_task

            inbox_task_text = inbox_task_status_to_rich_text(
                inbox_task.status, inbox_task.archived
            )
            inbox_task_text.append(" ")
            inbox_task_text.append(entity_id_to_rich_text(inbox_task.ref_id))
            inbox_task_text.append(f" {inbox_task.name}")

            inbox_task_info_text = Text("")
            inbox_task_info_text.append(source_to_rich_text(inbox_task.source))

            inbox_task_info_text.append(" ")
            inbox_task_info_text.append(eisen_to_rich_text(inbox_task.eisen))

            if inbox_task.difficulty:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(
                    difficulty_to_rich_text(inbox_task.difficulty)
                )

            if habit is not None:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(parent_entity_name_to_rich_text(habit.name))
            elif chore is not None:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(parent_entity_name_to_rich_text(chore.name))
            elif big_plan is not None:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(
                    parent_entity_name_to_rich_text(big_plan.name)
                )
            elif metric is not None:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(
                    parent_entity_name_to_rich_text(metric.name)
                )
            elif person is not None:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(
                    parent_entity_name_to_rich_text(person.name)
                )
            elif slack_task is not None:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(
                    parent_entity_name_to_rich_text(slack_task.simple_name)
                )

            if inbox_task.actionable_date:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(
                    actionable_date_to_rich_text(inbox_task.actionable_date)
                )

            if inbox_task.due_date:
                inbox_task_info_text.append(" ")
                inbox_task_info_text.append(due_date_to_rich_text(inbox_task.due_date))

            inbox_task_info_text.append(" ")
            inbox_task_info_text.append(project_to_rich_text(project.name))

            if inbox_task.archived:
                inbox_task_text.stylize("gray62")
                inbox_task_info_text.stylize("gray62")

            inbox_task_tree = rich_tree.add(
                inbox_task_text, guide_style="gray62" if inbox_task.archived else "blue"
            )
            inbox_task_tree.add(inbox_task_info_text)

        console = Console()
        console.print(rich_tree)
