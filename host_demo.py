from typing import Any, Mapping
from iot_devices.host.simple_host import SimpleHost
from iot_devices.device import Device

data = {"type": "DemoDevice", "name": "demo_device"}


class Host(SimpleHost):
    def get_config_for_device(self, parent_device: Any | None, full_device_name: str):
        """When a device wants to add a subdevice,
        The host can give it extra config
        """
        return {"device.fixed_number_multiplier": "10000000"}

    def set_data_point(
        self,
        name: str,
        value: int | float | str | bytes | Mapping[str, Any] | list[Any],
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        "This is how devices send data to hosts"
        print(
            f"set_data_point({self}, {name}, {value}, {timestamp}, {annotation}, {force_push_on_repeat})"
        )
        return super().set_data_point(
            name, value, timestamp, annotation, force_push_on_repeat
        )


host = Host()


host.add_new_device(data)

# Devices are accessed via containers so the host can store extra data on
# them
device_container = host.devices["demo_device"]
device = device_container.device


# One of the values this class exposes
print(device.datapoints["random"])

# This is an on-demand getter
print(device.request_data_point("dyn_random"))

print(device.subdevices["subdevice"].config)

# Now let's look at the subdevice
print(device.subdevices["subdevice"].datapoints["random"])
