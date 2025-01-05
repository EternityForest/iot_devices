from iot_devices.host import get_class
from iot_devices.device import Device

data = {"type": "DemoDevice"}


# Get the class that would be able to construct a matching device given the data
dev_cls = get_class(data)

# DemoDevice makes a subdevice with the name "subdevice".
# We will add some configuration.

# Note config keys must strictly be strings
subdevice_config = {"subdevice": {"device.fixed_number_multiplier": "10000000"}}

# We pass a function that takes a name and returns config for that subdevice
# Only use for very simple cases, prefer doing the config right in create_subdevice in a wrapped class


def f(device_name, *a, **k):
    return subdevice_config.get(device_name, {})


# Since subdevices are dynamic we want to be notified.


def wrap(c):
    class Wrapped(c):
        def create_subdevice(self, cls, *a, **k):
            # Customize the subdevice class with the same host integrations
            wrap(cls)

            sd = Device.create_subdevice(self, cls, *a, **k)
            print("Subdevice " + sd.title + " was created")
            return sd

    return Wrapped


# Wrapping is how the host customizes classes to integrate with host features
wrapped = wrap(dev_cls)

# Make an instance of that device
device = wrapped("Random Device", data, subdevice_config=f)

# One of the values this class exposes
print(device.datapoints["random"])

# This is an on-demand getter
print(device.request_data_point("dyn_random"))

# Now let's look at the subdevice
print(device.subdevices["subdevice"].datapoints["random"])
