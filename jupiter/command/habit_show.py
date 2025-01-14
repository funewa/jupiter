"""UseCase for showing the habits."""
from argparse import ArgumentParser, Namespace
from typing import Final

from rich.console import Console
from rich.text import Text
from rich.tree import Tree

from jupiter.command import command
from jupiter.command.rendering import (
    entity_id_to_rich_text,
    period_to_rich_text,
    eisen_to_rich_text,
    difficulty_to_rich_text,
    skip_rule_to_rich_text,
    due_at_time_to_rich_text,
    due_at_day_to_rich_text,
    due_at_month_to_rich_text,
    project_to_rich_text,
    inbox_task_summary_to_rich_text,
    actionable_from_day_to_rich_text,
    actionable_from_month_to_rich_text,
    RichConsoleProgressReporter,
)
from jupiter.domain.adate import ADate
from jupiter.domain.difficulty import Difficulty
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.framework.base.entity_id import EntityId
from jupiter.use_cases.habits.find import HabitFindUseCase
from jupiter.utils.global_properties import GlobalProperties


class HabitShow(command.ReadonlyCommand):
    """UseCase class for showing the habits."""

    _global_properties: Final[GlobalProperties]
    _command: Final[HabitFindUseCase]

    def __init__(
        self, global_properties: GlobalProperties, the_command: HabitFindUseCase
    ) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "habit-show"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Show the list of habits"

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
            help="The id of the vacations to show",
        )
        parser.add_argument(
            "--project",
            type=str,
            dest="project_keys",
            default=[],
            action="append",
            help="Allow only tasks from this project",
        )
        parser.add_argument(
            "--show-inbox-tasks",
            dest="show_inbox_tasks",
            default=False,
            action="store_const",
            const=True,
            help="Show inbox tasks",
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
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
        show_inbox_tasks = args.show_inbox_tasks

        result = self._command.execute(
            progress_reporter,
            HabitFindUseCase.Args(
                show_archived=show_archived,
                filter_ref_ids=ref_ids,
                filter_project_keys=project_keys,
            ),
        )

        rich_tree = Tree("💪️ Habits", guide_style="bold bright_blue")

        sorted_habits = sorted(
            result.habits,
            key=lambda ce: (
                ce.habit.archived,
                ce.habit.suspended,
                ce.habit.gen_params.period,
                ce.habit.gen_params.eisen,
                ce.habit.gen_params.difficulty or Difficulty.EASY,
            ),
        )

        for habit_entry in sorted_habits:
            habit = habit_entry.habit
            project = habit_entry.project
            inbox_tasks = habit_entry.inbox_tasks

            habit_text = Text("")
            habit_text.append(entity_id_to_rich_text(habit.ref_id))
            habit_text.append(f" {habit.name}")

            habit_info_text = Text("")
            habit_info_text.append(period_to_rich_text(habit.gen_params.period))
            habit_info_text.append(" ")
            habit_info_text.append(eisen_to_rich_text(habit.gen_params.eisen))

            if habit.gen_params.difficulty:
                habit_info_text.append(" ")
                habit_info_text.append(
                    difficulty_to_rich_text(habit.gen_params.difficulty)
                )

            if habit.skip_rule and str(habit.skip_rule) != "none":
                habit_info_text.append(" ")
                habit_info_text.append(skip_rule_to_rich_text(habit.skip_rule))

            if habit.gen_params.actionable_from_day:
                habit_info_text.append(" ")
                habit_info_text.append(
                    actionable_from_day_to_rich_text(
                        habit.gen_params.actionable_from_day
                    )
                )

            if habit.gen_params.actionable_from_month:
                habit_info_text.append(" ")
                habit_info_text.append(
                    actionable_from_month_to_rich_text(
                        habit.gen_params.actionable_from_month
                    )
                )

            if habit.gen_params.due_at_time:
                habit_info_text.append(" ")
                habit_info_text.append(
                    due_at_time_to_rich_text(habit.gen_params.due_at_time)
                )

            if habit.gen_params.due_at_day:
                habit_info_text.append(" ")
                habit_info_text.append(
                    due_at_day_to_rich_text(habit.gen_params.due_at_day)
                )

            if habit.gen_params.due_at_month:
                habit_info_text.append(" ")
                habit_info_text.append(
                    due_at_month_to_rich_text(habit.gen_params.due_at_month)
                )

            habit_info_text.append(" ")
            habit_info_text.append(project_to_rich_text(project.name))

            if habit.suspended:
                habit_text.stylize("yellow")
                habit_info_text.append(" #suspended")
                habit_info_text.stylize("yellow")

            if habit.archived:
                habit_text.stylize("gray62")
                habit_info_text.stylize("gray62")

            habit_tree = rich_tree.add(
                habit_text, guide_style="gray62" if habit.archived else "blue"
            )
            habit_tree.add(habit_info_text)

            if not show_inbox_tasks:
                continue
            if len(inbox_tasks) == 0:
                continue

            sorted_inbox_tasks = sorted(
                inbox_tasks,
                key=lambda it: (
                    it.archived,
                    it.status,
                    it.due_date if it.due_date else ADate.from_str("2100-01-01"),
                ),
            )

            for inbox_task in sorted_inbox_tasks:
                inbox_task_text = inbox_task_summary_to_rich_text(inbox_task)
                habit_tree.add(inbox_task_text)

        console = Console()
        console.print(rich_tree)
