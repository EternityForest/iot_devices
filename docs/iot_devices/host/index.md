# iot_devices.host

## Submodules

* [iot_devices.host.host](host/index.md)
* [iot_devices.host.simple_host](simple_host/index.md)
* [iot_devices.host.util](util/index.md)

## Classes

| [`Host`](#iot_devices.host.Host)                               | Represents the host for device plugins, meant to be subclassed.   |
|----------------------------------------------------------------|-------------------------------------------------------------------|
| [`DeviceHostContainer`](#iot_devices.host.DeviceHostContainer) | Represents the host's associated state for one device.            |

## Functions

| [`get_host`](#iot_devices.host.get_host)(→ Host)                              | Get the host that we are runing under, which is just                                                               |
|-------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| [`discover`](#iot_devices.host.discover)(→ Dict[str, Dict[str, Any]])         | Search system paths for modules that have a devices manifest.                                                      |
| [`get_class`](#iot_devices.host.get_class)(→ type[iot_devices.device.Device]) | Return the class that one would use to construct a device given it's data.  Automatically search all system paths. |
| [`get_description`](#iot_devices.host.get_description)(→ str)                 | Return the description for a device given it's type.  Automatically search all system paths.                       |

## Package Contents

### *class* iot_devices.host.Host(container_type: Type[\_HostContainerTypeVar])

Bases: `Generic`[`_HostContainerTypeVar`]

Represents the host for device plugins, meant to be subclassed.

Locking rules: Code in the on_foo() methods must never be called under
lock, so it does not deadlock.

devices is mutable, if you must iterate, make a copy.

#### \_\_container_type

#### devices *: dict[str, \_HostContainerTypeVar]*

#### closing *= False*

#### host_apis

#### \_\_async_loop *: asyncio.AbstractEventLoop | None* *= None*

#### \_\_lock

#### \_\_load_order *: list[weakref.ref[\_HostContainerTypeVar]]* *= []*

#### get_devices() → collections.abc.Mapping[str, \_HostContainerTypeVar]

Immutable snapshot of devices that is safe to iterate

#### get_event_loop(device: Host.get_event_loop.device) → asyncio.AbstractEventLoop

Devices can request an event loop to avoid having to manage it.
Currently does nothing except managing loop lifetime.

#### close()

#### close_device(name: str)

Thread note:Do not reopen the device with the same name until this call returns

#### delete_device(name: str)

Handle permanently deleting a device

#### resolve_datapoint_name(device_name: str, datapoint_name: str) → str

Given a device name and datapoint name, returns the full datapoint name in
the host-wide namespace.

#### *abstractmethod* string_data_point(device: str, name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[str, float, Any], Any] | None = None, default: str | None = None, interval: float = 0, writable: bool = True, subtype: str = '', dashboard: bool = True, \*\*kwargs: Any)

#### *abstractmethod* object_data_point(device: str, name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[collections.abc.Mapping[str, Any], float, Any], Any] | None = None, interval: float = 0, writable: bool = True, subtype: str = '', dashboard: bool = True, default: collections.abc.Mapping[str, Any] | None = None, \*\*kwargs: Any)

Register a new object data point with the given properties.   Here "object"
means a JSON-like object.

#### *abstractmethod* numeric_data_point(device: str, name: str, , min: float | None = None, max: float | None = None, hi: float | None = None, lo: float | None = None, default: float | None = None, description: str = '', unit: str = '', handler: collections.abc.Callable[[float, float, Any], Any] | None = None, interval: float = 0, subtype: str = '', writable: bool = True, dashboard: bool = True, \*\*kwargs: Any)

Called by the device to get a new data point.

#### *abstractmethod* bytestream_data_point(device: str, name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[bytes, float, Any], Any] | None = None, writable: bool = True, dashboard: bool = True, \*\*kwargs: Any)

register a new bytestream data point with the
given properties. handler will be called when it changes.
only meant to be called from within \_\_init_\_.

Bytestream data points do not store data,
they only push it through.

Despite the name, buffers of bytes may not be broken up or combined, this is buffer oriented,

#### request_data_point(device: str, name: str) → Any

Ask a device to refresh it's data point

#### *abstractmethod* set_string(device: str, name: str, value: str, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### *abstractmethod* set_number(device: str, name: str, value: float | int, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### *abstractmethod* set_bytes(device: str, name: str, value: bytes, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### fast_push_bytes(device: str, name: str, value: bytes, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### *abstractmethod* set_object(device: str, name: str, value: dict[str, Any], timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### add_new_device(config: dict[str, Any], , host_container_kwargs: dict[str, Any] = {}, \*\*kwargs: Any) → \_HostContainerTypeVar

#### add_device_from_class(cls: Type[iot_devices.host.device.Device], data: dict[str, Any], , host_container_kwargs: dict[str, Any] = {}, parent: iot_devices.host.device.Device | None = None, \*\*kwargs: Any) → \_HostContainerTypeVar

#### \_\_enter_\_()

#### \_\_exit_\_(\*a: Any, \*\*k: Any)

#### set_alarm(device: Host.set_alarm.device, name: str, datapoint: str, expression: str, priority: str = 'info', trip_delay: float = 0, auto_ack: bool = False, release_condition: str | None = None, \*\*kw)

#### get_config_for_device(parent_device: \_HostContainerTypeVar | None, full_device_name: str) → dict[str, Any]

Subclassable hook to load config on device creation

#### *abstractmethod* get_number(device: str, datapoint: str) → tuple[float | int, float, Any]

#### *abstractmethod* get_string(device: str, datapoint: str) → tuple[str, float, Any]

#### *abstractmethod* get_object(device: str, datapoint: str) → tuple[dict[str, Any], float, Any]

#### *abstractmethod* get_bytes(device: str, datapoint: str) → tuple[bytes, float, Any]

#### get_container_for_device(device: Host.get_container_for_device.device) → \_HostContainerTypeVar

#### get_config_folder(device: \_HostContainerTypeVar, create: bool = True) → str | None

#### on_device_exception(device: \_HostContainerTypeVar)

#### on_device_error(device: \_HostContainerTypeVar, error: str)

#### on_device_print(device: \_HostContainerTypeVar, message: str, title: str = '')

#### on_config_changed(device: \_HostContainerTypeVar, config: collections.abc.Mapping[str, Any])

Called when the device configuration has changed.
The host likely doesn't need to care about this
except to save the data.

Note that the device container might not actually have a device
set up yet, because this could be called from the init.

#### on_device_removed(device: \_HostContainerTypeVar)

#### on_device_added(device: \_HostContainerTypeVar)

#### on_before_device_added(name: str, device: \_HostContainerTypeVar, \*args: Any, \*\*kwargs: Any)

### iot_devices.host.get_host() → [Host](#iot_devices.host.Host)

Get the host that we are runing under, which is just
the last host in this thread doing a context manager.

### *class* iot_devices.host.DeviceHostContainer(host: [Host](#iot_devices.host.Host), parent: [DeviceHostContainer](#iot_devices.host.DeviceHostContainer) | None, device_config: collections.abc.Mapping[str, Any])

Represents the host's associated state for one device.
Created and made available before the device itself.

#### host

#### parent

#### name

#### device *: iot_devices.host.device.Device | None* *= None*

#### \_\_initial_config *: collections.abc.Mapping[str, Any]*

#### *property* config *: collections.abc.Mapping[str, Any]*

Return the current device config, or the initial config
if the device has not been initialized yet.

#### wait_device_ready() → iot_devices.host.device.Device

#### on_device_ready(device: DeviceHostContainer.on_device_ready.device)

Called when the device \_\_init_\_ is done

#### on_device_init_fail(exception: Exception)

#### \_\_repr_\_() → str

### iot_devices.host.discover() → Dict[str, Dict[str, Any]]

Search system paths for modules that have a devices manifest.

Returns:
: A dict indexed by the device type name, with the values being info dicts.
  Keys not documented here should be considered opaque.
  <br/>
  description: A free text, paragraph or less short description, taken from the device manifest.
  <br/>
  importable: The full module(including the submodule) you would import to get the class to build this device.
  <br/>
  classname: The name of the class you would import

### iot_devices.host.get_class(data: dict[str, Any]) → type[[iot_devices.device.Device](../device/index.md#iot_devices.device.Device)]

Return the class that one would use to construct a device given it's data.  Automatically search all system paths.

Returns:
: A class, not an instance

### iot_devices.host.get_description(t: str) → str

Return the description for a device given it's type.  Automatically search all system paths.
