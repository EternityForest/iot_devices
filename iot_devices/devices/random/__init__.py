from iot_devices import device

import random

class RandomDevice(device.Device):
    def __init__(self,name, data):
        device.Device.__init__(self,name, data)

        self.numeric_data_point("random")
        self.set_data_point("random",random.random())
