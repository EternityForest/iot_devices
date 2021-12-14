# iot_devices

Very early draft of an ultra-simple, platform independent abstraction of the idea of a "device".

The intent is that you can make plugins for automation frameworks that can also be trivially used as a standalone library.

The API is basically: Get a class based on a data dict, and make it.

It's designed so you can create a generic mixin that applies to any device matching the spec, and build your own API
that can be used to access any device using this spec.


## Implement a device
```python
from iot_devices import device

import random

class RandomDevice(device.Device):
    def __init__(self,name, data):
        device.Device.__init__(self,name, data)

        # Push type data point set by the device
        self.numeric_data_point("random")
        self.set_data_point("random",random.random())


        # On demand requestable data point pulled by application.
        # All you have to do is set the val to a callable.
        self.numeric_data_point("dyn_random")
        self.set_data_point_getter("random", random.random)
```

## Declare a module has devices
This tells the host what module you would need to import to get a device having a certain name.

```json
{
	"devices":{
		"RandomDevice": {
			"submodule":"devices.random"
			}
		}
} 
```

## Declare a module has devices 
```
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
