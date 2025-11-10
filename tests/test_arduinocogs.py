import time
import stamina
from iot_devices.host import get_class, create_device


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

    s = create_device(get_class(server_conf), "MyServerDevice", server_conf)

    while "test_bool" not in s.datapoints:
        time.sleep(1)

    assert s.datapoints["test_bool"] == 0
    s.set_data_point("test_bool", 1)
    assert s.datapoints["test_bool"] == 1

    client_conf = {
        "type": "ArduinoCogsClient",
        "url": "127.0.0.1:6741",
    }

    time.sleep(2)
    client = create_device(get_class(client_conf), "MyClientDevice", client_conf)

    for attempt in stamina.retry_context(on=Exception, attempts=20):
        with attempt:
            assert client.datapoints["test_bool"] == 1


# def physical_device():
#     client_conf = {
#         "type": "ArduinoCogsClient",
#         "url": "gbremote.local",
#     }

#     time.sleep(2)
#     client = create_device(get_class(client_conf), "MyClientDevice", client_conf)
#     time.sleep(2)

#     client.set_data_point("board.backlight", 255)


#     for i in range(10):
#         print(client.datapoints)
#         time.sleep(0.5)

if __name__ == "__main__":
    test_basic_loop()
