import time
import stamina
from iot_devices.host.simple_host import SimpleHost

h = SimpleHost()


def test_demo_device():
    data = {"type": "ServerMonitor", "name": "ServerMonitor", "target": "localhost"}

    my_device = h.add_new_device(data).wait_device_ready()
    time.sleep(0.5)

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert my_device.datapoints["status"].get()[0]
            assert isinstance(my_device.datapoints["status"].get()[0], int | float)
    my_device.close()
