"""UseCase for updating a smart list tag."""
from argparse import Namespace, ArgumentParser
from typing import Final

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.domain.smart_lists.smart_list_tag_name import SmartListTagName
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.update_action import UpdateAction
from jupiter.use_cases.smart_lists.tag.update import SmartListTagUpdateUseCase


class SmartListTagUpdate(command.Command):
    """UseCase for creating a smart list tag."""

    _command: Final[SmartListTagUpdateUseCase]

    def __init__(self, the_command: SmartListTagUpdateUseCase) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "smart-list-tag-update"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Update a smart list tag"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--id", dest="ref_id", required=True, help="The id of the smart list tag"
        )
        parser.add_argument(
            "--name", dest="tag_name", required=False, help="The name of the smart list"
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        ref_id = EntityId.from_raw(args.ref_id)
        if args.tag_name:
            tag_name = UpdateAction.change_to(SmartListTagName.from_raw(args.tag_name))
        else:
            tag_name = UpdateAction.do_nothing()

        self._command.execute(
            progress_reporter,
            SmartListTagUpdateUseCase.Args(ref_id=ref_id, tag_name=tag_name),
        )
