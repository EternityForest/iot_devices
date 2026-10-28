"""JSON lines device that talks over a serial port.

The device watches a glob for serial devices, opens the first one it
finds and speaks newline delimited JSON over it.  Both ``\\n`` and
``\\r\\n`` line endings are accepted.  Lines that are not valid JSON are
ignored, and lines beginning with ``#`` are printed to the host, which
makes it easy to add debug output to a microcontroller firmware.
"""

from __future__ import annotations

import glob
import json
import os
import time
from collections import deque
from collections.abc import Mapping
from threading import Event, RLock, Thread
from typing import Any

import serial

from . import JsonLinesDevice, extended_config_schema

MAX_LINE_BYTES = 65536
"""Largest partial line buffered before it is assumed to be garbage."""


class SerialJsonLines(JsonLinesDevice):
    """Talk JSON lines over a serial port found by globbing a pattern.

    The device keeps a background thread that finds the first file
    matching ``serial_glob``, opens it, and retries forever.  If the
    port disappears (for example a USB adapter is unplugged) the thread
    notices, closes the port, and waits for it to come back.
    """

    device_type = "SerialJsonLines"

    config_schema = extended_config_schema(
        serial_glob={
            "type": "string",
            "title": "Serial device glob",
            "default": "",
            "description": (
                "Glob pattern for the serial device, for example "
                "/dev/ttyUSB*.  The first matching file is used."
            ),
        },
        baudrate={
            "type": "integer",
            "title": "Baud rate",
            "default": 115200,
        },
        reconnect_interval={
            "type": "number",
            "title": "Reconnect interval",
            "default": 1,
            "description": ("Seconds to wait before retrying after a failure."),
        },
        max_queue={
            "type": "integer",
            "title": "Maximum queued packets",
            "default": 256,
            "description": (
                "Oldest outgoing packets are dropped once this many are "
                "waiting for the port to become writable."
            ),
        },
    )

    def __init__(self, config: dict[str, Any], **kw: Any):
        super().__init__(config, **kw)

        self.serial_glob = str(self.config.get("serial_glob", ""))
        if not self.serial_glob:
            raise ValueError("serial_glob must be set")

        self.baudrate = int(self.config.get("baudrate", 115200))
        self.reconnect_interval = float(
            self.config.get("reconnect_interval", 1)
        )
        self.max_queue = int(self.config.get("max_queue", 256))

        if self.reconnect_interval <= 0:
            raise ValueError("reconnect_interval must be greater than zero")
        if self.max_queue <= 0:
            raise ValueError("max_queue must be greater than zero")

        self.write_queue: deque[bytes] = deque()
        self.write_lock = RLock()

        self._stop = Event()
        self._error_reported = False

        self._thread = Thread(
            target=self._run,
            name="SerialJsonLines:" + self.name,
            daemon=True,
        )
        self._thread.start()

    # -- public API ------------------------------------------------------

    def push_json(self, data: Mapping[str, Any]) -> None:
        """Queue one packet to be written as a JSON line."""
        line = (json.dumps(data) + "\n").encode()
        with self.write_lock:
            if len(self.write_queue) >= self.max_queue:
                self.write_queue.popleft()
            self.write_queue.append(line)

    def wait_ready(self, timeout: float = 15) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.datapoints["connection.connected"].get()[0]:
                return
            time.sleep(0.01)
        raise TimeoutError(f"{self.name} did not connect within {timeout}s")

    def on_before_close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        super().on_before_close()

    # -- background thread ----------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            path = self._find_port()
            if path is None:
                self._stop.wait(self.reconnect_interval)
                continue

            try:
                port = serial.Serial(
                    path,
                    baudrate=self.baudrate,
                    timeout=0.1,
                    write_timeout=1,
                )
            except Exception:
                self._report_error()
                self._stop.wait(self.reconnect_interval)
                continue

            try:
                self._serve(port)
            except Exception:
                self._report_error()
            finally:
                try:
                    port.close()
                except Exception:
                    self.handle_exception()
                self._mark_disconnected()

            if not self._stop.is_set():
                self._stop.wait(self.reconnect_interval)

    def _find_port(self) -> str | None:
        """Return the first glob match that is not a directory.

        Serial ports are character devices (or symlinks to them), so a
        plain file check would wrongly reject them.
        """
        for match in sorted(glob.glob(self.serial_glob)):
            if os.path.exists(match) and not os.path.isdir(match):
                return match
        return None

    def _serve(self, port: serial.Serial) -> None:
        """Run one connection session, returning when it breaks."""
        self._error_reported = False
        self.discard_pending()
        with self.write_lock:
            self.write_queue.clear()

        self._send_state(port)
        self._mark_connected()

        buffer = bytearray()
        while not self._stop.is_set():
            self._flush_queue(port)

            chunk = port.read(port.in_waiting or 1)
            if not chunk:
                continue

            buffer.extend(chunk)
            if len(buffer) > MAX_LINE_BYTES:
                buffer.clear()
                continue

            while b"\n" in buffer:
                raw, _, rest = buffer.partition(b"\n")
                buffer = bytearray(rest)
                self._handle_json_line(raw)

    def _send_state(self, port: serial.Serial) -> None:
        state = self.get_state()
        if state:
            port.write((json.dumps(state) + "\n").encode())
            port.flush()

    def _flush_queue(self, port: serial.Serial) -> None:
        with self.write_lock:
            if not self.write_queue:
                return
            pending = list(self.write_queue)
            self.write_queue.clear()

        port.write(b"".join(pending))
        port.flush()

    def _report_error(self) -> None:
        """Report a connection failure once per outage."""
        if not self._error_reported:
            self._error_reported = True
            self.handle_exception()
