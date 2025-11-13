# iot_devices.devices.Yeelight

## Attributes

| [`logger`](#iot_devices.devices.Yeelight.logger)               |    |
|----------------------------------------------------------------|----|
| [`lookup`](#iot_devices.devices.Yeelight.lookup)               |    |
| [`lastRefreshed`](#iot_devices.devices.Yeelight.lastRefreshed) |    |
| [`lock`](#iot_devices.devices.Yeelight.lock)                   |    |

## Classes

| [`YeelightDevice`](#iot_devices.devices.Yeelight.YeelightDevice)   | represents exactly one "device".   |
|--------------------------------------------------------------------|------------------------------------|
| [`YeelightRGB`](#iot_devices.devices.Yeelight.YeelightRGB)         | represents exactly one "device".   |

## Functions

| [`maybeRefresh`](#iot_devices.devices.Yeelight.maybeRefresh)([t])                 |                                                            |
|-----------------------------------------------------------------------------------|------------------------------------------------------------|
| [`refresh`](#iot_devices.devices.Yeelight.refresh)([timeout])                     |                                                            |
| [`isIp`](#iot_devices.devices.Yeelight.isIp)(x)                                   |                                                            |
| [`getDevice`](#iot_devices.devices.Yeelight.getDevice)(locator[, timeout, klass]) | Since plugs can change name, you should't keep a reference |
| [`makeFlusher`](#iot_devices.devices.Yeelight.makeFlusher)(wr)                    |                                                            |

## Package Contents

### iot_devices.devices.Yeelight.logger

### iot_devices.devices.Yeelight.lookup

### iot_devices.devices.Yeelight.lastRefreshed *= 0*

### iot_devices.devices.Yeelight.lock

### iot_devices.devices.Yeelight.maybeRefresh(t=30)

### iot_devices.devices.Yeelight.refresh(timeout=8)

### iot_devices.devices.Yeelight.isIp(x)

### iot_devices.devices.Yeelight.getDevice(locator, timeout=10, klass=None)

Since plugs can change name, you should't keep a reference
to a plug for too long. Instead use this function.

### iot_devices.devices.Yeelight.makeFlusher(wr)

### *class* iot_devices.devices.Yeelight.YeelightDevice(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### lock

#### rssiCacheTime *= 0*

#### lastLoggedUnreachable *= 0*

#### getRawDevice()

#### rssi(cacheFor=120, timeout=3)

These bulbs don't have RSSI that i found, instead we just detect reachability or not

### *class* iot_devices.devices.Yeelight.YeelightRGB(name, data)

Bases: [`YeelightDevice`](#iot_devices.devices.Yeelight.YeelightDevice)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'YeelightRGB'*

Every device must have a unique device_type name

#### kdClass

#### descriptors

#### flush()

#### on_before_close()

Subclass defined cleanup handler.

#### closed *= False*

#### lastHueChange

#### allowedOperations *= 60*

#### lastRecalcedAllowed

#### hasData *= False*

#### huesat *= -1*

#### lastVal *= -1*

#### wasOff *= True*

#### oldTransitionRate *= -1*

#### getSwitch(channel, state)

#### setSwitch(channel, state, duration=1)

#### setHSV(channel, hue, sat, val, duration=1)

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
