"""Repository for vacations."""

from dataclasses import dataclass
import logging
import typing
from pathlib import Path
from types import TracebackType
from typing import ClassVar, List, Iterable, Optional

import pendulum

from models.basic import EntityId
from repository.common import RepositoryError
from utils.storage import StructuredCollectionStorage, JSONDictType

LOGGER = logging.getLogger(__name__)


@typing.final
@dataclass()
class Vacation:
    """A vacation."""

    ref_id: EntityId
    archived: bool
    name: str
    start_date: pendulum.DateTime
    end_date: pendulum.DateTime

    def is_in_vacation(self, start_date: pendulum.DateTime, end_date: pendulum.DateTime) -> bool:
        """Checks whether a particular date range is in this vacation."""
        return typing.cast(bool, self.start_date <= start_date) and typing.cast(bool, end_date <= self.end_date)


@typing.final
class VacationsRepository:
    """A repository for vacations."""

    _VACATIONS_FILE_PATH: ClassVar[Path] = Path("/data/vacations.yaml")

    _structured_storage: StructuredCollectionStorage[Vacation]

    def __init__(self) -> None:
        """Constructor."""
        self._structured_storage = StructuredCollectionStorage(self._VACATIONS_FILE_PATH, self)

    def __enter__(self) -> 'VacationsRepository':
        """Enter context."""
        self._structured_storage.initialize()
        return self

    def __exit__(
            self, exc_type: Optional[typing.Type[BaseException]], _exc_val: Optional[BaseException],
            _exc_tb: Optional[TracebackType]) -> None:
        """Exit context."""
        if exc_type is not None:
            return
        self._structured_storage.exit_save()

    def create_vacation(
            self, archived: bool, name: str, start_date: pendulum.DateTime, end_date: pendulum.DateTime) -> Vacation:
        """Create a vacation."""
        vacations_next_idx, vacations = self._structured_storage.load()

        new_vacation = Vacation(
            ref_id=EntityId(str(vacations_next_idx)),
            archived=archived,
            name=name,
            start_date=start_date,
            end_date=end_date)
        vacations_next_idx += 1
        vacations.append(new_vacation)
        vacations.sort(key=lambda v: v.start_date)

        self._structured_storage.save((vacations_next_idx, vacations))

        return new_vacation

    def archive_vacation(self, ref_id: EntityId) -> Vacation:
        """Remove a particular vacation."""
        vacations_next_idx, vacations = self._structured_storage.load()

        for vacation in vacations:
            if vacation.ref_id == ref_id:
                vacation.archived = True
                self._structured_storage.save((vacations_next_idx, vacations))
                return vacation

        raise RepositoryError(f"Vacation with id='{ref_id}' does not exist")

    def load_all_vacations(self, filter_archived: bool = True) -> Iterable[Vacation]:
        """Retrieve all the vacations defined."""
        _, vacations = self._structured_storage.load()
        return [v for v in vacations if (filter_archived is False or v.archived is False)]

    def load_vacation(self, ref_id: EntityId) -> Vacation:
        """Retrieve a particular vacation by its id."""
        _, vacations = self._structured_storage.load()
        found_vacation = self._find_vacation_by_id(ref_id, vacations)
        if not found_vacation:
            raise RepositoryError(f"Vacation with id={ref_id} does not exist")
        if found_vacation.archived:
            raise RepositoryError(f"Vacation with id={ref_id} is archived")
        return found_vacation

    def save_vacation(self, new_vacation: Vacation) -> Vacation:
        """Store a particular vacation with all new properties."""
        vacations_next_idx, vacations = self._structured_storage.load()
        if not self._find_vacation_by_id(new_vacation.ref_id, vacations):
            raise RepositoryError(f"Vacation with id={new_vacation.ref_id} does not exist")
        new_vacations = [(v if v.ref_id != new_vacation.ref_id else new_vacation) for v in vacations]
        self._structured_storage.save((vacations_next_idx, new_vacations))

        return new_vacation

    def hard_remove_vacation(self, ref_id: EntityId) -> Vacation:
        """Hard remove a vacation."""
        vacations_next_idx, vacations = self._structured_storage.load()
        found_vacations = self._find_vacation_by_id(ref_id, vacations)
        if not found_vacations:
            raise RepositoryError(f"Vacation with id='{ref_id}' does not exist")
        new_vacations = [it for it in vacations if it.ref_id != ref_id]
        self._structured_storage.save((vacations_next_idx, new_vacations))
        return found_vacations

    @staticmethod
    def _find_vacation_by_id(ref_id: EntityId, vacations: List[Vacation]) -> Optional[Vacation]:
        try:
            return next(v for v in vacations if v.ref_id == ref_id)
        except StopIteration:
            return None

    @staticmethod
    def storage_schema() -> JSONDictType:
        """The schema for the data."""
        return {
            "type": "object",
            "properties": {
                "ref_id": {"type": "string"},
                "archived": {"type": "boolean"},
                "name": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"}
            }
        }

    @staticmethod
    def storage_to_live(storage_form: JSONDictType) -> Vacation:
        """Transform the data reconstructed from basic storage into something useful for the live system."""
        return Vacation(
            ref_id=EntityId(typing.cast(str, storage_form["ref_id"])),
            archived=typing.cast(bool, storage_form["archived"]),
            name=typing.cast(str, storage_form["name"]),
            start_date=pendulum.parse(typing.cast(str, storage_form["start_date"])),
            end_date=pendulum.parse(typing.cast(str, storage_form["end_date"])))

    @staticmethod
    def live_to_storage(live_form: Vacation) -> JSONDictType:
        """Transform the live system data to something suitable for basic storage."""
        return {
            "ref_id": live_form.ref_id,
            "archived": live_form.archived,
            "name": live_form.name,
            "start_date": live_form.start_date.to_datetime_string(),
            "end_date": live_form.end_date.to_datetime_string()
        }
