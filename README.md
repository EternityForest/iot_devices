# iot_devices

Very early draft of a platform independent abstraction of the idea of a "device".

The intent is that you can make plugins for automation frameworks that can also be trivially used as a standalone library.

The API is basically: Get a class based on a data dict, and make it.

It's designed so you can create a generic mixin that applies to any device matching the spec, and build your own API
that can be used to access any device using this spec.

It also aims to include a library of commonly used devices.

It can be installed with "pip3 install iot_devices".

The Network Video Recorder device can be installed with "pip3 install NVRChannel".



## The tui-dash.py app

To use it, edit the tui-dash.conf file and run the tui-dash command after installing the app.  You'll get a nice text UI with all the devices in your file.

You can either put the file in ~/.config/tui-dash/tui-dash.conf, or pass the filename
as the first argument.


Each section represents a device that will be added.  For example, here is the configuration
to access YoLink's home automation devices via the TUI.

Only one device is needed here, the top level service, all other devices are autodiscovered, but you  can add extra configuration on a per-device basis.


```ini
[YoLinkService]
device.key= Your UAC key here
device.user_id=Your UAC password here
type = YoLinkService

# Hide this, it just creates the subdevices
hidden = True

[YoLinkService.Bedroom]
title = Bedroom Sensor

```



## Implement a device

Note: All devices must NOT do anything destructive when created with default arguments.

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

Note: We never have to import the module ourselves. It is imported on demand based on the data!  We automatically search sys.path.


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



### Docs for the included devices

See devicedocs.md.  Note these are generated with tui-dash inspect-deep, an experimental
command that actually creates an instance of every device.