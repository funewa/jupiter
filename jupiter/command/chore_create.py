"""UseCase for adding a chore."""
from argparse import Namespace, ArgumentParser
from typing import Final

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.domain.adate import ADate
from jupiter.domain.chores.chore_name import ChoreName
from jupiter.domain.difficulty import Difficulty
from jupiter.domain.eisen import Eisen
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.domain.recurring_task_due_at_day import RecurringTaskDueAtDay
from jupiter.domain.recurring_task_due_at_month import RecurringTaskDueAtMonth
from jupiter.domain.recurring_task_due_at_time import RecurringTaskDueAtTime
from jupiter.domain.recurring_task_period import RecurringTaskPeriod
from jupiter.domain.recurring_task_skip_rule import RecurringTaskSkipRule
from jupiter.use_cases.chores.create import ChoreCreateUseCase
from jupiter.utils.global_properties import GlobalProperties


class ChoreCreate(command.Command):
    """UseCase class for creating a chore."""

    _global_properties: Final[GlobalProperties]
    _command: Final[ChoreCreateUseCase]

    def __init__(
        self, global_properties: GlobalProperties, the_command: ChoreCreateUseCase
    ) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "chore-create"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Create a new chore"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--project",
            dest="project_key",
            required=False,
            help="The project key to add the task to",
        )
        parser.add_argument(
            "--name", dest="name", required=True, help="The name of the chore"
        )
        parser.add_argument(
            "--period",
            dest="period",
            choices=RecurringTaskPeriod.all_values(),
            required=True,
            help="The period for the chore",
        )
        parser.add_argument(
            "--eisen",
            dest="eisen",
            choices=Eisen.all_values(),
            help="The Eisenhower matrix values to use for task",
        )
        parser.add_argument(
            "--difficulty",
            dest="difficulty",
            choices=Difficulty.all_values(),
            help="The difficulty to use for tasks",
        )
        parser.add_argument(
            "--actionable-from-day",
            type=int,
            dest="actionable_from_day",
            metavar="DAY",
            help="The day of the interval the task will be actionable from",
        )
        parser.add_argument(
            "--actionable-from-month",
            type=int,
            dest="actionable_from_month",
            metavar="MONTH",
            help="The month of the interval the task will be actionable from",
        )
        parser.add_argument(
            "--due-at-time",
            dest="due_at_time",
            metavar="HH:MM",
            help="The time a task will be due on",
        )
        parser.add_argument(
            "--due-at-day",
            type=int,
            dest="due_at_day",
            metavar="DAY",
            help="The day of the interval the task will be due on",
        )
        parser.add_argument(
            "--due-at-month",
            type=int,
            dest="due_at_month",
            metavar="MONTH",
            help="The month of the interval the task will be due on",
        )
        parser.add_argument(
            "--start-at-date",
            dest="start_at_date",
            help="The date from which tasks should be generated",
        )
        parser.add_argument(
            "--end-at-date",
            dest="end_at_date",
            help="The date until which tasks should be generated",
        )
        parser.add_argument(
            "--must-do",
            dest="must_do",
            default=False,
            action="store_true",
            help="Whether to treat this task as must do or not",
        )
        parser.add_argument(
            "--skip-rule", dest="skip_rule", help="The skip rule for the task"
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        project_key = (
            ProjectKey.from_raw(args.project_key) if args.project_key else None
        )
        name = ChoreName.from_raw(args.name)
        period = RecurringTaskPeriod.from_raw(args.period)
        eisen = Eisen.from_raw(args.eisen) if args.eisen else None
        difficulty = Difficulty.from_raw(args.difficulty) if args.difficulty else None
        actionable_from_day = (
            RecurringTaskDueAtDay.from_raw(period, args.actionable_from_day)
            if args.actionable_from_day
            else None
        )
        actionable_from_month = (
            RecurringTaskDueAtMonth.from_raw(period, args.actionable_from_month)
            if args.actionable_from_month
            else None
        )
        due_at_time = (
            RecurringTaskDueAtTime.from_raw(args.due_at_time)
            if args.due_at_time
            else None
        )
        due_at_day = (
            RecurringTaskDueAtDay.from_raw(period, args.due_at_day)
            if args.due_at_day
            else None
        )
        due_at_month = (
            RecurringTaskDueAtMonth.from_raw(period, args.due_at_month)
            if args.due_at_month
            else None
        )
        skip_rule = (
            RecurringTaskSkipRule.from_raw(args.skip_rule) if args.skip_rule else None
        )
        start_at_date = (
            ADate.from_raw(self._global_properties.timezone, args.start_at_date)
            if args.start_at_date
            else None
        )
        end_at_date = (
            ADate.from_raw(self._global_properties.timezone, args.end_at_date)
            if args.end_at_date
            else None
        )

        self._command.execute(
            progress_reporter,
            ChoreCreateUseCase.Args(
                project_key=project_key,
                name=name,
                period=period,
                eisen=eisen,
                difficulty=difficulty,
                actionable_from_day=actionable_from_day,
                actionable_from_month=actionable_from_month,
                due_at_time=due_at_time,
                due_at_day=due_at_day,
                due_at_month=due_at_month,
                must_do=args.must_do,
                skip_rule=skip_rule,
                start_at_date=start_at_date,
                end_at_date=end_at_date,
            ),
        )
