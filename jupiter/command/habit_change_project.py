"""Change the project for a habit."""
from argparse import ArgumentParser, Namespace
from typing import Final

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.framework.base.entity_id import EntityId
from jupiter.use_cases.habits.change_project import HabitChangeProjectUseCase


class HabitChangeProject(command.Command):
    """UseCase class for hard removing habits."""

    _command: Final[HabitChangeProjectUseCase]

    def __init__(self, the_command: HabitChangeProjectUseCase) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "habit-change-project"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Change the project for a habit"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--id",
            type=str,
            dest="ref_id",
            required=True,
            help="Show only tasks selected by this id",
        )
        project = parser.add_mutually_exclusive_group()
        project.add_argument(
            "--project",
            dest="project_key",
            help="The project key to reassign this habit to",
        )
        project.add_argument(
            "--clear-project",
            dest="clear_project",
            default=False,
            action="store_const",
            const=True,
            help="Clear the project and use the default one",
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        # Parse arguments
        ref_id = EntityId.from_raw(args.ref_id)
        if args.clear_project:
            project_key = None
        else:
            project_key = ProjectKey.from_raw(args.project_key)

        self._command.execute(
            progress_reporter,
            HabitChangeProjectUseCase.Args(ref_id=ref_id, project_key=project_key),
        )
