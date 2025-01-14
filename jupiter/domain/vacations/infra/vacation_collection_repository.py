"""A repository for vacation collections."""
import abc

from jupiter.domain.vacations.vacation_collection import VacationCollection
from jupiter.framework.repository import TrunkEntityRepository, TrunkEntityNotFoundError


class VacationCollectionNotFoundError(TrunkEntityNotFoundError):
    """Error raised when a vacation collection is not found."""


class VacationCollectionRepository(TrunkEntityRepository[VacationCollection], abc.ABC):
    """A repository of vacation collections."""
