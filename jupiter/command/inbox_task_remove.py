"""UseCase for hard remove inbox tasks."""

from argparse import ArgumentParser, Namespace
from typing import Final

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.framework.base.entity_id import EntityId
from jupiter.use_cases.inbox_tasks.remove import InboxTaskRemoveUseCase


class InboxTaskRemove(command.Command):
    """UseCase class for hard removing inbox tasks."""

    _command: Final[InboxTaskRemoveUseCase]

    def __init__(self, the_command: InboxTaskRemoveUseCase) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "inbox-task-remove"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Hard remove inbox tasks"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--id",
            type=str,
            dest="ref_id",
            required=True,
            help="Show only tasks selected by this id",
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        # Parse arguments
        ref_id = EntityId.from_raw(args.ref_id)

        self._command.execute(progress_reporter, InboxTaskRemoveUseCase.Args(ref_id))
