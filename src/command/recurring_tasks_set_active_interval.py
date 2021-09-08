"""Command for setting the active interval of a recurring task."""
import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from controllers.recurring_tasks import RecurringTasksController
from domain.common.adate import ADate
from models.framework import EntityId
from utils.global_properties import GlobalProperties

LOGGER = logging.getLogger(__name__)


class RecurringTasksSetActiveInterval(command.Command):
    """Command class for setting the active interval of a recurring task."""

    _global_properties: Final[GlobalProperties]
    _recurring_tasks_controller: Final[RecurringTasksController]

    def __init__(
            self, global_properties: GlobalProperties, recurring_tasks_controller: RecurringTasksController) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._recurring_tasks_controller = recurring_tasks_controller

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "recurring-tasks-set-active-interval"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Change the active interval of a recurring task"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument("--id", type=str, dest="ref_id", required=True,
                            help="The id of the recurring task to modify")
        parser.add_argument("--start-at-date", dest="start_at_date",
                            help="The date from which tasks should be generated")
        parser.add_argument("--end-at-date", dest="end_at_date",
                            help="The date until which tasks should be generated")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        ref_id = EntityId.from_raw(args.ref_id)
        start_at_date = ADate.from_raw(self._global_properties.timezone, args.start_at_date) \
            if args.start_at_date else None
        end_at_date = ADate.from_raw(self._global_properties.timezone, args.end_at_date) \
            if args.end_at_date else None
        self._recurring_tasks_controller.set_recurring_task_active_interval(ref_id, start_at_date, end_at_date)
