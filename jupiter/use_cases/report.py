"""The command for reporting on progress."""
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import groupby
from operator import itemgetter
from typing import Optional, Iterable, Final, Dict, List, cast, DefaultDict

import pendulum
from pendulum import UTC

from jupiter.domain import schedules
from jupiter.domain.adate import ADate
from jupiter.domain.big_plans.big_plan import BigPlan
from jupiter.domain.big_plans.big_plan_name import BigPlanName
from jupiter.domain.big_plans.big_plan_status import BigPlanStatus
from jupiter.domain.chores.chore import Chore
from jupiter.domain.entity_name import EntityName
from jupiter.domain.habits.habit import Habit
from jupiter.domain.inbox_tasks.inbox_task import InboxTask
from jupiter.domain.inbox_tasks.inbox_task_source import InboxTaskSource
from jupiter.domain.inbox_tasks.inbox_task_status import InboxTaskStatus
from jupiter.domain.metrics.metric import Metric
from jupiter.domain.metrics.metric_key import MetricKey
from jupiter.domain.projects.project import Project
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.domain.recurring_task_period import RecurringTaskPeriod
from jupiter.domain.schedules import Schedule
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.use_case import (
    UseCaseArgsBase,
    UseCaseResultBase,
    ProgressReporter,
)
from jupiter.use_cases.infra.use_cases import AppReadonlyUseCase, AppUseCaseContext
from jupiter.utils.global_properties import GlobalProperties


class ReportUseCase(AppReadonlyUseCase["ReportUseCase.Args", "ReportUseCase.Result"]):
    """The command for reporting on progress."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        right_now: Timestamp
        filter_project_keys: Optional[Iterable[ProjectKey]]
        filter_sources: Optional[Iterable[InboxTaskSource]]
        filter_big_plan_ref_ids: Optional[Iterable[EntityId]]
        filter_habit_ref_ids: Optional[Iterable[EntityId]]
        filter_chore_ref_ids: Optional[Iterable[EntityId]]
        filter_metric_keys: Optional[Iterable[MetricKey]]
        filter_person_ref_ids: Optional[Iterable[EntityId]]
        filter_slack_task_ref_ids: Optional[Iterable[EntityId]]
        filter_email_task_ref_ids: Optional[Iterable[EntityId]]
        period: RecurringTaskPeriod
        breakdown_period: Optional[RecurringTaskPeriod]

    @dataclass(frozen=True)
    class NestedResult:
        """A result broken down by the various sources of inbox tasks."""

        total_cnt: int
        per_source_cnt: Dict[InboxTaskSource, int]

    @dataclass(frozen=True)
    class InboxTasksSummary:
        """A bigger summary for inbox tasks."""

        created: "ReportUseCase.NestedResult"
        accepted: "ReportUseCase.NestedResult"
        working: "ReportUseCase.NestedResult"
        not_done: "ReportUseCase.NestedResult"
        done: "ReportUseCase.NestedResult"

    @dataclass(frozen=True)
    class WorkableBigPlan:
        """The view of a big plan via a workable."""

        ref_id: EntityId
        name: BigPlanName
        actionable_date: Optional[ADate]

    @dataclass(frozen=True)
    class WorkableSummary:
        """The reporting summary."""

        created_cnt: int
        accepted_cnt: int
        working_cnt: int
        not_done_cnt: int
        done_cnt: int
        not_done_big_plans: List["ReportUseCase.WorkableBigPlan"]
        done_big_plans: List["ReportUseCase.WorkableBigPlan"]

    @dataclass(frozen=True)
    class BigPlanSummary:
        """The report for a big plan."""

        created_cnt: int
        accepted_cnt: int
        working_cnt: int
        not_done_cnt: int
        not_done_ratio: float
        done_cnt: int
        done_ratio: float

    @dataclass(frozen=True)
    class RecurringTaskSummary:
        """The reporting summary."""

        created_cnt: int
        accepted_cnt: int
        working_cnt: int
        not_done_cnt: int
        not_done_ratio: float
        done_cnt: int
        done_ratio: float
        streak_plot: str = field(hash=False, compare=False, repr=False, default="")

    @dataclass(frozen=True)
    class PerProjectBreakdownItem:
        """The report for a particular project."""

        name: EntityName
        inbox_tasks_summary: "ReportUseCase.InboxTasksSummary"
        big_plans_summary: "ReportUseCase.WorkableSummary"

    @dataclass(frozen=True)
    class PerPeriodBreakdownItem:
        """The report for a particular time period."""

        name: EntityName
        inbox_tasks_summary: "ReportUseCase.InboxTasksSummary"
        big_plans_summary: "ReportUseCase.WorkableSummary"

    @dataclass(frozen=True)
    class PerBigPlanBreakdownItem:
        """The report for a particular big plan."""

        ref_id: EntityId
        name: EntityName
        actionable_date: Optional[ADate]
        summary: "ReportUseCase.BigPlanSummary"

    @dataclass(frozen=True)
    class PerHabitBreakdownItem:
        """The report for a particular habit."""

        ref_id: EntityId
        name: EntityName
        archived: bool
        period: RecurringTaskPeriod
        suspended: bool
        summary: "ReportUseCase.RecurringTaskSummary"

    @dataclass(frozen=True)
    class PerChoreBreakdownItem:
        """The report for a particular chore."""

        ref_id: EntityId
        name: EntityName
        archived: bool
        period: RecurringTaskPeriod
        summary: "ReportUseCase.RecurringTaskSummary"

    @dataclass(frozen=True)
    class Result(UseCaseResultBase):
        """Result of the run report call."""

        global_inbox_tasks_summary: "ReportUseCase.InboxTasksSummary"
        global_big_plans_summary: "ReportUseCase.WorkableSummary"
        per_project_breakdown: List["ReportUseCase.PerProjectBreakdownItem"]
        per_period_breakdown: Optional[List["ReportUseCase.PerPeriodBreakdownItem"]]
        per_habit_breakdown: List["ReportUseCase.PerHabitBreakdownItem"]
        per_chore_breakdown: List["ReportUseCase.PerChoreBreakdownItem"]
        per_big_plan_breakdown: List["ReportUseCase.PerBigPlanBreakdownItem"]

    _global_properties: Final[GlobalProperties]

    def __init__(
        self, global_properties: GlobalProperties, storage_engine: DomainStorageEngine
    ) -> None:
        """Constructor."""
        super().__init__(storage_engine)
        self._global_properties = global_properties

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> "Result":
        """Execute the command."""
        workspace = context.workspace
        today = args.right_now.value.date()

        with self._storage_engine.get_unit_of_work() as uow:
            project_collection = uow.project_collection_repository.load_by_parent(
                workspace.ref_id
            )
            projects = uow.project_repository.find_all_with_filters(
                parent_ref_id=project_collection.ref_id,
                filter_keys=args.filter_project_keys,
            )
            filter_project_ref_ids = [p.ref_id for p in projects]
            projects_by_ref_id: Dict[EntityId, Project] = {
                p.ref_id: p for p in projects
            }

            inbox_task_collection = uow.inbox_task_collection_repository.load_by_parent(
                workspace.ref_id
            )
            habit_collection = uow.habit_collection_repository.load_by_parent(
                workspace.ref_id
            )
            chore_collection = uow.chore_collection_repository.load_by_parent(
                workspace.ref_id
            )
            big_plan_collection = uow.big_plan_collection_repository.load_by_parent(
                workspace.ref_id
            )

            metric_collection = uow.metric_collection_repository.load_by_parent(
                workspace.ref_id
            )
            metrics = uow.metric_repository.find_all(
                parent_ref_id=metric_collection.ref_id,
                allow_archived=True,
                filter_keys=args.filter_metric_keys,
            )
            metrics_by_ref_id: Dict[EntityId, Metric] = {m.ref_id: m for m in metrics}

            person_collection = uow.person_collection_repository.load_by_parent(
                workspace.ref_id
            )
            persons = uow.person_repository.find_all(
                parent_ref_id=person_collection.ref_id,
                allow_archived=True,
                filter_ref_ids=args.filter_person_ref_ids,
            )
            persons_by_ref_id = {p.ref_id: p for p in persons}

            schedule = schedules.get_schedule(
                args.period,
                EntityName("Helper"),
                args.right_now,
                self._global_properties.timezone,
                None,
                None,
                None,
                None,
                None,
                None,
            )

            all_inbox_tasks = [
                it
                for it in uow.inbox_task_repository.find_all_with_filters(
                    parent_ref_id=inbox_task_collection.ref_id,
                    allow_archived=True,
                    filter_sources=args.filter_sources,
                    filter_project_ref_ids=filter_project_ref_ids,
                )
                # (source is BIG_PLAN and (need to filter then (big_plan_ref_id in filter))
                if it.source is InboxTaskSource.USER
                or (
                    it.source is InboxTaskSource.BIG_PLAN
                    and (
                        not (args.filter_big_plan_ref_ids is not None)
                        or (
                            it.big_plan_ref_id is not None
                            and it.big_plan_ref_id in args.filter_big_plan_ref_ids
                        )
                    )
                )
                or (
                    it.source is InboxTaskSource.HABIT
                    and (
                        not (args.filter_habit_ref_ids is not None)
                        or (
                            it.habit_ref_id is not None
                            and it.habit_ref_id in args.filter_habit_ref_ids
                        )
                    )
                )
                or (
                    it.source is InboxTaskSource.CHORE
                    and (
                        not (args.filter_chore_ref_ids is not None)
                        or (
                            it.chore_ref_id is not None
                            and it.chore_ref_id in args.filter_chore_ref_ids
                        )
                    )
                )
                or (
                    it.source is InboxTaskSource.METRIC
                    and (
                        not (args.filter_metric_keys is not None)
                        or it.metric_ref_id in metrics_by_ref_id
                    )
                )
                or (
                    (
                        it.source is InboxTaskSource.PERSON_CATCH_UP
                        or it.source is InboxTaskSource.PERSON_BIRTHDAY
                    )
                    and (
                        not (args.filter_person_ref_ids is not None)
                        or it.person_ref_id in persons_by_ref_id
                    )
                )
                or (
                    it.source is InboxTaskSource.SLACK_TASK
                    and (
                        not (args.filter_slack_task_ref_ids is not None)
                        or (
                            it.slack_task_ref_id is not None
                            and it.slack_task_ref_id in args.filter_slack_task_ref_ids
                        )
                    )
                )
                or (
                    it.source is InboxTaskSource.EMAIL_TASK
                    and (
                        not (args.filter_email_task_ref_ids is not None)
                        or (
                            it.email_task_ref_id is not None
                            and it.email_task_ref_id in args.filter_email_task_ref_ids
                        )
                    )
                )
            ]

            all_habits = uow.habit_repository.find_all_with_filters(
                parent_ref_id=habit_collection.ref_id,
                allow_archived=True,
                filter_ref_ids=args.filter_habit_ref_ids,
                filter_project_ref_ids=filter_project_ref_ids,
            )
            all_habits_by_ref_id: Dict[EntityId, Habit] = {
                rt.ref_id: rt for rt in all_habits
            }

            all_chores = uow.chore_repository.find_all_with_filters(
                parent_ref_id=chore_collection.ref_id,
                allow_archived=True,
                filter_ref_ids=args.filter_chore_ref_ids,
                filter_project_ref_ids=filter_project_ref_ids,
            )
            all_chores_by_ref_id: Dict[EntityId, Chore] = {
                rt.ref_id: rt for rt in all_chores
            }

            all_big_plans = uow.big_plan_repository.find_all_with_filters(
                parent_ref_id=big_plan_collection.ref_id,
                allow_archived=True,
                filter_ref_ids=args.filter_big_plan_ref_ids,
                filter_project_ref_ids=filter_project_ref_ids,
            )
            big_plans_by_ref_id: Dict[EntityId, BigPlan] = {
                bp.ref_id: bp for bp in all_big_plans
            }

        global_inbox_tasks_summary = self._run_report_for_inbox_tasks(
            schedule, all_inbox_tasks
        )
        global_big_plans_summary = self._run_report_for_big_plan(
            schedule, all_big_plans
        )

        # Build per project breakdown

        # all_inbox_tasks.groupBy(it -> it.project.name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_project_inbox_tasks_summary = {
            k: self._run_report_for_inbox_tasks(schedule, (vx[1] for vx in v))
            for (k, v) in groupby(
                sorted(
                    [
                        (projects_by_ref_id[it.project_ref_id].name, it)
                        for it in all_inbox_tasks
                    ],
                    key=itemgetter(0),
                ),
                key=itemgetter(0),
            )
        }
        # all_big_plans.groupBy(it -> it.project..name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_project_big_plans_summary = {
            k: self._run_report_for_big_plan(schedule, (vx[1] for vx in v))
            for (k, v) in groupby(
                sorted(
                    [
                        (projects_by_ref_id[bp.project_ref_id].name, bp)
                        for bp in all_big_plans
                    ],
                    key=itemgetter(0),
                ),
                key=itemgetter(0),
            )
        }
        per_project_breakdown = [
            ReportUseCase.PerProjectBreakdownItem(
                name=s,
                inbox_tasks_summary=v,
                big_plans_summary=per_project_big_plans_summary.get(
                    s, ReportUseCase.WorkableSummary(0, 0, 0, 0, 0, [], [])
                ),
            )
            for (s, v) in per_project_inbox_tasks_summary.items()
        ]

        # Build per period breakdown
        per_period_breakdown = None
        if args.breakdown_period:
            all_schedules = {}
            curr_date = schedule.first_day.start_of_day()
            end_date = schedule.end_day.end_of_day()
            while curr_date < end_date and curr_date <= today:
                curr_date_as_time = Timestamp(
                    pendulum.DateTime(
                        curr_date.year, curr_date.month, curr_date.day, tzinfo=UTC
                    )
                )
                phase_schedule = schedules.get_schedule(
                    args.breakdown_period,
                    EntityName("Sub-period"),
                    curr_date_as_time,
                    self._global_properties.timezone,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                all_schedules[phase_schedule.full_name] = phase_schedule
                curr_date = curr_date.next_day()

            per_period_inbox_tasks_summary = {
                k: self._run_report_for_inbox_tasks(v, all_inbox_tasks)
                for (k, v) in all_schedules.items()
            }
            per_period_big_plans_summary = {
                k: self._run_report_for_big_plan(v, all_big_plans)
                for (k, v) in all_schedules.items()
            }
            per_period_breakdown = [
                ReportUseCase.PerPeriodBreakdownItem(
                    name=k,
                    inbox_tasks_summary=v,
                    big_plans_summary=per_period_big_plans_summary.get(
                        k, ReportUseCase.WorkableSummary(0, 0, 0, 0, 0, [], [])
                    ),
                )
                for (k, v) in per_period_inbox_tasks_summary.items()
            ]

        # Build per habit breakdown

        # all_inbox_tasks.groupBy(it -> it.habit.name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_habit_breakdown = [
            hb
            for hb in (
                ReportUseCase.PerHabitBreakdownItem(
                    ref_id=all_habits_by_ref_id[k].ref_id,
                    name=all_habits_by_ref_id[k].name,
                    archived=all_habits_by_ref_id[k].archived,
                    suspended=all_habits_by_ref_id[k].suspended,
                    period=all_habits_by_ref_id[k].gen_params.period,
                    summary=self._run_report_for_inbox_for_recurring_tasks(
                        schedule, [vx[1] for vx in v]
                    ),
                )
                for (k, v) in groupby(
                    sorted(
                        [
                            (it.habit_ref_id, it)
                            for it in all_inbox_tasks
                            if it.habit_ref_id
                        ],
                        key=itemgetter(0),
                    ),
                    key=itemgetter(0),
                )
            )
            if all_habits_by_ref_id[hb.ref_id].archived is False
        ]

        # Build per chore breakdown

        # all_inbox_tasks.groupBy(it -> it.chore.name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_chore_breakdown = [
            cb
            for cb in (
                ReportUseCase.PerChoreBreakdownItem(
                    ref_id=all_chores_by_ref_id[k].ref_id,
                    name=all_chores_by_ref_id[k].name,
                    archived=all_chores_by_ref_id[k].archived,
                    period=all_chores_by_ref_id[k].gen_params.period,
                    summary=self._run_report_for_inbox_for_recurring_tasks(
                        schedule, [vx[1] for vx in v]
                    ),
                )
                for (k, v) in groupby(
                    sorted(
                        [
                            (it.chore_ref_id, it)
                            for it in all_inbox_tasks
                            if it.chore_ref_id
                        ],
                        key=itemgetter(0),
                    ),
                    key=itemgetter(0),
                )
            )
            if all_chores_by_ref_id[cb.ref_id].archived is False
        ]

        # Build per big plan breakdown

        # all_inbox_tasks.groupBy(it -> it.bigPlan.name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_big_plan_breakdown = [
            bb
            for bb in (
                ReportUseCase.PerBigPlanBreakdownItem(
                    ref_id=big_plans_by_ref_id[k].ref_id,
                    name=big_plans_by_ref_id[k].name,
                    actionable_date=big_plans_by_ref_id[k].actionable_date,
                    summary=self._run_report_for_inbox_tasks_for_big_plan(
                        schedule, (vx[1] for vx in v)
                    ),
                )
                for (k, v) in groupby(
                    sorted(
                        [
                            (it.big_plan_ref_id, it)
                            for it in all_inbox_tasks
                            if it.big_plan_ref_id
                        ],
                        key=itemgetter(0),
                    ),
                    key=itemgetter(0),
                )
            )
            if big_plans_by_ref_id[bb.ref_id].archived is False
        ]

        return ReportUseCase.Result(
            global_inbox_tasks_summary=global_inbox_tasks_summary,
            global_big_plans_summary=global_big_plans_summary,
            per_project_breakdown=per_project_breakdown,
            per_period_breakdown=per_period_breakdown,
            per_habit_breakdown=per_habit_breakdown,
            per_chore_breakdown=per_chore_breakdown,
            per_big_plan_breakdown=per_big_plan_breakdown,
        )

    @staticmethod
    def _run_report_for_inbox_tasks(
        schedule: Schedule, inbox_tasks: Iterable[InboxTask]
    ) -> "InboxTasksSummary":
        created_cnt_total = 0
        created_per_source_cnt: DefaultDict[InboxTaskSource, int] = defaultdict(int)
        accepted_cnt_total = 0
        accepted_per_source_cnt: DefaultDict[InboxTaskSource, int] = defaultdict(int)
        working_cnt_total = 0
        working_per_source_cnt: DefaultDict[InboxTaskSource, int] = defaultdict(int)
        done_cnt_total = 0
        done_per_source_cnt: DefaultDict[InboxTaskSource, int] = defaultdict(int)
        not_done_cnt_total = 0
        not_done_per_source_cnt: DefaultDict[InboxTaskSource, int] = defaultdict(int)

        for inbox_task in inbox_tasks:
            if schedule.contains_timestamp(inbox_task.created_time):
                created_cnt_total += 1
                created_per_source_cnt[inbox_task.source] += 1

            if inbox_task.status.is_accepted and inbox_task.accepted_time is None:
                raise Exception(f"Invalid state for {inbox_task}")

            if inbox_task.status.is_completed and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.completed_time)
            ):
                if inbox_task.status == InboxTaskStatus.DONE:
                    done_cnt_total += 1
                    done_per_source_cnt[inbox_task.source] += 1
                else:
                    not_done_cnt_total += 1
                    not_done_per_source_cnt[inbox_task.source] += 1
            elif inbox_task.status.is_working and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.working_time)
            ):
                working_cnt_total += 1
                working_per_source_cnt[inbox_task.source] += 1
            elif inbox_task.status.is_accepted and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.accepted_time)
            ):
                accepted_cnt_total += 1
                accepted_per_source_cnt[inbox_task.source] += 1

        return ReportUseCase.InboxTasksSummary(
            created=ReportUseCase.NestedResult(
                total_cnt=created_cnt_total, per_source_cnt=created_per_source_cnt
            ),
            accepted=ReportUseCase.NestedResult(
                total_cnt=accepted_cnt_total, per_source_cnt=accepted_per_source_cnt
            ),
            working=ReportUseCase.NestedResult(
                total_cnt=working_cnt_total, per_source_cnt=working_per_source_cnt
            ),
            not_done=ReportUseCase.NestedResult(
                total_cnt=not_done_cnt_total, per_source_cnt=not_done_per_source_cnt
            ),
            done=ReportUseCase.NestedResult(
                total_cnt=done_cnt_total, per_source_cnt=done_per_source_cnt
            ),
        )

    @staticmethod
    def _run_report_for_inbox_tasks_for_big_plan(
        schedule: Schedule, inbox_tasks: Iterable[InboxTask]
    ) -> "BigPlanSummary":
        created_cnt = 0
        accepted_cnt = 0
        working_cnt = 0
        done_cnt = 0
        not_done_cnt = 0

        for inbox_task in inbox_tasks:
            if schedule.contains_timestamp(inbox_task.created_time):
                created_cnt += 1

            if inbox_task.status.is_completed and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.completed_time)
            ):
                if inbox_task.status == InboxTaskStatus.DONE:
                    done_cnt += 1
                else:
                    not_done_cnt += 1
            elif inbox_task.status.is_working and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.working_time)
            ):
                working_cnt += 1
            elif inbox_task.status.is_accepted and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.accepted_time)
            ):
                accepted_cnt += 1

        return ReportUseCase.BigPlanSummary(
            created_cnt=created_cnt,
            accepted_cnt=accepted_cnt,
            working_cnt=working_cnt,
            not_done_cnt=not_done_cnt,
            not_done_ratio=not_done_cnt / float(created_cnt)
            if created_cnt > 0
            else 0.0,
            done_cnt=done_cnt,
            done_ratio=done_cnt / float(created_cnt) if created_cnt > 0 else 0,
        )

    @staticmethod
    def _run_report_for_inbox_for_recurring_tasks(
        schedule: Schedule, inbox_tasks: List[InboxTask]
    ) -> "RecurringTaskSummary":
        # The simple summary computations here.
        created_cnt = 0
        accepted_cnt = 0
        working_cnt = 0
        done_cnt = 0
        not_done_cnt = 0

        for inbox_task in inbox_tasks:
            if schedule.contains_timestamp(inbox_task.created_time):
                created_cnt += 1

            if inbox_task.status.is_completed and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.completed_time)
            ):
                if inbox_task.status == InboxTaskStatus.DONE:
                    done_cnt += 1
                else:
                    not_done_cnt += 1
            elif inbox_task.status.is_working and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.working_time)
            ):
                working_cnt += 1
            elif inbox_task.status.is_accepted and schedule.contains_timestamp(
                cast(Timestamp, inbox_task.accepted_time)
            ):
                accepted_cnt += 1

        # The streak computations here.
        sorted_inbox_tasks = sorted(
            (it for it in inbox_tasks if schedule.contains_timestamp(it.created_time)),
            key=lambda it: (it.created_time, it.recurring_repeat_index),
        )
        used_skip_once = False
        streak_plot = []

        for inbox_task_idx, inbox_task in enumerate(sorted_inbox_tasks):
            if inbox_task.status == InboxTaskStatus.DONE:
                if inbox_task.recurring_repeat_index is None:
                    streak_plot.append("X")
                elif inbox_task.recurring_repeat_index == 0:
                    streak_plot.append("1")
                else:
                    streak_plot[-1] = str(int(streak_plot[-1], base=10) + 1)
            else:
                if (
                    inbox_task_idx != 0
                    and inbox_task_idx != len(sorted_inbox_tasks) - 1
                    and sorted_inbox_tasks[inbox_task_idx - 1].status
                    == InboxTaskStatus.DONE
                    and sorted_inbox_tasks[inbox_task_idx + 1].status
                    == InboxTaskStatus.DONE
                    and not used_skip_once
                ):
                    used_skip_once = True
                    if inbox_task.recurring_repeat_index is None:
                        streak_plot.append("x")
                    elif inbox_task.recurring_repeat_index == 0:
                        streak_plot.append("1")
                    else:
                        streak_plot[-1] = str(int(streak_plot[-1], base=10) + 1)
                else:
                    used_skip_once = False
                    if inbox_task.recurring_repeat_index is None:
                        streak_plot.append(
                            "."
                            if inbox_task_idx < (len(sorted_inbox_tasks) - 1)
                            else "?"
                        )
                    elif inbox_task.recurring_repeat_index == 0:
                        streak_plot.append(
                            "0"
                            if inbox_task_idx < (len(sorted_inbox_tasks) - 1)
                            else "?"
                        )

        return ReportUseCase.RecurringTaskSummary(
            created_cnt=created_cnt,
            accepted_cnt=accepted_cnt,
            working_cnt=working_cnt,
            not_done_cnt=not_done_cnt,
            not_done_ratio=not_done_cnt / float(created_cnt)
            if created_cnt > 0
            else 0.0,
            done_cnt=done_cnt,
            done_ratio=done_cnt / float(created_cnt) if created_cnt > 0 else 0.0,
            streak_plot="".join(streak_plot),
        )

    @staticmethod
    def _run_report_for_big_plan(
        schedule: Schedule, big_plans: Iterable[BigPlan]
    ) -> "WorkableSummary":
        created_cnt = 0
        accepted_cnt = 0
        working_cnt = 0
        not_done_cnt = 0
        done_cnt = 0
        not_done_projects = []
        done_projects = []

        for big_plan in big_plans:
            if schedule.contains_timestamp(big_plan.created_time):
                created_cnt += 1

            if big_plan.status.is_completed and schedule.contains_timestamp(
                cast(Timestamp, big_plan.completed_time)
            ):
                if big_plan.status == BigPlanStatus.DONE:
                    done_cnt += 1
                    done_projects.append(
                        ReportUseCase.WorkableBigPlan(
                            ref_id=big_plan.ref_id,
                            name=big_plan.name,
                            actionable_date=big_plan.actionable_date,
                        )
                    )
                else:
                    not_done_cnt += 1
                    not_done_projects.append(
                        ReportUseCase.WorkableBigPlan(
                            ref_id=big_plan.ref_id,
                            name=big_plan.name,
                            actionable_date=big_plan.actionable_date,
                        )
                    )
            elif big_plan.status.is_working and schedule.contains_timestamp(
                cast(Timestamp, big_plan.working_time)
            ):
                working_cnt += 1
            elif big_plan.status.is_accepted and schedule.contains_timestamp(
                cast(Timestamp, big_plan.accepted_time)
            ):
                accepted_cnt += 1

        return ReportUseCase.WorkableSummary(
            created_cnt=created_cnt,
            accepted_cnt=accepted_cnt,
            working_cnt=working_cnt,
            done_cnt=done_cnt,
            not_done_cnt=not_done_cnt,
            not_done_big_plans=not_done_projects,
            done_big_plans=done_projects,
        )
