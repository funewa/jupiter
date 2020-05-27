"""The controller for vacations."""
from typing import Final, Iterable

import pendulum

from models.basic import EntityId, SyncPrefer
from repository.vacations import Vacation
from service.vacations import VacationsService


class VacationsController:
    """The controller for vacations."""

    _vacations_service: Final[VacationsService]

    def __init__(self, vacations_service: VacationsService):
        """Constructor."""
        self._vacations_service = vacations_service

    def create_vacation(self, name: str, start_date: pendulum.DateTime, end_date: pendulum.DateTime) -> Vacation:
        """Create a vacation."""
        return self._vacations_service.create_vacation(name, start_date, end_date)

    def archive_vacation(self, ref_id: EntityId) -> None:
        """Archive a vacation."""
        self._vacations_service.archive_vacation(ref_id)

    def set_vacation_name(self, ref_id: EntityId, name: str) -> None:
        """Change the vacation name."""
        self._vacations_service.set_vacation_name(ref_id, name)

    def set_vacation_start_date(self, ref_id: EntityId, start_date: pendulum.DateTime) -> None:
        """Change the vacation start date."""
        self._vacations_service.set_vacation_start_date(ref_id, start_date)

    def set_vacation_end_date(self, ref_id: EntityId, end_date: pendulum.DateTime) -> None:
        """Change the vacation end date."""
        self._vacations_service.set_vacation_end_date(ref_id, end_date)

    def load_all_vacations(self, show_archived: bool = False) -> Iterable[Vacation]:
        """Retrieve all vacations."""
        return self._vacations_service.load_all_vacations(show_archived)

    def vacations_sync(self, sync_prefer: SyncPrefer) -> None:
        """Synchronise vacations between Notion and local."""
        self._vacations_service.vacations_sync(sync_prefer)