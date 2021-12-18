"""Command for creating projects."""
import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from domain.entity_name import EntityName
from domain.projects.project_key import ProjectKey
from use_cases.projects.create import ProjectCreateCommand

LOGGER = logging.getLogger(__name__)


class ProjectCreate(command.Command):
    """Command class for creating projects."""

    _command: Final[ProjectCreateCommand]

    def __init__(self, the_command: ProjectCreateCommand) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "project-create"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Create a project"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument("--project", dest="project_key", required=True, help="The key of the project")
        parser.add_argument("--name", dest="name", required=True, help="The name of the project")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        project_key = ProjectKey.from_raw(args.project_key)
        project_name = EntityName.from_raw(args.name)
        self._command.execute(ProjectCreateCommand.Args(key=project_key, name=project_name))