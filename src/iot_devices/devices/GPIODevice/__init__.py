"""GPIO input and output devices built on libgpiod (the ``gpiod`` client).

Unlike gpiozero, libgpiod has no software PWM, so output values are treated
as on/off.  Pins named like ``MOCK1`` are served by a small in-process mock
(see :mod:`.mock`) so the devices can be used and tested without hardware.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from typing import Any, override

from gpiod.line import Bias, Value

from iot_devices import device

from . import backend, mock

WATCH_TIMEOUT = 0.5
"""How long an input watcher blocks for edge events before re-reading."""

gpio_config_schema = {
    "type": "object",
    "properties": {
        "pin": {"type": "string", "default": "MOCK1"},
        "active_high": {"type": "boolean", "default": True},
        "initial_value": {"type": "number", "min": 0, "max": 1},
        "pull_up": {"type": "boolean", "default": False},
        "pull_down": {"type": "boolean", "default": False},
        "debounce_time_ms": {"type": "integer", "default": 0},
    },
    "required": ["pin"],
}


def _discover_pins(device_type: str) -> dict[str, dict[str, Any]]:
    """Suggest configs for every usable GPIO line on the system."""
    try:
        pins = backend.list_available_pins(include_mock=False)
    except Exception:
        return {"MOCK1": {"type": device_type, "pin": "MOCK1"}}

    if not pins:
        return {"MOCK1": {"type": device_type, "pin": "MOCK1"}}

    suggestions: dict[str, dict[str, Any]] = {}
    for line in pins:
        if line.used and backend.consumer_is_blocked(line.consumer):
            continue
        spec = backend.pin_spec_for(line)
        label = f"{spec} ({line.line_name})" if line.line_name else spec
        suggestions[label] = {"type": device_type, "pin": spec}
    return suggestions


class GPIOOutput(device.Device):
    device_type = "GPIOOutput"
    config_schema = gpio_config_schema

    upgrade_legacy_config_keys = {
        "device.pin": "pin",
        "device.active_high": "active_high",
        "device.initial_value": "initial_value",
    }

    def __init__(self, data: dict[str, Any], **kw: Any):
        device.Device.__init__(self, data, **kw)

        self.line: backend.ResolvedLine | None = None
        self.request: Any = None

        try:
            self.set_config_default("initial_value", 0)

            active_high = self.config["active_high"]
            initial_active = float(self.config["initial_value"]) >= 0.5

            line = backend.resolve_name(self.config["pin"])
            request = backend.open_output_line(
                line,
                active_low=not active_high,
                initial_active=initial_active,
                consumer=backend.CONSUMER_NAME + ": " + self.name,
            )
            self.line = line
            self.request = request
            self.metadata["driver"] = backend.describe_line(line)

            # Push type data point set by the device
            self.numeric_data_point(
                "value",
                writable=True,
                subtype="boolean",
                min=0,
                max=1,
                handler=self._set_pin,
                default=float(self.config["initial_value"]),
            )
            self.set_data_point("value", 1 if initial_active else 0)
        except Exception:
            self.handle_exception()

    @staticmethod
    @override
    def discover_devices(
        config: dict[str, Any],
        current_device: object | None = None,
        intent: str = "",
        **kwargs: Any,
    ) -> dict[str, dict[str, Any]]:
        return _discover_pins("GPIOOutput")

    def _set_pin(self, v: float, t: float, a: Any) -> None:
        if self.request is not None and self.line is not None:
            active = v >= 0.5
            self.request.set_value(
                self.line.offset,
                Value.ACTIVE if active else Value.INACTIVE,
            )

    @override
    def on_before_close(self):
        try:
            if self.request is not None:
                self.request.release()
                self.request = None
        except Exception:
            self.handle_exception()


class GPIOInput(device.Device):
    device_type = "GPIOInput"

    config_schema = {
        "type": "object",
        "properties": {
            "pin": {"type": "string", "default": "MOCK1"},
            "active_high": {"type": "boolean", "default": True},
            "pull_up": {"type": "boolean", "default": False},
            "pull_down": {"type": "boolean", "default": False},
            "debounce_time_ms": {"type": "integer", "default": 0},
        },
    }

    upgrade_legacy_config_keys = {
        "device.pin": "pin",
        "device.active_high": "active_high",
        "device.pull_up": "pull_up",
        "device.pull_down": "pull_down",
        "device.debounce_time_ms": "debounce_time_ms",
    }

    def __init__(self, data: dict[str, Any], **kw: Any):
        device.Device.__init__(self, data, **kw)

        self.line: backend.ResolvedLine | None = None
        self.request: Any = None
        self._stop = threading.Event()
        self._watcher: threading.Thread | None = None
        self._last = 0

        try:
            active_high = self.config["active_high"]
            bias = self._resolve_bias(active_high)
            debounce = timedelta(
                milliseconds=int(self.config["debounce_time_ms"])
            )

            line = backend.resolve_name(self.config["pin"])
            request = backend.open_input_line(
                line,
                active_low=not active_high,
                bias=bias,
                debounce_period=debounce,
                consumer=backend.CONSUMER_NAME + ": " + self.name,
            )
            self.line = line
            self.request = request
            self.metadata["driver"] = backend.describe_line(line)

            value = 1 if request.get_value(line.offset) else 0
            self._last = value

            self.numeric_data_point(
                "value",
                writable=False,
                min=0,
                max=1,
                subtype="boolean",
                default=value,
            )
            self.set_data_point("value", value)

            self._watcher = threading.Thread(
                target=self._watch,
                name=f"{self.name}-gpio",
                daemon=True,
            )
            self._watcher.start()
        except Exception:
            self.handle_exception()

    @staticmethod
    @override
    def discover_devices(
        config: dict[str, Any],
        current_device: object | None = None,
        intent: str = "",
        **kwargs: Any,
    ) -> dict[str, dict[str, Any]]:
        return _discover_pins("GPIOInput")

    def _resolve_bias(self, active_high: bool) -> Bias:
        """Translate the pull_up/pull_down config into a gpiod bias."""
        pull_up = self.config["pull_up"]
        pull_down = self.config["pull_down"]

        if pull_up and pull_down:
            raise ValueError("Can't have pull up and pull down")
        if pull_up:
            if active_high:
                raise ValueError("Can't have pull up and active high")
            return Bias.PULL_UP
        if pull_down:
            if not active_high:
                raise ValueError("Can't have pull down and active low")
            return Bias.PULL_DOWN
        return Bias.AS_IS

    def _watch(self) -> None:
        """Block on edge events, mirroring the line into the datapoint."""
        request = self.request
        line = self.line
        if request is None or line is None:
            return

        while not self._stop.is_set():
            try:
                request.wait_edge_events(WATCH_TIMEOUT)
                request.read_edge_events()
                value = 1 if request.get_value(line.offset) else 0
            except Exception:
                if self._stop.is_set():
                    break
                self.handle_exception()
                break

            if value != self._last:
                self._last = value
                self.set_data_point("value", value)

    def test_val(self, x: bool):
        """Drive the underlying mock pin.  Mock pins only."""
        if self.line is not None and self.line.mock:
            mock.drive_line(self.line.chip_path, self.line.offset, x)
        else:
            self.print("test_val is only supported for mock pins")

    @override
    def on_before_close(self):
        self._stop.set()
        try:
            if self.request is not None:
                self.request.release()
        except Exception:
            self.handle_exception()
        if self._watcher is not None:
            self._watcher.join(timeout=WATCH_TIMEOUT * 4)
        self.request = None
