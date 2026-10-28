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

from .recording_host import RecordingHost


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
    wait_for(lambda: dev.datapoints["connection.connected"].get()[0] == 0)

    serial.connect()
    wait_for(lambda: dev.datapoints["connection.connected"].get()[0] == 1)

    # On reconnect the device replays its output state.
    assert serial.read_packets(1) == [{"foo": 5}]


def test_create_port_device_destroy_port_create_device(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    """Create port, create device, destroy port, create device."""
    # 1. Create port (done by the serial fixture).
    # 2. Create device 1.
    dev1 = add_device(host, serial)
    dev1.wait_ready()

    dev1.set_data_point("foo", 1)
    assert serial.read_packets(1) == [{"foo": 1}]

    # 3. Destroy port.
    serial.disconnect()
    wait_for(lambda: dev1.datapoints["connection.connected"].get()[0] == 0)

    # Close the first device so it does not compete for the port.
    dev1.close()

    # 4. Create a new device while the port is down.
    config: dict[str, Any] = {
        "type": "SerialJsonLines",
        "name": "ser",
        "serial_glob": str(serial.link),
        "reconnect_interval": 0.1,
        "keys": KEYS,
    }
    dev2 = cast(
        SerialJsonLines, host.add_new_device(config).wait_device_ready()
    )
    wait_for(lambda: dev2.datapoints["connection.connected"].get()[0] == 0)

    # 5. Create the port again.
    serial.connect()

    # The new device should connect.
    dev2.wait_ready()
    dev2.set_data_point("foo", 2)
    assert serial.read_packets(1) == [{"foo": 2}]


def test_create_device_without_port_create_port(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    """Create device without port up, then create port."""
    # Start with no port.
    serial.disconnect()

    # Create device while the port is down.
    config: dict[str, Any] = {
        "type": "SerialJsonLines",
        "name": "ser",
        "serial_glob": str(serial.link),
        "reconnect_interval": 0.1,
        "keys": KEYS,
    }
    dev = cast(SerialJsonLines, host.add_new_device(config).wait_device_ready())
    wait_for(lambda: dev.datapoints["connection.connected"].get()[0] == 0)

    # Create the port.
    serial.connect()

    # The device should connect.
    dev.wait_ready()
    dev.set_data_point("foo", 3)
    assert serial.read_packets(1) == [{"foo": 3}]


def test_send_heartbeat_sends_empty_object(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    """An idle connection sends empty heartbeat packets."""
    dev = add_device(host, serial, send_heartbeat=0.2)
    dev.wait_ready()

    # No output state and no writes, so the first packet is a heartbeat.
    assert serial.read_packets(1, timeout=2.0) == [{}]


def test_send_heartbeat_skipped_after_recent_send(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    """A heartbeat is not sent if something was sent more recently."""
    dev = add_device(host, serial, send_heartbeat=0.5)
    dev.wait_ready()

    dev.set_data_point("foo", 7)
    assert serial.read_packets(1) == [{"foo": 7}]

    # The next heartbeat tick falls within the interval, so it is skipped.
    assert serial.read_packets(1, timeout=0.2) == []

    # After a full interval an idle heartbeat is sent.
    assert serial.read_packets(1, timeout=2.0) == [{}]


def test_expect_heartbeat_marks_offline(
    host: RecordingHost, serial: VirtualSerial
) -> None:
    """A connection with no incoming data is marked offline."""
    dev = add_device(host, serial, expect_heartbeat=0.3)
    dev.wait_ready()

    serial.send(b'{"bar": "alive"}\n')
    wait_for(lambda: dev.datapoints["bar"].get()[0] == "alive")
    wait_for(lambda: dev.datapoints["connection.connected"].get()[0] == 1)

    # No further data arrives, so the device goes offline.
    wait_for(
        lambda: dev.datapoints["connection.connected"].get()[0] == 0,
        timeout=2.0,
    )

    # Receiving data again brings it back online.
    serial.send(b'{"bar": "back"}\n')
    wait_for(lambda: dev.datapoints["bar"].get()[0] == "back")
    wait_for(lambda: dev.datapoints["connection.connected"].get()[0] == 1)


def test_missing_glob_raises(host: RecordingHost) -> None:
    with pytest.raises(ValueError):
        host.add_new_device(
            {
                "type": "SerialJsonLines",
                "name": "ser",
                "serial_glob": "",
            }
        ).wait_device_ready()
