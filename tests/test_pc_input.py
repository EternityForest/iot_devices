"""Tests for PCInputDevice using fake evdev devices.

Real ``/dev/input`` nodes are replaced with pipe backed stand ins, so
connection tracking, the event to datapoint mapping, rescans and the
permission checks can all be exercised on any machine.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import pytest
from evdev import ecodes

import iot_devices.devices.PCInput as pc_input
from iot_devices.devices.PCInput import PCInputDevice

from .recording_host import RecordingHost


def wait_for(predicate: Any, timeout: float = 3.0) -> None:
    """Poll until predicate is true, or fail with a useful message."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "condition was not met before the timeout"


def dp_value(dev: PCInputDevice, name: str) -> Any:
    """Current value of a datapoint, or None if it does not exist yet.

    Dynamic datapoints only appear once the first matching event
    arrives, so polling code must tolerate the datapoint being absent
    instead of raising a KeyError mid wait.
    """
    dp = dev.datapoints.get(name)
    return None if dp is None else dp.get()[0]


class FakeEvent:
    """Stand-in for an evdev InputEvent."""

    def __init__(self, etype: int, code: int, value: int) -> None:
        self.type = etype
        self.code = code
        self.value = value


class FakeDevice:
    """Stand-in for ``evdev.InputDevice`` backed by an OS pipe.

    Pushing an event writes a wakeup byte to the pipe, and unplugging
    closes the write end, so the reader sees EOF the same way it would
    when a real device is removed.
    """

    def __init__(self, path: str, name: str, phys: str = "") -> None:
        self.path = path
        self.name = name
        self.phys = phys
        self.queue: list[FakeEvent] = []
        self.gone = False
        self.closed = False
        self.read_fd, self.write_fd = os.pipe()

    @property
    def fd(self) -> int:
        return self.read_fd

    def push(self, etype: int, code: int, value: int) -> None:
        """Queue one event and wake the reader."""
        self.queue.append(FakeEvent(etype, code, value))
        os.write(self.write_fd, b"\x01")

    def read(self) -> list[FakeEvent]:
        """Consume the wakeup byte and return any queued events."""
        os.read(self.read_fd, 1)
        if self.gone:
            raise OSError(19, "No such device")
        events = self.queue
        self.queue = []
        return events

    def unplug(self) -> None:
        """Make the device look removed."""
        self.gone = True
        try:
            os.close(self.write_fd)
        except OSError:
            pass

    def close(self) -> None:
        self.closed = True
        for fd in (self.read_fd, self.write_fd):
            try:
                os.close(fd)
            except OSError:
                pass


class Environment:
    """A fake ``/dev/input`` for the device under test to scan."""

    def __init__(self) -> None:
        self.devices: dict[str, FakeDevice] = {}

    def add(self, path: str, name: str, phys: str = "") -> FakeDevice:
        dev = FakeDevice(path, name, phys)
        self.devices[path] = dev
        return dev

    def scan_candidates(self) -> list[tuple[str, bool]]:
        return [(path, True) for path in sorted(self.devices)]

    def open_device(self, path: str) -> FakeDevice:
        return self.devices[path]


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch) -> Environment:
    """Replace real /dev/input scanning with a fake environment."""
    e = Environment()
    monkeypatch.setattr(pc_input, "_scan_candidates", e.scan_candidates)
    monkeypatch.setattr(pc_input, "_open_device", e.open_device)
    return e


@pytest.fixture()
def host() -> Iterator[RecordingHost]:
    h = RecordingHost()
    yield h
    h.close()


def add_device(host: RecordingHost, **overrides: Any) -> PCInputDevice:
    config: dict[str, Any] = {
        "type": "PCInputDevice",
        "name": "pcinput",
        "device_filter": "keyboard",
        "scan_interval": 0.05,
    }
    config.update(overrides)
    dev = host.add_new_device(config).wait_device_ready()
    assert isinstance(dev, PCInputDevice)
    return dev


def test_connects_to_matching_device(
    env: Environment, host: RecordingHost
) -> None:
    env.add(
        "/dev/input/event0",
        "AT Translated Keyboard",
        "isa0060/serio0/input0",
    )
    dev = add_device(host)

    wait_for(lambda: dp_value(dev, "connected") == 1)
    assert dev.metadata["devices"] == [
        "/dev/input/event0 AT Translated Keyboard isa0060/serio0/input0"
    ]


def test_filter_requires_every_keyword(
    env: Environment, host: RecordingHost
) -> None:
    env.add("/dev/input/event0", "USB Ultra Keyboard", "usb-1/input0")
    env.add("/dev/input/event1", "USB Mouse", "usb-2/input0")
    env.add("/dev/input/event2", "PS/2 Keyboard", "pnp0/input0")
    dev = add_device(host, device_filter="usb keyboard")

    wait_for(lambda: dp_value(dev, "connected") == 1)
    assert dev.metadata["devices"] == [
        "/dev/input/event0 USB Ultra Keyboard usb-1/input0"
    ]


def test_blank_filter_matches_everything(
    env: Environment, host: RecordingHost
) -> None:
    env.add("/dev/input/event0", "Keyboard", "k/input0")
    env.add("/dev/input/event1", "Mouse", "m/input0")
    dev = add_device(host, device_filter="   ")

    wait_for(lambda: dp_value(dev, "connected") == 2)


def test_key_events(env: Environment, host: RecordingHost) -> None:
    kb = env.add("/dev/input/event0", "AT Keyboard", "isa/input0")
    dev = add_device(host)
    wait_for(lambda: dp_value(dev, "connected") == 1)

    kb.push(ecodes.EV_KEY, ecodes.KEY_A, 1)
    wait_for(lambda: dp_value(dev, "key_event") == "key_a_down")

    kb.push(ecodes.EV_KEY, ecodes.KEY_A, 0)
    wait_for(lambda: dp_value(dev, "key_event") == "key_a_up")

    kb.push(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
    wait_for(lambda: dp_value(dev, "key_event") == "btn_left_down")

    # Autorepeat events still count as down.
    kb.push(ecodes.EV_KEY, ecodes.KEY_A, 2)
    wait_for(lambda: dp_value(dev, "key_event") == "key_a_down")


def test_numeric_datapoints_created_on_first_event(
    env: Environment, host: RecordingHost
) -> None:
    mouse = env.add("/dev/input/event1", "Logitech Mouse", "usb-1/input0")
    dev = add_device(host, device_filter="mouse")
    wait_for(lambda: dp_value(dev, "connected") == 1)

    mouse.push(ecodes.EV_REL, ecodes.REL_X, 5)
    mouse.push(ecodes.EV_REL, ecodes.REL_WHEEL, -1)
    mouse.push(ecodes.EV_ABS, ecodes.ABS_X, 100)
    mouse.push(ecodes.EV_SW, ecodes.SW_LID, 1)

    wait_for(lambda: dp_value(dev, "rel_x") == 5)
    wait_for(lambda: dp_value(dev, "rel_wheel") == -1)
    wait_for(lambda: dp_value(dev, "abs_x") == 100)
    wait_for(lambda: dp_value(dev, "sw_lid") == 1)

    # Button events from the mouse feed key_event, not new datapoints.
    mouse.push(ecodes.EV_KEY, ecodes.BTN_RIGHT, 1)
    wait_for(lambda: dp_value(dev, "key_event") == "btn_right_down")


def test_unplugged_device_is_forgotten(
    env: Environment, host: RecordingHost
) -> None:
    kb = env.add("/dev/input/event0", "AT Keyboard", "isa/input0")
    dev = add_device(host)
    wait_for(lambda: dp_value(dev, "connected") == 1)

    kb.unplug()
    del env.devices["/dev/input/event0"]

    wait_for(lambda: dp_value(dev, "connected") == 0)
    wait_for(lambda: dev.metadata["devices"] == [])


def test_rescan_picks_up_new_devices(
    env: Environment, host: RecordingHost
) -> None:
    dev = add_device(host, device_filter="")
    wait_for(lambda: dp_value(dev, "connected") == 0)

    env.add("/dev/input/event3", "New Keyboard", "usb-3/input0")
    wait_for(lambda: dp_value(dev, "connected") == 1)
    assert dev.metadata["devices"] == [
        "/dev/input/event3 New Keyboard usb-3/input0"
    ]


def test_no_devices_is_not_an_error(
    env: Environment, host: RecordingHost
) -> None:
    dev = add_device(host)

    assert dp_value(dev, "connected") == 0


def test_raises_without_read_permission(
    monkeypatch: pytest.MonkeyPatch, host: RecordingHost
) -> None:
    monkeypatch.setattr(
        pc_input,
        "_scan_candidates",
        lambda: [("/dev/input/event0", False), ("/dev/input/event1", False)],
    )

    with pytest.raises(PermissionError):
        host.add_new_device({"type": "PCInputDevice", "name": "pcinput"})


def test_some_readable_devices_are_enough(
    monkeypatch: pytest.MonkeyPatch, host: RecordingHost
) -> None:
    monkeypatch.setattr(
        pc_input,
        "_scan_candidates",
        lambda: [("/dev/input/event0", False), ("/dev/input/event1", True)],
    )
    monkeypatch.setattr(
        pc_input,
        "_open_device",
        lambda path: FakeDevice(path, "AT Keyboard", "isa/input0"),
    )

    dev = add_device(host)
    wait_for(lambda: dp_value(dev, "connected") == 1)


def test_close_stops_readers_without_errors(
    env: Environment, host: RecordingHost
) -> None:
    env.add("/dev/input/event0", "AT Keyboard", "isa/input0")
    dev = add_device(host)
    wait_for(lambda: dp_value(dev, "connected") == 1)

    dev.close()
    time.sleep(0.3)

    assert host.errors == []
    assert any(
        "Connected to input device" in message
        for message, _title in host.prints
    )
