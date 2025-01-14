"""UseCase for syncing the local and Notion-side data."""
from argparse import ArgumentParser, Namespace
from typing import Final

from jupiter.command import command
from jupiter.command.rendering import RichConsoleProgressReporter
from jupiter.domain.metrics.metric_key import MetricKey
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.domain.smart_lists.smart_list_key import SmartListKey
from jupiter.domain.sync_prefer import SyncPrefer
from jupiter.domain.sync_target import SyncTarget
from jupiter.framework.base.entity_id import EntityId
from jupiter.use_cases.sync import SyncUseCase


class Sync(command.Command):
    """UseCase class for syncing the local and Notion-side data."""

    _command: Final[SyncUseCase]

    def __init__(self, the_command: SyncUseCase) -> None:
        """Constructor."""
        self._command = the_command

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
        parser.add_argument(
            "--target",
            dest="sync_targets",
            default=[],
            action="append",
            choices=SyncTarget.all_values(),
            help="What exactly to try to sync",
        )
        parser.add_argument(
            "--vacation-id",
            dest="vacation_ref_ids",
            default=[],
            action="append",
            help="Sync only from this vacation",
        )
        parser.add_argument(
            "--project",
            dest="project_keys",
            default=[],
            action="append",
            help="Sync only from this project",
        )
        parser.add_argument(
            "--inbox-task-id",
            dest="inbox_task_ref_ids",
            default=[],
            action="append",
            help="Sync only these particular tasks",
        )
        parser.add_argument(
            "--big-plan-id",
            dest="big_plan_ref_ids",
            default=[],
            action="append",
            help="Sync only these particular big plans",
        )
        parser.add_argument(
            "--habit-id",
            dest="habit_ref_ids",
            default=[],
            action="append",
            help="Sync only these habits",
        )
        parser.add_argument(
            "--chore-id",
            dest="chore_ref_ids",
            default=[],
            action="append",
            help="Sync only these chores",
        )
        parser.add_argument(
            "--smart-list",
            dest="smart_list_keys",
            default=[],
            action="append",
            help="Sync only these smart lists",
        )
        parser.add_argument(
            "--smart-list-item-id",
            dest="smart_list_item_ref_ids",
            default=[],
            action="append",
            help="Sync only these smart list items",
        )
        parser.add_argument(
            "--metric",
            dest="metric_keys",
            default=[],
            action="append",
            help="Sync only these metrics",
        )
        parser.add_argument(
            "--metric-entry-id",
            dest="metric_entry_ref_ids",
            default=[],
            action="append",
            help="Sync only these metric entries",
        )
        parser.add_argument(
            "--person-id",
            dest="person_ref_ids",
            default=[],
            action="append",
            help="Sync only these persons",
        )
        parser.add_argument(
            "--slack-task-id",
            dest="slack_task_ref_ids",
            default=[],
            action="append",
            help="Sync only these Slack tasks",
        )
        parser.add_argument(
            "--email-task-id",
            dest="email_task_ref_ids",
            default=[],
            action="append",
            help="Sync only these Email tasks",
        )
        parser.add_argument(
            "--prefer",
            dest="sync_prefer",
            choices=SyncPrefer.all_values(),
            default=SyncPrefer.NOTION.value,
            help="Which source to prefer",
        )
        parser.add_argument(
            "--drop-all-notion",
            dest="drop_all_notion",
            action="store_true",
            default=False,
            help="Drop all Notion-side entities before syncing and restore from local entirely",
        )
        parser.add_argument(
            "--ignore-modified-times",
            dest="sync_even_if_not_modified",
            action="store_true",
            default=False,
            help="Drop all Notion-side archived",
        )

    def run(
        self, progress_reporter: RichConsoleProgressReporter, args: Namespace
    ) -> None:
        """Callback to execute when the command is invoked."""
        sync_targets = (
            [SyncTarget.from_raw(st) for st in args.sync_targets]
            if len(args.sync_targets) > 0
            else list(st for st in SyncTarget if st is not SyncTarget.STRUCTURE)
        )
        vacation_ref_ids = (
            [EntityId.from_raw(v) for v in args.vacation_ref_ids]
            if len(args.vacation_ref_ids) > 0
            else None
        )
        project_keys = (
            [ProjectKey.from_raw(pk) for pk in args.project_keys]
            if len(args.project_keys) > 0
            else None
        )
        inbox_task_ref_ids = (
            [EntityId.from_raw(bp) for bp in args.inbox_task_ref_ids]
            if len(args.inbox_task_ref_ids) > 0
            else None
        )
        big_plan_ref_ids = (
            [EntityId.from_raw(bp) for bp in args.big_plan_ref_ids]
            if len(args.big_plan_ref_ids) > 0
            else None
        )
        habit_ref_ids = (
            [EntityId.from_raw(rt) for rt in args.habit_ref_ids]
            if len(args.habit_ref_ids) > 0
            else None
        )
        chore_ref_ids = (
            [EntityId.from_raw(rt) for rt in args.chore_ref_ids]
            if len(args.chore_ref_ids) > 0
            else None
        )
        smart_list_keys = (
            [SmartListKey.from_raw(sl) for sl in args.smart_list_keys]
            if len(args.smart_list_keys) > 0
            else None
        )
        smart_list_item_ref_ids = (
            [EntityId.from_raw(sli) for sli in args.smart_list_item_ref_ids]
            if len(args.smart_list_item_ref_ids) > 0
            else None
        )
        metric_keys = (
            [MetricKey.from_raw(mk) for mk in args.metric_keys]
            if len(args.metric_keys) > 0
            else None
        )
        metric_entry_ref_ids = (
            [EntityId.from_raw(sli) for sli in args.metric_entry_ref_ids]
            if len(args.metric_entry_ref_ids) > 0
            else None
        )
        person_ref_ids = (
            [EntityId.from_raw(sli) for sli in args.person_ref_ids]
            if len(args.person_ref_ids) > 0
            else None
        )
        slack_task_ref_ids = (
            [EntityId.from_raw(rid) for rid in args.slack_task_ref_ids]
            if len(args.slack_task_ref_ids) > 0
            else None
        )
        email_task_ref_ids = (
            [EntityId.from_raw(rid) for rid in args.email_task_ref_ids]
            if len(args.email_task_ref_ids) > 0
            else None
        )
        sync_prefer = SyncPrefer.from_raw(args.sync_prefer)
        drop_all_notion = args.drop_all_notion
        sync_even_if_not_modified = args.sync_even_if_not_modified

        self._command.execute(
            progress_reporter,
            SyncUseCase.Args(
                sync_targets=sync_targets,
                drop_all_notion=drop_all_notion,
                sync_even_if_not_modified=sync_even_if_not_modified,
                filter_vacation_ref_ids=vacation_ref_ids,
                filter_project_keys=project_keys,
                filter_inbox_task_ref_ids=inbox_task_ref_ids,
                filter_big_plan_ref_ids=big_plan_ref_ids,
                filter_habit_ref_ids=habit_ref_ids,
                filter_chore_ref_ids=chore_ref_ids,
                filter_smart_list_keys=smart_list_keys,
                filter_smart_list_item_ref_ids=smart_list_item_ref_ids,
                filter_metric_keys=metric_keys,
                filter_metric_entry_ref_ids=metric_entry_ref_ids,
                filter_person_ref_ids=person_ref_ids,
                filter_slack_task_ref_ids=slack_task_ref_ids,
                filter_email_task_ref_ids=email_task_ref_ids,
                sync_prefer=sync_prefer,
            ),
        )
