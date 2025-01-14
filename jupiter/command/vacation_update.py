"""UseCase for updating a vacation's properties."""
from argparse import Namespace, ArgumentParser
from typing import Final

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.domain.adate import ADate
from jupiter.domain.vacations.vacation_name import VacationName
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.update_action import UpdateAction
from jupiter.use_cases.vacations.update import VacationUpdateUseCase
from jupiter.utils.global_properties import GlobalProperties


class VacationUpdate(command.Command):
    """UseCase for updating a vacation's properties."""

    _global_properties: Final[GlobalProperties]
    _command: Final[VacationUpdateUseCase]

    def __init__(
        self, global_properties: GlobalProperties, the_command: VacationUpdateUseCase
    ) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "vacation-update"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Update a vacation"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--id",
            type=str,
            dest="ref_id",
            required=True,
            help="The id of the vacation to modify",
        )
        parser.add_argument(
            "--name", dest="name", required=False, help="The name of the vacation"
        )
        parser.add_argument(
            "--start-date",
            dest="start_date",
            required=False,
            help="The vacation start date",
        )
        parser.add_argument(
            "--end-date", dest="end_date", required=False, help="The vacation end date"
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        ref_id = EntityId.from_raw(args.ref_id)
        if args.name is not None:
            name = UpdateAction.change_to(VacationName.from_raw(args.name))
        else:
            name = UpdateAction.do_nothing()
        if args.start_date is not None:
            start_date = UpdateAction.change_to(
                ADate.from_raw(self._global_properties.timezone, args.start_date)
            )
        else:
            start_date = UpdateAction.do_nothing()
        if args.end_date is not None:
            end_date = UpdateAction.change_to(
                ADate.from_raw(self._global_properties.timezone, args.end_date)
            )
        else:
            end_date = UpdateAction.do_nothing()

        self._command.execute(
            progress_reporter,
            VacationUpdateUseCase.Args(
                ref_id=ref_id, name=name, start_date=start_date, end_date=end_date
            ),
        )
