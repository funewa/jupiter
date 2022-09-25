"""Integration tests for big plans."""
import re

from tests.integration.infra import JupiterIntegrationTestCase


class BigPlanIntegrationTestCase(JupiterIntegrationTestCase):
    """Integration tests for big plans."""

    def test_create_big_plan(self) -> None:
        """Creation of a big plan."""
        self.jupiter(
            "big-plan-create",
            "--name",
            "Get a cat",
            "--actionable-date",
            "2022-05-01",
            "--due-date",
            "2022-05-20",
        )

        self.go_to_notion("My Work", "Big Plans")

        notion_row = self.get_notion_row_in_database(
            "Get a cat",
            ["Status", "Actionable Date", "Due Date", "Project"],
        )

        assert re.search(r"Get a cat", notion_row.title)
        assert notion_row.attributes["Status"] == "Accepted"
        assert notion_row.attributes["Actionable Date"] == "May 1, 2022"
        assert notion_row.attributes["Due Date"] == "May 20, 2022"
        assert notion_row.attributes["Project"] == "Work"

        big_plan_out = self.jupiter("big-plan-show")

        assert re.search(r"Get a cat", big_plan_out)
        assert re.search(r"🔧", big_plan_out)
        assert re.search(r"From 2022-05-01", big_plan_out)
        assert re.search(r"Due at 2022-05-20", big_plan_out)
        assert re.search(r"In Project Work", big_plan_out)

    def test_update_big_plan(self) -> None:
        """Updating a big plan."""
        big_plan_id = self.jupiter_create(
            "big-plan-create",
            "--name",
            "Get a cat",
            "--actionable-date",
            "2022-05-01",
            "--due-date",
            "2022-05-20",
            hint="Get a cat",
        )

        self.jupiter(
            "big-plan-update",
            "--id",
            big_plan_id,
            "--status",
            "in-progress",
            "--name",
            "Get the cat",
            "--actionable-date",
            "2022-05-02",
            "--due-date",
            "2022-05-21",
        )

        self.go_to_notion("My Work", "Big Plans")

        notion_row = self.get_notion_row_in_database(
            "Get the cat",
            ["Status", "Actionable Date", "Due Date", "Project"],
        )

        assert re.search(r"Get the cat", notion_row.title)
        assert notion_row.attributes["Status"] == "In Progress"
        assert re.search("May 2, 2022", notion_row.attributes["Actionable Date"])
        assert re.search("May 21, 2022", notion_row.attributes["Due Date"])
        assert notion_row.attributes["Project"] == "Work"

        big_plan_out = self.jupiter("big-plan-show")

        assert re.search(r"Get the cat", big_plan_out)
        assert re.search(r"🚧", big_plan_out)
        assert re.search(r"From 2022-05-02", big_plan_out)
        assert re.search(r"Due at 2022-05-21", big_plan_out)
        assert re.search(r"In Project Work", big_plan_out)

    def test_change_project(self) -> None:
        """Change the project of an big plan."""
        big_plan_id = self.jupiter_create(
            "big-plan-create",
            "--name",
            "Get a cat",
            "--actionable-date",
            "2022-05-01",
            "--due-date",
            "2022-05-20",
            hint="Get a cat",
        )

        self.jupiter(
            "big-plan-change-project", "--id", big_plan_id, "--project", "personal"
        )

        self.go_to_notion("My Work", "Big Plans")

        notion_row = self.get_notion_row_in_database(
            "Get a cat",
            ["Status", "Actionable Date", "Due Date", "Project"],
        )

        assert re.search(r"Get a cat", notion_row.title)
        assert notion_row.attributes["Status"] == "Accepted"
        assert re.search(r"May 1, 2022", notion_row.attributes["Actionable Date"])
        assert re.search(r"May 20, 2022", notion_row.attributes["Due Date"])
        assert notion_row.attributes["Project"] == "Personal"

        big_plan_out = self.jupiter("big-plan-show")

        assert re.search(r"Get a cat", big_plan_out)
        assert re.search(r"🔧", big_plan_out)
        assert re.search(r"From 2022-05-01", big_plan_out)
        assert re.search(r"Due at 2022-05-20", big_plan_out)
        assert re.search(r"In Project Personal", big_plan_out)

    def test_archive_big_plan(self) -> None:
        """Archiving a big plan."""
        big_plan_id = self.jupiter_create(
            "big-plan-create",
            "--name",
            "Get a cat",
            "--actionable-date",
            "2022-05-01",
            "--due-date",
            "2022-05-20",
            hint="Get a cat",
        )

        self.jupiter(
            "inbox-task-create",
            "--name",
            "Take kitty to the vet",
            "--eisen",
            "important",
            "--difficulty",
            "hard",
            "--due-date",
            "2022-05-20",
            "--big-plan",
            big_plan_id,
        )

        self.jupiter("big-plan-archive", "--id", big_plan_id)

        self.go_to_notion("My Work", "Big Plans")

        assert not self.check_notion_row_exists("Get a cat")

        big_plan_out = self.jupiter("big-plan-show", "--show-archived")

        assert re.search(r"Get a cat", big_plan_out)

        self.go_to_notion("My Work", "Inbox Tasks")

        assert not self.check_notion_row_exists("Take kitty to the vet")

        inbox_task_out = self.jupiter("inbox-task-show", "--show-archived")

        assert re.search(r"Take kitty to the vet", inbox_task_out)

    def test_remove_big_plan(self) -> None:
        """Archiving a big plan."""
        big_plan_id = self.jupiter_create(
            "big-plan-create",
            "--name",
            "Get a cat",
            "--actionable-date",
            "2022-05-01",
            "--due-date",
            "2022-05-20",
            hint="Get a cat",
        )

        self.jupiter(
            "inbox-task-create",
            "--name",
            "Take kitty to the vet",
            "--eisen",
            "important",
            "--difficulty",
            "hard",
            "--due-date",
            "2022-05-20",
            "--big-plan",
            big_plan_id,
        )

        self.jupiter("big-plan-remove", "--id", big_plan_id)

        self.go_to_notion("My Work", "Big Plans")

        assert not self.check_notion_row_exists("Get a cat")

        big_plan_out = self.jupiter("big-plan-show", "--show-archived")

        assert not re.search(r"Get a cat", big_plan_out)

        self.go_to_notion("My Work", "Inbox Tasks")

        assert not self.check_notion_row_exists("Take kitty to the vet")

        inbox_task_out = self.jupiter("inbox-task-show", "--show-archived")

        assert not re.search(r"Take kitty to the vet", inbox_task_out)
