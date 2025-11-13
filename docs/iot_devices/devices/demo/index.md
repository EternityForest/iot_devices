# iot_devices.devices.demo

## Classes

| [`DemoDevice`](#iot_devices.devices.demo.DemoDevice)   | represents exactly one "device".   |
|--------------------------------------------------------|------------------------------------|

## Package Contents

### *class* iot_devices.devices.demo.DemoDevice(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'DemoDevice'*

Every device must have a unique device_type name

#### text_config_files *= ['test.conf']*

#### update_config(config: dict[str, Any])

Update the config dynamically at runtime.
May be subclassed by the device to respond to config changes.

#### *static* discover_devices(config={}, current_device=None, intent=None, \*\*kw)

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
