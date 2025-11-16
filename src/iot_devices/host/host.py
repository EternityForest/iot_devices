from __future__ import annotations
import copy
import asyncio
import warnings
import threading
import traceback
import time
import logging
import weakref
import abc
from collections.abc import Callable, Mapping

from typing import Type, Any, final, Generic, TypeVar, Self, TYPE_CHECKING

from .util import get_class
from ..util import str_to_bool

if TYPE_CHECKING:
    from iot_devices import device


class _ThreadLocalData(threading.local):
    host: list[Host]


_logger = logging.getLogger(__name__)
_host_context = _ThreadLocalData()
_host_context.host = []


def apply_defaults(data, schema):
    if "properties" in schema and isinstance(data, dict):
        for prop, prop_schema in schema["properties"].items():
            if prop not in data and "default" in prop_schema:
                data[prop] = prop_schema["default"]
            elif isinstance(data.get(prop), dict) and "properties" in prop_schema:
                apply_defaults(data[prop], prop_schema)
    return data


def normalize_legacy_config(cls, config: dict[str, Any]):
    # Even if we don't need it, keep for consistency.
    if "extensions" not in config:
        config["extensions"] = {}

    for i in cls.upgrade_legacy_config_keys:
        if i in config:
            warnings.warn(f"Auto upgrading legacy config key {i}", DeprecationWarning)
            v = config[i]
            del config[i]

            t = cls.config_schema.get("properties", {}).get(i, {}).get("type", None)
            if t in ("bool", "boolean"):
                v = str_to_bool(v)
            elif t in ("int", "integer"):
                v = int(v)
            elif t in ("float", "number"):
                v = float(v)

            config[cls.upgrade_legacy_config_keys[i]] = v

    if config.get("type", cls.device_type) != cls.device_type:
        # Special placeholder
        if cls.device_type not in ("unsupported", "placeholder"):
            tp = config.get("type", cls.device_type)
            assert isinstance(tp, str)
            raise ValueError(
                "Configured type "
                + tp
                + " does not match this class type:"
                + str((config["type"], cls, type))
            )

    return config


class DeviceHostContainer:
    """Represents the host's associated state for one device.
    Created and made available before the device itself.
    """

    def __init__(
        self,
        host: Host,
        parent_container: DeviceHostContainer | None,
        device_config: Mapping[str, Any],
    ):
        """MUST NOT block!"""
        self.host = host
        self.parent: Self | None = parent_container  # type: ignore
        self.name = device_config["name"]
        self.device: device.Device | None = None
        self._device_exception: Exception | None = None

        self.__initial_config: Mapping[str, Any] = device_config

    @property
    def config(self) -> Mapping[str, Any]:
        """Return the current device config, or the initial config
        if the device has not been initialized yet."""
        d = self.device
        if d is not None:
            return d.config
        else:
            return self.__initial_config

    @final
    def wait_device_ready(self) -> device.Device:
        while self.device is None:
            if self._device_exception is not None:
                raise self._device_exception
            time.sleep(0.1)

        return self.device

    def on_device_ready(self, device: device.Device):
        """Called when the device __init__ is done"""

    def on_device_init_fail(self, exception: Exception):
        pass

    def on_after_device_removed(self):
        """Note that the Host Container also has this method,
        you can handle the action in either place as fits your architecture."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} for {repr(self.device)}>"


_HostContainerTypeVar = TypeVar("_HostContainerTypeVar", bound=DeviceHostContainer)


class Host(Generic[_HostContainerTypeVar]):
    """Represents the host for device plugins, meant to be subclassed.

    Locking rules: Code in the on_foo() methods must never be called under
    lock, so it does not deadlock.

    devices is mutable, if you must iterate, make a copy.

    """

    def __init__(self, container_type: type[_HostContainerTypeVar]):
        self.__container_type = container_type
        self.devices: dict[str, _HostContainerTypeVar] = {}

        self.closing = False

        self.host_apis = {}

        self.__async_loop: asyncio.AbstractEventLoop | None = None

        # Bottom layer lock, out code cannot call user code
        # While under this.  Just to protect iterable state
        self.__lock = threading.RLock()

        self.__load_order: list[weakref.ref[_HostContainerTypeVar]] = []

    @final
    def get_devices(self) -> Mapping[str, _HostContainerTypeVar]:
        """Immutable snapshot of devices that is safe to iterate"""
        with self.__lock:
            return copy.copy(self.devices)

    @final
    def get_event_loop(self, device: device.Device) -> asyncio.AbstractEventLoop:
        """Devices can request an event loop to avoid having to manage it.
        Currently does nothing except managing loop lifetime.
        """
        with self.__lock:
            if self.__async_loop is None:
                self.__async_loop = asyncio.get_event_loop()
                t = threading.Thread(
                    target=self.__async_loop.run_forever,
                    name="HostAsyncLoop",
                )
                t.start()
            return self.__async_loop

    @final
    def close(self):
        if self.closing:
            return

        with self.__lock:
            self.closing = True
            ordered = [i() for i in self.__load_order]
            ordered = [i for i in ordered if i]
            ordered.reverse()

            x = list(self.devices.values())

            if self.__async_loop:
                self.__async_loop.stop()
                # Reduce nuisance errors
                for i in range(100):
                    if self.__async_loop.is_running():
                        break

        for i in ordered:
            d = i.device
            if d:
                try:
                    if not d.config.get("is_subdevice", False):
                        d.close()
                except Exception:
                    _logger.exception("Error closing device")
                try:
                    x.remove(i)
                except ValueError:
                    pass

        # Close anything the ordered list somehow missed

        # Close outside of lock for deadlock prevention
        for i in x:
            d = i.device
            if d:
                if not d.config.get("is_subdevice", False):
                    try:
                        d.close()
                    except Exception:
                        _logger.exception("Error closing device")

        # Close any subdevices that the parent didn't close
        for i in x:
            try:
                d = i.device
                if d:
                    warnings.warn(
                        f"Parent should have closed subdevice {d.name}",
                        RuntimeWarning,
                    )
                    d.close()
            except Exception:
                _logger.exception("Error closing device")

        with self.__lock:
            self.devices.clear()

    @final
    def close_device(self, name: str):
        """
        Thread note:Do not reopen the device with the same name until this call returns"""
        x = None
        c = None

        with self.__lock:
            if name in self.devices:
                c = self.devices[name]
                x = c.device
                del self.devices[name]

        if c:
            if x:
                x.close()
            c.on_after_device_removed()
            self.on_after_device_removed(c)

            if x.subdevices:
                warnings.warn(
                    f"Device {name} had subdevices and did not close them.",
                )

    @final
    def delete_device(self, name: str):
        """Handle permanently deleting a device"""
        d = self.devices.get(name, None)
        if d is None:
            return
        dev = d.device
        if not dev:
            raise Exception(f"Device with name {name} exists but is not ready")

        dev.on_delete()
        self.close_device(name)

    def resolve_datapoint_name(self, device_name: str, datapoint_name: str) -> str:
        """Given a device name and datapoint name, returns the full datapoint name in
        the host-wide namespace."""
        return f"{device_name}.{datapoint_name}"

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
        raise NotImplementedError

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
    ) -> None:
        """Register a new object data point with the given properties.   Here "object"
        means a JSON-like object.
        """
        raise NotImplementedError

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
    ) -> None:
        """Called by the device to get a new data point."""
        raise NotImplementedError

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
        on_request: Callable[[], Any] | None = None,
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> None:
        """register a new bytestream data point with the
        given properties. handler will be called when it changes.
        only meant to be called from within __init__.

        Bytestream data points do not store data,
        they only push it through.

        Despite the name, buffers of bytes may not be broken up or combined, this is buffer oriented,

        """
        raise NotImplementedError

    @final
    def request_data_point(self, device: str, name: str) -> None:
        """Ask a device to refresh it's data point"""

        d = self.devices[device]
        dev = d.device
        if not dev:
            raise Exception(f"Device with name {device} exists but is not ready")

        x = dev.datapoint_getter_functions.get(name, None)
        if x is not None:
            x()

    @abc.abstractmethod
    def set_string(
        self,
        device: str,
        name: str,
        value: str,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ) -> None:
        """Subclass to handle data points.  Must happen locklessly."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_number(
        self,
        device: str,
        name: str,
        value: float | int,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ) -> None:
        """Subclass to handle data points.  Must happen locklessly."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_bytes(
        self,
        device: str,
        name: str,
        value: bytes,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ) -> None:
        """Subclass to handle data points.  Must happen locklessly."""
        raise NotImplementedError

    def fast_push_bytes(
        self,
        device: str,
        name: str,
        value: bytes,
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ) -> None:
        """Subclass to handle data points.  Must happen locklessly."""
        self.set_bytes(device, name, value, timestamp, annotation, force_push_on_repeat)

    @abc.abstractmethod
    def set_object(
        self,
        device: str,
        name: str,
        value: dict[str, Any],
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ) -> None:
        """Subclass to handle data points.  Must happen locklessly."""
        raise NotImplementedError

    @final
    def add_new_device(
        self,
        config: dict[str, Any],
        *,
        host_container_kwargs: dict[str, Any] = {},
        **kwargs: Any,
    ) -> _HostContainerTypeVar:
        c = get_class(config)

        # Make it visible and hang onto config for a while
        if "is_subdevice" in config and config["is_subdevice"]:
            c = device.UnusedSubdevice

        return self.add_device_from_class(
            c, config, host_container_kwargs=host_container_kwargs, **kwargs
        )

    # This is the only function to actually add a device
    @final
    def add_device_from_class(
        self,
        cls: type[device.Device],
        data: dict[str, Any],
        *,
        host_container_kwargs: dict[str, Any] = {},
        parent: device.Device | None = None,
        **kwargs: Any,
    ) -> _HostContainerTypeVar:
        with self:
            name = data["name"]

            if data.get("is_subdevice", False) and parent is None:
                raise Exception("Subdevice must have a parent")

            data = copy.deepcopy(data)

            data = apply_defaults(data, cls.config_schema)

            data = normalize_legacy_config(cls, data)

            data.update(self.get_config_for_device(None, data["name"]))

            # Container available before device
            with self.__lock:
                if name in self.devices:
                    d = self.devices[name]
                    dev = d.device
                    if not dev:
                        raise Exception(
                            f"Device with name {name} already exists but is not ready"
                        )

                    if dev.device_type not in ("UnusedSubdevice"):
                        raise Exception(f"Device with name {name} already exists")

                parentContainer = None
                if parent is not None:
                    parentContainer = self.get_container_for_device(parent)

                cont = self.__container_type(
                    self, parentContainer, data, **host_container_kwargs
                )
                self.devices[name] = cont

            try:
                self.on_before_device_added(name, cont)

                d = cls(data)

                with self.__lock:
                    self.__load_order.append(weakref.ref(cont))
                    self.__load_order = [
                        x for x in self.__load_order if x() is not None
                    ]

                cont.device = d
                cont.on_device_ready(d)
                self.on_device_added(self.devices[name])

            # If device creation fails, remove the empty container
            except Exception as e:
                with self.__lock:
                    x = self.devices.pop(name, None)
                if x is not None:
                    x._device_exception = e
                    x.on_device_init_fail(e)
                raise

            return cont

    @final
    def __enter__(self):
        if not hasattr(_host_context, "host"):
            _host_context.host = []
        _host_context.host.append(self)
        return self

    @final
    def __exit__(self, *a: Any, **k: Any):
        _host_context.host.pop()

    def set_alarm(
        self,
        device: device.Device,
        name: str,
        datapoint: str,
        expression: str,
        priority: str = "info",
        trip_delay: float = 0,
        auto_ack: bool = False,
        release_condition: str | None = None,
        **kw,
    ):
        pass

    def get_config_for_device(
        self,
        parent_device_container: _HostContainerTypeVar | None,
        full_device_name: str,
    ) -> Mapping[str, Any]:
        """Subclassable hook to load config on device creation"""
        return {}

    @abc.abstractmethod
    def get_number(self, device: str, datapoint: str) -> tuple[float | int, float, Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_string(self, device: str, datapoint: str) -> tuple[str, float, Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_object(
        self, device: str, datapoint: str
    ) -> tuple[dict[str, Any], float, Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_bytes(self, device: str, datapoint: str) -> tuple[bytes, float, Any]:
        raise NotImplementedError

    @final
    def get_container_for_device(self, device: device.Device) -> _HostContainerTypeVar:
        x = self.devices[device.name]

        # Might not be set because it's still being initialized,
        # Do a basic state corruption check
        if x.device is not None:
            assert x.device is device

        return x

    def get_config_folder(
        self, device_container: _HostContainerTypeVar, create: bool = True
    ) -> str | None:
        # Can still call with create false just to check
        if create:
            raise NotImplementedError(
                "Your framework probably doesn't support this device"
            )

    def on_device_exception(self, device_container: _HostContainerTypeVar) -> None:
        self.on_device_error(device_container, traceback.format_exc())

    def on_device_error(
        self, device_container: _HostContainerTypeVar, error: str
    ) -> None:
        pass

    def on_device_print(
        self, device_container: _HostContainerTypeVar, message: str, title: str = ""
    ) -> None:
        pass

    def on_config_changed(
        self, device_container: _HostContainerTypeVar, config: Mapping[str, Any]
    ) -> None:
        """Called when the device configuration has changed.
        The host likely doesn't need to care about this
        except to save the data.

        Note that the device container might not actually have a device
        set up yet, because this could be called from the init.
        """

    def on_after_device_removed(self, device_container: _HostContainerTypeVar) -> None:
        pass

    def on_device_added(self, device_container: _HostContainerTypeVar) -> None:
        pass

    def on_before_device_added(
        self,
        name: str,
        device_container: _HostContainerTypeVar,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        pass


def get_host() -> Host:
    """Get the host that we are runing under, which is just
    the last host in this thread doing a context manager.
    """

    if not _host_context.host:
        raise RuntimeError("No host running in this thread")

    return _host_context.host[-1]
