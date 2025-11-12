import time
import stamina
from iot_devices.host.simple_host import SimpleHost


def test_basic_loop():
    server_conf = {
        "type": "ArduinoCogsServer",
        "port": 6741,
        "tagpoints": [
            {
                "name": "test_bool",
                "writable": True,
                "resolution": 1,
                "min": 0,
                "max": 1,
                "unit": "bool",
                "subtype": "bool",
            }
        ],
    }

    h = SimpleHost()
    dc = h.add_new_device(server_conf)
    s = dc.wait_device_ready()

    while "test_bool" not in s.datapoints:
        time.sleep(1)

    assert s.datapoints["test_bool"].get()[0] == 0
    s.set_data_point("test_bool", 1)
    assert s.datapoints["test_bool"].get()[0] == 1

    client_conf = {
        "type": "ArduinoCogsClient",
        "name": "MyClientDevice",
        "url": "127.0.0.1:6741",
    }

    time.sleep(2)
    clientcontainer = h.add_new_device(client_conf)
    client = clientcontainer.wait_device_ready()

    for attempt in stamina.retry_context(on=Exception, attempts=20):
        with attempt:
            assert client.datapoints["test_bool"].get()[0] == 1


if __name__ == "__main__":
    test_basic_loop()
