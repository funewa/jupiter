"""The command for reporting on progress."""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import groupby
from operator import itemgetter
from typing import Optional, Iterable, Final, Dict, List, cast, Tuple, DefaultDict

import pendulum
from nested_dataclasses import nested
from pendulum import UTC

from jupiter.domain import schedules
from jupiter.domain.big_plans.big_plan import BigPlan
from jupiter.domain.big_plans.big_plan_status import BigPlanStatus
from jupiter.domain.entity_name import EntityName
from jupiter.domain.inbox_tasks.inbox_task import InboxTask
from jupiter.domain.inbox_tasks.inbox_task_source import InboxTaskSource
from jupiter.domain.inbox_tasks.inbox_task_status import InboxTaskStatus
from jupiter.domain.metrics.metric import Metric
from jupiter.domain.metrics.metric_key import MetricKey
from jupiter.domain.projects.project import Project
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.domain.recurring_task_period import RecurringTaskPeriod
from jupiter.domain.recurring_task_type import RecurringTaskType
from jupiter.domain.recurring_tasks.recurring_task import RecurringTask
from jupiter.domain.schedules import Schedule
from jupiter.domain.storage_engine import StorageEngine
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.use_case import UseCase
from jupiter.utils.global_properties import GlobalProperties

LOGGER = logging.getLogger(__name__)


class ReportUseCase(UseCase['ReportUseCase.Args', 'ReportUseCase.Result']):
    """The command for reporting on progress."""

    @dataclass()
    class Args:
        """Args."""
        right_now: Timestamp
        filter_project_keys: Optional[Iterable[ProjectKey]]
        filter_sources: Optional[Iterable[InboxTaskSource]]
        filter_big_plan_ref_ids: Optional[Iterable[EntityId]]
        filter_recurring_task_ref_ids: Optional[Iterable[EntityId]]
        filter_metric_keys: Optional[Iterable[MetricKey]]
        filter_person_ref_ids: Optional[Iterable[EntityId]]
        period: RecurringTaskPeriod
        breakdown_period: Optional[RecurringTaskPeriod]

    @nested()
    @dataclass()
    class InboxTasksSummary:
        """A bigger summary for inbox tasks."""

        @nested()
        @dataclass()
        class NestedResult:
            """A result broken down by the various sources of inbox tasks."""
            total_cnt: int
            per_source_cnt: Dict[InboxTaskSource, int]

        created: NestedResult
        accepted: NestedResult
        working: NestedResult
        not_done: NestedResult
        done: NestedResult

    @nested()
    @dataclass()
    class WorkableSummary:
        """The reporting summary."""
        created_cnt: int
        accepted_cnt: int
        working_cnt: int
        not_done_cnt: int
        done_cnt: int
        not_done_projects: List[EntityName]
        done_projects: List[EntityName]

    @nested()
    @dataclass()
    class BigPlanSummary:
        """The report for a big plan."""
        created_cnt: int
        accepted_cnt: int
        working_cnt: int
        not_done_cnt: int
        not_done_ratio: float
        done_cnt: int
        done_ratio: float
        completed_ratio: float

    @nested()
    @dataclass()
    class RecurringTaskSummary:
        """The reporting summary."""
        created_cnt: int
        accepted_cnt: int
        working_cnt: int
        not_done_cnt: int
        not_done_ratio: float
        done_cnt: int
        done_ratio: float
        completed_ratio: float
        current_streak_size: int
        longest_streak_size: int
        zero_streak_size_histogram: Dict[int, int] = field(hash=False, compare=False, repr=False, default_factory=dict)
        one_streak_size_histogram: Dict[int, int] = field(hash=False, compare=False, repr=False, default_factory=dict)
        avg_done_total: float = field(hash=False, compare=False, repr=False, default=0)
        avg_done_last_period: Dict[RecurringTaskPeriod, float] = \
            field(hash=False, compare=False, repr=False, default_factory=dict)
        streak_plot: str = field(hash=False, compare=False, repr=False, default="")

    @nested()
    @dataclass()
    class PerProjectBreakdownItem:
        """The report for a particular project."""
        name: EntityName
        inbox_tasks_summary: 'ReportUseCase.InboxTasksSummary'
        big_plans_summary: 'ReportUseCase.WorkableSummary'

    @nested()
    @dataclass()
    class PerPeriodBreakdownItem:
        """The report for a particular time period."""
        name: EntityName
        inbox_tasks_summary: 'ReportUseCase.InboxTasksSummary'
        big_plans_summary: 'ReportUseCase.WorkableSummary'

    @nested()
    @dataclass()
    class PerBigPlanBreakdownItem:
        """The report for a particular big plan."""
        name: EntityName
        summary: 'ReportUseCase.BigPlanSummary'

    @nested()
    @dataclass()
    class PerRecurringTaskBreakdownItem:
        """The report for a particular recurring task."""
        name: EntityName
        the_type: RecurringTaskType
        summary: 'ReportUseCase.RecurringTaskSummary'

    @nested()
    @dataclass()
    class Result:
        """Result of the run report call."""
        global_inbox_tasks_summary: 'ReportUseCase.InboxTasksSummary'
        global_big_plans_summary: 'ReportUseCase.WorkableSummary'
        per_project_breakdown: List['ReportUseCase.PerProjectBreakdownItem']
        per_period_breakdown: Optional[List['ReportUseCase.PerPeriodBreakdownItem']]
        per_big_plan_breakdown: List['ReportUseCase.PerBigPlanBreakdownItem']
        per_recurring_task_breakdown: List['ReportUseCase.PerRecurringTaskBreakdownItem']

    _global_properties: Final[GlobalProperties]
    _storage_engine: Final[StorageEngine]

    def __init__(self, global_properties: GlobalProperties, storage_engine: StorageEngine) -> None:
        """Constructor."""
        self._global_properties = global_properties
        self._storage_engine = storage_engine

    def execute(self, args: Args) -> 'Result':
        """Execute the command."""
        today = args.right_now.value.date()
        with self._storage_engine.get_unit_of_work() as uow:
            projects = uow.project_repository.find_all(filter_keys=args.filter_project_keys)
            projects_by_ref_id: Dict[EntityId, Project] = {p.ref_id: p for p in projects}

            metrics = uow.metric_repository.find_all(allow_archived=True, filter_keys=args.filter_metric_keys)
            metrics_by_ref_id: Dict[EntityId, Metric] = {m.ref_id: m for m in metrics}

            persons = uow.person_repository.find_all(allow_archived=True, filter_ref_ids=args.filter_person_ref_ids)
            persons_by_ref_id = {p.ref_id: p for p in persons}

            schedule = schedules.get_schedule(
                args.period, EntityName("Helper"), args.right_now, self._global_properties.timezone,
                None, None, None, None, None, None)

            inbox_task_collections = uow.inbox_task_collection_repository.find_all(
                filter_project_ref_ids=[p.ref_id for p in projects])
            all_inbox_tasks = [
                it for it in uow.inbox_task_repository.find_all(
                    allow_archived=True,
                    filter_inbox_task_collection_ref_ids=[itc.ref_id for itc in inbox_task_collections],
                    filter_sources=args.filter_sources)
                # (source is BIG_PLAN and (need to filter then (big_plan_ref_id in filter))
                if it.source is InboxTaskSource.USER
                or (it.source is InboxTaskSource.BIG_PLAN and
                    (not (args.filter_big_plan_ref_ids is not None) or
                     (it.big_plan_ref_id is not None and it.big_plan_ref_id in args.filter_big_plan_ref_ids)))
                or (it.source is InboxTaskSource.RECURRING_TASK and
                    (not (args.filter_recurring_task_ref_ids is not None) or
                     (it.recurring_task_ref_id is not None
                      and it.recurring_task_ref_id in args.filter_recurring_task_ref_ids)))
                or (it.source is InboxTaskSource.METRIC and
                    (not (args.filter_metric_keys is not None) or it.metric_ref_id in metrics_by_ref_id))
                or ((it.source is InboxTaskSource.PERSON_CATCH_UP or it.source is InboxTaskSource.PERSON_BIRTHDAY) and
                    (not (args.filter_person_ref_ids is not None) or it.person_ref_id in persons_by_ref_id))]

            big_plan_collections = \
                uow.big_plan_collection_repository.find_all(
                    filter_project_ref_ids=[p.ref_id for p in projects])
            all_big_plans = uow.big_plan_repository.find_all(
                allow_archived=True, filter_ref_ids=args.filter_big_plan_ref_ids,
                filter_big_plan_collection_ref_ids=[bpc.ref_id for bpc in big_plan_collections])
            big_plans_by_ref_id: Dict[EntityId, BigPlan] = {bp.ref_id: bp for bp in all_big_plans}

            recurring_task_collections = \
                uow.recurring_task_collection_repository.find_all(
                    filter_project_ref_ids=[p.ref_id for p in projects])
            all_recurring_tasks = uow.recurring_task_repository.find_all(
                allow_archived=True, filter_ref_ids=args.filter_recurring_task_ref_ids,
                filter_recurring_task_collection_ref_ids=[rtc.ref_id for rtc in recurring_task_collections])
            all_recurring_tasks_by_ref_id: Dict[EntityId, RecurringTask] = {rt.ref_id: rt for rt in all_recurring_tasks}

        global_inbox_tasks_summary = self._run_report_for_inbox_tasks(schedule, all_inbox_tasks)
        global_big_plans_summary = self._run_report_for_big_plan(schedule, all_big_plans)

        # Build per project breakdown

        # all_inbox_tasks.groupBy(it -> it.project.name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_project_inbox_tasks_summary = {
            k: self._run_report_for_inbox_tasks(schedule, (vx[1] for vx in v)) for (k, v) in
            groupby(sorted(
                [(projects_by_ref_id[it.project_ref_id].name, it) for it in all_inbox_tasks],
                key=itemgetter(0)),
                    key=itemgetter(0))}
        # all_big_plans.groupBy(it -> it.project..name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_project_big_plans_summary = {
            k: self._run_report_for_big_plan(schedule, (vx[1] for vx in v)) for (k, v) in
            groupby(sorted(
                [(projects_by_ref_id[bp.project_ref_id].name, bp) for bp in all_big_plans],
                key=itemgetter(0)),
                    key=itemgetter(0))}
        per_project_breakdown = [
            ReportUseCase.PerProjectBreakdownItem(
                name=s,
                inbox_tasks_summary=v,
                big_plans_summary=
                per_project_big_plans_summary.get(s, ReportUseCase.WorkableSummary(0, 0, 0, 0, 0, [], [])))
            for (s, v) in per_project_inbox_tasks_summary.items()]

        # Build per period breakdown
        per_period_breakdown = None
        if args.breakdown_period:
            all_schedules = {}
            curr_date = schedule.first_day.start_of_day()
            end_date = schedule.end_day.end_of_day()
            while curr_date < end_date and curr_date <= today:
                curr_date_as_time = \
                    Timestamp(pendulum.DateTime(curr_date.year, curr_date.month, curr_date.day, tzinfo=UTC))
                phase_schedule = schedules.get_schedule(
                    args.breakdown_period, EntityName("Sub-period"), curr_date_as_time,
                    self._global_properties.timezone, None, None, None, None, None, None)
                all_schedules[phase_schedule.full_name] = phase_schedule
                curr_date = curr_date.next_day()

            per_period_inbox_tasks_summary = {
                k: self._run_report_for_inbox_tasks(v, all_inbox_tasks) for (k, v) in all_schedules.items()}
            per_period_big_plans_summary = {
                k: self._run_report_for_big_plan(v, all_big_plans) for (k, v) in all_schedules.items()}
            per_period_breakdown = [
                ReportUseCase.PerPeriodBreakdownItem(
                    name=k,
                    inbox_tasks_summary=v,
                    big_plans_summary=
                    per_period_big_plans_summary.get(k, ReportUseCase.WorkableSummary(0, 0, 0, 0, 0, [], [])))
                for (k, v) in per_period_inbox_tasks_summary.items()]

        # Build per big plan breakdown

        # all_inbox_tasks.groupBy(it -> it.bigPlan.name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_big_plan_breakdown = [
            ReportUseCase.PerBigPlanBreakdownItem(
                k, self._run_report_for_inbox_tasks_for_big_plan(schedule, (vx[1] for vx in v)))
            for (k, v) in
            groupby(sorted(
                [(big_plans_by_ref_id[it.big_plan_ref_id].name, it) for it in all_inbox_tasks if it.big_plan_ref_id],
                key=itemgetter(0)),
                    key=itemgetter(0))]

        # Build per recurring task breakdown

        # all_inbox_tasks.groupBy(it -> it.recurringTask.name).map((k, v) -> (k, run_report_for_group(v))).asDict()
        per_recurring_task_breakdown = [
            ReportUseCase.PerRecurringTaskBreakdownItem(
                name=all_recurring_tasks_by_ref_id[k].name,
                the_type=all_recurring_tasks_by_ref_id[k].the_type,
                summary=self._run_report_for_inbox_for_recurring_tasks(
                    all_recurring_tasks_by_ref_id[k].period, args.right_now, schedule, [vx[1] for vx in v]))
            for (k, v) in
            groupby(sorted(
                [(it.recurring_task_ref_id, it)
                 for it in all_inbox_tasks if it.recurring_task_ref_id],
                key=itemgetter(0)),
                    key=itemgetter(0))]

        return ReportUseCase.Result(
            global_inbox_tasks_summary=global_inbox_tasks_summary,
            global_big_plans_summary=global_big_plans_summary,
            per_project_breakdown=per_project_breakdown,
            per_period_breakdown=per_period_breakdown,
            per_big_plan_breakdown=per_big_plan_breakdown,
            per_recurring_task_breakdown=per_recurring_task_breakdown)

    @staticmethod
    def _run_report_for_inbox_tasks(schedule: Schedule, inbox_tasks: Iterable[InboxTask]) -> 'InboxTasksSummary':
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
                LOGGER.error(inbox_task)

            if inbox_task.status.is_completed \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.completed_time)):
                if inbox_task.status == InboxTaskStatus.DONE:
                    done_cnt_total += 1
                    done_per_source_cnt[inbox_task.source] += 1
                else:
                    not_done_cnt_total += 1
                    not_done_per_source_cnt[inbox_task.source] += 1
            elif inbox_task.status.is_working \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.working_time)):
                working_cnt_total += 1
                working_per_source_cnt[inbox_task.source] += 1
            elif inbox_task.status.is_accepted \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.accepted_time)):
                accepted_cnt_total += 1
                accepted_per_source_cnt[inbox_task.source] += 1

        return ReportUseCase.InboxTasksSummary(
            created=ReportUseCase.InboxTasksSummary.NestedResult(
                total_cnt=created_cnt_total,
                per_source_cnt=created_per_source_cnt),
            accepted=ReportUseCase.InboxTasksSummary.NestedResult(
                total_cnt=accepted_cnt_total,
                per_source_cnt=accepted_per_source_cnt),
            working=ReportUseCase.InboxTasksSummary.NestedResult(
                total_cnt=working_cnt_total,
                per_source_cnt=working_per_source_cnt),
            not_done=ReportUseCase.InboxTasksSummary.NestedResult(
                total_cnt=not_done_cnt_total,
                per_source_cnt=not_done_per_source_cnt),
            done=ReportUseCase.InboxTasksSummary.NestedResult(
                total_cnt=done_cnt_total,
                per_source_cnt=done_per_source_cnt))

    @staticmethod
    def _run_report_for_inbox_tasks_for_big_plan(
            schedule: Schedule, inbox_tasks: Iterable[InboxTask]) -> 'BigPlanSummary':
        created_cnt = 0
        accepted_cnt = 0
        working_cnt = 0
        done_cnt = 0
        not_done_cnt = 0

        for inbox_task in inbox_tasks:
            if schedule.contains_timestamp(inbox_task.created_time):
                created_cnt += 1

            if inbox_task.status.is_completed \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.completed_time)):
                if inbox_task.status == InboxTaskStatus.DONE:
                    done_cnt += 1
                else:
                    not_done_cnt += 1
            elif inbox_task.status.is_working \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.working_time)):
                working_cnt += 1
            elif inbox_task.status.is_accepted \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.accepted_time)):
                accepted_cnt += 1

        return ReportUseCase.BigPlanSummary(
            created_cnt=created_cnt,
            accepted_cnt=accepted_cnt,
            working_cnt=working_cnt,
            not_done_cnt=not_done_cnt,
            not_done_ratio=not_done_cnt / float(created_cnt) if created_cnt > 0 else 0.0,
            done_cnt=done_cnt,
            done_ratio=done_cnt / float(created_cnt) if created_cnt > 0 else 0,
            completed_ratio=(done_cnt + not_done_cnt) / float(created_cnt) if created_cnt > 0 else 0.0)

    def _run_report_for_inbox_for_recurring_tasks(
            self, recurring_task_period: RecurringTaskPeriod, right_now: Timestamp, schedule: Schedule,
            inbox_tasks: List[InboxTask]) -> 'RecurringTaskSummary':

        def _build_bigger_periods_and_schedules() -> List[Tuple[RecurringTaskPeriod, Schedule]]:
            the_bigger_periods_and_schedules = []
            the_current_period = recurring_task_period
            the_bigger_period = ReportUseCase._one_bigger_than_period(the_current_period)

            while the_current_period != the_bigger_period:
                the_bigger_schedule = schedules.get_schedule(
                    the_bigger_period, EntityName("Helper"), right_now, self._global_properties.timezone,
                    None, None, None, None, None, None)

                the_bigger_periods_and_schedules.append((the_bigger_period, the_bigger_schedule))
                the_current_period = the_bigger_period
                the_bigger_period = ReportUseCase._one_bigger_than_period(the_current_period)

            return the_bigger_periods_and_schedules

        created_cnt = 0
        accepted_cnt = 0
        working_cnt = 0
        done_cnt = 0
        not_done_cnt = 0

        for inbox_task in inbox_tasks:
            if schedule.contains_timestamp(inbox_task.created_time):
                created_cnt += 1

            if inbox_task.status.is_completed \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.completed_time)):
                if inbox_task.status == InboxTaskStatus.DONE:
                    done_cnt += 1
                else:
                    not_done_cnt += 1
            elif inbox_task.status.is_working \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.working_time)):
                working_cnt += 1
            elif inbox_task.status.is_accepted \
                    and schedule.contains_timestamp(cast(Timestamp, inbox_task.accepted_time)):
                accepted_cnt += 1

        bigger_periods_and_schedules = _build_bigger_periods_and_schedules()

        longest_streak_size = 0
        zero_current_streak_size = 0
        zero_streak_size_histogram: Dict[int, int] = {}
        one_current_streak_size = 0
        one_streak_size_histogram: Dict[int, int] = {}
        sorted_inbox_tasks = sorted(
            (it for it in inbox_tasks if schedule.contains_timestamp(it.created_time)), key=lambda it: it.created_time)
        used_skip_once = False
        done_cnt_with_one_streak = 0
        done_cnt_with_one_streak_per_last_period: Dict[RecurringTaskPeriod, int] = \
            {bp: 0 for bp, _ in bigger_periods_and_schedules}
        total_cnt_per_last_period: Dict[RecurringTaskPeriod, int] = \
            {bp: 0 for bp, _ in bigger_periods_and_schedules}
        streak_plot = []

        for inbox_task_idx, inbox_task in enumerate(sorted_inbox_tasks):
            for bigger_period, bigger_period_schedule in bigger_periods_and_schedules:
                if inbox_task.due_date is None:
                    LOGGER.warning(f'There is an inbox task here without a due date "{inbox_task.name}"')
                    continue
                if bigger_period_schedule.contains_adate(inbox_task.due_date):
                    total_cnt_per_last_period[bigger_period] += 1
            if inbox_task.status == InboxTaskStatus.DONE:
                zero_current_streak_size += 1
                one_current_streak_size += 1
                done_cnt_with_one_streak += 1
                for bigger_period, bigger_period_schedule in bigger_periods_and_schedules:
                    if inbox_task.due_date is not None and bigger_period_schedule.contains_adate(inbox_task.due_date):
                        done_cnt_with_one_streak_per_last_period[bigger_period] += 1
                streak_plot.append("X")
            else:
                longest_streak_size = max(zero_current_streak_size, longest_streak_size)
                if zero_current_streak_size > 0:
                    zero_streak_size_histogram[zero_current_streak_size] = \
                        zero_streak_size_histogram.get(zero_current_streak_size, 0) + 1
                zero_current_streak_size = 0

                if inbox_task_idx != 0 \
                        and inbox_task_idx != len(sorted_inbox_tasks) - 1 \
                        and sorted_inbox_tasks[inbox_task_idx - 1].status == InboxTaskStatus.DONE \
                        and sorted_inbox_tasks[inbox_task_idx + 1].status == InboxTaskStatus.DONE \
                        and not used_skip_once:
                    one_current_streak_size += 1
                    used_skip_once = True
                    done_cnt_with_one_streak += 1
                    for bigger_period, bigger_period_schedule in bigger_periods_and_schedules:
                        if inbox_task.due_date is not None and \
                                bigger_period_schedule.contains_adate(inbox_task.due_date):
                            done_cnt_with_one_streak_per_last_period[bigger_period] += 1
                    streak_plot.append("x")
                else:
                    if one_current_streak_size > 0:
                        one_streak_size_histogram[one_current_streak_size] = \
                            one_streak_size_histogram.get(one_current_streak_size, 0) + 1
                    one_current_streak_size = 0
                    used_skip_once = False
                    streak_plot.append("." if inbox_task_idx < (len(sorted_inbox_tasks) - 1) else "?")
        longest_streak_size = max(zero_current_streak_size, longest_streak_size)
        if zero_current_streak_size > 0:
            zero_streak_size_histogram[zero_current_streak_size] = \
                zero_streak_size_histogram.get(zero_current_streak_size, 0) + 1
        if one_current_streak_size > 0:
            one_streak_size_histogram[one_current_streak_size] = \
                one_streak_size_histogram.get(one_current_streak_size, 0) + 1

        return ReportUseCase.RecurringTaskSummary(
            created_cnt=created_cnt,
            accepted_cnt=accepted_cnt,
            working_cnt=working_cnt,
            not_done_cnt=not_done_cnt,
            not_done_ratio=not_done_cnt / float(created_cnt) if created_cnt > 0 else 0.0,
            done_cnt=done_cnt,
            done_ratio=done_cnt / float(created_cnt) if created_cnt > 0 else 0.0,
            completed_ratio=(done_cnt + not_done_cnt) / float(created_cnt) if created_cnt > 0 else 0.0,
            current_streak_size=zero_current_streak_size,
            longest_streak_size=longest_streak_size,
            zero_streak_size_histogram=zero_streak_size_histogram,
            one_streak_size_histogram=one_streak_size_histogram,
            avg_done_total=float(done_cnt_with_one_streak) / len(sorted_inbox_tasks)
            if len(sorted_inbox_tasks) > 0 else 0,
            avg_done_last_period={
                bigger_period: float(done_cnt_with_one_streak_per_last_period[bigger_period]) /
                               total_cnt_per_last_period[bigger_period]
                               if total_cnt_per_last_period[bigger_period] else 0
                for bigger_period, _ in bigger_periods_and_schedules},
            streak_plot="".join(streak_plot))

    @staticmethod
    def _run_report_for_big_plan(schedule: Schedule, big_plans: Iterable[BigPlan]) -> 'WorkableSummary':
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

            if big_plan.status.is_completed and schedule.contains_timestamp(cast(Timestamp, big_plan.completed_time)):
                if big_plan.status == BigPlanStatus.DONE:
                    done_cnt += 1
                    done_projects.append(big_plan.name)
                else:
                    not_done_cnt += 1
                    not_done_projects.append(big_plan.name)
            elif big_plan.status.is_working and schedule.contains_timestamp(cast(Timestamp, big_plan.working_time)):
                working_cnt += 1
            elif big_plan.status.is_accepted and schedule.contains_timestamp(cast(Timestamp, big_plan.accepted_time)):
                accepted_cnt += 1

        return ReportUseCase.WorkableSummary(
            created_cnt=created_cnt,
            accepted_cnt=accepted_cnt,
            working_cnt=working_cnt,
            done_cnt=done_cnt,
            not_done_cnt=not_done_cnt,
            not_done_projects=not_done_projects,
            done_projects=done_projects)

    @staticmethod
    def _one_bigger_than_period(period: RecurringTaskPeriod) -> RecurringTaskPeriod:
        if period == RecurringTaskPeriod.YEARLY:
            return RecurringTaskPeriod.YEARLY
        elif period == RecurringTaskPeriod.QUARTERLY:
            return RecurringTaskPeriod.YEARLY
        elif period == RecurringTaskPeriod.MONTHLY:
            return RecurringTaskPeriod.QUARTERLY
        elif period == RecurringTaskPeriod.WEEKLY:
            return RecurringTaskPeriod.MONTHLY
        elif period == RecurringTaskPeriod.DAILY:
            return RecurringTaskPeriod.WEEKLY
        else:
            raise RuntimeError(f"Invalid period {period}")