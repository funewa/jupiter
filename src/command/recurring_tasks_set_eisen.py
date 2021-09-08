"""Command for setting the Eisenhower status of a recurring task."""
import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from controllers.recurring_tasks import RecurringTasksController
from domain.common.eisen import Eisen
from models.framework import EntityId

LOGGER = logging.getLogger(__name__)


class RecurringTasksSetEisen(command.Command):
    """Command class for setting the Eisenhower status of a recurring task."""

    _recurring_tasks_controller: Final[RecurringTasksController]

    def __init__(self, recurring_tasks_controller: RecurringTasksController) -> None:
        """Constructor."""
        self._recurring_tasks_controller = recurring_tasks_controller

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "recurring-tasks-set-eisen"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Change the Eisenhower status of a recurring task"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument("--id", type=str, dest="ref_id", required=True,
                            help="The id of the recurring task to modify")
        parser.add_argument("--eisen", dest="eisen", default=[], action="append",
                            choices=Eisen.all_values(), help="The Eisenhower matrix values to use for task")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        ref_id = EntityId.from_raw(args.ref_id)
        eisen = [Eisen.from_raw(e) for e in args.eisen]
        self._recurring_tasks_controller.set_recurring_task_eisen(ref_id, eisen)
