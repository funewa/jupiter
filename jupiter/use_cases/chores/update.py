"""The command for updating a chore."""
from dataclasses import dataclass
from typing import Optional, Final, cast

from jupiter.domain import schedules
from jupiter.domain.adate import ADate
from jupiter.domain.chores.chore_name import ChoreName
from jupiter.domain.chores.infra.chore_notion_manager import ChoreNotionManager
from jupiter.domain.chores.notion_chore import NotionChore
from jupiter.domain.difficulty import Difficulty
from jupiter.domain.eisen import Eisen
from jupiter.domain.inbox_tasks.infra.inbox_task_notion_manager import (
    InboxTaskNotionManager,
)
from jupiter.domain.inbox_tasks.notion_inbox_task import NotionInboxTask
from jupiter.domain.recurring_task_due_at_day import RecurringTaskDueAtDay
from jupiter.domain.recurring_task_due_at_month import RecurringTaskDueAtMonth
from jupiter.domain.recurring_task_due_at_time import RecurringTaskDueAtTime
from jupiter.domain.recurring_task_gen_params import RecurringTaskGenParams
from jupiter.domain.recurring_task_period import RecurringTaskPeriod
from jupiter.domain.recurring_task_skip_rule import RecurringTaskSkipRule
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.event import EventSource
from jupiter.framework.update_action import UpdateAction
from jupiter.framework.use_case import (
    MutationUseCaseInvocationRecorder,
    UseCaseArgsBase,
    ProgressReporter,
    MarkProgressStatus,
)
from jupiter.use_cases.infra.use_cases import (
    AppUseCaseContext,
    AppMutationUseCase,
)
from jupiter.utils.global_properties import GlobalProperties
from jupiter.utils.time_provider import TimeProvider


class ChoreUpdateUseCase(AppMutationUseCase["ChoreUpdateUseCase.Args", None]):
    """The command for updating a chore."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        ref_id: EntityId
        name: UpdateAction[ChoreName]
        period: UpdateAction[RecurringTaskPeriod]
        eisen: UpdateAction[Eisen]
        difficulty: UpdateAction[Optional[Difficulty]]
        actionable_from_day: UpdateAction[Optional[RecurringTaskDueAtDay]]
        actionable_from_month: UpdateAction[Optional[RecurringTaskDueAtMonth]]
        due_at_time: UpdateAction[Optional[RecurringTaskDueAtTime]]
        due_at_day: UpdateAction[Optional[RecurringTaskDueAtDay]]
        due_at_month: UpdateAction[Optional[RecurringTaskDueAtMonth]]
        must_do: UpdateAction[bool]
        skip_rule: UpdateAction[Optional[RecurringTaskSkipRule]]
        start_at_date: UpdateAction[ADate]
        end_at_date: UpdateAction[Optional[ADate]]

    _global_properties: Final[GlobalProperties]
    _inbox_task_notion_manager: Final[InboxTaskNotionManager]
    _chore_notion_manager: Final[ChoreNotionManager]

    def __init__(
        self,
        global_properties: GlobalProperties,
        time_provider: TimeProvider,
        invocation_recorder: MutationUseCaseInvocationRecorder,
        storage_engine: DomainStorageEngine,
        inbox_task_notion_manager: InboxTaskNotionManager,
        chore_notion_manager: ChoreNotionManager,
    ) -> None:
        """Constructor."""
        super().__init__(time_provider, invocation_recorder, storage_engine)
        self._global_properties = global_properties
        self._inbox_task_notion_manager = inbox_task_notion_manager
        self._chore_notion_manager = chore_notion_manager

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> None:
        """Execute the command's action."""
        workspace = context.workspace

        with progress_reporter.start_updating_entity(
            "chore", args.ref_id
        ) as entity_reporter:
            with self._storage_engine.get_unit_of_work() as uow:
                chore = uow.chore_repository.load_by_id(args.ref_id)
                entity_reporter.mark_known_name(str(chore.name))

                project = uow.project_repository.load_by_id(chore.project_ref_id)

                need_to_change_inbox_tasks = (
                    args.name.should_change
                    or args.period.should_change
                    or args.eisen.should_change
                    or args.difficulty.should_change
                    or args.actionable_from_day.should_change
                    or args.actionable_from_month.should_change
                    or args.due_at_time.should_change
                    or args.due_at_day.should_change
                    or args.due_at_month.should_change
                )

                if (
                    args.period.should_change
                    or args.eisen.should_change
                    or args.difficulty.should_change
                    or args.actionable_from_day.should_change
                    or args.actionable_from_month.should_change
                    or args.due_at_time.should_change
                    or args.due_at_day.should_change
                    or args.due_at_month.should_change
                ):
                    need_to_change_inbox_tasks = True
                    chore_gen_params = UpdateAction.change_to(
                        RecurringTaskGenParams(
                            args.period.or_else(chore.gen_params.period),
                            args.eisen.or_else(chore.gen_params.eisen),
                            args.difficulty.or_else(chore.gen_params.difficulty),
                            args.actionable_from_day.or_else(
                                chore.gen_params.actionable_from_day
                            ),
                            args.actionable_from_month.or_else(
                                chore.gen_params.actionable_from_month
                            ),
                            args.due_at_time.or_else(chore.gen_params.due_at_time),
                            args.due_at_day.or_else(chore.gen_params.due_at_day),
                            args.due_at_month.or_else(chore.gen_params.due_at_month),
                        )
                    )
                else:
                    chore_gen_params = UpdateAction.do_nothing()

                chore = chore.update(
                    name=args.name,
                    gen_params=chore_gen_params,
                    must_do=args.must_do,
                    skip_rule=args.skip_rule,
                    start_at_date=args.start_at_date,
                    end_at_date=args.end_at_date,
                    source=EventSource.CLI,
                    modification_time=self._time_provider.get_current_time(),
                )

                uow.chore_repository.save(chore)
                entity_reporter.mark_local_change()

            chore_direct_info = NotionChore.DirectInfo(
                all_projects_map={project.ref_id: project}
            )
            notion_chore = self._chore_notion_manager.load_leaf(
                chore.chore_collection_ref_id, chore.ref_id
            )
            notion_chore = notion_chore.join_with_entity(chore, chore_direct_info)
            self._chore_notion_manager.save_leaf(
                chore.chore_collection_ref_id, notion_chore
            )
            entity_reporter.mark_remote_change()

        if need_to_change_inbox_tasks:
            with self._storage_engine.get_unit_of_work() as uow:
                inbox_task_collection = (
                    uow.inbox_task_collection_repository.load_by_parent(
                        workspace.ref_id
                    )
                )
                all_inbox_tasks = uow.inbox_task_repository.find_all_with_filters(
                    parent_ref_id=inbox_task_collection.ref_id,
                    allow_archived=True,
                    filter_chore_ref_ids=[chore.ref_id],
                )

            for inbox_task in all_inbox_tasks:
                with progress_reporter.start_updating_entity(
                    "inbox task", inbox_task.ref_id, str(inbox_task.name)
                ) as entity_reporter:
                    schedule = schedules.get_schedule(
                        chore.gen_params.period,
                        chore.name,
                        cast(Timestamp, inbox_task.recurring_gen_right_now),
                        self._global_properties.timezone,
                        chore.skip_rule,
                        chore.gen_params.actionable_from_day,
                        chore.gen_params.actionable_from_month,
                        chore.gen_params.due_at_time,
                        chore.gen_params.due_at_day,
                        chore.gen_params.due_at_month,
                    )

                    inbox_task = inbox_task.update_link_to_chore(
                        project_ref_id=project.ref_id,
                        name=schedule.full_name,
                        timeline=schedule.timeline,
                        actionable_date=schedule.actionable_date,
                        due_date=schedule.due_time,
                        eisen=chore.gen_params.eisen,
                        difficulty=chore.gen_params.difficulty,
                        source=EventSource.CLI,
                        modification_time=self._time_provider.get_current_time(),
                    )
                    entity_reporter.mark_known_name(str(inbox_task.name))

                    with self._storage_engine.get_unit_of_work() as uow:
                        uow.inbox_task_repository.save(inbox_task)
                        entity_reporter.mark_local_change()

                    if inbox_task.archived:
                        entity_reporter.mark_remote_change(
                            MarkProgressStatus.NOT_NEEDED
                        )
                        continue

                    inbox_task_direct_info = NotionInboxTask.DirectInfo(
                        all_projects_map={project.ref_id: project}, all_big_plans_map={}
                    )
                    notion_inbox_task = self._inbox_task_notion_manager.load_leaf(
                        inbox_task.inbox_task_collection_ref_id, inbox_task.ref_id
                    )
                    notion_inbox_task = notion_inbox_task.join_with_entity(
                        inbox_task, inbox_task_direct_info
                    )
                    self._inbox_task_notion_manager.save_leaf(
                        inbox_task.inbox_task_collection_ref_id, notion_inbox_task
                    )
                    entity_reporter.mark_remote_change()
