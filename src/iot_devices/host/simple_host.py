from __future__ import annotations
import copy
import time
import logging
from collections.abc import Callable, Mapping
from typing import Any, TYPE_CHECKING
from .host import Host, DeviceHostContainer

if TYPE_CHECKING:
    from .. import device

_logger = logging.getLogger(__name__)


class SimpleAlert:
    def __init__(
        self, host: SimpleHost, name: str, datapoint: str, message: str, condition: str
    ):
        self.name = name
        self.datapoint = datapoint
        self.message = message
        self.condition = condition
        self.host = host
        self.ctx = {}
        self.f = compile(condition, "<string>", "eval")

    def check(self):
        self.ctx["value"] = self.host.datapoint_vta[self.datapoint][0]
        return eval(self.f, self.ctx)


class SimpleHostDeviceContainer(DeviceHostContainer):
    def __init__(
        self, host: Host, parent: DeviceHostContainer | None, config: Mapping[str, Any]
    ):
        super().__init__(host, parent, config)
        self.alerts: list[SimpleAlert] = []


class SimpleHost(Host[SimpleHostDeviceContainer]):
    """Represents the host for device plugins, meant to be subclassed.

    Locking rules: Code in the on_foo() methods *must not block*,
    because it happens synchronously under the host's lock and
    will most likely cause a deadlock if that happens.

    """

    def __init__(self):
        super().__init__(SimpleHostDeviceContainer)

        self.datapoint_vta: dict[str, tuple[Any, float, Any]] = {}
        """This is where the data point values are stored,
        with the format devicename.datapointname"""

        # Functions devices use that are called when a data point changes
        self.datapoint_handlers: dict[str, Callable[[Any, float, Any], Any] | None] = {}

    def string_data_point(
        self,
        device: str,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[str, float, Any], Any] | None = None,
        default: str | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        writable: bool = True,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        dashboard: bool = True,  # pylint: disable=unused-argument
        on_request: Callable[[], Any] | None = None,
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> None:
        name = self.resolve_datapoint_name(device, name)
        self.datapoint_vta[name] = (default, 0, None)
        self.datapoint_handlers[name] = handler

    def object_data_point(
        self,
        device: str,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[Mapping[str, Any], float, Any], Any] | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        writable: bool = True,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        dashboard: bool = True,  # pylint: disable=unused-argument
        default: Mapping[str, Any] | None = None,
        on_request: Callable[[], Any] | None = None,
        **kwargs: Any,  # pylint: disable=unused-argument
    ):
        """Register a new object data point with the given properties.   Here "object"
        means a JSON-like object.

        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None

        Interval annotates the default data rate the point will produce, for use in setting default poll
        rates by the host, if the host wants to poll.

        Most fields are just extra annotations to the host.

        Args:
            description: Free text

            handler: A function taking the value,timestamp, and annotation on changes

            interval :annotates the default data rate the point will produce, for use in setting default poll
                rates by the host, if the host wants to poll.  It does not mean the host SHOULD poll this,
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

            subtype: A string further describing the data type of this value, as a hint to UI generation.

            dashboard: Whether to show this data point in overview displays.
        """
        name = self.resolve_datapoint_name(device, name)
        self.datapoint_vta[name] = (copy.deepcopy(default), 0, None)

        self.datapoint_handlers[name] = handler

    def numeric_data_point(
        self,
        device: str,
        name: str,
        *,
        min: float | None = None,
        max: float | None = None,
        hi: float | None = None,  # pylint: disable=unused-argument
        lo: float | None = None,  # pylint: disable=unused-argument
        default: float | None = None,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[float, float, Any], Any] | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        writable: bool = True,  # pylint: disable=unused-argument
        dashboard: bool = True,  # pylint: disable=unused-argument
        on_request: Callable[[], Any] | None = None,
        **kwargs: Any,  # pylint: disable=unused-argument
    ):
        """Called by the device to get a new data point."""
        name = self.resolve_datapoint_name(device, name)
        self.datapoint_vta[name] = (default, 0, None)
        self.datapoint_handlers[name] = handler

    def bytestream_data_point(
        self,
        device: str,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[bytes, float, Any], Any] | None = None,
        writable: bool = True,  # pylint: disable=unused-argument
        dashboard: bool = True,  # pylint: disable=unused-argument
        **kwargs: Any,  # pylint: disable=unused-argument
    ):
        """register a new bytestream data point with the
        given properties. handler will be called when it changes.
        only meant to be called from within __init__.

        Bytestream data points do not store data,
        they only push it through.

        Despite the name, buffers of bytes may not be broken up or combined, this is buffer oriented,

        """
        name = self.resolve_datapoint_name(device, name)
        self.datapoint_vta[name] = (b"", 0, None)
        self.datapoint_handlers[name] = handler

    def set_string(
        self,
        device: str,
        name: str,
        value: str,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        """Subclass to handle data points.  Must happen locklessly."""

        name = self.resolve_datapoint_name(device, name)
        self.set_data_point(name, value, timestamp, annotation, force_push_on_repeat)

    def set_number(
        self,
        device: str,
        name: str,
        value: float | int,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        """Subclass to handle data points.  Must happen locklessly."""
        name = self.resolve_datapoint_name(device, name)
        self.set_data_point(name, value, timestamp, annotation, force_push_on_repeat)

    def set_bytes(
        self,
        device: str,
        name: str,
        value: bytes,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        """Subclass to handle data points.  Must happen locklessly."""
        name = self.resolve_datapoint_name(device, name)
        self.set_data_point(name, value, timestamp, annotation, force_push_on_repeat)

    def fast_push_bytes(
        self,
        device: str,
        name: str,
        value: bytes,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        """Subclass to handle data points.  Must happen locklessly."""
        name = self.resolve_datapoint_name(device, name)
        self.set_data_point(name, value, timestamp, annotation, force_push_on_repeat)

    def set_object(
        self,
        device: str,
        name: str,
        value: dict[str, Any],
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        """Subclass to handle data points.  Must happen locklessly."""
        name = self.resolve_datapoint_name(device, name)
        self.set_data_point(name, value, timestamp, annotation, force_push_on_repeat)

    def set_data_point(
        self,
        name: str,
        value: int | float | str | bytes | Mapping[str, Any] | list[Any],
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        """
        Set a data point of the device. Used by the device code.
        """
        if timestamp is None:
            timestamp = time.time()

        if isinstance(value, Mapping):
            value = copy.deepcopy(value)

        changed = force_push_on_repeat

        if self.datapoint_vta[name][0] != value:
            changed = True

        if self.datapoint_vta[name][1] == 0:
            changed = True

        self.datapoint_vta[name] = (value, timestamp, annotation)
        if changed:
            x = self.datapoint_handlers.get(name)
            if x is not None:
                x(value, timestamp, annotation)

    def get_config_for_device(
        self, parent_device: DeviceHostContainer | None, full_device_name: str
    ) -> dict[str, Any]:
        """Subclassable hook to load config on device creation"""
        return {}

    def _get_data_point(self, device: str, datapoint: str) -> tuple[Any, float, Any]:
        return self.datapoint_vta[self.resolve_datapoint_name(device, datapoint)]

    def get_number(self, device: str, datapoint: str) -> tuple[float | int, float, Any]:
        return self._get_data_point(device, datapoint)

    def get_string(self, device: str, datapoint: str) -> tuple[str, float, Any]:
        return self._get_data_point(device, datapoint)

    def get_object(
        self, device: str, datapoint: str
    ) -> tuple[dict[str, Any], float, Any]:
        return self._get_data_point(device, datapoint)

    def get_bytes(self, device: str, datapoint: str) -> tuple[bytes, float, Any]:
        return self._get_data_point(device, datapoint)

    def get_config_folder(
        self, device: DeviceHostContainer, create: bool = True
    ) -> str | None:
        # Can still call with create false just to check
        if create:
            raise NotImplementedError(
                "Your framework probably doesn't support this device"
            )

    def on_device_error(self, device: DeviceHostContainer, error: str):
        pass

    def on_device_print(
        self, device: DeviceHostContainer, message: str, title: str = ""
    ):
        pass

    def on_config_changed(self, device: DeviceHostContainer, config: Mapping[str, Any]):
        """Called when the device configuration has changed.
        The host likely doesn't need to care about this
        except to save the data.
        """
        _logger.debug(f"on_config_changed {device.name}")

    def on_after_device_removed(self, device: DeviceHostContainer):
        with self:
            dev = device.device
            if dev:
                for d in dev.datapoints:
                    i = dev.datapoints[d].full_name
                    if i in self.datapoint_vta:
                        del self.datapoint_vta[i]
                    if i in self.datapoint_handlers:
                        del self.datapoint_handlers[i]

    def on_device_added(self, device: DeviceHostContainer):
        pass
