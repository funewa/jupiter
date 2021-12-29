"""Repository for vacations."""
import logging
import typing
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Iterable, Optional, Final

from jupiter.domain.adate import ADate
from jupiter.domain.entity_name import EntityName
from jupiter.domain.vacations.infra.vacation_repository import VacationRepository, VacationNotFoundError
from jupiter.domain.vacations.vacation import Vacation
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.json import JSONDictType
from jupiter.repository.yaml.infra.storage import BaseEntityRow, EntitiesStorage, In, StorageEntityNotFoundError
from jupiter.utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


@dataclass()
class _VacationRow(BaseEntityRow):
    """A vacation."""
    name: EntityName
    start_date: ADate
    end_date: ADate


class YamlVacationRepository(VacationRepository):
    """A repository for vacations."""

    _VACATIONS_FILE_PATH: ClassVar[Path] = Path("./vacations")
    _VACATIONS_NUM_SHARDS: ClassVar[int] = 1

    _storage: Final[EntitiesStorage[_VacationRow]]

    def __init__(self, time_provider: TimeProvider) -> None:
        """Constructor."""
        self._storage = EntitiesStorage[_VacationRow](
            self._VACATIONS_FILE_PATH, self._VACATIONS_NUM_SHARDS, time_provider, self)

    def __enter__(self) -> 'YamlVacationRepository':
        """Enter context."""
        self._storage.initialize()
        return self

    def __exit__(
            self, exc_type: Optional[typing.Type[BaseException]], _exc_val: Optional[BaseException],
            _exc_tb: Optional[TracebackType]) -> None:
        """Exit context."""
        if exc_type is not None:
            return

    def initialize(self) -> None:
        """Initialise the repo."""
        self._storage.initialize()

    def create(self, vacation: Vacation) -> Vacation:
        """Create a vacation."""
        new_vacation_row = self._storage.create(_VacationRow(
            archived=vacation.archived,
            name=vacation.name,
            start_date=vacation.start_date,
            end_date=vacation.end_date))
        vacation.assign_ref_id(new_vacation_row.ref_id)
        return vacation

    def save(self, vacation: Vacation) -> Vacation:
        """Save a vacation - it should already exist."""
        try:
            vacation_row = self._entity_to_row(vacation)
            vacation_row = self._storage.update(vacation_row)
            return self._row_to_entity(vacation_row)
        except StorageEntityNotFoundError as err:
            raise VacationNotFoundError(f"Vacation with id {vacation.ref_id} does not exist") from err

    def load_by_id(self, ref_id: EntityId, allow_archived: bool = False) -> Vacation:
        """Find a vacation by id."""
        try:
            return self._row_to_entity(self._storage.load(ref_id, allow_archived=allow_archived))
        except StorageEntityNotFoundError as err:
            raise VacationNotFoundError(f"Vacation with id {ref_id} does not exist") from err

    def find_all(
            self,
            allow_archived: bool = False,
            filter_ref_ids: Optional[Iterable[EntityId]] = None) -> typing.List[Vacation]:
        """Find all vacations matching some criteria."""
        return [self._row_to_entity(vr)
                for vr in self._storage.find_all(
                    allow_archived=allow_archived,
                    ref_id=In(*filter_ref_ids) if filter_ref_ids else None)]

    def remove(self, ref_id: EntityId) -> None:
        """Hard remove a vacation - an irreversible operation."""
        try:
            self._storage.remove(ref_id=ref_id)
        except StorageEntityNotFoundError as err:
            raise VacationNotFoundError(f"Vacation with id {ref_id} does not exist") from err

    @staticmethod
    def storage_schema() -> JSONDictType:
        """The schema for the data."""
        return {
            "name": {"type": "string"},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
        }

    @staticmethod
    def storage_to_live(storage_form: JSONDictType) -> _VacationRow:
        """Transform the data reconstructed from basic storage into something useful for the live system."""
        return _VacationRow(
            archived=typing.cast(bool, storage_form["archived"]),
            name=EntityName.from_raw(typing.cast(str, storage_form["name"])),
            start_date=ADate.from_str(typing.cast(str, storage_form["start_date"])),
            end_date=ADate.from_str(typing.cast(str, storage_form["end_date"])))

    @staticmethod
    def live_to_storage(live_form: _VacationRow) -> JSONDictType:
        """Transform the live system data to something suitable for basic storage."""
        return {
            "name": str(live_form.name),
            "start_date": str(live_form.start_date),
            "end_date": str(live_form.end_date)
        }

    @staticmethod
    def _entity_to_row(vacation: Vacation) -> _VacationRow:
        vacation_row = _VacationRow(
            archived=vacation.archived,
            name=vacation.name,
            start_date=vacation.start_date,
            end_date=vacation.end_date)
        vacation_row.ref_id = vacation.ref_id
        vacation_row.created_time = vacation.created_time
        vacation_row.archived_time = vacation.archived_time
        vacation_row.last_modified_time = vacation.last_modified_time
        return vacation_row

    @staticmethod
    def _row_to_entity(row: _VacationRow) -> Vacation:
        return Vacation(
            _ref_id=row.ref_id,
            _archived=row.archived,
            _created_time=row.created_time,
            _archived_time=row.archived_time,
            _last_modified_time=row.last_modified_time,
            _events=[],
            _name=row.name,
            _start_date=row.start_date,
            _end_date=row.end_date)