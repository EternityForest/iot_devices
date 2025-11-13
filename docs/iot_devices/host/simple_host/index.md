# iot_devices.host.simple_host

## Classes

| [`SimpleAlert`](#iot_devices.host.simple_host.SimpleAlert)                             |                                                                 |
|----------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| [`SimpleHostDeviceContainer`](#iot_devices.host.simple_host.SimpleHostDeviceContainer) |                                                                 |
| [`SimpleHost`](#iot_devices.host.simple_host.SimpleHost)                               | Represents the host for device plugins, meant to be subclassed. |

## Module Contents

### *class* iot_devices.host.simple_host.SimpleAlert(host: [SimpleHost](#iot_devices.host.simple_host.SimpleHost), name: str, datapoint: str, message: str, condition: str)

#### name

#### datapoint

#### message

#### condition

#### host

#### ctx

#### f

#### check()

### *class* iot_devices.host.simple_host.SimpleHostDeviceContainer(host: [iot_devices.host.host.Host](../host/index.md#iot_devices.host.host.Host), parent: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer) | None, config: collections.abc.Mapping[str, Any])

Bases: [`iot_devices.host.host.DeviceHostContainer`](../host/index.md#iot_devices.host.host.DeviceHostContainer)

#### alerts *: list[[SimpleAlert](#iot_devices.host.simple_host.SimpleAlert)]* *= []*

### *class* iot_devices.host.simple_host.SimpleHost

Bases: [`iot_devices.host.host.Host`](../host/index.md#iot_devices.host.host.Host)[[`SimpleHostDeviceContainer`](#iot_devices.host.simple_host.SimpleHostDeviceContainer)]

Represents the host for device plugins, meant to be subclassed.

Locking rules: Code in the on_foo() methods *must not block*,
because it happens synchronously under the host's lock and
will most likely cause a deadlock if that happens.

#### datapoint_vta *: dict[str, tuple[Any, float, Any]]*

This is where the data point values are stored,
with the format devicename.datapointname

#### datapoint_handlers *: dict[str, collections.abc.Callable[[Any, float, Any], Any] | None]*

#### string_data_point(device: str, name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[str, float, Any], Any] | None = None, default: str | None = None, interval: float = 0, writable: bool = True, subtype: str = '', dashboard: bool = True, \*\*kwargs: Any)

#### object_data_point(device: str, name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[collections.abc.Mapping[str, Any], float, Any], Any] | None = None, interval: float = 0, writable: bool = True, subtype: str = '', dashboard: bool = True, default: collections.abc.Mapping[str, Any] | None = None, \*\*kwargs: Any)

Register a new object data point with the given properties.   Here "object"
means a JSON-like object.

Handler will be called when it changes.
self.datapoints[name] will start out with tha value of None

Interval annotates the default data rate the point will produce, for use in setting default poll
rates by the host, if the host wants to poll.

Most fields are just extra annotations to the host.

Args:
: description: Free text
  <br/>
  handler: A function taking the value,timestamp, and annotation on changes
  <br/>
  interval :annotates the default data rate the point will produce, for use in setting default poll
  : rates by the host, if the host wants to poll.  It does not mean the host SHOULD poll this,
    it only suggest a rate to poll at if the host has an interest in this data.
  <br/>
  writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.
  <br/>
  subtype: A string further describing the data type of this value, as a hint to UI generation.
  <br/>
  dashboard: Whether to show this data point in overview displays.

#### numeric_data_point(device: str, name: str, , min: float | None = None, max: float | None = None, hi: float | None = None, lo: float | None = None, default: float | None = None, description: str = '', unit: str = '', handler: collections.abc.Callable[[float, float, Any], Any] | None = None, interval: float = 0, subtype: str = '', writable: bool = True, dashboard: bool = True, \*\*kwargs: Any)

Called by the device to get a new data point.

#### bytestream_data_point(device: str, name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[bytes, float, Any], Any] | None = None, writable: bool = True, dashboard: bool = True, \*\*kwargs: Any)

register a new bytestream data point with the
given properties. handler will be called when it changes.
only meant to be called from within \_\_init_\_.

Bytestream data points do not store data,
they only push it through.

Despite the name, buffers of bytes may not be broken up or combined, this is buffer oriented,

#### set_string(device: str, name: str, value: str, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### set_number(device: str, name: str, value: float | int, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### set_bytes(device: str, name: str, value: bytes, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### fast_push_bytes(device: str, name: str, value: bytes, timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### set_object(device: str, name: str, value: dict[str, Any], timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Subclass to handle data points.  Must happen locklessly.

#### set_data_point(name: str, value: int | float | str | bytes | collections.abc.Mapping[str, Any] | list[Any], timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

Set a data point of the device. Used by the device code.

#### get_config_for_device(parent_device: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer) | None, full_device_name: str) → dict[str, Any]

Subclassable hook to load config on device creation

#### get_number(device: str, datapoint: str) → tuple[float | int, float, Any]

#### get_string(device: str, datapoint: str) → tuple[str, float, Any]

#### get_object(device: str, datapoint: str) → tuple[dict[str, Any], float, Any]

#### get_bytes(device: str, datapoint: str) → tuple[bytes, float, Any]

#### get_config_folder(device: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer), create: bool = True) → str | None

#### on_device_error(device: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer), error: str)

#### on_device_print(device: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer), message: str, title: str = '')

#### on_config_changed(device: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer), config: collections.abc.Mapping[str, Any])

Called when the device configuration has changed.
The host likely doesn't need to care about this
except to save the data.

#### on_device_removed(device: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer))

#### on_device_added(device: [iot_devices.host.host.DeviceHostContainer](../host/index.md#iot_devices.host.host.DeviceHostContainer))
