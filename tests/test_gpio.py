"""End to end tests for the GPIO input and output devices.

These run against the in-process gpiod mock (see
:mod:`iot_devices.devices.GPIODevice.mock`), which is used automatically
for pins named like ``MOCK17``.  The tests exercise the real device
classes through a :class:`SimpleHost`, so they cover config parsing, pin
resolution, safety checks, and both directions of the
datapoint <-> physical pin relationship.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any, cast, override

import pytest

from iot_devices.device import Device
from iot_devices.devices.GPIODevice import (
    GPIOInput,
    GPIOOutput,
    backend,
    mock,
)
from iot_devices.host.simple_host import SimpleHost


class RecordingHost(SimpleHost):
    """A host that records device errors so tests can assert on them."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    @override
    def on_device_error(self, device: Any, error: str) -> None:
        self.errors.append(error)


@pytest.fixture(autouse=True)
def _isolate_mock() -> Iterator[None]:
    """Give every test a fresh mock chip registry."""
    mock.reset()
    yield
    mock.reset()


@pytest.fixture()
def host() -> Iterator[RecordingHost]:
    h = RecordingHost()
    yield h
    h.close()


def add_device(host: RecordingHost, config: dict[str, Any]) -> Device:
    "Create a device through the host and wait for it to be ready."
    return host.add_new_device(config).wait_device_ready()


def add_output(host: RecordingHost, **config: Any) -> GPIOOutput:
    return cast(
        GPIOOutput,
        add_device(host, {"type": "GPIOOutput", "name": "out", **config}),
    )


def add_input(host: RecordingHost, **config: Any) -> GPIOInput:
    return cast(
        GPIOInput,
        add_device(host, {"type": "GPIOInput", "name": "in", **config}),
    )


def wait_for_value(dev: Device, expected: float, timeout: float = 2.0) -> None:
    """Poll a device's ``value`` datapoint until it matches (or fail)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if dev.datapoints["value"].get()[0] == expected:
            return
        time.sleep(0.005)
    assert dev.datapoints["value"].get()[0] == expected


def use_chips(monkeypatch: pytest.MonkeyPatch, *paths: str) -> None:
    """Pretend the given mock chips are the real GPIO chips on the system."""
    monkeypatch.setattr(backend, "real_chip_paths", lambda: list(paths))


# ---------------------------------------------------------------------------
# Output device
# ---------------------------------------------------------------------------


def test_output_defaults_resolve_mock_pin(host: RecordingHost):
    dev = add_output(host)

    assert host.errors == []
    # The schema default pin is MOCK1.
    assert dev.line is not None
    assert dev.line.mock is True
    assert backend.pin_spec_for(dev.line) == "MOCK1"
    assert "mock" in dev.metadata["driver"]
    assert dev.config["active_high"] is True
    # PWM is gone for good.
    assert "pwm_frequency" not in dev.config


def test_output_pin_name_is_case_insensitive(host: RecordingHost):
    dev = add_output(host, pin="mock5")

    assert host.errors == []
    assert dev.line is not None
    assert dev.line.offset == 5


def test_output_datapoint_drives_pin(host: RecordingHost):
    dev = add_output(host, pin="MOCK17")

    assert host.errors == []
    assert dev.datapoints["value"].get()[0] == 0
    assert mock.get_line_state("mock", 17).physical is False

    dev.set_data_point("value", 1)
    assert dev.datapoints["value"].get()[0] == 1
    assert mock.get_line_state("mock", 17).physical is True

    dev.set_data_point("value", 0)
    assert dev.datapoints["value"].get()[0] == 0
    assert mock.get_line_state("mock", 17).physical is False


def test_output_initial_value_seeds_datapoint(host: RecordingHost):
    dev = add_output(host, pin="MOCK17", initial_value=1)

    assert host.errors == []
    assert dev.datapoints["value"].get()[0] == 1
    assert mock.get_line_state("mock", 17).physical is True


def test_output_active_low_inverts_pin(host: RecordingHost):
    dev = add_output(host, pin="MOCK17", active_high=False, initial_value=0)

    assert host.errors == []
    # Logically off means physically high when active_low.
    assert dev.datapoints["value"].get()[0] == 0
    assert mock.get_line_state("mock", 17).physical is True

    dev.set_data_point("value", 1)
    assert mock.get_line_state("mock", 17).physical is False

    dev.set_data_point("value", 0)
    assert mock.get_line_state("mock", 17).physical is True


@pytest.mark.parametrize(
    ("written", "active"),
    [(0.4, False), (0.5, True), (1, True), (0, False)],
)
def test_output_value_threshold(
    host: RecordingHost, written: float, active: bool
):
    dev = add_output(host, pin="MOCK17")

    assert host.errors == []
    dev.set_data_point("value", written)
    assert mock.get_line_state("mock", 17).physical is active


def test_output_refuses_blocklisted_consumer(host: RecordingHost):
    mock.set_line_consumer("mock", 17, "kernel")

    dev = add_output(host, pin="MOCK17")

    assert len(host.errors) == 1
    assert "Refusing to use MOCK17" in host.errors[0]
    assert "kernel" in host.errors[0]
    # The failed open must not leave a half-built device behind.
    assert dev.line is None
    assert dev.request is None
    assert "value" not in dev.datapoints


# ---------------------------------------------------------------------------
# Input device
# ---------------------------------------------------------------------------


def test_input_default_is_floating(host: RecordingHost):
    dev = add_input(host)

    assert host.errors == []
    assert dev.datapoints["value"].get()[0] == 0

    # Driving the underlying pin must update the datapoint.
    dev.test_val(True)
    wait_for_value(dev, 1)

    dev.test_val(False)
    wait_for_value(dev, 0)


def test_input_active_low_floating(host: RecordingHost):
    dev = add_input(host, active_high=False)

    assert host.errors == []
    # A floating pin reads low, which is "active" when active_low.
    assert dev.datapoints["value"].get()[0] == 1

    dev.test_val(True)
    wait_for_value(dev, 0)

    dev.test_val(False)
    wait_for_value(dev, 1)


def test_input_pull_up_active_low(host: RecordingHost):
    dev = add_input(host, pull_up=True, active_high=False)

    assert host.errors == []
    # Pulled up at rest -> physically high but logically inactive.
    assert mock.get_line_state("mock", 1).physical is True
    assert dev.datapoints["value"].get()[0] == 0

    dev.test_val(False)
    wait_for_value(dev, 1)

    dev.test_val(True)
    wait_for_value(dev, 0)


def test_input_pull_down_active_high(host: RecordingHost):
    dev = add_input(host, pull_down=True)

    assert host.errors == []
    # Pulled down at rest -> physically low and logically inactive.
    assert mock.get_line_state("mock", 1).physical is False
    assert dev.datapoints["value"].get()[0] == 0

    dev.test_val(True)
    wait_for_value(dev, 1)

    dev.test_val(False)
    wait_for_value(dev, 0)


def test_input_debounce_is_applied(host: RecordingHost):
    add_input(host, debounce_time_ms=500)

    assert host.errors == []
    assert mock.get_line_state("mock", 1).debounce_period == timedelta(
        milliseconds=500
    )


def test_input_debounce_disabled_when_zero(host: RecordingHost):
    add_input(host)

    assert host.errors == []
    assert mock.get_line_state("mock", 1).debounce_period == timedelta()


def test_input_refuses_blocklisted_consumer(host: RecordingHost):
    mock.set_line_consumer("mock", 1, "kernel")

    dev = add_input(host)

    assert len(host.errors) == 1
    assert "Refusing to use MOCK1" in host.errors[0]
    assert dev.line is None
    assert dev.request is None
    assert "value" not in dev.datapoints


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (
            {"pull_up": True, "pull_down": True},
            "pull up and pull down",
        ),
        (
            {"pull_up": True},
            "pull up and active high",
        ),
        (
            {"pull_down": True, "active_high": False},
            "pull down and active low",
        ),
    ],
)
def test_input_invalid_pull_combinations(
    host: RecordingHost, extra: dict[str, Any], message: str
):
    dev = add_input(host, **extra)

    assert len(host.errors) == 1
    assert message in host.errors[0]
    # The device must not register datapoints when init fails.
    assert "value" not in dev.datapoints


# ---------------------------------------------------------------------------
# Pin resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "expected"),
    [("17", 17), ("0", 0), ("BCM17", 17), ("bcm4", 4), ("007", 7)],
)
def test_parse_offset_accepts_legacy_specs(spec: str, expected: int):
    assert backend.parse_offset(spec) == expected


@pytest.mark.parametrize("spec", ["MOCK1", "gpiochip0:17", "", "banana"])
def test_parse_offset_rejects_other_specs(spec: str):
    with pytest.raises(ValueError):
        backend.parse_offset(spec)


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("0", "/dev/gpiochip0"),
        ("gpiochip2", "/dev/gpiochip2"),
        ("/dev/gpiochip3", "/dev/gpiochip3"),
    ],
)
def test_normalize_chip_path(part: str, expected: str):
    assert backend.normalize_chip_path(part) == expected


def test_normalize_chip_path_rejects_blank():
    with pytest.raises(ValueError):
        backend.normalize_chip_path("  ")


@pytest.mark.parametrize(
    ("consumer", "blocked"),
    [
        ("kernel", True),
        ("Kernel", True),
        ("kernel-gpio", True),
        ("iot_devices", False),
        ("", False),
    ],
)
def test_consumer_is_blocked(consumer: str, blocked: bool):
    assert backend.consumer_is_blocked(consumer) is blocked


def test_resolve_name_mock():
    line = backend.resolve_name("MOCK17")
    assert line.mock is True
    assert line.chip_path == mock.MOCK_CHIP_PATH
    assert line.offset == 17
    assert line.line_name == "MOCK17"


def test_resolve_name_rejects_missing_mock_pin():
    with pytest.raises(ValueError, match="does not exist"):
        backend.resolve_name("MOCK1000")


def test_resolve_name_legacy_offset_uses_first_matching_chip(
    monkeypatch: pytest.MonkeyPatch,
):
    mock.register_chip("/dev/gpiochip0", num_lines=8, label="small")
    mock.register_chip("/dev/gpiochip1", num_lines=32, label="big")
    use_chips(monkeypatch, "/dev/gpiochip0", "/dev/gpiochip1")

    # gpiochip0 has no line 17, so it falls through to gpiochip1.
    line = backend.resolve_name("BCM17")
    assert line.chip_path == "/dev/gpiochip1"
    assert line.offset == 17
    assert line.chip_label == "big"


def test_resolve_name_legacy_offset_uses_first_chip_when_present(
    monkeypatch: pytest.MonkeyPatch,
):
    mock.register_chip("/dev/gpiochip0", num_lines=32, label="first")
    mock.register_chip("/dev/gpiochip1", num_lines=32, label="second")
    use_chips(monkeypatch, "/dev/gpiochip0", "/dev/gpiochip1")

    line = backend.resolve_name("17")
    assert line.chip_path == "/dev/gpiochip0"
    assert line.chip_label == "first"


def test_resolve_name_legacy_offset_with_no_chips(
    monkeypatch: pytest.MonkeyPatch,
):
    use_chips(monkeypatch)
    with pytest.raises(ValueError, match="No GPIO chip exposes"):
        backend.resolve_name("17")


def test_resolve_name_explicit_offset(monkeypatch: pytest.MonkeyPatch):
    mock.register_chip("/dev/gpiochip1", num_lines=32, label="pinctrl")
    use_chips(monkeypatch, "/dev/gpiochip1")

    line = backend.resolve_name("gpiochip1:17")
    assert line.chip_path == "/dev/gpiochip1"
    assert line.offset == 17
    assert backend.pin_spec_for(line) == "gpiochip1:17"


def test_resolve_name_explicit_line_name(monkeypatch: pytest.MonkeyPatch):
    mock.register_chip(
        "/dev/gpiochip0",
        num_lines=32,
        label="pinctrl",
        line_names={5: "BTN5"},
    )
    use_chips(monkeypatch, "/dev/gpiochip0")

    line = backend.resolve_name("gpiochip0:BTN5")
    assert line.offset == 5
    assert line.line_name == "BTN5"

    # A bare chip number works too.
    assert backend.resolve_name("0:BTN5").offset == 5


def test_resolve_name_explicit_line_name_unknown(
    monkeypatch: pytest.MonkeyPatch,
):
    mock.register_chip(
        "/dev/gpiochip0",
        num_lines=8,
        label="pinctrl",
        line_names={5: "BTN5"},
    )
    use_chips(monkeypatch, "/dev/gpiochip0")

    with pytest.raises(ValueError, match="Known names"):
        backend.resolve_name("gpiochip0:NOPE")


def test_resolve_name_explicit_unknown_chip():
    with pytest.raises(ValueError, match="is not a GPIO chip"):
        backend.resolve_name("gpiochip99:1")


def test_resolve_name_blank():
    with pytest.raises(ValueError, match="may not be blank"):
        backend.resolve_name("   ")


def test_list_available_pins_includes_mock():
    lines = backend.list_available_pins(include_mock=True)
    assert any(line.mock for line in lines)
    assert any(backend.pin_spec_for(line) == "MOCK1" for line in lines)


def test_list_available_pins_excludes_mock(monkeypatch: pytest.MonkeyPatch):
    use_chips(monkeypatch)
    assert backend.list_available_pins(include_mock=False) == []


def test_check_line_is_safe_allows_free_line():
    line = backend.resolve_name("MOCK17")
    backend.check_line_is_safe(line)


def test_check_line_is_safe_blocks_kernel():
    mock.set_line_consumer("mock", 17, "kernel")
    line = backend.resolve_name("MOCK17")
    with pytest.raises(ValueError, match="Refusing to use"):
        backend.check_line_is_safe(line)


def test_check_line_is_safe_allows_our_own_consumer():
    mock.set_line_consumer("mock", 17, backend.CONSUMER_NAME)
    line = backend.resolve_name("MOCK17")
    backend.check_line_is_safe(line)


def test_describe_line(monkeypatch: pytest.MonkeyPatch):
    mock.register_chip(
        "/dev/gpiochip0",
        num_lines=32,
        label="pinctrl",
        line_names={3: "LED3"},
    )
    use_chips(monkeypatch, "/dev/gpiochip0")

    line = backend.resolve_name("gpiochip0:3")
    assert backend.describe_line(line) == "gpiod gpiochip0:3 [LED3]"


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------


def test_discover_devices_lists_free_lines(monkeypatch: pytest.MonkeyPatch):
    mock.register_chip(
        "/dev/gpiochip0",
        num_lines=4,
        label="pinctrl",
        line_names={1: "BTN1"},
    )
    use_chips(monkeypatch, "/dev/gpiochip0")

    found = GPIOOutput.discover_devices({})
    assert "gpiochip0:0" in found
    assert "gpiochip0:1 (BTN1)" in found
    assert found["gpiochip0:1 (BTN1)"] == {
        "type": "GPIOOutput",
        "pin": "gpiochip0:1",
    }


def test_discover_devices_skips_blocklisted_lines(
    monkeypatch: pytest.MonkeyPatch,
):
    mock.register_chip("/dev/gpiochip0", num_lines=4, label="pinctrl")
    use_chips(monkeypatch, "/dev/gpiochip0")
    mock.set_line_consumer("/dev/gpiochip0", 2, "kernel")

    found = GPIOOutput.discover_devices({})
    assert "gpiochip0:2" not in found
    assert "gpiochip0:3" in found


def test_discover_devices_falls_back_to_mock(
    monkeypatch: pytest.MonkeyPatch,
):
    use_chips(monkeypatch)
    assert GPIOOutput.discover_devices({}) == {
        "MOCK1": {"type": "GPIOOutput", "pin": "MOCK1"}
    }
