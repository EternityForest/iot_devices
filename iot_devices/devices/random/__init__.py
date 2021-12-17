from iot_devices import device

import random

class RandomDevice(device.Device):
    device_type = "RandomDevice"
    def __init__(self,name, data):
        device.Device.__init__(self,name, data)

        self.set_config_default("device.fixed_number_multiplier","1")

        # Push type data point set by the device
        self.numeric_data_point("random")
        self.set_data_point("random",random.random() * float(self.config['device.fixed_number_multiplier']))


        # On demand requestable data point pulled by application.
        # All you have to do is set the val to a callable.
        self.numeric_data_point("dyn_random")
        self.set_data_point_getter("dyn_random", random.random)

    @classmethod
    def discover_devices(cls, config={}, current_device=None, intent=None, **kw):

    
        # Return a modified version of the existing.
        # Never get rid of existing user work for no reason
        cfg = {
            'device.fixed_number_multiplier':"1000"
        }
        config= config.copy()
        config.update(cfg)

        return{ "Big fixed numbers":config}