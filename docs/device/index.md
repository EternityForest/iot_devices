# iot_devices.device

## Attributes

| [`DeviceClassTypeVar`](#iot_devices.device.DeviceClassTypeVar)   |    |
|------------------------------------------------------------------|----|
| [`devices_list_lock`](#iot_devices.device.devices_list_lock)     |    |
| [`all_devices`](#iot_devices.device.all_devices)                 |    |
| [`minimum`](#iot_devices.device.minimum)                         |    |
| [`maximum`](#iot_devices.device.maximum)                         |    |

## Classes

| [`LegacyConfigProperties`](#iot_devices.device.LegacyConfigProperties)   | Represents the old style config properties dict,   |
|--------------------------------------------------------------------------|----------------------------------------------------|
| [`Device`](#iot_devices.device.Device)                                   | represents exactly one "device".                   |

## Functions

| [`apply_defaults`](#iot_devices.device.apply_defaults)(data, schema)   |    |
|------------------------------------------------------------------------|----|

## Module Contents

### iot_devices.device.DeviceClassTypeVar

### iot_devices.device.apply_defaults(data, schema)

### iot_devices.device.devices_list_lock

### iot_devices.device.all_devices *: dict[str, weakref.ref[[Device](#iot_devices.device.Device)]]*

### iot_devices.device.minimum

### iot_devices.device.maximum

### *class* iot_devices.device.LegacyConfigProperties(device: [Device](#iot_devices.device.Device), config: dict[str, Any])

Represents the old style config properties dict,
and converts anything you do

#### device

#### config

#### *property* raw

#### \_\_iter_\_()

#### \_\_getitem_\_(key: str)

#### \_\_setitem_\_(key: str, value: dict[str, Any])

### *class* iot_devices.device.Device(name: str, config: dict[str, str], subdevice_config: dict[str, Any] | None = None, \*\*kw: Any)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *: str* *= 'Device'*

#### readme *: str* *= ''*

Schema defining the config

#### config_schema *: dict[str, Any]*

DEPRECATED, use config_schema

#### json_schema *: dict[str, Any]*

#### upgrade_legacy_config_keys *: dict[str, str]*

#### *property* is_subdevice *: bool*

True if this is a subdevice, as determine by the is_subdevice key in the config

#### *property* config_properties *: [LegacyConfigProperties](#iot_devices.device.LegacyConfigProperties)*

Included for basic compatibility, hosts can stll work without the data but should
upgrade to JSON schemas.

#### get_full_schema() → dict[str, Any]

Returns a full schema of the device. Including
auto-generated properties, and generic things all devices should have.

Frameworks may subclass to add their own extension properties.

#### close_subdevice(name: str)

Close and deletes a subdevice without permanently deleting
any config associated with it.  Should only be called by the
device itself.

#### create_subdevice(cls: type[DeviceClassTypeVar], name: str, config: dict[str, Any], \*a: Any, \*\*k: Any) → DeviceClassTypeVar

Creates a subdevice
Args:

> cls: The class used to make the device
> name: The base name of the device.  The full name will be parent.basename

> > but you only supply the base name here.

> config: The config as would be passed to any other device, which the host may override.

Returns:
: The device object

Allows a device to create it's own subdevices.

The host implementation must take the class, make whatever subclass
is needed based on it, Then instantiate it as if the other parameters were given straight to
the device, overriding them with any user config that is known by the host.

The host will put the device object into the parent device's subdevice
dict. Alll subdevices must be closed before the parent.

The host will rename the device to reflect that it is a subdevice.
It's full name will be parent.basename.

The host will allow configuration of the device like any other device.
It will override whatever config that you give this function
with the user config.

Once the subdevice exists, the host cannot close it, that is the responsibility
of the main device.  The host can only close the parent device.

it must update the config in place if the user wants to make changes,
using set_config_option or update_config.d

When closing a device, the device must close all of it's subdevices and
clean up after itself.  The default close() does this for you.

The entry in self.subdevices will always be exactly as given
to this function, referred to as the base name

The host will add is_subdevice=True to the config dict.

#### get_config_folder(create: bool = True)

Devices may, in some frameworks, have their own folder in which they can place additional
configuration, allowing for advanced features that depend on user content.

Returns:
: An absolute path

#### *static* discover_devices(config: dict[str, Any], current_device: object | None = None, intent: str = '', \*\*kwargs: Any) → dict[str, dict[str, Any]]

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

#### set_config_option(key: str, value: Any)

sets a top-level key in self.config. used for subclassing as you may want
to persist.

\_\_init_\_ will automatically set the state.  this is used by the device
itself to set it's own persistent values at runtime, perhaps in response
to a websocket message.

\_\_init_\_ will automatically set the state when passed the config dict,
you don't have to do that part.

This is used by the device itself to set it's own persistent values at
runtime, perhaps in response to a websocket message.

the host is responsible for subclassing this and actually saving the
data somehow, should that feature be needed.

The device may subclass this to respond to realtime config changes.

Devices should not clean up or get rid of keys they do not understand,
because the host application may use (suitably prefixed for uniqueness) extra
keys.

#### set_config_default(key: str, value: str)

sets an top-level option in self.config if it does not exist or is blank.
Calls into set_config_option, you should not need to subclass this.

#### wait_ready(timeout: float = 15)

Call this to block for up to timeout seconds for the device to be fully initialized.
Use this in quick scripts with a devices that readies itself asynchronously.

May be implemented by the device, but is not required.

#### print(s: str, title: str = '')

used by the device to print to the hosts live device message feed, if such a thing should happen to exist

#### handle_error(s: str, title: str = '')

like print but specifically marked as error. may get special notification.  should not be used for brief network loss

#### handle_exception()

Helper function that just calls handle_error with a traceback.

#### handle_event(event: str, data: Any | None)

Handle arbitrary messages from the host

#### numeric_data_point(name: str, , min: float | None = None, max: float | None = None, hi: float | None = None, lo: float | None = None, default: float | None = None, description: str = '', unit: str = '', handler: collections.abc.Callable[[float, float, Any], Any] | None = None, interval: float = 0, subtype: str = '', writable: bool = True, dashboard: bool = True, \*\*kwargs: Any)

Register a new numeric data point with the given properties.

Handler will be called when it changes.
self.datapoints[name] will start out with tha value of None

The intent is that you can subclass this and have your own implementation of data points,
such as exposing an MQTT api or whatever else.

Most fields are just extra annotations to the host.

Args:
: min: The min value the point can take on
  max: The max value the point can take on
  <br/>
  hi: A value the point can take on that would be
  : considered excessive
  <br/>
  lo: A value the point can take on that would be
  : considered excessively low
  <br/>
  description: Free text
  <br/>
  unit: A unit of measure, such as "degC" or "MPH"
  <br/>
  default: If unset default value is None,
  : or may be framework defined. Default does not trigger handler.
  <br/>
  handler: A function taking the value,timestamp,
  : and annotation on changes.
  <br/>
  interval :annotates the default data rate the point
  : will produce, for use in setting default poll
    rates by the host, if the host wants to poll.
    It does not mean the host SHOULD poll this,
    it only suggest a rate to poll at if the host
    has an interest in this data.
  <br/>
  writable:  is purely for a host that might subclass
  : this, to determine if it should allow writing to the point.
  <br/>
  subtype: A string further describing the data
  : type of this value, as a hint to UI generation.
  <br/>
  dashboard: Whether to show this data point in overview displays.

#### string_data_point(name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[str, float, Any], Any] | None = None, default: str | None = None, interval: float = 0, writable: bool = True, subtype: str = '', dashboard: bool = True, \*\*kwargs: Any)

Register a new string data point with the given properties.

Handler will be called when it changes.
self.datapoints[name] will start out with tha value of None

Interval annotates the default data rate the point will produce, for use in setting default poll
rates by the host, if the host wants to poll.

Most fields are just extra annotations to the host.

Args:
: description: Free text
  <br/>
  default: If unset default value is None, or may be framework defined. Default does not trigger handler.
  <br/>
  handler: A function taking the value,timestamp, and annotation on changes.
  <br/>
  interval: annotates the default data rate the point will produce, for use in setting default poll
  : rates by the host if the host wants to poll.
    <br/>
    It does not mean the host SHOULD poll this,
    it only suggest a rate to poll at if the host has an interest in this data.
  <br/>
  writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.
  <br/>
  subtype: A string further describing the data type of this value, as a hint to UI generation.
  <br/>
  dashboard: Whether to show this data point in overview displays.

#### object_data_point(name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[collections.abc.Mapping[str, Any], float, Any], Any] | None = None, interval: float = 0, writable: bool = True, subtype: str = '', dashboard: bool = True, \*\*kwargs: Any)

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

#### bytestream_data_point(name: str, , description: str = '', unit: str = '', handler: collections.abc.Callable[[bytes, float, Any], Any] | None = None, writable: bool = True, dashboard: bool = True, \*\*kwargs: Any)

register a new bytestream data point with the
given properties. handler will be called when it changes.
only meant to be called from within \_\_init_\_.

Bytestream data points do not store data,
they only push it through.

Despite the name, buffers of bytes may not be broken up or combined, this is buffer oriented,

#### push_bytes(name: str, value: bytes)

Same as set_data_point but for bytestream data

#### set_data_point(name: str, value: int | float | str | bytes | collections.abc.Mapping[str, Any] | list[Any], timestamp: float | None = None, annotation: Any | None = None)

Set a data point of the device. may be called by the device itself or by user code.

This is the primary api and we try to funnel as much as absolutely possible into it.

things like button presses that are not actually
"data points" can be represented as things like
(button_event_name, timestamp) tuples in object_tags.

things like autodiscovered ui can be done just by
adding more descriptive metadata to a data point.

Args:
: name: The data point to set
  <br/>
  value: The literal value.
  : Use set_data_point_getter for a
    callable which will return such.
  <br/>
  timestamp: if present is a time.time() time.
  <br/>
  annotation: is an arbitrary object meant to be
  : compared for identity,
    for various uses, such as loop prevention
    when dealting with network sync, when you need
    to know where a value came from.

This must be thread safe, but the change detection
could glitch out and discard if you go from A to B
and back to A again.

When there is multiple writers you will want
to either do your own lock or ensure that
dyou use unique values,
like with an event counter.

#### set_data_point_getter(name: str, getter: collections.abc.Callable[[], int | float | str | bytes | collections.abc.Mapping[str, Any] | None])

Set the Getter of a datapoint, making it into an
on-request point.
The callable may return either the new value,
or None if it has no new data.

#### on_data_change(name: str, value: Any, timestamp: float, annotation: Any)

Used for subclassing, this is how you watch for
data changes

#### request_data_point(name: str) → Any

Rather than just passively read, actively
request a data point's new value.
May return None and just cause the point to be updated later.

Meant to be called by external host code.

#### set_alarm(name: str, datapoint: str, expression: str, priority: str = 'info', trip_delay: float = 0, auto_ack: bool = False, release_condition: str | None = None, \*\*kw: Any)

declare an alarm on a certain data point.
means we should consider the data point to be in an
alarm state whenever the expression is true.

used by the device itself to tell the host what
it considers to be an alarm condition.

the expression must look like "value > 90", where
the operator can be any of the common comparision
operators(<,>,<=,>=,==,!= )

you may set the trip delay to require it to stay
tripped for a certain time,
polling during that time and resettig if it is not
tripped.

the alarm remains in the alarm state till the release
condition is met, by default it's just when the trip
condition is inactive.  at which point it will need
to be acknowledged by the user.

these alarms should be considered "presets" that
the user can override if possible.
by default this function could just be a no-op,
it's here because of kaithem_automation's alarm support,
but many applications may be better off with full manual
alarming.

in kaithem the expression is arbitrary,
but for this lowest common denominator definition
it's likely best to
limit it to easily semantically parsible strings.

#### close()

Release all resources and clean up

#### on_delete()

release all persistent resources, used by the host
app to tell the user the device is being permanently
deleted.
may be used to delete any files automatically created.

#### update_config(config: dict[str, Any])

Update the config dynamically at runtime.
May be subclassed by the device, not the host.

By default just uses set_config_option once for every top-level key.
