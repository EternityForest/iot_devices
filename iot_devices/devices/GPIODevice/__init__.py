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
        self.config_properties['device.active_high'] = {
            'description': 'This pin can be a mock pin like MOCK1, or any pin name supported by gpiozero, like BCM17 on a RasPi'
        }

        self.set_config_default("device.active_high", "1")
        self.config_properties['device.active_high'] = {
            'type': 'bool'
        }

        self.set_config_default("device.pwm_frequency", "100")

        self.set_config_default("device.initial_value", "0")
        self.config_properties['device.initial_value'] = {
            'type': 'float',
            'min': 0,
            'max': 1
        }
        try:
            driver = None
            pin = self.config['device.pin']

            freq = int(self.config['device.pwm_frequency'])

            if 'mock' in self.config['device.pin'].lower():
                driver = MockFactory()
                pin = pin.lower().replace('mock', '')

            # Push type data point set by the device
            self.numeric_data_point("value", writable=True, subtype='boolean', min=0, max=1, handler=self._set_pin,
                                    default=float(self.config['device.initial_value']))

            active_high = str_to_bool(self.config['device.active_high'])

            if pin:
                try:
                    self.pin = gpiozero.PWMLED(pin,
                                               active_high=active_high,
                                               # Host may have altered this default
                                               initial_value=self.datapoints['value'],
                                               pin_factory=driver,
                                               frequency=freq)
                except gpiozero.exc.PinPWMUnsupported:
                    self.print("Not support PWN on this pin")
                    self.pin = gpiozero.LED(pin,
                                            active_high=active_high,
                                            # Host may have altered this default
                                            initial_value=self.datapoints['value'],
                                            pin_factory=driver)

                self.metadata['driver'] = str(self.pin.pin_factory)
            else:
                self.pin = None
        except Exception:
            self.handle_exception()

    def close(self):
        if self.pin:
            self.pin.close()

    def _set_pin(self, v, t, a):
        if self.pin:
            self.pin.value = v

    @classmethod
    def discover_devices(cls, config={}, current_device=None, intent=None, **kw):
        return {}


class GPIOInput(device.Device):
    device_type = "GPIOInput"

    def __init__(self, name, data, **kw):
        device.Device.__init__(self, name, data, **kw)

        self.set_config_default("device.pin", "MOCK1")
        self.config_properties['device.active_high'] = {
            'description': 'This pin can be a mock pin like MOCK1, or any pin name supported by gpiozero, like BCM17 on a RasPi'
        }

        self.set_config_default("device.active_high", "true")
        self.config_properties['device.active_high'] = {
            'type': 'bool'
        }

        self.set_config_default("device.pull_up", "false")
        self.config_properties['device.pull_up'] = {
            'type': 'bool'
        }

        self.set_config_default("device.pull_down", "false")
        self.config_properties['device.pull_down'] = {
            'type': 'bool'
        }

        self.set_config_default("device.debounce_time_ms", "0")
        try:
            driver = None
            pin = self.config['device.pin']

            debounce = int(self.config['device.debounce_time_ms']) or None

            if 'mock' in self.config['device.pin'].lower():
                driver = MockFactory()
                pin = pin.lower().replace('mock', '')

            active_high = str_to_bool(self.config['device.active_high'])

            pull = None

            if str_to_bool(self.config['device.pull_up']):
                if str_to_bool(self.config['device.pull_down']):
                    raise ValueError("Can't have pull up and pull down")
                pull = True

                if active_high:
                    raise ValueError("Can't have pull up and active high")
                else:
                    active_high = None

            if str_to_bool(self.config['device.pull_down']):
                pull = False

                if not active_high:
                    raise ValueError("Can't have pull down and active low")
                else:
                    active_high = None

            if pin:
                self.pin = gpiozero.Button(pin,
                                           pull_up=pull,
                                           # Host may have altered this default
                                           active_state=active_high,
                                           pin_factory=driver,
                                           bounce_time=debounce)
                v = 1 if self.pin.value else 0

                self.pin.when_pressed = self.pressed
                self.pin.when_released = self.released

                self.metadata['driver'] = str(self.pin.pin_factory)
                # TODO race condition betweenset value and setup callbacks?
            else:
                v = 0
                self.pin = None

            self.numeric_data_point("value", writable=False, min=0, max=1,
                                    subtype='boolean',
                                    default=v)
            self.set_data_point('value', v)
        except Exception:
            self.handle_exception()

    def pressed(self):
        self.set_data_point('value', 1)

    def released(self):
        self.set_data_point('value', 0)

    def close(self):
        if self.pin:
            self.pin.close()
