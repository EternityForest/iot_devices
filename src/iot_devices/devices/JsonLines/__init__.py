"""Base class for devices that exchange JSON packets with a remote peer.

A concrete device only needs to implement
:meth:`JsonLinesDevice.push_json` and call
:meth:`JsonLinesDevice.on_json` with every packet it receives.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from collections.abc import Callable, Mapping
from threading import RLock
from typing import Any, NotRequired, TypedDict, final

from scullery import scheduling
from scullery.ratelimits import RateLimiter

import iot_devices.device

logger = logging.getLogger(__name__)

REMOTE_ANNOTATION = "FromRemoteDevice"
"""Annotation used for values that came from the remote peer.

Values set with this annotation are not echoed back to the peer unless
the ``echo`` config option is enabled.
"""

TRIGGER_SUBTYPES = ("bang", "trigger")
"""Subtypes representing one-shot events that must not be replayed."""


class KeyConfig(TypedDict):
    """Configuration for one key in the exchanged JSON packets."""

    local_name: str
    type: str
    subtype: NotRequired[str]
    output: NotRequired[bool]
    min: NotRequired[float]
    max: NotRequired[float]
    unit: NotRequired[str]


config_schema: dict[str, Any] = {
    "type": "object",
    "properties": {
        "keys": {
            "type": "object",
            "title": "Keys",
            "description": (
                "Mapping of remote JSON packet key names to local "
                "datapoint definitions."
            ),
            "default": {},
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "local_name": {
                        "type": "string",
                        "title": "Local name",
                    },
                    "type": {
                        "type": "string",
                        "title": "Type",
                        "enum": ["number", "string"],
                    },
                    "subtype": {
                        "type": "string",
                        "title": "Subtype",
                        "default": "",
                    },
                    "output": {
                        "type": "boolean",
                        "title": "Output",
                        "default": False,
                        "description": (
                            "If true, the datapoint is writable and its "
                            "value is pushed to the remote peer."
                        ),
                    },
                    "min": {"type": "number", "title": "Minimum"},
                    "max": {"type": "number", "title": "Maximum"},
                    "unit": {
                        "type": "string",
                        "title": "Unit",
                        "default": "",
                    },
                },
                "required": ["local_name", "type"],
                "additionalProperties": False,
            },
        },
        "rate_limit": {
            "type": "number",
            "title": "Rate limit",
            "default": 10,
            "description": (
                "Maximum outgoing packets per second, with bursts allowed "
                "up to the burst size."
            ),
        },
        "burst": {
            "type": "number",
            "title": "Burst",
            "default": 100,
            "description": (
                "Maximum number of packets that may be sent back to back."
            ),
        },
        "echo": {
            "type": "boolean",
            "title": "Echo",
            "default": False,
            "description": (
                "If set, values received from the remote peer are sent "
                "back to it."
            ),
        },
    },
}


def extended_config_schema(**extra_properties: Any) -> dict[str, Any]:
    """Return the base config schema with extra top level properties.

    Subclasses use this so they only have to describe the options their
    transport adds, rather than repeating the shared ``keys``,
    rate limiting and echo options.

    Args:
        **extra_properties: JSON schema fragments to add, keyed by the
            property name.
    """
    schema = copy.deepcopy(config_schema)
    schema["properties"].update(extra_properties)
    return schema


class JsonLinesDevice(iot_devices.device.Device):
    """Base class for a family of JSON key/value devices.

    Subclasses implement :meth:`push_json` to transmit a packet and call
    :meth:`on_json` for every packet received.  All rate limiting,
    echo suppression and reconnect state handling is done here.

    Each entry in the ``keys`` config maps a remote JSON key name to a
    local datapoint.  Keys marked ``output`` become writable datapoints
    whose values are pushed to the peer; all other keys are read only and
    are only ever written by incoming packets.
    """

    device_type = "JsonLinesDevice"

    config_schema = config_schema

    def __init__(self, config: dict[str, Any], **kw: Any):
        super().__init__(config, **kw)

        self.lock = RLock()

        # Pending outgoing packet, keyed by remote JSON key name.
        self.outgoing: dict[str, Any] = {}
        self.scheduled_flush: scheduling.Event | None = None

        self.rate_limit = float(self.config.get("rate_limit", 10))
        self.burst = float(self.config.get("burst", 100))
        self.echo = bool(self.config.get("echo", False))

        if self.rate_limit <= 0:
            raise ValueError("rate_limit must be greater than zero")

        self.ratelimiter = RateLimiter(self.rate_limit, self.burst)

        keys: dict[str, KeyConfig] = dict(self.config.get("keys", {}))
        self.keys = keys

        # Maps local datapoint names back to their remote key names.
        self.local_to_remote: dict[str, str] = {}

        for remote_name, key in keys.items():
            self._add_datapoint(remote_name, key)

    def _add_datapoint(self, remote_name: str, key: KeyConfig) -> None:
        """Create the datapoint for a single ``keys`` entry."""
        local_name = key["local_name"]

        if local_name in self.local_to_remote:
            raise ValueError(
                f"Duplicate local_name {local_name!r} in keys config"
            )
        self.local_to_remote[local_name] = remote_name

        subtype = key.get("subtype", "")
        output = bool(key.get("output", False))

        handler: Callable[[Any, float, Any], None] | None = None
        if output:
            handler = self._make_handler(remote_name)

        if key["type"] == "number":
            self.numeric_data_point(
                local_name,
                min=key.get("min"),
                max=key.get("max"),
                unit=key.get("unit", ""),
                subtype=subtype,
                writable=output,
                handler=handler,
            )
        elif key["type"] == "string":
            self.string_data_point(
                local_name,
                unit=key.get("unit", ""),
                subtype=subtype,
                writable=output,
                handler=handler,
            )
        else:
            raise ValueError(
                f"Unsupported key type {key['type']!r} for {local_name!r}"
            )

    def _make_handler(
        self, remote_name: str
    ) -> Callable[[Any, float, Any], None]:
        """Build the datapoint handler that queues an outgoing value."""

        def handler(value: Any, timestamp: float, annotation: Any) -> None:
            # Never echo a value straight back at the peer unless asked to.
            if annotation == REMOTE_ANNOTATION and not self.echo:
                return

            with self.lock:
                self.outgoing[remote_name] = value
            self._maybe_send()

        return handler

    def _credits_available(self) -> float:
        """Return how many rate limit credits are currently available.

        This mirrors the refill calculation of
        :class:`scullery.ratelimits.RateLimiter` without consuming a
        credit.  ``RateLimiter.limit()`` returns the credits *remaining*
        after it consumes one, which is a tiny positive float rather
        than zero when the last credit is used, so its return value
        cannot be used to decide between an immediate and a deferred
        send.
        """
        limiter = self.ratelimiter
        elapsed = max(0.0, time.monotonic() - limiter.timestamp)
        return min(
            limiter.current_limit + limiter.rate * elapsed,
            limiter.accum_limit,
        )

    def _maybe_send(self) -> None:
        """Send the pending packet now, or schedule it if rate limited.

        If a send is already scheduled the pending values are simply
        merged into the packet that is already queued.
        """
        with self.lock:
            if not self.outgoing:
                return
            if self.scheduled_flush is not None:
                return

            if self._credits_available() >= 1:
                self.ratelimiter.limit()
                packet = self.outgoing
                self.outgoing = {}
            else:
                self.scheduled_flush = scheduling.scheduler.schedule(
                    self._flush, time.time() + (1.0 / self.rate_limit)
                )
                return

        self._push(packet)

    def _flush(self) -> None:
        """Scheduled callback that pushes whatever is pending."""
        with self.lock:
            self.scheduled_flush = None
            self.ratelimiter.limit()
            packet = self.outgoing
            self.outgoing = {}

        if packet:
            self._push(packet)

    def _push(self, packet: dict[str, Any]) -> None:
        try:
            self.push_json(packet)
        except Exception:
            self.handle_exception()

    @final
    def on_json(self, data: Mapping[str, Any]) -> None:
        """Handle one JSON packet received from the remote peer.

        Any queued outgoing value for a received key is discarded, so a
        value from the peer always overwrites one waiting to be sent.
        The received value is then stored in the matching local
        datapoint.
        """
        with self.lock:
            for remote_name in data:
                self.outgoing.pop(remote_name, None)

        for remote_name, value in data.items():
            key = self.keys.get(remote_name)
            if key is None:
                continue
            try:
                self.set_data_point(
                    key["local_name"],
                    value,
                    annotation=REMOTE_ANNOTATION,
                )
            except Exception:
                # A single bad value must not tear down the transport.
                self.handle_exception()

    def _handle_json_line(self, raw: bytes) -> None:
        """Feed one newline delimited packet to :meth:`on_json`.

        Blank and malformed lines are ignored, and lines beginning with
        ``#`` are printed to the host so firmware can add debug output
        to the stream.
        """
        line = raw.strip()
        if not line:
            return

        if line.startswith(b"#"):
            self.print(line.decode("utf-8", "replace"))
            return

        try:
            data = json.loads(line)
        except ValueError:
            # Malformed lines are ignored by design.
            return

        if isinstance(data, dict):
            self.on_json(data)

    def discard_pending(self) -> None:
        """Drop any values waiting to be sent to the peer.

        Subclasses call this when they (re)connect, because the peer is
        resynced from :meth:`get_state` instead.  This also stops
        one-shot ``bang``/``trigger`` values from being delivered late.
        """
        with self.lock:
            event = self.scheduled_flush
            self.scheduled_flush = None
            self.outgoing = {}

        if event is not None:
            try:
                event.unregister()
            except Exception:
                logger.debug("Failed to unregister flush event", exc_info=True)

    def get_state(self) -> dict[str, Any]:
        """Return the current state of every output datapoint.

        This is meant to be sent to the peer when reconnecting so it can
        be resynced.  One-shot ``bang``/``trigger`` outputs are skipped,
        as they represent events that must not be replayed.
        """
        state: dict[str, Any] = {}

        for remote_name, key in self.keys.items():
            if not key.get("output", False):
                continue
            if key.get("subtype", "") in TRIGGER_SUBTYPES:
                continue

            value, _timestamp, _annotation = self.datapoints[
                key["local_name"]
            ].get()
            if value is not None:
                state[remote_name] = value

        return state

    def push_json(self, data: Mapping[str, Any]) -> None:
        """Send a JSON-serializable packet to the remote peer.

        Subclasses must implement this.
        """
        raise NotImplementedError

    def on_before_close(self) -> None:
        with self.lock:
            event = self.scheduled_flush
            self.scheduled_flush = None

        if event is not None:
            try:
                event.unregister()
            except Exception:
                logger.debug("Failed to unregister flush event", exc_info=True)

        super().on_before_close()
