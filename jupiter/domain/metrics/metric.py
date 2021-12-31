"""A metric."""
from dataclasses import dataclass
from typing import Optional

from jupiter.domain.metrics.metric_key import MetricKey
from jupiter.domain.metrics.metric_name import MetricName
from jupiter.domain.metrics.metric_unit import MetricUnit
from jupiter.domain.recurring_task_gen_params import RecurringTaskGenParams
from jupiter.framework.aggregate_root import AggregateRoot
from jupiter.framework.base.entity_id import BAD_REF_ID
from jupiter.framework.base.timestamp import Timestamp


@dataclass()
class Metric(AggregateRoot):
    """A metric."""

    @dataclass(frozen=True)
    class Created(AggregateRoot.Created):
        """Created event."""

    @dataclass(frozen=True)
    class Updated(AggregateRoot.Updated):
        """Updated event."""

    _key: MetricKey
    _name: MetricName
    _collection_params: Optional[RecurringTaskGenParams]
    _metric_unit: Optional[MetricUnit]

    @staticmethod
    def new_metric(
            key: MetricKey, name: MetricName, collection_params: Optional[RecurringTaskGenParams],
            metric_unit: Optional[MetricUnit], created_time: Timestamp) -> 'Metric':
        """Create a metric."""
        metric = Metric(
            _ref_id=BAD_REF_ID,
            _archived=False,
            _created_time=created_time,
            _archived_time=None,
            _last_modified_time=created_time,
            _events=[],
            _key=key,
            _name=name,
            _collection_params=collection_params,
            _metric_unit=metric_unit)
        metric.record_event(Metric.Created.make_event_from_frame_args(created_time))

        return metric

    def change_name(self, name: MetricName, modification_time: Timestamp) -> 'Metric':
        """Change the name of the metric."""
        if self._name == name:
            return self
        self._name = name
        self.record_event(Metric.Updated.make_event_from_frame_args(modification_time))
        return self

    def change_collection_params(
            self, collection_params: Optional[RecurringTaskGenParams], modification_time: Timestamp) -> 'Metric':
        """Change the collection period of the metric."""
        if self._collection_params == collection_params:
            return self
        self._collection_params = collection_params
        self.record_event(Metric.Updated.make_event_from_frame_args(modification_time))
        return self

    @property
    def key(self) -> MetricKey:
        """The key of the metric."""
        return self._key

    @property
    def name(self) -> MetricName:
        """The name of the metric."""
        return self._name

    @property
    def collection_params(self) -> Optional[RecurringTaskGenParams]:
        """The collection parameters of the metric."""
        return self._collection_params

    @property
    def metric_unit(self) -> Optional[MetricUnit]:
        """The metric unit of the metric."""
        return self._metric_unit
