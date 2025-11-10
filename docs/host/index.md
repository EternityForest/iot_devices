# iot_devices.host

## Attributes

| [`device_classes`](#iot_devices.host.device_classes)           | This dict lets you programmatically add new devices                                             |
|----------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| [`app_exit_functions`](#iot_devices.host.app_exit_functions)   | These are called on exit                                                                        |
| [`app_exit_lock`](#iot_devices.host.app_exit_lock)             |                                                                                                 |
| [`already_did_cleanup`](#iot_devices.host.already_did_cleanup) |                                                                                                 |
| [`api`](#iot_devices.host.api)                                 | The host may place functions here to make available to all device plugins.  Functions must have |

## Functions

| [`app_exit_cleanup`](#iot_devices.host.app_exit_cleanup)(\*a, \*\*k)            | Called by the host to clean up all devices and also close them.                                                    |
|---------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| [`app_exit_register`](#iot_devices.host.app_exit_register)(f)                   | A device type plugin registers a cleanup function here                                                             |
| [`discover`](#iot_devices.host.discover)(→ Dict[str, Dict[str, Any]])           | Search system paths for modules that have a devices manifest.                                                      |
| [`get_class`](#iot_devices.host.get_class)(→ type[iot_devices.device.Device])   | Return the class that one would use to construct a device given it's data.  Automatically search all system paths. |
| [`get_description`](#iot_devices.host.get_description)(→ str)                   | Return the description for a device given it's type.  Automatically search all system paths.                       |
| [`register_subdevice`](#iot_devices.host.register_subdevice)(parent, child)     | A device can create other devices.  This lets a host do something with them.                                       |
| [`create_device`](#iot_devices.host.create_device)(→ iot_devices.device.Device) | Create a new device from it's data, given the device class,                                                        |

## Module Contents

### iot_devices.host.device_classes *: weakref.WeakValueDictionary[str, type[[iot_devices.device.Device](../device/index.md#iot_devices.device.Device)]]*

This dict lets you programmatically add new devices

### iot_devices.host.app_exit_functions *: list[collections.abc.Callable[[], None]]* *= []*

These are called on exit

### iot_devices.host.app_exit_lock

### iot_devices.host.already_did_cleanup *= False*

### iot_devices.host.api

The host may place functions here to make available to all device plugins.  Functions must have
string keys, and use UUID, com.site.foo, or some other similar notation.

Host functions should be very simple and not need changes later!

### iot_devices.host.app_exit_cleanup(\*a: Any, \*\*k: Any)

Called by the host to clean up all devices and also close them.

### iot_devices.host.app_exit_register(f: collections.abc.Callable[[], None])

A device type plugin registers a cleanup function here

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

### iot_devices.host.register_subdevice(parent: object, child: object)

A device can create other devices.  This lets a host do something with them.

### iot_devices.host.create_device(cls: Type[[iot_devices.device.Device](../device/index.md#iot_devices.device.Device)], name: str, data: dict[str, Any]) → [iot_devices.device.Device](../device/index.md#iot_devices.device.Device)

Create a new device from it's data, given the device class,
and add any framework specific hooks.
This function is meant to be overriden by the host app,
to add framework specific functionality
