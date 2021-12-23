"""Framework level elements for entity events."""
import dataclasses
import inspect
import typing
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar, Dict

from pendulum import Date, DateTime

from framework.base.timestamp import Timestamp
from framework.json import JSONValueType
from framework.update_action import UpdateAction


@dataclass(frozen=True)
class Event:
    """The base class for all events."""

    timestamp: Timestamp

    def to_serializable_dict(self) -> JSONValueType:
        """Transform an event into a serialisation-ready dictionary."""
        def process_primitive(primitive: typing.Union[None, int, float, str, object], key: str) -> JSONValueType:
            if primitive is None:
                return primitive
            elif isinstance(primitive, int):
                return primitive
            elif isinstance(primitive, float):
                return primitive
            elif isinstance(primitive, str):
                return primitive
            elif isinstance(primitive, Date):
                return str(primitive)
            elif isinstance(primitive, DateTime):
                return str(primitive)
            elif isinstance(primitive, Enum):
                return process_primitive(primitive.value, key)
            elif isinstance(primitive, UpdateAction):
                return {
                    "should_change": primitive.should_change,
                    "value": process_primitive(primitive.value, key) if primitive.should_change else None
                }
            elif dataclasses.is_dataclass(primitive):
                return {k: process_primitive(v, k) for k, v in dataclasses.asdict(primitive).items()}
            elif isinstance(primitive, list):
                return [process_primitive(p, key) for p in primitive]
            elif isinstance(primitive, dict):
                return {k: process_primitive(v, k) for k, v in primitive.items()}
            else:
                raise Exception(f"Invalid type for event field {key} of type {primitive.__class__.__name__}")
        return process_primitive(self, "root")


EventType = TypeVar('EventType', bound='Event2')


@dataclass(frozen=True)
class Event2(Event):
    """An event for an aggregate root."""

    frame_args: Dict[str, object]

    @staticmethod
    def make_event_from_frame_args(
            event_type: typing.Type[EventType], timestamp: Timestamp, **kwargs: object) -> EventType:
        """Construct the data for an event from the arguments of the method which calls this one."""
        frame = inspect.currentframe()
        if frame is None:
            raise Exception("There's no recovery from stuff like this - part one")

        try:
            parent_frame = frame.f_back
            if parent_frame is None:
                raise Exception("There's no recovery from stuff like this - part two")

            try:
                args = inspect.getargvalues(parent_frame) # pylint: disable=deprecated-method
                frame_args = {}
                for arg_name in args.args:
                    frame_args[arg_name] = args.locals[arg_name]
                for kwarg_name, kwargs_value in kwargs.items():
                    frame_args[kwarg_name] = kwargs_value
                new_event = event_type(timestamp=timestamp, frame_args=frame_args)
                return new_event
            finally:
                del parent_frame
        finally:
            del frame