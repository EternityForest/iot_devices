import time
import stamina
from iot_devices.host.simple_host import SimpleHost

h = SimpleHost()


def test_demo_device():
    data = {"type": "DemoDevice", "name": "demo"}

    my_device = h.add_new_device(data).wait_device_ready()
    time.sleep(0.5)

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert "subdevice" in my_device.subdevices
    my_device.close()
