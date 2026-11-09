import time

import pytest
import stamina

from iot_devices.devices.demo import DemoDevice
from iot_devices.host.simple_host import SimpleHost

h = SimpleHost()


def test_demo_device():
    data = {"type": "DemoDevice", "name": "demo"}

    my_device = h.add_new_device(data).wait_device_ready()
    time.sleep(0.5)

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert "subdevice" in my_device.subdevices

    assert my_device.subdevices["subdevice"].get_parent(DemoDevice) is my_device
    my_device.close()


def test_demo_device_throw_on_create():
    data = {
        "type": "DemoDevice",
        "name": "throw_on_create",
        "device.throw_on_create": True,
    }

    with pytest.raises(Exception):
        h.add_new_device(data).wait_device_ready()


def test_demo_device_throw_on_close():
    data = {
        "type": "DemoDevice",
        "name": "throw_on_close",
        "device.throw_on_close": True,
    }

    my_device = h.add_new_device(data).wait_device_ready()

    # The exception raised by the device must be contained by the device
    # framework and reported to the host, not propagate out of close().
    my_device.close()

    # The host must still be fully usable after the failed close.
    d = h.add_new_device(
        {"type": "DemoDevice", "name": "after_close_error"}
    ).wait_device_ready()
    d.close()
