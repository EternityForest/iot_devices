# iot_devices docs

TODO: better organization for the docs!

## Subdevices

By far the most complicated part of the device API.

Subdevices are devices created by another device, always having the name parent.child.

You will have to reimpliment most of create_subdevice in your host to do anything with them,
I did not think the architecture was really suitable for reuse.

### Random tips

They cannot be updated by the host the same way as normal devices.

Instead, you call update_config(c) with any new config.  By default, this just uses set_config_option for every key, but a device may subclass it to respond
dynamically.

Most subdevices should keep configurability to a minimum and be purely configured through the settings on the parent device, aside
from things that the subdevice itself doesn't need to know about.

Subdevice config is just a set of overrides for whatever config the parent passes.

Subdevices are dynamic.  A device may call create_subdevice at any time, but it cannot currently delete them.

Instead, closing a device always closes all subdevices. The main intent is for lists of autodiscovered devices. If you need to refresh the list,
recreate the master device.


You create a subdevice via device.create_subdevice(self, cls, name: str, config: Dict, *a, **k), passing ut the subdevice class, name(Just the nase name, not the parent name), and the config.

This function will add is_subdevice to config, along with setting name to parentname.childname.

It then adds the subdevice to parent.subdevices, listed under the child name.



The host should override this to detect a new device and do whatever is needed with it.

Only the host should call close() on a subdevice.


## Developing


### Misc

#### Device.\_\_init\_\_

This does nothing if called a second time, to simplify more complex inheritance patterns, as it is likely your device will need to call this before
doing anything, and other mixin classes used by the host may need to do the same.

#### Stateless services

Nothing should be added here that would preclude a device from being used in a stateless service container with all persistent data on a remote host.

#### Describing your data point type

You have a subtype parameter when declaring data types, as a hint to the GU generator. See [List of subtypes](docs/subtypes.md).

You also have a unit for numeric types.

#### Describing your config options

Every device class can have a "json_schema" variable for it's config.  If you don't set
one, iot_devices will always try to generate one. UIs can allways use device.get_full_schema()
and generate an editor page from that.


#### Special Data Point Names

If possible, use these names, hosts should know they are important and give them easy accessibility.

"color" with subtype color for a lighting device, "switch", for the main way you turn something on or off,
"start" and "stop" with subtype trigger for things you can control but do not generally remain on when turned on.

"rssi" for the recieved signal strength, "battery" with unit percent for the battery, "open" for the status of doors,
"on" for things with an on/off state but that you do not control manually, "powered" to indicate something has full power and is not running on backup batteries.

#### Documentation
This project uses google style docstrings with pdoc3.

`pdoc3 --html --output-dir=docs --force iot_devices` is used to generate the docs.

### Device tips


#### Interacting with the device.

There is no API for making calls to the device, or doing anything but reading, setting, and requesting data points,
and non-changed values are ignored.

If you have something like a button that needs to express one-time events, just use a counter so the data changes on every trigger.
If you need events with data, use a data point with `[eventname, timestamp]` or `[eventname, timestamp, data]`.

#### Networking

All devices are responsible for handling their own connection and auto-reconnection to any external servers.
There is no connect() API call and will not be!

#### Blank devices

All device keys beyond the type and name must be optional.  Devices should auto-add any other required keys.
Hosts can then let users edit from there.  The device can log errors for the missing info but has to be constructible.

#### Cleanup

Modules must handle there own cleanup when no more devices of a type are used. There is no separate concept of an "integration"
or "adapter" to unload or clean up.  There's just devices.

#### Interactive setup

There is not and will not be an interactive setup feature. You can do it yourself using the management form API, or use discovery.

Starting with a partially-configured device that has enough information to do discovery(Such as MQTT accound info or the like),
you can just pass that config to the discover_devices dict and allow a user to choose one of them.

If there are more steps, the user can fill out missing info on the new device and do the discovery again.
