# iot_devices.devices.WeatherPlugin

## Attributes

| [`cache`](#iot_devices.devices.WeatherPlugin.cache)   |    |
|-------------------------------------------------------|----|

## Classes

| [`WeatherClient`](#iot_devices.devices.WeatherPlugin.WeatherClient)   | represents exactly one "device".   |
|-----------------------------------------------------------------------|------------------------------------|

## Functions

| [`fetch`](#iot_devices.devices.WeatherPlugin.fetch)(url[, cachetime])             |    |
|-----------------------------------------------------------------------------------|----|
| [`getWeather`](#iot_devices.devices.WeatherPlugin.getWeather)(place[, cachetime]) |    |

## Package Contents

### iot_devices.devices.WeatherPlugin.cache

### iot_devices.devices.WeatherPlugin.fetch(url, cachetime=1 \* 3600)

### iot_devices.devices.WeatherPlugin.getWeather(place, cachetime=1 \* 3600)

### *class* iot_devices.devices.WeatherPlugin.WeatherClient(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'WeatherClient'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### upgrade_legacy_config_keys

\_\_init_\_ uses this to auto rename old config keys to new ones
if your device renames things.  They are type coerced according
to the schema too.

#### shouldRun *= True*

#### thread

#### update()

#### on_before_close()

Subclass defined cleanup handler.
