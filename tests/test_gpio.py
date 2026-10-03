"""End to end tests for the GPIO input and output devices.

These use gpiozero's mock pin factory, which is forced whenever "mock"
appears in the configured pin name (e.g. "MOCK17").  The tests exercise
the real device classes through a SimpleHost, so they cover config
parsing, pin resolution, and both directions of the
datapoint <-> physical pin relationship.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import gpiozero
import pytest

from iot_devices.device import Device
from iot_devices.host.simple_host import SimpleHost


class RecordingHost(SimpleHost):
    """A host that records device errors so tests can assert on them."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def on_device_error(self, device: Any, error: str) -> None:
        self.errors.append(error)


@pytest.fixture()
def host() -> Iterator[RecordingHost]:
    h = RecordingHost()
    yield h
    h.close()


def add_device(host: RecordingHost, config: dict[str, Any]) -> Device:
    "Create a device through the host and wait for it to be ready."
    return host.add_new_device(config).wait_device_ready()


# ---------------------------------------------------------------------------
# Output device
# ---------------------------------------------------------------------------


def test_output_defaults_resolve_mock_pin(host: RecordingHost):
    dev = add_device(host, {"type": "GPIOOutput", "name": "out"})

    assert host.errors == []
    # The schema default pin is MOCK1.
    assert str(dev.pin.pin) == "GPIO1"
    assert isinstance(dev.pin.pin_factory, gpiozero.pins.mock.MockFactory)
    assert "MockFactory" in dev.metadata["driver"]
    assert dev.config["active_high"] is True
    assert dev.config["pwm_frequency"] == 100


def test_output_pin_name_is_case_insensitive(host: RecordingHost):
    dev = add_device(
        host, {"type": "GPIOOutput", "name": "out", "pin": "mock5"}
    )

    assert host.errors == []
    assert str(dev.pin.pin) == "GPIO5"


def test_output_datapoint_drives_pin(host: RecordingHost):
    dev = add_device(
        host, {"type": "GPIOOutput", "name": "out", "pin": "MOCK17"}
    )

    assert host.errors == []
    assert dev.datapoints["value"].get()[0] == 0
    assert dev.pin.pin.state == 0

    dev.set_data_point("value", 1)
    assert dev.pin.value == 1
    assert dev.pin.pin.state == 1

    dev.set_data_point("value", 0)
    assert dev.pin.value == 0
    assert dev.pin.pin.state == 0


def test_output_initial_value_seeds_datapoint(host: RecordingHost):
    dev = add_device(
        host,
        {
            "type": "GPIOOutput",
            "name": "out",
            "pin": "MOCK17",
            "initial_value": 1,
        },
    )

    assert host.errors == []
    assert dev.datapoints["value"].get()[0] == 1
    assert dev.pin.value == 1
    assert dev.pin.pin.state == 1


def test_output_active_low_inverts_pin(host: RecordingHost):
    dev = add_device(
        host,
        {
            "type": "GPIOOutput",
            "name": "out",
            "pin": "MOCK17",
            "active_high": False,
            "initial_value": 0,
        },
    )

    assert host.errors == []
    assert dev.pin.active_high is False
    # Logically off means physically high when active_low.
    assert dev.datapoints["value"].get()[0] == 0
    assert dev.pin.pin.state == 1

    dev.set_data_point("value", 1)
    assert dev.pin.is_active is True
    assert dev.pin.pin.state == 0

    dev.set_data_point("value", 0)
    assert dev.pin.is_active is False
    assert dev.pin.pin.state == 1


def test_output_pwm_frequency_and_duty_cycle(host: RecordingHost):
    dev = add_device(
        host,
        {
            "type": "GPIOOutput",
            "name": "out",
            "pin": "MOCK17",
            "pwm_frequency": 500,
        },
    )

    assert host.errors == []
    assert isinstance(dev.pin, gpiozero.PWMLED)
    assert dev.pin.frequency == 500

    dev.set_data_point("value", 0.5)
    assert dev.pin.value == 0.5
    assert dev.pin.pin.state == 0.5


# ---------------------------------------------------------------------------
# Input device
# ---------------------------------------------------------------------------


def test_input_default_is_floating(host: RecordingHost):
    dev = add_device(host, {"type": "GPIOInput", "name": "in", "pin": "MOCK1"})

    assert host.errors == []
    assert dev.pin.pull_up is None
    assert dev.datapoints["value"].get()[0] == 0

    # Driving the underlying pin must update the datapoint.
    dev.test_val(True)
    assert dev.datapoints["value"].get()[0] == 1
    assert dev.pin.is_active is True

    dev.test_val(False)
    assert dev.datapoints["value"].get()[0] == 0
    assert dev.pin.is_active is False


def test_input_active_low_floating(host: RecordingHost):
    dev = add_device(
        host,
        {
            "type": "GPIOInput",
            "name": "in",
            "pin": "MOCK1",
            "active_high": False,
        },
    )

    assert host.errors == []
    # A floating pin reads low, which is "active" when active_low.
    assert dev.datapoints["value"].get()[0] == 1

    dev.test_val(True)
    assert dev.datapoints["value"].get()[0] == 0

    dev.test_val(False)
    assert dev.datapoints["value"].get()[0] == 1


def test_input_pull_up_active_low(host: RecordingHost):
    dev = add_device(
        host,
        {
            "type": "GPIOInput",
            "name": "in",
            "pin": "MOCK1",
            "pull_up": True,
            "active_high": False,
        },
    )

    assert host.errors == []
    assert dev.pin.pull_up is True
    # Pulled up at rest -> physically high but logically inactive.
    assert dev.pin.pin.state == 1
    assert dev.datapoints["value"].get()[0] == 0

    dev.test_val(False)
    assert dev.datapoints["value"].get()[0] == 1

    dev.test_val(True)
    assert dev.datapoints["value"].get()[0] == 0


def test_input_pull_down_active_high(host: RecordingHost):
    dev = add_device(
        host,
        {
            "type": "GPIOInput",
            "name": "in",
            "pin": "MOCK1",
            "pull_down": True,
        },
    )

    assert host.errors == []
    assert dev.pin.pull_up is False
    # Pulled down at rest -> physically low and logically inactive.
    assert dev.pin.pin.state == 0
    assert dev.datapoints["value"].get()[0] == 0

    dev.test_val(True)
    assert dev.datapoints["value"].get()[0] == 1

    dev.test_val(False)
    assert dev.datapoints["value"].get()[0] == 0


def test_input_debounce_converted_to_seconds(host: RecordingHost):
    dev = add_device(
        host,
        {
            "type": "GPIOInput",
            "name": "in",
            "pin": "MOCK1",
            "debounce_time_ms": 500,
        },
    )

    assert host.errors == []
    # gpiozero expects seconds, the config is in milliseconds.
    assert dev.pin.pin.bounce == 0.5


def test_input_debounce_disabled_when_zero(host: RecordingHost):
    dev = add_device(host, {"type": "GPIOInput", "name": "in", "pin": "MOCK1"})

    assert host.errors == []
    assert dev.pin.pin.bounce is None


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
    dev = add_device(
        host, {"type": "GPIOInput", "name": "in", "pin": "MOCK1", **extra}
    )

    assert len(host.errors) == 1
    assert message in host.errors[0]
    # The device must not register datapoints when init fails.
    assert "value" not in dev.datapoints
