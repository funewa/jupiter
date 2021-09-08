"""Command for initialising a workspace."""
import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from controllers.workspaces import WorkspacesController
from domain.common.entity_name import EntityName
from domain.projects.project_key import ProjectKey
from domain.workspaces.notion_space_id import NotionSpaceId
from domain.workspaces.notion_token import NotionToken
from domain.common.timezone import Timezone

LOGGER = logging.getLogger(__name__)


class WorkspaceInit(command.Command):
    """Command class for initialising a workspace."""

    _workspaces_controller: Final[WorkspacesController]

    def __init__(self, workspaces_controller: WorkspacesController) -> None:
        """Constructor."""
        self._workspaces_controller = workspaces_controller

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "workspace-init"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Initialise a workspace"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--name", required=True, help="The plan name to use")
        parser.add_argument(
            "--timezone", required=True, help="The timezone you're currently in")
        parser.add_argument(
            "--notion-space-id", dest="notion_space_id", required=True, help="The Notion space id to use")
        parser.add_argument(
            "--notion_token", dest="notion_space_id", required=True, help="The Notion access token to use")
        parser.add_argument(
            "--project-key", dest="first_project_key", required=True, help="The key of the first project")
        parser.add_argument(
            "--project-name", dest="first_project_name", required=True, help="The name of the first project")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        name = EntityName.from_raw(args.name)
        timezone = Timezone.from_raw(args.timezone)
        notion_space_id = NotionSpaceId.from_raw(args.notion_space_id)
        notion_token = NotionToken.from_raw(args.notion_space_id)
        first_project_key = ProjectKey.from_raw(args.first_project_key)
        first_project_name = EntityName.from_raw(args.first_project_name)

        self._workspaces_controller.create_workspace(
            name, timezone, notion_space_id, notion_token, first_project_key, first_project_name)
