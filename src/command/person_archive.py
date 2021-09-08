"""Command for archiving a person."""

import logging
from argparse import Namespace, ArgumentParser
from typing import Final

import command.command as command
from domain.prm.commands.person_archive import PersonArchiveCommand
from models.framework import EntityId

LOGGER = logging.getLogger(__name__)


class PersonArchive(command.Command):
    """Command for archiving a person."""

    _command: Final[PersonArchiveCommand]

    def __init__(self, the_command: PersonArchiveCommand) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "person-archive"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Archive a person"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument("--id", dest="ref_id", required=True, help="The id of the person")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        ref_id = EntityId.from_raw(args.ref_id)
        self._command.execute(ref_id)
