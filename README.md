# iot_devices

Very early draft of a platform independent abstraction of the idea of a "device".

The intent is that you can make plugins for automation frameworks that can also be trivially used as a standalone library.

The API is basically: Get a class based on a data dict, and make it.

It's designed so you can create a generic mixin that applies to any device matching the spec, and build your own API
that can be used to access any device using this spec.

It also aims to include a library of commonly used devices.

Note: The included example devices all have their own dependencies.  Most need Scullery.


## The tui-dash.py app

Code quality may not be the best here, it's just a demo/testing platform.  You will need the urwid TUI library to run this.

To use it, edit the tui-dash.conf file and run tui-dash.py  You'll get a nice text UI with all the devices.

Each section represents a device that will be added.  For example, here is the configuration
to access YoLink's home automation devices via the TUI.

Only one device is needed here, the top level service, all other devices are autodiscovered, but you 
can add extra configuration on a per-device basis.  The YoLink device requires paho-mqtt to function.

"""ini
[YoLinkService]
device.key= Your UAC key here
device.user_id=Your UAC password here
type = YoLinkService

# Hide this, it just creates the subdevices
hidden = True

[YoLinkService.Bedroom]
title = Bedroom Sensor

"""



## Implement a device

[Full device API docs](https://eternityforest.github.io/iot_devices/docs/iot_devices/device.html)

```python
from iot_devices import device

import random

class RandomDevice(device.Device):
    device_type = "RandomDevice"
    def __init__(self,name, data, **kw):
        device.Device.__init__(self,name, data, **kw)

        # Push type data point set by the device
        self.numeric_data_point("random")
        self.set_data_point("random",random.random())


        # On demand requestable data point pulled by application.
        # All you have to do is set the val to a callable.
        self.numeric_data_point("dyn_random")
        self.set_data_point_getter("dyn_random", random.random)
```

## Declare a module has devices
This tells the host what module you would need to import to get a device having a certain name.

This would go in a devices_manifest.json file in the root folder of any module.

Note that the name RandomDevice matches the name of the class.

The system will effectively do `from your_module.devices.random import RandomDevice` to find the device class.

```json
{
    "devices":{
        "RandomDevice": {
            "submodule":"devices.random"
            }
        }
} 
```


## Using the device

Note: We never have to import the module ourselves. It is imported on demand based on the data!
We automatically search sys.path and the demo device folder


[Full host API docs](https://eternityforest.github.io/iot_devices/docs/iot_devices/host.html)

``` python
from iot_devices.host import get_class

data = {
    "type": "RandomDevice"
}


# Get the class that would be able to construct a matching device given the data
c = get_class(data)

# Make an instance of that device
device = c("Random Device", data)

#One of the values this class exposes.
# Note that values here can be "None" if there is no data yet.
print(device.datapoints['random'])

# This is an on-demand getter.  
# This explicitly calls the getter we set.
# It also sets the key in device.datapoints
print(device.request_data_point('dyn_random'))

# clean up
c.close()
```

### Using subdevices

See host_demo.py







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

You also have a unit for numeric types.   There should not ever be any kind of complex schema language!!

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
 