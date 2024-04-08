import random
import iot_devices.device as device
from iot_devices.host import get_class, create_device


class RandomDevice(device.Device):
    "Text making custom devices"

    device_type = "RandomDevice"

    def __init__(self, name, data, **kw):
        device.Device.__init__(self, name, data, **kw)

        # Push type data point set by the device
        self.numeric_data_point("random")
        self.set_data_point("random", random.random())

        # On demand requestable data point pulled by application.
        # All you have to do is set the val to a callable.
        self.numeric_data_point("dyn_random")
        self.set_data_point_getter("dyn_random", random.random)


def test_random():
    r = RandomDevice("DevName", {})
    v = r.request_data_point("dyn_random")
    v2 = r.request_data_point("dyn_random")
    assert v != v2


def test_demo_device():
    data = {"type": "DemoDevice"}

    c = get_class(data)
    my_device = create_device(c, "A Device", data)

    assert my_device.datapoints["random"] > 0
    assert my_device.datapoints["random"] < 1

    v = my_device.request_data_point("dyn_random")
    v2 = my_device.request_data_point("dyn_random")

    assert v != v2

    # clean up
    my_device.close()
