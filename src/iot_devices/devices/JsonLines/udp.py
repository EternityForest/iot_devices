"""JSON lines device that talks over UDP.

Unicast, broadcast and multicast peers are all supported.  The remote
address is periodically re-resolved, and when it is an mDNS ``.local``
name the socket is rebuilt every few minutes, because the socket can end
up bound to a stale interface after the network disconnects and
reconnects.

Incoming packets are dropped unless their source or destination IP
matches the latest remote address.  The destination check lets several
devices share one multicast group without acting on each other's
traffic.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import struct
import time
from collections.abc import Mapping
from threading import Event, RLock, Thread
from typing import Any

from . import JsonLinesDevice, extended_config_schema

logger = logging.getLogger(__name__)

LOCAL_SUFFIX = ".local"
MAX_PACKET_BYTES = 65536
RECV_TIMEOUT = 0.5


def parse_address(value: str) -> tuple[str, int]:
    """Split a ``host:port`` string, allowing a blank host."""
    host, sep, port = value.rpartition(":")
    if not sep or not port.isdigit():
        raise ValueError(f"Address {value!r} must look like host:port")
    return host, int(port)


def is_multicast(host: str) -> bool:
    """Return True if host is a numeric IPv4 multicast address."""
    try:
        return ipaddress.ip_address(host).is_multicast
    except ValueError:
        return False


class UDPJsonLines(JsonLinesDevice):
    """Exchange JSON lines with a UDP peer."""

    device_type = "UDPJsonLines"

    config_schema = extended_config_schema(
        local_address={
            "type": "string",
            "title": "Local address",
            "default": "0.0.0.0:5000",
            "description": (
                "Address to bind, as host:port.  Use a multicast group "
                "address to join that group."
            ),
        },
        remote_address={
            "type": "string",
            "title": "Remote address",
            "default": "",
            "description": (
                "Peer to send to, as host:port.  May be a hostname, "
                "including an mDNS .local name."
            ),
        },
        interface={
            "type": "string",
            "title": "Interface",
            "default": "",
            "description": (
                "Local interface IP used to send multicast and to join "
                "multicast groups.  Blank uses the OS default."
            ),
        },
        resolve_interval={
            "type": "number",
            "title": "Resolve interval",
            "default": 60,
            "description": "Seconds between re-resolving the remote host.",
        },
        local_refresh_interval={
            "type": "number",
            "title": "mDNS refresh interval",
            "default": 300,
            "description": (
                "For .local remote names, seconds between rebuilding the "
                "socket."
            ),
        },
        reconnect_interval={
            "type": "number",
            "title": "Reconnect interval",
            "default": 5,
            "description": ("Seconds to wait before retrying after a failure."),
        },
    )

    def __init__(self, config: dict[str, Any], **kw: Any):
        super().__init__(config, **kw)

        local = str(self.config.get("local_address", ""))
        remote = str(self.config.get("remote_address", ""))
        if not local:
            raise ValueError("local_address must be set")
        if not remote:
            raise ValueError("remote_address must be set")

        self.local_host, self.local_port = parse_address(local)
        self.remote_host, self.remote_port = parse_address(remote)
        self.interface = str(self.config.get("interface", ""))

        self.resolve_interval = float(self.config.get("resolve_interval", 60))
        self.local_refresh_interval = float(
            self.config.get("local_refresh_interval", 300)
        )
        self.reconnect_interval = float(
            self.config.get("reconnect_interval", 5)
        )
        for name, value in (
            ("resolve_interval", self.resolve_interval),
            ("local_refresh_interval", self.local_refresh_interval),
            ("reconnect_interval", self.reconnect_interval),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")

        self.sock_lock = RLock()
        self.sock: socket.socket | None = None
        self.remote_ip: str | None = None
        self.remote_is_multicast = is_multicast(self.remote_host)
        self.remote_sockaddr: tuple[str, int] | None = None

        self._stop = Event()
        self._error_reported = False

        self.numeric_data_point(
            "connected",
            min=0,
            max=1,
            default=0,
            subtype="bool",
            writable=False,
        )

        self._thread = Thread(
            target=self._run,
            name="UDPJsonLines:" + self.name,
            daemon=True,
        )
        self._thread.start()

    # -- public API ------------------------------------------------------

    def push_json(self, data: Mapping[str, Any]) -> None:
        """Send one packet to the peer, if the socket is ready."""
        line = (json.dumps(data) + "\n").encode()
        with self.sock_lock:
            sock = self.sock
            addr = self.remote_sockaddr
            if sock is None or addr is None:
                return
            try:
                sock.sendto(line, addr)
            except OSError:
                self.handle_exception()

    def wait_ready(self, timeout: float = 15) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.datapoints["connected"].get()[0]:
                return
            time.sleep(0.01)
        raise TimeoutError(f"{self.name} did not connect within {timeout}s")

    def on_before_close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._close_socket()
        super().on_before_close()

    # -- background thread ----------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._open_socket()
                self._resolve_remote()
            except Exception:
                self._report_error()
                self._stop.wait(self.reconnect_interval)
                continue

            self._serve()

            if not self._stop.is_set():
                self._stop.wait(self.reconnect_interval)

    def _serve(self) -> None:
        """Run one connection session, returning when it breaks."""
        self._error_reported = False
        self.discard_pending()
        self.set_data_point("connected", 1)
        self._send_state()

        next_resolve = time.monotonic() + self.resolve_interval
        next_refresh = time.monotonic() + self.local_refresh_interval

        try:
            while not self._stop.is_set():
                now = time.monotonic()

                if now >= next_resolve:
                    next_resolve = now + self.resolve_interval
                    self._refresh_remote()

                if self._needs_refresh() and now >= next_refresh:
                    next_refresh = now + self.local_refresh_interval
                    self._replace_socket()
                    self._send_state()

                self._recv_once()
        except Exception:
            self._report_error()
        finally:
            self._close_socket()
            self.set_data_point("connected", 0)

    def _refresh_remote(self) -> None:
        """Re-resolve the remote, tolerating a transient failure."""
        try:
            self._resolve_remote()
        except Exception:
            logger.debug("Failed to re-resolve remote", exc_info=True)

    def _needs_refresh(self) -> bool:
        return self.remote_host.lower().endswith(LOCAL_SUFFIX)

    def _resolve_remote(self) -> None:
        infos = socket.getaddrinfo(
            self.remote_host, self.remote_port, type=socket.SOCK_DGRAM
        )
        for family, _type, _proto, _canon, sockaddr in infos:
            if family == socket.AF_INET:
                if sockaddr[0] != self.remote_ip:
                    self.remote_ip = sockaddr[0]
                    self.remote_sockaddr = sockaddr
                    self.print(f"Resolved {self.remote_host} to {sockaddr[0]}")
                return

        raise OSError(
            f"Could not resolve {self.remote_host!r} to an IPv4 address"
        )

    def _open_socket(self) -> None:
        with self.sock_lock:
            if self.sock is None:
                self.sock = self._create_socket()

    def _close_socket(self) -> None:
        with self.sock_lock:
            sock = self.sock
            self.sock = None

        if sock is not None:
            try:
                sock.close()
            except OSError:
                logger.debug("Failed to close socket", exc_info=True)

    def _replace_socket(self) -> None:
        self._close_socket()
        self._open_socket()

    def _create_socket(self) -> socket.socket:
        bind_host = self.local_host or "0.0.0.0"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_PKTINFO, 1)
            sock.bind((bind_host, self.local_port))

            if is_multicast(bind_host):
                self._join_group(sock, bind_host)

            if self.interface:
                sock.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_MULTICAST_IF,
                    socket.inet_aton(self.interface),
                )

            sock.settimeout(RECV_TIMEOUT)
        except Exception:
            sock.close()
            raise
        return sock

    def _join_group(self, sock: socket.socket, group: str) -> None:
        iface = self.interface or "0.0.0.0"
        membership = struct.pack(
            "4s4s", socket.inet_aton(group), socket.inet_aton(iface)
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)

    def _send_state(self) -> None:
        state = self.get_state()
        if state:
            self.push_json(state)

    def _recv_once(self) -> None:
        sock = self.sock
        if sock is None:
            raise OSError("Socket is not open")

        try:
            data, ancdata, _flags, addr = sock.recvmsg(MAX_PACKET_BYTES, 1024)
        except TimeoutError:
            return

        if not self._matches(addr[0], self._destination_ip(ancdata)):
            return

        for raw in data.split(b"\n"):
            self._handle_json_line(raw)

    def _matches(self, src_ip: str, dst_ip: str | None) -> bool:
        """Return True if a received packet belongs to our remote peer.

        A packet matches when its source is the remote address.  For a
        multicast remote the group address is the destination instead,
        so a matching destination is also accepted.  Everything else,
        such as traffic from other members of a shared multicast group,
        is dropped.
        """
        remote = self.remote_ip
        if remote is None:
            return False
        if src_ip == remote:
            return True
        return self.remote_is_multicast and dst_ip == remote

    @staticmethod
    def _destination_ip(ancdata: list[tuple[int, int, bytes]]) -> str | None:
        for level, kind, cmsg in ancdata:
            if level == socket.IPPROTO_IP and kind == socket.IP_PKTINFO:
                _ifindex, _spec_dst, dst = struct.unpack("=I4s4s", cmsg)
                return socket.inet_ntoa(dst)
        return None

    def _report_error(self) -> None:
        """Report a connection failure once per outage."""
        if not self._error_reported:
            self._error_reported = True
            self.handle_exception()
