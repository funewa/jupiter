"""UseCase for creating a smart list item."""
from argparse import Namespace, ArgumentParser
from typing import Final

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.domain.smart_lists.smart_list_item_name import SmartListItemName
from jupiter.domain.smart_lists.smart_list_key import SmartListKey
from jupiter.domain.smart_lists.smart_list_tag_name import SmartListTagName
from jupiter.domain.url import URL
from jupiter.use_cases.smart_lists.item.create import SmartListItemCreateUseCase


class SmartListItemCreate(command.Command):
    """UseCase for creating a smart list item."""

    _command: Final[SmartListItemCreateUseCase]

    def __init__(self, the_command: SmartListItemCreateUseCase) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "smart-list-item-create"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Create a new smart list item"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--smart-list",
            dest="smart_list_key",
            required=True,
            help="The key of the smart list to add the item to",
        )
        parser.add_argument(
            "--name", dest="name", required=True, help="The name of the smart list item"
        )
        parser.add_argument(
            "--done",
            dest="is_done",
            default=False,
            action="store_const",
            const=True,
            help="Mark the smart list item as done",
        )
        parser.add_argument(
            "--tag",
            dest="tag_names",
            default=[],
            action="append",
            help="Tags for the smart list item",
        )
        parser.add_argument("--url", dest="url", help="An url for the smart list item")

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        smart_list_key = SmartListKey.from_raw(args.smart_list_key)
        name = SmartListItemName.from_raw(args.name)
        is_done = args.is_done
        tag_names = [SmartListTagName.from_raw(t) for t in args.tag_names]
        url = URL.from_raw(args.url) if args.url else None

        self._command.execute(
            progress_reporter,
            SmartListItemCreateUseCase.Args(
                smart_list_key=smart_list_key,
                name=name,
                is_done=is_done,
                tag_names=tag_names,
                url=url,
            ),
        )
