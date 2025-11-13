from iot_devices import device
import gpiozero
from gpiozero.pins.mock import MockFactory


gpio_config_schema = {
    "type": "object",
    "properties": {
        "pin": {"type": "string", "default": "MOCK1"},
        "active_high": {"type": "boolean", "default": True},
        "pwm_frequency": {"type": "integer", "default": 100},
        "initial_value": {"type": "float", "min": 0, "max": 1},
        "pull_up": {"type": "boolean", "default": False},
        "pull_down": {"type": "boolean", "default": False},
        "debounce_time_ms": {"type": "integer", "default": 0},
    },
    "required": ["pin"],
}


class GPIOOutput(device.Device):
    device_type = "GPIOOutput"
    config_schema = gpio_config_schema

    upgrade_legacy_config_keys = {
        "device.pin": "pin",
        "device.active_high": "active_high",
        "device.pwm_frequency": "pwm_frequency",
        "device.initial_value": "initial_value",
    }

    def __init__(self, data, **kw):
        device.Device.__init__(self, data, **kw)

        try:
            driver = None
            pin = self.config["pin"]

            freq = int(self.config["pwm_frequency"])

            if "mock" in self.config["pin"].lower():
                driver = MockFactory()
                pin = pin.lower().replace("mock", "")

            # Push type data point set by the device
            self.numeric_data_point(
                "value",
                writable=True,
                subtype="boolean",
                min=0,
                max=1,
                handler=self._set_pin,
                default=float(self.config["initial_value"]),
            )

            active_high = self.config["active_high"]

            if pin:
                try:
                    self.pin = gpiozero.PWMLED(
                        pin,
                        active_high=active_high,
                        # Host may have altered this default
                        initial_value=self.datapoints["value"].get()[0],
                        pin_factory=driver,
                        frequency=freq,
                    )
                except gpiozero.exc.PinPWMUnsupported:
                    self.print("Not support PWN on this pin")
                    self.pin = gpiozero.LED(
                        pin,
                        active_high=active_high,
                        # Host may have altered this default
                        initial_value=self.datapoints["value"].get()[0],
                        pin_factory=driver,
                    )

                self.metadata["driver"] = str(self.pin.pin_factory)
            else:
                self.pin = None
        except Exception:
            self.handle_exception()

    def on_before_close(self):
        if self.pin:
            self.pin.close()

    def _set_pin(self, v, t, a):
        if self.pin:
            self.pin.value = v


class GPIOInput(device.Device):
    device_type = "GPIOInput"

    config_schema = {
        "type": "object",
        "properties": {
            "pin": {"type": "string", "default": "MOCK1"},
            "active_high": {"type": "boolean", "default": True},
            "pull_up": {"type": "boolean", "default": False},
            "pull_down": {"type": "boolean", "default": False},
            "debounce_time_ms": {"type": "integer", "default": 0},
        },
    }

    upgrade_legacy_config_keys = {
        "device.pin": "pin",
        "device.active_high": "active_high",
        "device.pull_up": "pull_up",
        "device.pull_down": "pull_down",
        "device.debounce_time_ms": "debounce_time_ms",
    }

    def __init__(self, data, **kw):
        device.Device.__init__(self, data, **kw)

        try:
            driver = None
            pin = self.config["pin"]

            debounce = int(self.config["debounce_time_ms"]) or None

            if "mock" in self.config["pin"].lower():
                driver = MockFactory()
                pin = pin.lower().replace("mock", "")

            active_high = self.config["active_high"]

            pull = None

            if self.config["pull_up"]:
                if self.config["pull_down"]:
                    raise ValueError("Can't have pull up and pull down")
                pull = True

                if active_high:
                    raise ValueError("Can't have pull up and active high")
                else:
                    active_high = None

            if self.config["pull_down"]:
                pull = False

                if not active_high:
                    raise ValueError("Can't have pull down and active low")
                else:
                    active_high = None

            if pin:
                self.pin = gpiozero.Button(
                    pin,
                    pull_up=(pull is True),
                    # Host may have altered this default
                    active_state=active_high,
                    pin_factory=driver,
                    bounce_time=debounce,
                )
                v = 1 if self.pin.value else 0

                self.pin.when_pressed = self.pressed
                self.pin.when_released = self.released

                self.metadata["driver"] = str(self.pin.pin_factory)
                # TODO race condition betweenset value and setup callbacks?
            else:
                v = 0
                self.pin = None

            self.numeric_data_point(
                "value", writable=False, min=0, max=1, subtype="boolean", default=v
            )
            self.set_data_point("value", v)
        except Exception:
            self.handle_exception()

    def test_val(self, x: bool):
        if self.pin:
            if x:
                self.pin.drive_high()  # type: ignore
            else:
                self.pin.drive_low()  # type: ignore

    def pressed(self):
        self.set_data_point("value", 1)

    def released(self):
        self.set_data_point("value", 0)

    def on_before_close(self):
        if self.pin:
            self.pin.close()
