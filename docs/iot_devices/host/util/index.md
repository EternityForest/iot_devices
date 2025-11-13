# iot_devices.host.util

## Attributes

| [`device_classes`](#iot_devices.host.util.device_classes)   | This dict lets you programmatically add new devices   |
|-------------------------------------------------------------|-------------------------------------------------------|

## Functions

| [`discover`](#iot_devices.host.util.discover)(→ Dict[str, Dict[str, Any]])         | Search system paths for modules that have a devices manifest.                                                      |
|------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| [`get_class`](#iot_devices.host.util.get_class)(→ type[iot_devices.device.Device]) | Return the class that one would use to construct a device given it's data.  Automatically search all system paths. |
| [`get_description`](#iot_devices.host.util.get_description)(→ str)                 | Return the description for a device given it's type.  Automatically search all system paths.                       |

## Module Contents

### iot_devices.host.util.device_classes *: weakref.WeakValueDictionary[str, type[[iot_devices.device.Device](../../device/index.md#iot_devices.device.Device)]]*

This dict lets you programmatically add new devices

### iot_devices.host.util.discover() → Dict[str, Dict[str, Any]]

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

### iot_devices.host.util.get_class(data: dict[str, Any]) → type[[iot_devices.device.Device](../../device/index.md#iot_devices.device.Device)]

Return the class that one would use to construct a device given it's data.  Automatically search all system paths.

Returns:
: A class, not an instance

### iot_devices.host.util.get_description(t: str) → str

Return the description for a device given it's type.  Automatically search all system paths.
