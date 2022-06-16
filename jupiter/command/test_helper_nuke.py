"""Test helper command for completely destroying a workspace."""
import logging
from argparse import ArgumentParser, Namespace
from typing import Final

from jupiter.command import command
from jupiter.use_cases.test_helper.nuke import NukeUseCase

LOGGER = logging.getLogger(__name__)


class TestHelperNuke(command.TestHelperCommand):
    """Test helper command for completely destroying a workspace."""

    _command: Final[NukeUseCase]

    def __init__(self, the_command: NukeUseCase) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "test-helper-nuke"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Completely destroy a workspace"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        self._command.execute(NukeUseCase.Args())
