"""End to end tests for :class:`UDPJsonLines`.

Real UDP sockets on the loopback interface are used, covering unicast,
broadcast and multicast.  The device talks to a peer socket owned by the
test, so address resolution, socket setup and the incoming packet
filtering are all exercised for real.
"""

from __future__ import annotations

import json
import socket
import struct
import time
from collections.abc import Iterator
from typing import Any, cast

import pytest

from iot_devices.devices.JsonLines.udp import UDPJsonLines

from .recording_host import RecordingHost

GROUP = "239.255.42.99"
BROADCAST = "127.255.255.255"


def free_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for an unused UDP port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


class Peer:
    """A plain UDP socket used as the remote peer in the tests."""

    def __init__(
        self,
        bind: tuple[str, int],
        group: str | None = None,
        interface: str = "127.0.0.1",
    ) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(bind)
        if group is not None:
            membership = struct.pack(
                "4s4s",
                socket.inet_aton(group),
                socket.inet_aton(interface),
            )
            self.sock.setsockopt(
                socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership
            )
            self.sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_IF,
                socket.inet_aton(interface),
            )
        self.sock.settimeout(0.05)

    def send(self, data: bytes, dest: tuple[str, int]) -> None:
        self.sock.sendto(data, dest)

    def packets(
        self, count: int = 1, timeout: float = 3.0
    ) -> list[dict[str, Any]]:
        """Read up to ``count`` JSON packets sent by the device."""
        deadline = time.monotonic() + timeout
        buffer = bytearray()
        result: list[dict[str, Any]] = []

        while len(result) < count and time.monotonic() < deadline:
            try:
                chunk = self.sock.recv(65536)
            except TimeoutError:
                continue
            buffer.extend(chunk)
            while b"\n" in buffer:
                raw, _, rest = buffer.partition(b"\n")
                buffer = bytearray(rest)
                raw = raw.strip()
                if raw:
                    result.append(json.loads(raw))

        return result

    def close(self) -> None:
        self.sock.close()


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


KEYS: dict[str, dict[str, Any]] = {
    "foo": {"local_name": "foo", "type": "number", "output": True},
    "bar": {"local_name": "bar", "type": "string"},
}


def add_device(host: RecordingHost, **overrides: Any) -> UDPJsonLines:
    config: dict[str, Any] = {
        "type": "UDPJsonLines",
        "name": "udp",
        "reconnect_interval": 0.2,
        "keys": KEYS,
    }
    config.update(overrides)
    dev = host.add_new_device(config).wait_device_ready()
    return cast(UDPJsonLines, dev)


def test_unicast_round_trip(host: RecordingHost) -> None:
    remote_port = free_port()
    peer = Peer(("127.0.0.1", remote_port))
    local_port = free_port()

    dev = add_device(
        host,
        local_address=f"127.0.0.1:{local_port}",
        remote_address=f"127.0.0.1:{remote_port}",
    )
    dev.wait_ready()

    dev.set_data_point("foo", 3)
    assert peer.packets(1) == [{"foo": 3}]

    peer.send(b'{"bar": "hi"}\n', ("127.0.0.1", local_port))
    wait_for(lambda: dev.datapoints["bar"].get()[0] == "hi")
    peer.close()


def test_ignores_packets_from_other_sources(host: RecordingHost) -> None:
    remote_port = free_port()
    peer = Peer(("127.0.0.1", remote_port))
    local_port = free_port("127.0.0.2")

    dev = add_device(
        host,
        local_address=f"127.0.0.2:{local_port}",
        remote_address=f"127.0.0.1:{remote_port}",
    )
    dev.wait_ready()

    # A third party on a different IP must be ignored.
    rogue = Peer(("127.0.0.3", free_port("127.0.0.3")))
    rogue.send(b'{"bar": "evil"}\n', ("127.0.0.2", local_port))
    time.sleep(0.3)
    assert dev.datapoints["bar"].get()[0] is None

    # The configured remote is still accepted.
    peer.send(b'{"bar": "good"}\n', ("127.0.0.2", local_port))
    wait_for(lambda: dev.datapoints["bar"].get()[0] == "good")

    rogue.close()
    peer.close()


def test_multicast_round_trip(host: RecordingHost) -> None:
    local_port = free_port()
    remote_port = free_port()
    peer = Peer(("", remote_port), group=GROUP)

    dev = add_device(
        host,
        local_address=f"{GROUP}:{local_port}",
        remote_address=f"{GROUP}:{remote_port}",
        interface="127.0.0.1",
    )
    dev.wait_ready()

    dev.set_data_point("foo", 3)
    assert peer.packets(1) == [{"foo": 3}]

    peer.send(b'{"bar": "hi"}\n', (GROUP, local_port))
    wait_for(lambda: dev.datapoints["bar"].get()[0] == "hi")
    peer.close()


def test_broadcast_send(host: RecordingHost) -> None:
    remote_port = free_port()
    peer = Peer(("", remote_port))
    local_port = free_port()

    dev = add_device(
        host,
        local_address=f"0.0.0.0:{local_port}",
        remote_address=f"{BROADCAST}:{remote_port}",
    )
    dev.wait_ready()

    dev.set_data_point("foo", 3)
    assert peer.packets(1) == [{"foo": 3}]
    peer.close()


def test_resolves_hostname(host: RecordingHost) -> None:
    remote_port = free_port()
    peer = Peer(("127.0.0.1", remote_port))
    local_port = free_port()

    dev = add_device(
        host,
        local_address=f"127.0.0.1:{local_port}",
        remote_address=f"localhost:{remote_port}",
    )
    dev.wait_ready()

    wait_for(lambda: dev.remote_ip == "127.0.0.1")
    dev.set_data_point("foo", 1)
    assert peer.packets(1) == [{"foo": 1}]
    peer.close()


def test_re_resolves_remote_periodically(
    host: RecordingHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    addresses = ["127.0.0.1"]

    def fake_getaddrinfo(hostname: str, port: int, **kwargs: Any) -> list[Any]:
        return [
            (socket.AF_INET, socket.SOCK_DGRAM, 17, "", (addresses[0], port))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    dev = add_device(
        host,
        local_address=f"127.0.0.1:{free_port()}",
        remote_address=f"example.invalid:{free_port()}",
        resolve_interval=0.2,
    )
    dev.wait_ready()
    wait_for(lambda: dev.remote_ip == "127.0.0.1")

    # A new address must be picked up on the next resolve.
    addresses[0] = "127.0.0.2"
    wait_for(lambda: dev.remote_ip == "127.0.0.2")


def test_local_names_rebuild_the_socket(
    host: RecordingHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_getaddrinfo(hostname: str, port: int, **kwargs: Any) -> list[Any]:
        return [
            (socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("127.0.0.1", port))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    dev = add_device(
        host,
        local_address=f"127.0.0.1:{free_port()}",
        remote_address="sensor.local:9999",
        local_refresh_interval=0.2,
    )
    assert dev._needs_refresh() is True

    dev.wait_ready()
    first_socket = dev.sock
    assert first_socket is not None

    # The socket is rebuilt periodically for .local remotes.
    wait_for(
        lambda: dev.sock is not None and dev.sock is not first_socket,
        timeout=3.0,
    )


def test_plain_remote_does_not_need_refresh(
    host: RecordingHost,
) -> None:
    dev = add_device(
        host,
        local_address=f"127.0.0.1:{free_port()}",
        remote_address=f"127.0.0.1:{free_port()}",
    )
    assert dev._needs_refresh() is False


def test_missing_addresses_raise(host: RecordingHost) -> None:
    with pytest.raises(ValueError):
        host.add_new_device(
            {
                "type": "UDPJsonLines",
                "name": "udp",
                "local_address": "",
                "remote_address": "",
            }
        ).wait_device_ready()
