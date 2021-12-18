"""Command for updating the workspace."""

import logging
from argparse import ArgumentParser, Namespace
from typing import Final

import command.command as command
from domain.entity_name import EntityName
from domain.projects.project_key import ProjectKey
from domain.timezone import Timezone
from domain.workspaces.notion_token import NotionToken
from models.framework import UpdateAction
from remote.notion.infra.connection import NotionConnection
from use_cases.workspaces.update import WorkspaceUpdateCommand

LOGGER = logging.getLogger(__name__)


class WorkspaceUpdate(command.Command):
    """Command class for updating the workspace."""

    _notion_connection: Final[NotionConnection]
    _command: Final[WorkspaceUpdateCommand]

    def __init__(self, notion_connection: NotionConnection, the_command: WorkspaceUpdateCommand) -> None:
        """Constructor."""
        self._notion_connection = notion_connection
        self._command = the_command

    @staticmethod
    def name() -> str:
        """The name of the command."""
        return "workspace-update"

    @staticmethod
    def description() -> str:
        """The description of the command."""
        return "Update the workspace"

    def build_parser(self, parser: ArgumentParser) -> None:
        """Construct a argparse parser for the command."""
        parser.add_argument(
            "--name", required=False, help="The plan name to use")
        parser.add_argument(
            "--timezone", required=False, help="The timezone you're currently in")
        parser.add_argument("--notion-token", dest="notion_token", required=False, help="The Notion token")
        parser.add_argument(
            "--default-project-key", dest="default_project_key", required=False, help="The key of the default project")

    def run(self, args: Namespace) -> None:
        """Callback to execute when the command is invoked."""
        if args.name is not None:
            name = UpdateAction.change_to(EntityName.from_raw(args.name))
        else:
            name = UpdateAction.do_nothing()
        if args.timezone is not None:
            timezone = UpdateAction.change_to(Timezone.from_raw(args.timezone))
        else:
            timezone = UpdateAction.do_nothing()
        if args.default_project_key is not None:
            default_project_key = UpdateAction.change_to(ProjectKey.from_raw(args.default_project_key))
        else:
            default_project_key = UpdateAction.do_nothing()
        self._command.execute(WorkspaceUpdateCommand.Args(
            name=name, timezone=timezone, default_project_key=default_project_key))
        # This is quite the hack for now!
        if args.notion_token is not None:
            self._notion_connection.update_token(NotionToken.from_raw(args.notion_token))