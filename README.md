# iot_devices

Very early draft of an ultra-simple, platform independent abstraction of the idea of a "device".

The intent is that you can make plugins for automation frameworks that can also be trivially used as a standalone library.

The API is basically: Get a class based on a data dict, and make it.

It's designed so you can create a generic mixin that applies to any device matching the spec, and build your own API
that can be used to access any device using this spec.

It also aims to include a library of commonly used devices.

Note: The included example devices all have their own dependencies.  Most need Scullery.

## Implement a device

[Full device API docs](https://eternityforest.github.io/iot_devices/docs/iot_devices/device.html)

```python
from iot_devices import device

import random

class RandomDevice(device.Device):
    device_type = "RandomDevice"
    def __init__(self,name, data):
        device.Device.__init__(self,name, data)

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
```


## Developing

### Misc

#### Stateless services

Nothing should be added here that would preclude a device from being used in a stateless service container with all persistent data on a remote host.

#### Describing your data point type

You have a subtype parameter when declaring data types, as a hint to the GU generator. See [List of subtypes](docs/subtypes.md).

You also have a unit for numeric types.   There should not ever be any kind of complex schema language!!


#### Documentation
This project uses google style docstrings with pdoc3.

`pdoc3 --html --output-dir=docs --force iot_devices` is used to generate the docs.

### Device tips

### Property names

If the device has "subdevices",  the properties should be of the form "subdevicename.property"


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
 