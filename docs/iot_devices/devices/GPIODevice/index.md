# iot_devices.devices.GPIODevice

## Attributes

| [`gpio_config_schema`](#iot_devices.devices.GPIODevice.gpio_config_schema)   |    |
|------------------------------------------------------------------------------|----|

## Classes

| [`GPIOOutput`](#iot_devices.devices.GPIODevice.GPIOOutput)   | represents exactly one "device".   |
|--------------------------------------------------------------|------------------------------------|
| [`GPIOInput`](#iot_devices.devices.GPIODevice.GPIOInput)     | represents exactly one "device".   |

## Package Contents

### iot_devices.devices.GPIODevice.gpio_config_schema

### *class* iot_devices.devices.GPIODevice.GPIOOutput(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'GPIOOutput'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### upgrade_legacy_config_keys

\_\_init_\_ uses this to auto rename old config keys to new ones
if your device renames things.  They are type coerced according
to the schema too.

#### on_before_close()

Subclass defined cleanup handler.

### *class* iot_devices.devices.GPIODevice.GPIOInput(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'GPIOInput'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### upgrade_legacy_config_keys

\_\_init_\_ uses this to auto rename old config keys to new ones
if your device renames things.  They are type coerced according
to the schema too.

#### test_val(x: bool)

#### pressed()

#### released()

#### on_before_close()

Subclass defined cleanup handler.
