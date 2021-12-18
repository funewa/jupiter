"""Command for archiving done tasks."""
import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from domain.projects.project_key import ProjectKey
from domain.sync_target import SyncTarget
from use_cases.gc import GCCommand

LOGGER = logging.getLogger(__name__)


class GC(command.Command):
    """Command class for archiving done tasks."""

    _command: Final[GCCommand]

    def __init__(self, the_command: GCCommand) -> None:
        """Constructor."""
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "gc"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Garbage collect the Notion-side"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument("--target", dest="sync_targets", default=[], action="append",
                            choices=SyncTarget.all_values(), help="What exactly to try to sync")
        parser.add_argument("--project", dest="project_keys", default=[], action="append",
                            help="Allow only tasks from this project")
        parser.add_argument("--no-archival", dest="do_archival", default=True, action="store_const", const=False,
                            help="Skip the archival phase")
        parser.add_argument("--no-anti-entropy", dest="do_anti_entropy", default=True, action="store_const",
                            const=False, help="Skip the anti-entropy fixing phase")
        parser.add_argument("--no-notion-cleanup", dest="do_notion_cleanup", default=True, action="store_const",
                            const=False, help="Skip the Notion cleanup phase")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        gc_targets = [SyncTarget.from_raw(st) for st in args.sync_targets] \
            if len(args.sync_targets) > 0 else list(st for st in SyncTarget)
        project_keys = [ProjectKey.from_raw(pk) for pk in args.project_keys] if len(args.project_keys) > 0 else None
        do_archival = args.do_archival
        do_anti_entropy = args.do_anti_entropy
        do_notion_cleanup = args.do_notion_cleanup
        self._command.execute(GCCommand.Args(
            sync_targets=gc_targets, project_keys=project_keys, do_archival=do_archival,
            do_anti_entropy=do_anti_entropy, do_notion_cleanup=do_notion_cleanup))