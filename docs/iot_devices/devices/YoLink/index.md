# iot_devices.devices.YoLink

## Attributes

| [`log`](#iot_devices.devices.YoLink.log)                           | Object representation for YoLink MQTT Client   |
|--------------------------------------------------------------------|------------------------------------------------|
| [`server_url`](#iot_devices.devices.YoLink.server_url)             |                                                |
| [`mqtt_url`](#iot_devices.devices.YoLink.mqtt_url)                 |                                                |
| [`readme`](#iot_devices.devices.YoLink.readme)                     |                                                |
| [`deviceTypes`](#iot_devices.devices.YoLink.deviceTypes)           |                                                |
| [`connectRateLimit`](#iot_devices.devices.YoLink.connectRateLimit) |                                                |

## Classes

| [`RateLimiter`](#iot_devices.devices.YoLink.RateLimiter)                         |                                  |
|----------------------------------------------------------------------------------|----------------------------------|
| [`YoLinkMQTTClient`](#iot_devices.devices.YoLink.YoLinkMQTTClient)               |                                  |
| [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)                       | represents exactly one "device". |
| [`YoLinkDoorSensor`](#iot_devices.devices.YoLink.YoLinkDoorSensor)               | represents exactly one "device". |
| [`YoLinkOutlet`](#iot_devices.devices.YoLink.YoLinkOutlet)                       | represents exactly one "device". |
| [`YoLinkLeakSensor`](#iot_devices.devices.YoLink.YoLinkLeakSensor)               | represents exactly one "device". |
| [`YoLinkMotionSensor`](#iot_devices.devices.YoLink.YoLinkMotionSensor)           | represents exactly one "device". |
| [`YoLinkVibrationSensor`](#iot_devices.devices.YoLink.YoLinkVibrationSensor)     | represents exactly one "device". |
| [`YoLinkSiren`](#iot_devices.devices.YoLink.YoLinkSiren)                         | represents exactly one "device". |
| [`YoLinkTemperatureSensor`](#iot_devices.devices.YoLink.YoLinkTemperatureSensor) | represents exactly one "device". |
| [`YoLinkService`](#iot_devices.devices.YoLink.YoLinkService)                     | represents exactly one "device". |

## Functions

| [`listify`](#iot_devices.devices.YoLink.listify)(d)                                  |    |
|--------------------------------------------------------------------------------------|----|
| [`get_from_state_or_data`](#iot_devices.devices.YoLink.get_from_state_or_data)(d, p) |    |

## Package Contents

### iot_devices.devices.YoLink.log

Object representation for YoLink MQTT Client

### iot_devices.devices.YoLink.server_url *= 'https://api.yosmart.com'*

### iot_devices.devices.YoLink.mqtt_url *= 'api.yosmart.com'*

### iot_devices.devices.YoLink.readme *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    Get the UAC ID and key in the advanced settings of the YoLink app.
    It will auto-discover all your devices.  Save this device again to update the list.
    Supports leak, temperature, door, and siren

    Note that kaithem's devices and tag points are named based on the discovered YoLink names.
    Changing the names in the YoLink app will break your automations and you will have to set them up again.

    Also, you can replace a lost sensor just by giving the replacement the same name, as the identity is linked to
    the name rather than the unique ID.

    This uses an UNENCRYPTED cloud API at the moment. Do NOT use from inside a network you don't trust.

    Also note that subdevices are created dynamically.  This means that your events and modules might be created before this device is finshed
    loading all your YoLink sensors.

    Since this uses a cloud API, it is very possible for the internet connection to fail.
    Commands sent to devices while the network is out will be ignored.
"""
```

</details>

### *class* iot_devices.devices.YoLink.RateLimiter(count, duration)

#### interval

#### count

#### duration

#### lastRefill

#### limit()

### *class* iot_devices.devices.YoLink.YoLinkMQTTClient(uid, key, homeid, parent, mqtt_port=8003, client_id=os.getpid())

#### topic

#### topic2

#### mqtt_url *= 'api.yosmart.com'*

#### mqtt_port *= 8003*

#### key

#### parent

#### close()

#### connect_to_broker()

#### on_message(client, userdata, msg)

#### on_connect(client, userdata, flags, rc)

#### on_disconnect(\*a, \*\*k)

### iot_devices.devices.YoLink.listify(d)

### iot_devices.devices.YoLink.get_from_state_or_data(d, p)

### *class* iot_devices.devices.YoLink.YoLinkDevice(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkDevice'*

Every device must have a unique device_type name

#### readme *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    Get the UAC ID and key in the advanced settings of the YoLink app.
    It will auto-discover all your devices.  Save this device again to update the list.
    Supports leak, temperature, door, and siren

    Note that kaithem's devices and tag points are named based on the discovered YoLink names.
    Changing the names in the YoLink app will break your automations and you will have to set them up again.

    Also, you can replace a lost sensor just by giving the replacement the same name, as the identity is linked to
    the name rather than the unique ID.

    This uses an UNENCRYPTED cloud API at the moment. Do NOT use from inside a network you don't trust.

    Also note that subdevices are created dynamically.  This means that your events and modules might be created before this device is finshed
    loading all your YoLink sensors.

    Since this uses a cloud API, it is very possible for the internet connection to fail.
    Commands sent to devices while the network is out will be ignored.
"""
```

</details>

#### has_battery *= True*

#### onData(data)

#### downlink(d)

#### simpleMethod(m)

#### refresh()

### *class* iot_devices.devices.YoLink.YoLinkDoorSensor(data, \*\*kw)

Bases: [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkDoorSensor'*

Every device must have a unique device_type name

#### onData(data)

#### refresh()

### *class* iot_devices.devices.YoLink.YoLinkOutlet(data, \*\*kw)

Bases: [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkOutlet'*

Every device must have a unique device_type name

#### has_battery *= False*

#### onData(data)

#### setState(v, \*a, \*\*k)

#### refresh()

### *class* iot_devices.devices.YoLink.YoLinkLeakSensor(data, \*\*kw)

Bases: [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkLeakSensor'*

Every device must have a unique device_type name

#### onData(data)

#### refresh()

### *class* iot_devices.devices.YoLink.YoLinkMotionSensor(data, \*\*kw)

Bases: [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkMotionSensor'*

Every device must have a unique device_type name

#### onData(data)

#### refresh()

### *class* iot_devices.devices.YoLink.YoLinkVibrationSensor(data, \*\*kw)

Bases: [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkVibrationSensor'*

Every device must have a unique device_type name

#### onData(data)

#### refresh()

### *class* iot_devices.devices.YoLink.YoLinkSiren(data, \*\*kw)

Bases: [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkSiren'*

Every device must have a unique device_type name

#### refresh()

#### doSiren(v, \*a, \*\*k)

#### stopSiren(v, \*a, \*\*k)

#### onData(data)

### *class* iot_devices.devices.YoLink.YoLinkTemperatureSensor(data, \*\*kw)

Bases: [`YoLinkDevice`](#iot_devices.devices.YoLink.YoLinkDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkTemperatureSensor'*

Every device must have a unique device_type name

#### onData(data)

#### refresh()

### iot_devices.devices.YoLink.deviceTypes

### iot_devices.devices.YoLink.connectRateLimit

### *class* iot_devices.devices.YoLink.YoLinkService(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YoLinkService'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### upgrade_legacy_config_keys

\_\_init_\_ uses this to auto rename old config keys to new ones
if your device renames things.  They are type coerced according
to the schema too.

#### makeRequest(r)

#### on_before_close()

Subclass defined cleanup handler.

#### sendDownlink(device, data)

#### initialConnection()

#### retryLoop()

#### shouldRun *= False*

#### *classmethod* discover_devices(config={}, current_device=None, intent=None, \*\*kw)

Discover a set of suggested configs that could be used to build a new device.

Not required to be implemented and may just return {}

other than what the user provided them for,
unless the protocol does not actually reveal the secrets
to the server.

You do not want to autosuggest trying the same credentials
at bad.com that the user gave for example.com.

The suggested UI semantics for discover commands is
"Add a similar device" and "Reconfigure this device".

Reconfiguration should always be available as the user
might always want to take an existing device object and
swap out the actual physical device it connects to.

Kwargs is reserved for further hints on what kinds of
devices should be discovered.

Args:
: config: You may pass a partial config, or a completed
  : config to find other
    similar devices. The device should reuse as much
    of the given config as possible and logical,
    discarding anything that wouldn't  work with the
    selected device.
  <br/>
  current_device: May be set to the current version of a
  : device, if it is being used in a UI along the lines of
    suggesting how to further set up a partly configured
    device, or suggesting ways to add another
    similar device.
  <br/>
  kwargs: is reserved for further hints on what kinds
  : of devices should be discovered.
  <br/>
  intent: may be a hint as to what kind of config you are
  : > looking for.
    <br/>
    If it is "new", that means the host wants to add
    another similar device.  If it is "replace",
    the host wants to keep the same config
    but point at a different physical device.
    <br/>
    If it is "configure",  the host wants to look
    for alternate configurations available for the
    same exact device.
    <br/>
    If it is "step", the user wants to refine
    the existing config.

Returns:
: A dict of device data dicts that could be used
  to create a new device, indexed by a descriptive name.
