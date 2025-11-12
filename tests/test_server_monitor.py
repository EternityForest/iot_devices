import time
import stamina
from iot_devices.host import get_class, create_device


def test_demo_device():
    data = {"type": "ServerMonitor", "target": "localhost"}

    c = get_class(data)
    my_device = create_device(c, "ADevice", data)
    time.sleep(0.5)

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert my_device.datapoints["status"].get()[0]
            assert isinstance(my_device.datapoints["status"].get()[0], int | float)
    my_device.close()
