"""Pin name resolution, chip discovery and safety checks on top of gpiod.

Accepted pin specs:

* ``MOCK1``            -- offset 1 on the built-in mock chip (no hardware).
* ``17`` or ``BCM17``  -- offset 17 on the first ``/dev/gpiochip*`` that
  exposes a line there.  This keeps old configs working.
* ``gpiochip0:17``     -- offset 17 on ``gpiochip0``.
* ``gpiochip0:BTN1``   -- the line named ``BTN1`` on ``gpiochip0``.

:func:`resolve_name` finds the matching line, while
:func:`list_available_pins` enumerates what is present on the system.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from glob import glob

import gpiod
from gpiod.line import Bias, Direction, Edge, Value
from gpiod.line_settings import LineSettings

from . import mock

CONSUMER_NAME = "iot_devices"
"""Consumer string reported to the kernel for our requests."""

BLOCKED_CONSUMERS = ("kernel",)
"""Consumers (matched case-insensitively, by substring) we refuse to poke."""

GPIOCHIP_GLOB = "/dev/gpiochip*"
"""Glob matching GPIO chip character devices."""

MOCK_PREFIX = "mock"
"""Prefix identifying a mock pin, e.g. ``MOCK1``."""

_OFFSET_RE = re.compile(r"bcm(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class ResolvedLine:
    """A concrete GPIO line: a chip plus an offset within it."""

    chip_path: str
    offset: int
    line_name: str
    chip_label: str
    mock: bool
    used: bool
    consumer: str


def parse_offset(spec: str) -> int:
    """Parse a legacy pin spec: a plain number or ``BCMx``.

    Raises:
        ValueError: if the spec is neither.
    """
    spec = spec.strip()
    if spec.isdigit():
        return int(spec)
    match = _OFFSET_RE.fullmatch(spec)
    if match:
        return int(match.group(1))
    raise ValueError(
        f"Unsupported pin name {spec!r}; expected MOCK1, 17, BCM17, "
        f"or gpiochip0:17"
    )


def normalize_chip_path(part: str) -> str:
    """Normalize a chip reference to an absolute device path.

    Accepts ``0``, ``gpiochip0`` or ``/dev/gpiochip0``.
    """
    part = part.strip()
    if not part:
        raise ValueError("Chip name may not be blank")
    if part.isdigit():
        return f"/dev/gpiochip{part}"
    if not part.startswith("/"):
        return f"/dev/{part}"
    return part


def open_chip(chip_path: str):
    """Open a chip, dispatching mock paths to the mock backend."""
    if mock.is_mock_chip(chip_path):
        return mock.MockChip(chip_path)
    return gpiod.Chip(chip_path)


def _is_gpiochip(path: str) -> bool:
    if mock.is_mock_chip(path):
        return True
    try:
        return gpiod.is_gpiochip_device(path)
    except Exception:
        return False


def real_chip_paths() -> list[str]:
    """Return the paths of GPIO chips present on the system, sorted."""
    return sorted(path for path in glob(GPIOCHIP_GLOB) if _is_gpiochip(path))


def iter_lines(chip_path: str) -> Iterator[ResolvedLine]:
    """Yield a :class:`ResolvedLine` for every line on ``chip_path``."""
    chip = open_chip(chip_path)
    try:
        info = chip.get_info()
        for offset in range(info.num_lines):
            line_info = chip.get_line_info(offset)
            yield ResolvedLine(
                chip_path=chip_path,
                offset=offset,
                line_name=line_info.name,
                chip_label=info.label,
                mock=mock.is_mock_chip(chip_path),
                used=line_info.used,
                consumer=line_info.consumer,
            )
    finally:
        chip.close()


def list_available_pins(include_mock: bool = True) -> list[ResolvedLine]:
    """List every GPIO line available for use.

    Args:
        include_mock: also include the built-in mock chip's lines.
    """
    pins: list[ResolvedLine] = []
    if include_mock:
        pins.extend(iter_lines(mock.MOCK_CHIP_PATH))
    for path in real_chip_paths():
        if path == mock.MOCK_CHIP_PATH:
            continue
        try:
            pins.extend(iter_lines(path))
        except Exception:
            continue
    return pins


def pin_spec_for(line: ResolvedLine) -> str:
    """Return the canonical pin spec for a resolved line."""
    if line.chip_path == mock.MOCK_CHIP_PATH:
        return f"MOCK{line.offset}"
    return f"{posixpath.basename(line.chip_path)}:{line.offset}"


def describe_line(line: ResolvedLine) -> str:
    """Human readable description, stored in device metadata."""
    is_mock = line.chip_path == mock.MOCK_CHIP_PATH
    kind = "mock" if is_mock else "gpiod"
    return f"{kind} {pin_spec_for(line)} [{line.line_name}]"


def consumer_is_blocked(consumer: str) -> bool:
    """True if a line's consumer is on the do-not-touch blacklist."""
    low = consumer.lower()
    return any(blocked in low for blocked in BLOCKED_CONSUMERS)


def _resolve_mock(spec: str) -> ResolvedLine:
    remainder = spec[len(MOCK_PREFIX) :]
    if not remainder.isdigit():
        raise ValueError(
            f"Unsupported mock pin {spec!r}; expected a number, e.g. MOCK1"
        )
    offset = int(remainder)
    try:
        state = mock.get_line_state(mock.MOCK_CHIP_PATH, offset)
    except (KeyError, IndexError) as ex:
        raise ValueError(
            f"Mock pin {spec!r} does not exist; the mock chip exposes "
            f"{mock.DEFAULT_NUM_LINES} lines "
            f"(MOCK0-MOCK{mock.DEFAULT_NUM_LINES - 1})"
        ) from ex
    return ResolvedLine(
        chip_path=mock.MOCK_CHIP_PATH,
        offset=offset,
        line_name=state.name,
        chip_label="mock",
        mock=True,
        used=state.used,
        consumer=state.consumer,
    )


def _line_from_chip(chip_path: str, offset: int) -> ResolvedLine:
    chip = open_chip(chip_path)
    try:
        info = chip.get_info()
        line_info = chip.get_line_info(offset)
        return ResolvedLine(
            chip_path=chip_path,
            offset=offset,
            line_name=line_info.name,
            chip_label=info.label,
            mock=mock.is_mock_chip(chip_path),
            used=line_info.used,
            consumer=line_info.consumer,
        )
    finally:
        chip.close()


def _resolve_by_offset(offset: int) -> ResolvedLine:
    for path in real_chip_paths():
        chip = open_chip(path)
        try:
            num_lines = chip.get_info().num_lines
        finally:
            chip.close()
        if offset < num_lines:
            return _line_from_chip(path, offset)
    raise ValueError(
        f"No GPIO chip exposes a line at offset {offset}. "
        f"Available chips: {real_chip_paths() or 'none'}"
    )


def _resolve_explicit(chip_part: str, line_part: str) -> ResolvedLine:
    if not line_part:
        raise ValueError("A line offset or name is required after ':'")
    chip_path = normalize_chip_path(chip_part)
    if not _is_gpiochip(chip_path):
        raise ValueError(f"{chip_path} is not a GPIO chip")
    chip = open_chip(chip_path)
    try:
        try:
            offset = chip.line_offset_from_id(
                int(line_part) if line_part.isdigit() else line_part
            )
            line_info = chip.get_line_info(offset)
            label = chip.get_info().label
        except (OSError, ValueError) as ex:
            names = [
                line.line_name
                for line in iter_lines(chip_path)
                if line.line_name
            ]
            raise ValueError(
                f"No line {line_part!r} on {chip_path}. "
                f"Known names: {names or 'none'}"
            ) from ex
    finally:
        chip.close()
    return ResolvedLine(
        chip_path=chip_path,
        offset=offset,
        line_name=line_info.name,
        chip_label=label,
        mock=mock.is_mock_chip(chip_path),
        used=line_info.used,
        consumer=line_info.consumer,
    )


def resolve_name(spec: str) -> ResolvedLine:
    """Resolve a pin spec into a concrete :class:`ResolvedLine`.

    Raises:
        ValueError: if the spec is malformed or matches nothing.
    """
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("Pin name may not be blank")
    if spec.lower().startswith(MOCK_PREFIX):
        return _resolve_mock(spec)
    if ":" in spec:
        chip_part, _, line_part = spec.partition(":")
        return _resolve_explicit(chip_part, line_part)
    return _resolve_by_offset(parse_offset(spec))


def _fresh_line_info(line: ResolvedLine):
    chip = open_chip(line.chip_path)
    try:
        return chip.get_line_info(line.offset)
    finally:
        chip.close()


def check_line_is_safe(line: ResolvedLine) -> None:
    """Refuse to touch a line claimed by a blacklisted consumer.

    Raises:
        ValueError: if the line is in use by a blacklisted consumer.
    """
    info = _fresh_line_info(line)
    if info.used and consumer_is_blocked(info.consumer):
        raise ValueError(
            f"Refusing to use {pin_spec_for(line)}: already in use by "
            f"{info.consumer!r}"
        )


def open_output_line(
    line: ResolvedLine,
    *,
    active_low: bool,
    initial_active: bool,
    consumer: str = CONSUMER_NAME,
):
    """Request an exclusive output line, checking safety first."""
    check_line_is_safe(line)
    settings = LineSettings(
        direction=Direction.OUTPUT,
        active_low=active_low,
        output_value=Value.ACTIVE if initial_active else Value.INACTIVE,
    )
    return _request_line(line.chip_path, line.offset, settings, consumer)


def open_input_line(
    line: ResolvedLine,
    *,
    active_low: bool,
    bias: Bias,
    debounce_period: timedelta,
    consumer: str = CONSUMER_NAME,
):
    """Request an exclusive input line with edge detection."""
    check_line_is_safe(line)
    settings = LineSettings(
        direction=Direction.INPUT,
        edge_detection=Edge.BOTH,
        active_low=active_low,
        bias=bias,
        debounce_period=debounce_period,
    )
    return _request_line(line.chip_path, line.offset, settings, consumer)


def _request_line(
    chip_path: str, offset: int, settings: LineSettings, consumer: str
):
    if mock.is_mock_chip(chip_path):
        return mock.request_lines(
            chip_path, {offset: settings}, consumer=consumer
        )
    return gpiod.request_lines(chip_path, {offset: settings}, consumer=consumer)
