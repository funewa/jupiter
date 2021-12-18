"""Command for hard removing recurring tasks."""
import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from models.framework import EntityId
from use_cases.recurring_tasks.remove import RecurringTaskRemoveCommand

LOGGER = logging.getLogger(__name__)


class RecurringTaskRemove(command.Command):
    """Command class for hard removing recurring tasks."""

    _command: Final[RecurringTaskRemoveCommand]

    def __init__(self, the_command: RecurringTaskRemoveCommand) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "recurring-task-remove"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Hard remove recurring tasks"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument("--id", type=str, dest="ref_id",
                            required=True, help="Show only tasks selected by this id")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        # Parse arguments
        ref_id = EntityId.from_raw(args.ref_id)
        self._command.execute(RecurringTaskRemoveCommand.Args(ref_id))