# iot_devices.devices.servermonitor

## Attributes

| [`imported_time`](#iot_devices.devices.servermonitor.imported_time)   |    |
|-----------------------------------------------------------------------|----|
| [`schema`](#iot_devices.devices.servermonitor.schema)                 |    |

## Classes

| [`ServerMonitor`](#iot_devices.devices.servermonitor.ServerMonitor)   | represents exactly one "device".   |
|-----------------------------------------------------------------------|------------------------------------|

## Functions

| [`ping_ok`](#iot_devices.devices.servermonitor.ping_ok)(→ bool)   |    |
|-------------------------------------------------------------------|----|

## Package Contents

### iot_devices.devices.servermonitor.imported_time

### iot_devices.devices.servermonitor.ping_ok(sHost) → bool

### iot_devices.devices.servermonitor.schema

### *class* iot_devices.devices.servermonitor.ServerMonitor(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'ServerMonitor'*

Every device must have a unique device_type name

#### upgrade_legacy_config_keys

\_\_init_\_ uses this to auto rename old config keys to new ones
if your device renames things.  They are type coerced according
to the schema too.

#### config_schema

Schema defining the config

#### stop_flag

#### on_before_close()

Subclass defined cleanup handler.

#### work_loop()

This runs until the device is closed
