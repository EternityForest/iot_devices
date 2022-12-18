from iot_devices.host import get_class

data = {
    "type": "DemoDevice"
}


# Get the class that would be able to construct a matching device given the data
c = get_class(data)

# DemoDevice makes a subdevice with the name "subdevice".
# We will add some configuration.

# Note config keys must strictly be strings
subdevice_config={
    "subdevice":{
        "device.fixed_number_multiplier": "10000000"
    }
}

# We pass a function that takes a name and returns config for that subdevice
def f(device_name):
    return subdevice_config.get(device_name, {})


#Since subdevices are dynamic we want to be notified.
class Wrapped(c):
    def create_subdevice(self,*a,**k):
        sd = c.create_subdevice(self, *a, **k)
        print("Subdevice "+ sd.title + " was created")
        return sd


# Make an instance of that device
device = Wrapped("Random Device", data, subdevice_config=f)

#One of the values this class exposes
print(device.datapoints['random'])

# This is an on-demand getter
print(device.request_data_point('dyn_random'))

#Now let's look at the subdevice
print(device.subdevices['subdevice'].datapoints['random'])