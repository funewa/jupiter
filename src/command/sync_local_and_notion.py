"""Command for syncing the local and Notion-side data."""

import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from controllers.sync_local_and_notion import SyncLocalAndNotionController
from models.basic import BasicValidator, SyncPrefer, SyncTarget

LOGGER = logging.getLogger(__name__)


class SyncLocalAndNotion(command.Command):
    """Command class for syncing the local and Notion-side data."""

    _basic_validator: Final[BasicValidator]
    _sync_local_and_notion_controller: Final[SyncLocalAndNotionController]

    def __init__(
            self, basic_validator: BasicValidator,
            sync_local_and_notion_controller: SyncLocalAndNotionController) -> None:
        """Constructor."""
        self._basic_validator = basic_validator
        self._sync_local_and_notion_controller = sync_local_and_notion_controller

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "sync"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Sync the local and Notion-side data"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument("--target", dest="sync_targets", default=[], action="append",
                            choices=BasicValidator.sync_target_values(), help="What exactly to try to sync")
        parser.add_argument("--project", dest="project_keys", default=[], action="append",
                            help="Sync only from this project")
        parser.add_argument("--prefer", dest="sync_prefer", choices=BasicValidator.sync_prefer_values(),
                            default=SyncPrefer.NOTION.value, help="Which source to prefer")
        parser.add_argument("--anti-entropy", dest="anti_entropy", action="store_true", default=False,
                            help="Try to correct issues due to lack of local-to-Notion transactionality")
        parser.add_argument("--drop-all-notion", dest="drop_all_notion", action="store_true", default=False,
                            help="Drop all Notion-side entities before syncing and restore from local entirely")
        parser.add_argument("--gc-notion", dest="drop_all_notion_archived", action="store_true", default=False,
                            help="Drop all Notion-side archived")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        sync_targets = [self._basic_validator.sync_target_validate_and_clean(st) for st in args.sync_targets]\
            if len(args.sync_targets) > 0 else list(st for st in SyncTarget)
        project_keys = [self._basic_validator.project_key_validate_and_clean(pk) for pk in args.project_keys]\
            if len(args.project_keys) > 0 else None
        sync_prefer = self._basic_validator.sync_prefer_validate_and_clean(args.sync_prefer)
        anti_entropy = args.anti_entropy
        drop_all_notion = args.drop_all_notion
        drop_all_notion_archived = args.drop_all_notion_archived
        self._sync_local_and_notion_controller.sync(
            sync_targets, anti_entropy, drop_all_notion, drop_all_notion_archived, project_keys, sync_prefer)