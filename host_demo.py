from iot_devices.host import get_class

data = {
    "type": "RandomDevice"
}


# Get the class that would be able to construct a matching device given the data
c = get_class(data)

# Make an instance of that device
device = c("Random Device", data)

#One of the values this class exposes
print(device.datapoints['random'])