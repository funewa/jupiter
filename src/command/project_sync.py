"""Command for syncing the projects from Notion."""

import logging

from notion.client import NotionClient

import command.command as command
import repository.projects as projects
import repository.workspaces as workspaces
import space_utils
import storage
from models.basic import BasicValidator, SyncPrefer

LOGGER = logging.getLogger(__name__)


class ProjectSync(command.Command):
    """Command class for syncing the projects from Notion."""

    @staticmethod
    def name():
        """The name of the command."""
        return "project-sync"

    @staticmethod
    def description():
        """The description of the command."""
        return "Synchronises Notion and the local storage"

    def build_parser(self, parser):
        """Construct a argparse parser for the command."""
        parser.add_argument("--project", dest="project_key", required=True, help="The key of the project")
        parser.add_argument("--prefer", dest="sync_prefer", choices=BasicValidator.sync_prefer_values(),
                            default=SyncPrefer.NOTION.value, help="Which source to prefer")

    def run(self, args):
        """Callback to execute when the command is invoked."""
        basic_validator = BasicValidator()

        # Parse arguments
        project_key = basic_validator.project_key_validate_and_clean(args.project_key)
        sync_prefer = basic_validator.sync_prefer_validate_and_clean(args.sync_prefer)

        # Load local storage

        system_lock = storage.load_lock_file()
        workspace_repository = workspaces.WorkspaceRepository()
        projects_repository = projects.ProjectsRepository()

        workspace = workspace_repository.load_workspace()
        project = projects_repository.load_project_by_key(project_key)
        LOGGER.info("Found project file")

        # Prepare Notion connection

        client = NotionClient(token_v2=workspace.token)

        # Apply changes locally

        project_root_page = space_utils.find_page_from_space_by_id(
            client, system_lock["projects"][project_key]["root_page_id"])
        LOGGER.info(f"Found the root page via id {project_root_page}")

        if sync_prefer == SyncPrefer.LOCAL:
            project_root_page.title = project.name
            LOGGER.info("Applied changes to Notion")
        elif sync_prefer == SyncPrefer.NOTION:
            project.name = project_root_page.title
            projects_repository.save_project(project)
            LOGGER.info("Applied local change")
        else:
            raise Exception(f"Invalid preference {sync_prefer}")
