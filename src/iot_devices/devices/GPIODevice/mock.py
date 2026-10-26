"""A minimal in-process mock of the libgpiod v2 Python API.

The real :mod:`gpiod` bindings talk to the kernel over a character device,
which is unavailable (and undesirable) in tests and on machines without GPIO
hardware.  This module re-implements just the small subset of the API that
the GPIO devices rely on.  Pins named like ``MOCK1`` are served by a mock
chip whose state is shared process-wide, keyed by chip path, so that mock
pins behave like real ones.

The helpers at the bottom of the module let a test inspect or drive a mock
line directly, and simulate a line that is already claimed by a foreign
consumer such as the kernel.
"""

from __future__ import annotations

import errno
import posixpath
import threading
import time
from dataclasses import dataclass, field
from datetime import timedelta

from gpiod.edge_event import EdgeEvent
from gpiod.exception import RequestReleasedError
from gpiod.line import Bias, Direction, Edge, Value
from gpiod.line_settings import LineSettings

MOCK_CHIP_PATH = "mock"
"""Chip path used by pins named like ``MOCK1``."""

DEFAULT_NUM_LINES = 64
"""Number of lines exposed by an auto-created mock chip."""


@dataclass
class MockLine:
    """Mutable state for a single mock line.

    ``physical`` is the electrical level, while :meth:`logical_value`
    applies the ``active_low`` inversion the way libgpiod does.
    """

    offset: int
    name: str
    used: bool = False
    consumer: str = ""
    direction: Direction = Direction.AS_IS
    active_low: bool = False
    bias: Bias = Bias.AS_IS
    debounce_period: timedelta = timedelta()
    physical: bool = False

    def logical_value(self) -> Value:
        if self.physical != self.active_low:
            return Value.ACTIVE
        return Value.INACTIVE

    def apply_settings(self, settings: LineSettings) -> None:
        """Apply a request's line settings, seeding physical state."""
        self.direction = settings.direction
        self.active_low = settings.active_low
        self.bias = settings.bias
        self.debounce_period = settings.debounce_period
        if settings.direction == Direction.OUTPUT:
            active = settings.output_value == Value.ACTIVE
            self.physical = active != self.active_low
        elif settings.direction == Direction.INPUT:
            if settings.bias == Bias.PULL_UP:
                self.physical = True
            elif settings.bias == Bias.PULL_DOWN:
                self.physical = False

    def reset(self) -> None:
        """Return the line to its idle, unrequested state."""
        self.used = False
        self.consumer = ""
        self.direction = Direction.AS_IS
        self.active_low = False
        self.bias = Bias.AS_IS
        self.debounce_period = timedelta()
        self.physical = False


@dataclass(frozen=True)
class MockChipInfo:
    name: str
    label: str
    num_lines: int


@dataclass(frozen=True)
class MockLineInfo:
    offset: int
    name: str
    used: bool
    consumer: str
    direction: Direction
    active_low: bool
    bias: Bias
    edge_detection: Edge
    debounce_period: timedelta


@dataclass(frozen=True)
class MockEdgeEvent:
    event_type: EdgeEvent.Type
    line_offset: int
    timestamp_ns: int


@dataclass
class MockChipState:
    """Shared state for one mock chip, keyed by path in ``_chips``."""

    path: str
    label: str
    lines: dict[int, MockLine]
    condition: threading.Condition = field(default_factory=threading.Condition)
    events: list[tuple[int, EdgeEvent.Type]] = field(default_factory=list)


_registry_lock = threading.RLock()
_chips: dict[str, MockChipState] = {}


def _default_line_name(path: str, offset: int) -> str:
    """Line names the mock reports for lines the caller did not name.

    The synthetic mock chip uses ``MOCKn``; chips standing in for real
    hardware default to unnamed, like most real GPIO lines.
    """
    if path == MOCK_CHIP_PATH:
        return f"MOCK{offset}"
    return ""


def _get_chip(path: str) -> MockChipState:
    with _registry_lock:
        state = _chips.get(path)
        if state is None:
            state = _create_chip(path, DEFAULT_NUM_LINES, "mock", {})
        return state


def _create_chip(
    path: str,
    num_lines: int,
    label: str,
    line_names: dict[int, str],
) -> MockChipState:
    if num_lines < 1:
        raise ValueError("A mock chip must expose at least one line")
    lines = {
        offset: MockLine(
            offset=offset,
            name=line_names.get(offset, _default_line_name(path, offset)),
        )
        for offset in range(num_lines)
    }
    state = MockChipState(path=path, label=label, lines=lines)
    _chips[path] = state
    return state


class MockChip:
    """Mock stand-in for :class:`gpiod.Chip`."""

    def __init__(self, path: str):
        self._path = path
        self._state = _get_chip(path)
        self._closed = False

    def __enter__(self) -> MockChip:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._closed = True

    @property
    def path(self) -> str:
        return self._path

    def get_info(self) -> MockChipInfo:
        return MockChipInfo(
            name=posixpath.basename(self._path),
            label=self._state.label,
            num_lines=len(self._state.lines),
        )

    def line_offset_from_id(self, id: str | int) -> int:
        if isinstance(id, int):
            offset = id
        else:
            name = id
            for line in self._state.lines.values():
                if line.name == name:
                    return line.offset
            try:
                offset = int(name)
            except ValueError:
                raise OSError(errno.ENOENT, f"No line named {name!r}") from None
        if offset not in self._state.lines:
            raise ValueError("line offset out of range")
        return offset

    def get_line_info(self, line: str | int) -> MockLineInfo:
        offset = self.line_offset_from_id(line)
        mock_line = self._state.lines[offset]
        return MockLineInfo(
            offset=mock_line.offset,
            name=mock_line.name,
            used=mock_line.used,
            consumer=mock_line.consumer,
            direction=mock_line.direction,
            active_low=mock_line.active_low,
            bias=mock_line.bias,
            edge_detection=Edge.BOTH,
            debounce_period=mock_line.debounce_period,
        )

    def request_lines(
        self,
        config: dict[int | str, LineSettings | None],
        consumer: str | None = None,
        event_buffer_size: int | None = None,  # noqa: ARG002
        output_values: dict[int | str, Value] | None = None,  # noqa: ARG002
    ) -> MockLineRequest:
        offsets = [self.line_offset_from_id(line) for line in config]
        with self._state.condition:
            for offset in offsets:
                if self._state.lines[offset].used:
                    raise OSError(
                        errno.EBUSY, f"Line {offset} is already in use"
                    )
            for offset, settings in zip(offsets, config.values()):
                line = self._state.lines[offset]
                line.used = True
                line.consumer = consumer or ""
                line.apply_settings(settings or LineSettings())
            self._state.condition.notify_all()
        return MockLineRequest(self._state, offsets, consumer)


class MockLineRequest:
    """Mock stand-in for :class:`gpiod.LineRequest`."""

    def __init__(
        self,
        state: MockChipState,
        offsets: list[int],
        consumer: str | None,
    ):
        self._state = state
        self._offsets = list(offsets)
        self._consumer = consumer
        self._released = False

    def __bool__(self) -> bool:
        return not self._released

    @property
    def offsets(self) -> list[int]:
        return list(self._offsets)

    @property
    def num_lines(self) -> int:
        return len(self._offsets)

    @property
    def chip_name(self) -> str:
        return posixpath.basename(self._state.path)

    def _check_released(self) -> None:
        if self._released:
            raise RequestReleasedError()

    def _offset(self, line: int | str) -> int:
        if isinstance(line, int):
            return line
        for offset in self._offsets:
            if self._state.lines[offset].name == line:
                return offset
        raise ValueError(f"unknown line name: {line}")

    def set_value(self, line: int | str, value: Value) -> None:
        self.set_values({line: value})

    def set_values(self, values: dict[int | str, Value]) -> None:
        self._check_released()
        with self._state.condition:
            for line, value in values.items():
                offset = self._offset(line)
                mock_line = self._state.lines[offset]
                mock_line.physical = (
                    value == Value.ACTIVE
                ) != mock_line.active_low
                if mock_line.direction == Direction.INPUT:
                    self._state.events.append(
                        (offset, _edge_type(mock_line.physical))
                    )
            self._state.condition.notify_all()

    def get_value(self, line: int | str) -> Value:
        self._check_released()
        return self._state.lines[self._offset(line)].logical_value()

    def get_values(self, lines: list[int | str] | None = None) -> list[Value]:
        self._check_released()
        return [self.get_value(line) for line in (lines or self._offsets)]

    def wait_edge_events(self, timeout: float | None = None) -> bool:
        self._check_released()
        if timeout is None:
            deadline = None
        else:
            deadline = time.monotonic() + float(timeout)
        with self._state.condition:
            while not self._state.events:
                if deadline is None:
                    self._state.condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._state.condition.wait(remaining)
            return True

    def read_edge_events(
        self, max_events: int | None = None
    ) -> list[MockEdgeEvent]:
        self._check_released()
        with self._state.condition:
            take = (
                self._state.events
                if max_events is None
                else (self._state.events[:max_events])
            )
            del self._state.events[: len(take)]
            return [
                MockEdgeEvent(
                    event_type=event_type,
                    line_offset=offset,
                    timestamp_ns=time.monotonic_ns(),
                )
                for offset, event_type in take
            ]

    def release(self) -> None:
        if self._released:
            return
        with self._state.condition:
            for offset in self._offsets:
                self._state.lines[offset].reset()
            self._state.events.clear()
            self._state.condition.notify_all()
        self._released = True


def _edge_type(physical: bool) -> EdgeEvent.Type:
    if physical:
        return EdgeEvent.Type.RISING_EDGE
    return EdgeEvent.Type.FALLING_EDGE


def request_lines(
    path: str,
    config: dict[int | str, LineSettings | None],
    consumer: str | None = None,
    event_buffer_size: int | None = None,
    output_values: dict[int | str, Value] | None = None,
) -> MockLineRequest:
    """Mock equivalent of :func:`gpiod.request_lines`."""
    return MockChip(path).request_lines(
        config,
        consumer=consumer,
        event_buffer_size=event_buffer_size,
        output_values=output_values,
    )


# --------------------------------------------------------------------------
# Test helpers
# --------------------------------------------------------------------------


def is_mock_chip(path: str) -> bool:
    """True if ``path`` should be served by the mock backend."""
    if path == MOCK_CHIP_PATH:
        return True
    with _registry_lock:
        return path in _chips


def register_chip(
    path: str,
    *,
    num_lines: int = DEFAULT_NUM_LINES,
    label: str = "mock",
    line_names: dict[int, str] | None = None,
) -> None:
    """Create (or replace) a mock chip at an arbitrary path.

    Used by tests to stand in for a real ``/dev/gpiochipX`` device.
    """
    with _registry_lock:
        _create_chip(path, num_lines, label, line_names or {})


def get_line_state(chip_path: str, offset: int) -> MockLine:
    """Return the mutable mock line, mainly for test assertions."""
    return _get_chip(chip_path).lines[offset]


def drive_line(chip_path: str, offset: int, physical: bool) -> None:
    """Externally drive a mock line's electrical level.

    This stands in for a button or sensor attached to an input pin.
    """
    state = _get_chip(chip_path)
    with state.condition:
        line = state.lines[offset]
        line.physical = physical
        if line.direction == Direction.INPUT:
            state.events.append((offset, _edge_type(line.physical)))
        state.condition.notify_all()


def set_line_consumer(chip_path: str, offset: int, consumer: str) -> None:
    """Pretend a line is already claimed by some other consumer."""
    state = _get_chip(chip_path)
    with state.condition:
        line = state.lines[offset]
        line.used = True
        line.consumer = consumer


def reset() -> None:
    """Drop all mock chip state.  Call between tests for isolation."""
    with _registry_lock:
        for state in _chips.values():
            with state.condition:
                for line in state.lines.values():
                    line.reset()
                state.events.clear()
        _chips.clear()
