import subprocess
import os
import time
import stamina
from iot_devices.host.simple_host import SimpleHost


esphome_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "esphome_test"))

h = SimpleHost()


def test_bad_pw():
    subprocess.check_call(
        ["esphome", "compile", "test_server_conf.yaml"], cwd=esphome_dir
    )
    subprocess.call(["pkill", "-f", "esphome_test"])

    p = subprocess.Popen(
        [".esphome/build/hosttest/.pioenvs/hosttest/program"], cwd=esphome_dir
    )
    time.sleep(0.1)
    # Make sure it's running
    assert p.poll() is None

    deviceData = {
        "type": "ESPHomeDevice",
        "name": "MyDevice",
        "hostname": "127.0.0.1",
        "apikey": "LkNUUoOtGdp0C2aiVGjnerDtF1/lBe7nNq142V12Zj0=",
    }

    device = h.add_new_device(deviceData).wait_device_ready()

    time.sleep(5)

    assert not device.datapoints["native_api_connected"].get()[0]
    print(device.datapoints)
    device.close()
    p.kill()


def test_native_api():
    subprocess.check_call(
        ["esphome", "compile", "test_server_conf.yaml"], cwd=esphome_dir
    )
    subprocess.call(["pkill", "-f", "esphome_test"])

    p = subprocess.Popen(
        [".esphome/build/hosttest/.pioenvs/hosttest/program"], cwd=esphome_dir
    )
    time.sleep(0.1)
    # Make sure it's running
    assert p.poll() is None

    deviceData = {
        "type": "ESPHomeDevice",
        "name": "MyDevice",
        "device.hostname": "127.0.0.1",
        "device.apikey": "LkMUUoOtGdp0C2aiVGjnerDtF1/lBe7nNq142V12Zj0=",
    }

    device = h.add_new_device(deviceData).wait_device_ready()

    while "native_api_connected" not in device.datapoints:
        time.sleep(1)

    time.sleep(2)
    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert device.datapoints["native_api_connected"].get()[0]
            assert "testbutton" in device.datapoints

    device.set_data_point("testbutton", 1)

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert device.datapoints["button_counter"].get()[0] == 1

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert device.datapoints["seconds_counter"].get()[0] > 0

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert "myfixedtextsensor" in device.datapoints

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert (
                device.datapoints["myfixedtextsensor"].get()[0]
                == "This is my fixed text value"
            )

    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert device.datapoints["loopback_num_out"].get()[0] == 0

    device.set_data_point("loopback_num_in", 5)
    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert device.datapoints["loopback_num_out"].get()[0] == 5

    assert device.datapoints["loopback_bool_out"].get()[0] == 0

    device.set_data_point("loopback_bool_in", 1)
    for attempt in stamina.retry_context(on=AssertionError, attempts=20):
        with attempt:
            assert device.datapoints["loopback_bool_out"].get()[0] == 1

    device.close()
    p.kill()


if __name__ == "__main__":
    test_native_api()
