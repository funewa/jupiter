"""Command for syncing the workspace info from Notion."""

import logging

from notion.client import NotionClient

import command.command as command
from models.basic import BasicValidator, SyncPrefer
import repository.workspaces as workspaces
import space_utils
import storage

LOGGER = logging.getLogger(__name__)


class WorkspaceSync(command.Command):
    """Command class for syncing the workspace info from Notion."""

    @staticmethod
    def name():
        """The name of the command."""
        return "ws-sync"

    @staticmethod
    def description():
        """The description of the command."""
        return "Synchronises Notion and the local storage"

    def build_parser(self, parser):
        """Construct a argparse parser for the command."""
        parser.add_argument("--prefer", dest="sync_prefer", choices=BasicValidator.sync_prefer_values(),
                            default=SyncPrefer.LOCAL.value, help="Which source to prefer")

    def run(self, args):
        """Callback to execute when the command is invoked."""
        basic_validator = BasicValidator()

        # Parse arguments

        sync_prefer = basic_validator.sync_prefer_validate_and_clean(args.sync_prefer)

        # Load local storage

        system_lock = storage.load_lock_file()
        LOGGER.info("Loaded lockfile")

        workspace_repository = workspaces.WorkspaceRepository()
        workspace = workspace_repository.load_workspace()

        # Load Notion storage

        client = NotionClient(token_v2=workspace.token)
        LOGGER.info("Connected to Notion")
        found_root_page = space_utils.find_page_from_space_by_id(client, system_lock["root_page"]["root_page_id"])
        LOGGER.info(f"Found the root page via id {found_root_page}")

        if sync_prefer == "notion":
            name = found_root_page.title
            workspace.name = name
            workspace_repository.save_workspace(workspace)
            LOGGER.info("Applied changes on local side")
        elif sync_prefer == "local":
            found_root_page.title = workspace.name
            LOGGER.info("Applied changes on Notion side")
        else:
            raise Exception(f"Invalid preference {sync_prefer}")
