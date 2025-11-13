# iot_devices

![MIT](badges/mit.png)
![Python](badges/python.png)
![Pre-commit Badge](badges/pre-commit.png)
![Pytest](badges/pytest.png)


Platform independent abstraction of the idea of a "device".

The intent is that you can make plugins for automation frameworks that can also be trivially used as a standalone library.

The API is basically: Get a class based on a data dict, and make it.

It's designed so you can create a generic mixin that applies to any device matching the spec, and build your own API
that can be used to access any device using this spec.

It also aims to include a library of commonly used devices.

It can be installed with "pip3 install iot_devices".


## The tui-dash.py app

To use it, edit the tui-dash.conf file and run the tui-dash command in your virtual env with the project and any plugins.

You'll get a nice text UI with all the devices in your file.

This is being rewritten, so it doesn't do very much at the moment.

```ini
[[devices]]
name="Demo"
type="DemoDevice"

[[devices]]
name="AnotherDemo"
type="DemoDevice"

```



## Implement a device

All devices must NOT do anything destructive when created with default arguments,
as is users are meant to be able to make a blank device in the UI.

[Full device API docs](https://eternityforest.github.io/iot_devices/docs/iot_devices/device.html)

```python
import iot_devices.device as device
import random

class RandomDevice(device.Device):
    device_type = "RandomDevice"

    # This schema determines the config a host will give us.
    # The host will also give us a few extra special keys.
    config_schema = {
        "properties":{
            "demo_param":
                {
                    "type": "string"
                }
        }
    }

    def __init__(self,name, config, **kw):
        device.Device.__init__(self,name, config, **kw)

        # Push type data point set by the device
        d = self.numeric_data_point("random")
        d.set(random.random())
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

Note: We never have to import the module ourselves. It is imported on demand based on the data!  We automatically search sys.path.  But you can also import the class yourself for low level control.


[Full host API docs](https://eternityforest.github.io/iot_devices/docs/iot_devices/host.html)

``` python
from iot_devices.host.simple_host import SimpleHost

data = {
    "type": "DemoDevice",
    "name": "MyDemo"
}

h = SimpleHost()
dev = h.add_new_device(data).wait_device_ready()

print(dev.datapoints)
dev.close()
```

### Using subdevices

See host_demo.py




## Bool Values
iot_devices use the following strings to represent booleans.

```python
TRUE_STRINGS = ("true", "yes", "on", "enable", "active", "enabled", "1")
FALSE_STRINGS = ("false", "no", "off", "disable", "inactive", "disabled", "0")
```

Use `iot_devices.util.str_to_bool(f)` to check the value, and raise a ValueError on an invalid string.


### Docs for the included devices

See devicedocs.md for a code example of each one.  Note these are generated with iot_devices_scan.py.  This script searches all of the python paths for any folder that contains devices,  creates
an instance of each one, and inspects the object to generate report, including a usable code example.

For example, here's an auto-generated example of using a GPIO input, powered by the GPIOZero library.

```python
from iot_devices.host import create_device
from iot_devices.devices.GPIODevice import GPIOInput

dev = create_device(GPIOInput, "name", {
    'active_high': 'true',
    'pull_up': 'false',
    'pull_down': 'false',
    'pin': 'MOCK1',
    'debounce_time_ms': '0'
})



# boolean
print(dev.datapoints['value'])
# >>> 0

```

## Add Metadata to your data points

Full signature of data point functions:

```python
    def numeric_data_point(
        self,
        name: str,
        *,
        min: float | None = None,
        max: float | None = None,
        hi: float | None = None,  # pylint: disable=unused-argument
        lo: float | None = None,  # pylint: disable=unused-argument
        default: float | None = None,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[float, float, Any], Any] | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        writable=True,  # pylint: disable=unused-argument
        dashboard=True,  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ):
        """Register a new numeric data point with the given properties.

        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None

        The intent is that you can subclass this and have your own implementation of data points,
        such as exposing an MQTT api or whatever else.

        Most fields are just extra annotations to the host.

        Args:
            min: The min value the point can take on
            max: The max value the point can take on

            hi: A value the point can take on that would be
                considered excessive
            lo: A value the point can take on that would be
                considered excessively low

            description: Free text

            unit: A unit of measure, such as "degC" or "MPH"

            default: If unset default value is None,
                or may be framework defined. Default does not trigger handler.

            handler: A function taking the value,timestamp,
                and annotation on changes.

            interval :annotates the default data rate the point
                will produce, for use in setting default poll
                rates by the host, if the host wants to poll.
                It does not mean the host SHOULD poll this,
                it only suggest a rate to poll at if the host
                has an interest in this data.

            writable:  is purely for a host that might subclass
                this, to determine if it should allow writing to the point.

            subtype: A string further describing the data
                type of this value, as a hint to UI generation.

            dashboard: Whether to show this data point in overview displays.

        """

    def string_data_point(
        self,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[str, float, Any], Any] | None = None,
        default: str | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        writable=True,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        dashboard=True,  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ):
        """Register a new string data point with the given properties.

        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None

        Interval annotates the default data rate the point will produce, for use in setting default poll
        rates by the host, if the host wants to poll.

        Most fields are just extra annotations to the host.


        Args:
            description: Free text

            default: If unset default value is None, or may be framework defined. Default does not trigger handler.

            handler: A function taking the value,timestamp, and annotation on changes.

            interval: annotates the default data rate the point will produce, for use in setting default poll
                rates by the host if the host wants to poll.

                It does not mean the host SHOULD poll this,
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

            subtype: A string further describing the data type of this value, as a hint to UI generation.

            dashboard: Whether to show this data point in overview displays.
        """

    def object_data_point(
        self,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[dict, float, Any], Any] | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        writable=True,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        dashboard=True,  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ):
        """Register a new object data point with the given properties.   Here "object"
        means a JSON-like object.

        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None

        Interval annotates the default data rate the point will produce, for use in setting default poll
        rates by the host, if the host wants to poll.

        Most fields are just extra annotations to the host.

        Args:
            description: Free text

            handler: A function taking the value,timestamp, and annotation on changes

            interval :annotates the default data rate the point will produce, for use in setting default poll
                rates by the host, if the host wants to poll.  It does not mean the host SHOULD poll this,
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

            subtype: A string further describing the data type of this value, as a hint to UI generation.

            dashboard: Whether to show this data point in overview displays.
        """

    def bytestream_data_point(
        self,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[bytes, float, Any], Any] | None = None,
        writable=True,  # pylint: disable=unused-argument
        dashboard=True,  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ):
        """register a new bytestream data point with the
        given properties. handler will be called when it changes.
        only meant to be called from within __init__.

        Bytestream data points do not store data,
        they only push it through.

        Despite the name, buffers of bytes may not be broken up or combined, this is buffer oriented,

        """
```

## Datapoint edge cases

When a data point is created, it has timestamp 0,
and value of whatever you pass as the default param.

Timestamps can be seen at device.datapoint_timestamps.  In the future a race condition free API
may be added to access the point and timestamp at once.

### Handling data that was created before device loads

The host app may override this by subclassing, so after creating a data point, check the datapoint timestamp to see if the host has set the it to something.

This is because the host might be restoring saved data, or connecting it to some existing data sources.

This initial setup will never trigger a change that would call the handler, as it is not actually a data change, only a loading of old data.

### Handlers and changes

Handlers trigger when the value changes, with one exception.  If the timestamp is zero, and something sets the value, the handler fires even if the value stays the same, because if the timestamp is zero it's considered "still on the default" which is treated specially.

Imagine something like a temperature sensor that defaults to 25C if it doesn't have real data, when the first real data comes in, you probably expect the handler to fire even if the real data is 25C.