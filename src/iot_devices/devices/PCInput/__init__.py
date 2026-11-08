"""Local PC input devices (keyboards, mice, etc) via python-evdev.

One device represents every Linux evdev input device whose
``"<path> <name> <phys>"`` string matches a keyword filter.  Key and
button presses are exposed through the ``key_event`` string datapoint,
while axis, relative and switch events are exposed as numeric
datapoints that are created on first use.

Devices are only ever opened read-only, so neither write access nor an
exclusive grab is needed.  A background thread periodically rescans
``/dev/input``, so devices may be plugged in or unplugged at any time.
"""

from __future__ import annotations

import glob
import logging
import os
import selectors
import stat
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, override

import evdev
from evdev import ecodes

import iot_devices.device

logger = logging.getLogger(__name__)

INPUT_DEVICE_GLOB = "/dev/input/event*"
"""Where the kernel exposes evdev input device nodes."""

POLL_INTERVAL = 5.0
"""How long a device reader waits for events between shutdown checks."""

DEFAULT_SCAN_INTERVAL = 15.0
"""Default number of seconds between scans for new devices."""

KEY_EVENT_DATAPPOINT = "key_event"
CONNECTED_DATAPPOINT = "connected"

_TYPE_MAPPINGS: dict[int, dict[int, Any]] = {
    ecodes.EV_ABS: ecodes.ABS,
    ecodes.EV_REL: ecodes.REL,
    ecodes.EV_SW: ecodes.SW,
}
"""Event type to ecodes name mapping for the numeric event types."""


def _scan_candidates() -> list[tuple[str, bool]]:
    """List evdev device nodes as (path, readable_by_this_user) pairs.

    ``evdev.list_devices()`` is not used because it silently drops
    devices that are not *writable*, which would hide permission
    problems from a read-only client like this one.
    """
    out: list[tuple[str, bool]] = []
    for path in sorted(glob.glob(INPUT_DEVICE_GLOB)):
        try:
            if not stat.S_ISCHR(os.stat(path).st_mode):
                continue
        except OSError:
            continue
        out.append((path, os.access(path, os.R_OK)))
    return out


def _open_device(path: str) -> evdev.InputDevice[str]:
    """Open one evdev device read-only and non-blocking."""
    return evdev.InputDevice(path)


def _resolve_name(mapping: Mapping[int, Any], code: int) -> str | None:
    """Return the canonical constant name for an event code.

    The ``ecodes`` mappings give some codes several names, presented
    as a list (272 is both BTN_LEFT and BTN_MOUSE, for example).  For
    keys and buttons the ``key_``/``btn_`` spelling is preferred.
    """
    value = mapping.get(code)
    if isinstance(value, (list, tuple)):
        for candidate in value:
            if isinstance(candidate, str) and candidate.lower().startswith(
                ("key_", "btn_")
            ):
                return candidate
        value = value[0] if value else None
    return value if isinstance(value, str) else None


def _event_name(etype: int, code: int) -> str | None:
    """Resolve the name of an event we care about, else None."""
    if etype == ecodes.EV_KEY:
        # Buttons are looked up first so they keep their btn_ names.
        return _resolve_name(ecodes.BTN, code) or _resolve_name(
            ecodes.KEY, code
        )
    return _resolve_name(_TYPE_MAPPINGS.get(etype, {}), code)


@dataclass
class _TrackedDevice:
    """One currently open input device and its reader thread."""

    path: str
    device_string: str
    device: evdev.InputDevice[str]
    thread: threading.Thread | None = None


class PCInputDevice(iot_devices.device.Device):
    """Aggregate local evdev input devices matching a keyword filter.

    The ``device_filter`` config is split on whitespace, and a device
    matches when every keyword appears, case insensitively, in its
    full ``"<path> <name> <phys>"`` string.  A blank filter matches
    every device.

    Datapoints:

    ``key_event``
        String.  Set to ``<name>_down`` or ``<name>_up`` (for example
        ``key_a_down``) for every ``key_`` or ``btn_`` event.  Repeat
        events count as down.

    ``connected``
        Numeric.  How many matching devices are currently open.

    ``<event code>``
        One numeric datapoint per ``abs``, ``rel`` or ``sw`` event
        code seen (``abs_x``, ``rel_wheel``, ``sw_lid``, ...), created
        the first time such an event arrives.
    """

    device_type = "PCInputDevice"

    config_schema = {
        "type": "object",
        "properties": {
            "device_filter": {
                "type": "string",
                "title": "Device filter",
                "default": "keyboard",
                "description": (
                    "Space separated keywords.  A device matches when "
                    "every keyword appears, case insensitively, in its "
                    "'<path> <name> <phys>' string.  Blank matches all."
                ),
            },
            "scan_interval": {
                "type": "number",
                "title": "Scan interval",
                "default": DEFAULT_SCAN_INTERVAL,
                "description": (
                    "Seconds between scans for newly plugged input devices."
                ),
            },
        },
    }

    def __init__(self, config: dict[str, Any], **kw: Any):
        iot_devices.device.Device.__init__(self, config, **kw)

        self.lock = threading.RLock()

        raw = str(self.config.get("device_filter", "keyboard"))
        self.keywords: list[str] = [
            word for word in (w.strip() for w in raw.split()) if word
        ]

        self.scan_interval = float(
            self.config.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        )
        if self.scan_interval <= 0:
            raise ValueError("scan_interval must be greater than zero")

        self._stop = threading.Event()
        self._devices: dict[str, _TrackedDevice] = {}
        self._connected = 0
        self._error_reported = False
        self.metadata["devices"] = []  # type: ignore

        self.string_data_point(
            KEY_EVENT_DATAPPOINT,
            writable=False,
            description=(
                "Last key or button event, as '<name>_down' or '<name>_up'."
            ),
        )
        self.numeric_data_point(
            CONNECTED_DATAPPOINT,
            min=0,
            default=0,
            writable=False,
            unit="devices",
            description="Number of matching input devices connected.",
        )

        # Fail loudly instead of silently reporting zero devices when
        # the user lacks permission to read input devices.
        candidates = _scan_candidates()
        if candidates and not any(r for _p, r in candidates):
            raise PermissionError(
                "This user has no read access to any /dev/input/event* "
                "device.  Add the user to the 'input' group and log in "
                "again, e.g. 'sudo usermod -aG input $USER'."
            )

        self._thread = threading.Thread(
            target=self._run, name=f"PCInput:{self.name}", daemon=True
        )
        self._thread.start()

    # -- datapoint handling ----------------------------------------------

    def _process_event(self, event: Any) -> None:
        """Map one raw evdev event to datapoint updates."""
        name = _event_name(event.type, event.code)
        if name is None:
            return
        lowered = name.lower()

        if event.type == ecodes.EV_KEY:
            if not lowered.startswith(("key_", "btn_")):
                return
            suffix = "up" if not event.value else "down"
            self.set_data_point(KEY_EVENT_DATAPPOINT, f"{lowered}_{suffix}")
            return

        # abs, rel and sw events each feed a numeric datapoint.
        self._ensure_numeric_datapoint(lowered)
        self.set_data_point(lowered, event.value)

    def _ensure_numeric_datapoint(self, name: str) -> None:
        """Create a numeric datapoint for an abs/rel/sw code once."""
        with self.lock:
            if name in self.datapoints:
                return
            self.numeric_data_point(
                name,
                writable=False,
                description=f"Raw {name.upper()} input events.",
            )

    # -- device tracking ---------------------------------------------------

    def _matches(self, device_string: str) -> bool:
        """Check every filter keyword against a device string."""
        lowered = device_string.lower()
        return all(word in lowered for word in self.keywords)

    def _run(self) -> None:
        """Periodically scan for matching devices until closed."""
        while not self._stop.is_set():
            try:
                self._scan()
            except Exception:
                self.handle_exception()
            self._stop.wait(self.scan_interval)

    def _scan(self) -> None:
        """Open any new matching devices and update the count."""
        for path, readable in _scan_candidates():
            with self.lock:
                known = path in self._devices
            if known:
                continue
            if not readable:
                logger.debug("Skipping unreadable input device %s", path)
                continue

            try:
                dev = _open_device(path)
            except OSError:
                # Permission races and devices that died mid-scan.
                self._report_error()
                continue
            except Exception:
                self.handle_exception()
                continue

            device_string = f"{dev.path} {dev.name} {dev.phys}"
            if not self._matches(device_string):
                self._close(dev)
                continue

            record = _TrackedDevice(
                path=path, device_string=device_string, device=dev
            )
            with self.lock:
                if self._stop.is_set() or path in self._devices:
                    # Closing, or a reader for this path just appeared.
                    self._close(dev)
                    continue
                self._devices[path] = record
                self._error_reported = False

            self.print(f"Connected to input device: {device_string}")
            record.thread = threading.Thread(
                target=self._reader,
                args=(record,),
                name=f"PCInput:{self.name}:{path}",
                daemon=True,
            )
            record.thread.start()

        self._update_connected()
        self._refresh_metadata()

    def _reader(self, record: _TrackedDevice) -> None:
        """Pump events from one device until it goes away or we close."""
        dev = record.device
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(dev.fd, selectors.EVENT_READ)
                while not self._stop.is_set():
                    if not sel.select(POLL_INTERVAL):
                        continue
                    try:
                        events = list(dev.read())
                    except BlockingIOError:
                        continue
                    except OSError:
                        # The device was unplugged or otherwise vanished.
                        break
                    for event in events:
                        try:
                            self._process_event(event)
                        except Exception:
                            self.handle_exception()
        except Exception:
            if not self._stop.is_set():
                self.handle_exception()
        finally:
            self._forget(record)

    def _forget(self, record: _TrackedDevice) -> None:
        """Drop a device after its reader finished, for any reason."""
        with self.lock:
            if self._devices.get(record.path) is record:
                del self._devices[record.path]
        self._close(record.device)
        self._update_connected()
        self._refresh_metadata()

    def _update_connected(self) -> None:
        """Push the number of open devices to the datapoint."""
        with self.lock:
            count = len(self._devices)
        if count != self._connected:
            self._connected = count
            self.set_data_point(CONNECTED_DATAPPOINT, count)

    def _refresh_metadata(self) -> None:
        """Expose the full strings of the connected devices."""
        with self.lock:
            devices = sorted(r.device_string for r in self._devices.values())
        self.metadata["devices"] = devices

    def _report_error(self) -> None:
        """Report a scan failure once per outage."""
        if not self._error_reported:
            self._error_reported = True
            self.handle_exception()

    @staticmethod
    def _close(dev: evdev.InputDevice[str]) -> None:
        """Close a device, ignoring errors from an already dead one."""
        try:
            dev.close()
        except Exception:
            logger.debug("Error closing input device", exc_info=True)

    @override
    def on_before_close(self) -> None:
        self._stop.set()

        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)

        with self.lock:
            records = list(self._devices.values())
        for record in records:
            self._close(record.device)
        for record in records:
            if record.thread is not None:
                record.thread.join(timeout=POLL_INTERVAL * 4)

        super().on_before_close()
