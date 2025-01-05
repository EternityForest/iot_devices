import random
from typing import Any
import iot_devices.device as device
from iot_devices.host import get_class, create_device


class RandomDevice(device.Device):
    "Text making custom devices"

    device_type = "RandomDevice"

    def __init__(self, name: str, data: dict[str, Any], **kw: Any):
        device.Device.__init__(self, name, data, **kw)

        # Push type data point set by the device
        self.numeric_data_point("random")
        self.set_data_point("random", random.random())

        # On demand requestable data point pulled by application.
        # All you have to do is set the val to a callable.
        self.numeric_data_point("dyn_random")
        self.set_data_point_getter("dyn_random", random.random)

        self.obj = {"foo": 0}

        def obj_getter():
            self.obj["foo"] += 1
            return self.obj

        def str_getter():
            return "foo"

        def bytes_getter():
            return b"foo"

        self.object_data_point("obj")
        self.set_data_point_getter("obj", obj_getter)

        self.string_data_point("str")
        self.set_data_point_getter("str", str_getter)

        self.bytestream_data_point("bytes")
        self.set_data_point_getter("bytes", bytes_getter)

        self.string_data_point("steamedhams")
        self.set_data_point("steamedhams", "foo")

        self.bytestream_data_point("steamedhams3")
        self.set_data_point("steamedhams3", b"foo")

        self.set_config_default("device.steamedhams", "1")


def test_random():
    r = RandomDevice("DevName", {})
    v = r.request_data_point("dyn_random")
    v2 = r.request_data_point("dyn_random")
    assert v != v2

    # Auto generated property
    assert r.get_full_schema()["properties"]["device.steamedhams"]["type"] == "string"

    assert r.datapoints["steamedhams"] == "foo"
    assert r.datapoints["steamedhams3"] == b"foo"

    r.request_data_point("str")
    r.request_data_point("bytes")
    r.request_data_point("obj")

    assert r.datapoints["str"] == "foo"
    assert r.datapoints["bytes"] == b"foo"
    assert r.datapoints["obj"] == {"foo": 1}

    # It should have been copyed to prevent
    # mutating the source object, not that people should be
    # mutating it in the first place.
    assert id(r.datapoints["obj"]) != id(r.obj)

    r.request_data_point("obj")
    assert r.datapoints["obj"] == {"foo": 2}


def test_demo_device():
    data = {"type": "DemoDevice"}

    c = get_class(data)
    my_device = create_device(c, "A Device", data)

    assert isinstance(my_device.datapoints["random"], (float, int))
    assert my_device.datapoints["random"] > 0
    assert my_device.datapoints["random"] < 1

    v = my_device.request_data_point("dyn_random")
    v2 = my_device.request_data_point("dyn_random")

    assert v != v2

    # clean up
    my_device.close()
