"""UseCase for updating big plans."""
from argparse import ArgumentParser, Namespace
from typing import Final, Optional

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.domain.adate import ADate
from jupiter.domain.big_plans.big_plan_name import BigPlanName
from jupiter.domain.big_plans.big_plan_status import BigPlanStatus
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.update_action import UpdateAction
from jupiter.use_cases.big_plans.update import BigPlanUpdateUseCase
from jupiter.utils.global_properties import GlobalProperties


class BigPlanUpdate(command.Command):
    """UseCase class for updating big plans."""

    _global_properties: Final[GlobalProperties]
    _command: Final[BigPlanUpdateUseCase]

    def __init__(
        self, global_properties: GlobalProperties, the_command: BigPlanUpdateUseCase
    ) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "big-plan-update"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Update a big plan"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--id",
            type=str,
            dest="ref_id",
            required=True,
            help="The id of the big plan to modify",
        )
        parser.add_argument(
            "--name", dest="name", required=False, help="The name of the big plan"
        )
        parser.add_argument(
            "--status",
            dest="status",
            required=False,
            choices=BigPlanStatus.all_values(),
            help="The status of the big plan",
        )
        actionable_date = parser.add_mutually_exclusive_group()
        actionable_date.add_argument(
            "--actionable-date",
            dest="actionable_date",
            help="The actionable date of the big plan",
        )
        actionable_date.add_argument(
            "--clear-actionable-date",
            dest="clear_actionable_date",
            default=False,
            action="store_const",
            const=True,
            help="Clear the actionable date of the big plan",
        )
        due_date = parser.add_mutually_exclusive_group()
        due_date.add_argument(
            "--due-date", dest="due_date", help="The due date of the big plan"
        )
        due_date.add_argument(
            "--clear-due-date",
            dest="clear_due_date",
            default=False,
            action="store_const",
            const=True,
            help="Clear the due date of the big plan",
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        ref_id = EntityId.from_raw(args.ref_id)
        if args.name:
            name = UpdateAction.change_to(BigPlanName.from_raw(args.name))
        else:
            name = UpdateAction.do_nothing()
        if args.status:
            status = UpdateAction.change_to(BigPlanStatus.from_raw(args.status))
        else:
            status = UpdateAction.do_nothing()
        actionable_date: UpdateAction[Optional[ADate]]
        if args.clear_actionable_date:
            actionable_date = UpdateAction.change_to(None)
        elif args.actionable_date:
            actionable_date = UpdateAction.change_to(
                ADate.from_raw(self._global_properties.timezone, args.actionable_date)
            )
        else:
            actionable_date = UpdateAction.do_nothing()
        due_date: UpdateAction[Optional[ADate]]
        if args.clear_due_date:
            due_date = UpdateAction.change_to(None)
        elif args.due_date:
            due_date = UpdateAction.change_to(
                ADate.from_raw(self._global_properties.timezone, args.due_date)
            )
        else:
            due_date = UpdateAction.do_nothing()

        self._command.execute(
            progress_reporter,
            BigPlanUpdateUseCase.Args(ref_id, name, status, actionable_date, due_date),
        )
