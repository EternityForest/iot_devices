"""End to end tests for :class:`SerialJsonLines`.

The tests use a real pty pair as a virtual serial loopback.  The device
opens the slave end through a symlink glob, and the test drives the
master end directly, so the whole stack (globbing, pyserial, line
splitting, reconnect logic and the JSON packet handling) is exercised.
"""

from __future__ import annotations

import json
import os
import pty
import select
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from iot_devices.devices.JsonLines.serial import SerialJsonLines
from iot_devices.host.simple_host import SimpleHost


class RecordingHost(SimpleHost):
    """A host that records errors and prints so tests can assert on them."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []
        self.prints: list[tuple[str, str]] = []

    def on_device_error(self, device: Any, error: str) -> None:
        self.errors.append(error)

    def on_device_print(
        self, device: Any, message: str, title: str = ""
    ) -> None:
        self.prints.append((message, title))


class VirtualSerial:
    """A pty pair presented to the device as a symlink in a temp dir."""

    def __init__(self, directory: Path, name: str = "device0") -> None:
        self.directory = directory
        self.link = directory / name
        self.master_fd = -1
        self.slave_fd = -1
        self.connect()

    def connect(self) -> None:
        """(Re)create the pty pair and point the glob at it."""
        self.master_fd, self.slave_fd = pty.openpty()
        if self.link.is_symlink():
            self.link.unlink()
        self.link.symlink_to(os.ttyname(self.slave_fd))

    def disconnect(self) -> None:
        """Tear down the pty and remove the symlink."""
        if self.link.is_symlink():
            self.link.unlink()
        for fd in (self.master_fd, self.slave_fd):
            if fd >= 0:
                os.close(fd)
        self.master_fd = self.slave_fd = -1

    def send(self, data: bytes) -> None:
        """Send raw bytes to the device (as the remote peer would)."""
        os.write(self.master_fd, data)

    def read_packets(
        self, count: int = 1, timeout: float = 3.0
    ) -> list[dict[str, Any]]:
        """Read up to ``count`` JSON packets from the device."""
        deadline = time.monotonic() + timeout
        buffer = bytearray()
        packets: list[dict[str, Any]] = []

        while len(packets) < count and time.monotonic() < deadline:
            readable, _, _ = select.select([self.master_fd], [], [], 0.05)
            if not readable:
                continue
            chunk = os.read(self.master_fd, 65536)
            if not chunk:
                break
            buffer.extend(chunk)
            while b"\n" in buffer:
                raw, _, rest = buffer.partition(b"\n")
                buffer = bytearray(rest)
                raw = raw.strip()
                if raw:
                    packets.append(json.loads(raw))

        return packets


def wait_for(predicate: Any, timeout: float = 3.0) -> None:
    """Poll until predicate is true, or fail with a useful message."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "condition was not met before the timeout"


@pytest.fixture()
def host() -> Iterator[RecordingHost]:
    h = RecordingHost()
    yield h
    h.close()


@pytest.fixture()
def serial(tmp_path: Path) -> Iterator[VirtualSerial]:
    vs = VirtualSerial(tmp_path)
    yield vs
    vs.disconnect()


KEYS: dict[str, dict[str, Any]] = {
    "foo": {"local_name": "foo", "type": "number", "output": True},
    "bar": {"local_name": "bar", "type": "string"},
    "baz": {
        "local_name": "baz",
        "type": "number",
        "subtype": "bang",
        "output": True,
    },
}


def add_device(
    host: RecordingHost, serial: VirtualSerial, **overrides: Any
) -> SerialJsonLines:
    config: dict[str, Any] = {
        "type": "SerialJsonLines",
        "name": "ser",
        "serial_glob": str(serial.link),
        "reconnect_interval": 0.1,
        "keys": KEYS,
    }
    config.update(overrides)
    dev = host.add_new_device(config).wait_device_ready()
    return cast(SerialJsonLines, dev)


def test_incoming_values_update_datapoints(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial)
    dev.wait_ready()

    serial.send(b'{"bar": "hello", "foo": 3}\n')

    wait_for(lambda: dev.datapoints["bar"].get()[0] == "hello")
    assert dev.datapoints["foo"].get()[0] == 3
    assert host.errors == []


def test_crlf_and_lf_both_work(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial)
    dev.wait_ready()

    serial.send(b'{"bar": "first"}\r\n')
    wait_for(lambda: dev.datapoints["bar"].get()[0] == "first")

    serial.send(b'{"bar": "second"}\n')
    wait_for(lambda: dev.datapoints["bar"].get()[0] == "second")


def test_malformed_lines_ignored_and_comments_printed(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial)
    dev.wait_ready()

    serial.send(b"this is not json\n")
    serial.send(b"# firmware debug line\n")
    serial.send(b'{"bar": "still works"}\n')

    wait_for(lambda: dev.datapoints["bar"].get()[0] == "still works")
    wait_for(lambda: ("# firmware debug line", "") in host.prints)
    assert host.errors == []


def test_local_writes_are_pushed(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial)
    dev.wait_ready()

    dev.set_data_point("foo", 42)

    packets = serial.read_packets(1)
    assert packets == [{"foo": 42}]


def test_get_state_blacklists_triggers(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial)
    dev.wait_ready()

    dev.set_data_point("foo", 5)
    dev.set_data_point("baz", 1)
    dev.set_data_point("bar", "read only")

    # Only the plain output key is replayed on reconnect.
    assert dev.get_state() == {"foo": 5}


def test_incoming_does_not_echo_by_default(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial)
    dev.wait_ready()

    serial.send(b'{"foo": 7}\n')
    wait_for(lambda: dev.datapoints["foo"].get()[0] == 7)

    # Nothing should come back from the device.
    assert serial.read_packets(1, timeout=0.5) == []
    assert host.errors == []


def test_echo_config_sends_values_back(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial, echo=True)
    dev.wait_ready()

    serial.send(b'{"foo": 7}\n')

    assert serial.read_packets(1) == [{"foo": 7}]


def test_rate_limit_defers_extra_sends(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial, rate_limit=1, burst=1)
    dev.wait_ready()

    dev.set_data_point("foo", 1)
    dev.set_data_point("foo", 2)

    first = serial.read_packets(1, timeout=0.5)
    assert first == [{"foo": 1}]

    # The second value was rate limited and must arrive later.
    second = serial.read_packets(1, timeout=3.0)
    assert second == [{"foo": 2}]


def test_incoming_overwrites_queued_outgoing(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    # burst=1 lets the first send through, then queues the next one, so
    # there is a queued outgoing value that an incoming packet can
    # overwrite.
    dev = add_device(host, serial, rate_limit=1, burst=1)
    dev.wait_ready()

    dev.set_data_point("foo", 1)
    assert serial.read_packets(1) == [{"foo": 1}]

    dev.set_data_point("foo", 2)
    serial.send(b'{"foo": 99}\n')
    wait_for(lambda: dev.datapoints["foo"].get()[0] == 99)

    # The stale queued value must never be sent.
    assert serial.read_packets(1, timeout=1.5) == []


def test_reconnect_resyncs_state(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    dev = add_device(host, serial)
    dev.wait_ready()

    dev.set_data_point("foo", 5)
    assert serial.read_packets(1) == [{"foo": 5}]

    serial.disconnect()
    wait_for(lambda: dev.datapoints["connected"].get()[0] == 0)

    serial.connect()
    wait_for(lambda: dev.datapoints["connected"].get()[0] == 1)

    # On reconnect the device replays its output state.
    assert serial.read_packets(1) == [{"foo": 5}]


def test_missing_glob_raises(host: RecordingHost) -> None:
    with pytest.raises(ValueError):
        host.add_new_device(
            {
                "type": "SerialJsonLines",
                "name": "ser",
                "serial_glob": "",
            }
        ).wait_device_ready()
