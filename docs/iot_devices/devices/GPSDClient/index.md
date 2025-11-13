# iot_devices.devices.GPSDClient

## Classes

| [`GPSDClient`](#iot_devices.devices.GPSDClient.GPSDClient)   | represents exactly one "device".   |
|--------------------------------------------------------------|------------------------------------|

## Package Contents

### *class* iot_devices.devices.GPSDClient.GPSDClient(config: dict[str, Any], \*\*kw: Any)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'GPSDClient'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### thread()

#### should_run *= True*

#### thread_handle

#### on_before_close()

Subclass defined cleanup handler.
