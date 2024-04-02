from iot_devices import device
import gpiozero
from gpiozero.pins.mock import MockFactory


def str_to_bool(s: str):
    s = s.lower()
    if s in ('1', 'yes', 'true', 'on', 'enabled'):
        return True
    elif s in ('0', 'no', 'false', 'off', 'disabled'):
        return False
    else:
        raise ValueError("Not a valid boolean string")


class GPIOOutput(device.Device):
    device_type = "GPIOOutput"

    def __init__(self, name, data, **kw):
        device.Device.__init__(self, name, data, **kw)

        self.set_config_default("device.pin", "MOCK1")

        self.set_config_default("device.active_high", "1")
        self.config_properties['device.active_high'] = {
            'type': 'bool'
        }

        self.set_config_default("device.initial_value", "0")
        self.config_properties['device.initial_value'] = {
            'type': 'float',
            'min': 0,
            'max': 1
        }

        driver = None
        pin = self.config['device.pin']

        if 'mock' in self.config['device.pin'].lower():
            driver = MockFactory()
            pin = pin.lower().replace('mock', '')

        # Push type data point set by the device
        self.numeric_data_point("value", writable=True, min=0, max=1, handler=self._set_pin,
                                default=float(self.config['device.initial_value']))

        active_high = str_to_bool(self.config['device.active_high'])

        if pin:
            try:
                self.pin = gpiozero.PWMLED(pin,
                                           active_high=active_high,
                                           # Host may have altered this default
                                           initial_value=self.datapoints['value'],
                                           pin_factory=driver)
            except Exception:
                self.print("Not support PWN on this pin")
                self.pin = gpiozero.LED(pin,
                                        active_high=active_high,
                                        # Host may have altered this default
                                        initial_value=self.datapoints['value'],
                                        pin_factory=driver)

            self.metadata['driver'] = str(self.pin.pin_factory)
        else:
            self.pin = None

    def _set_pin(self, v, t, a):
        if self.pin:
            self.pin.value = v

    @classmethod
    def discover_devices(cls, config={}, current_device=None, intent=None, **kw):
        return {}
