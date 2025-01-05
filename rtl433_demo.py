from iot_devices.host import get_class


# Connect to an MQTT server.
# Listen for data from stuff like weather stations with this command:
# rtl_433 -F json -M utc | mosquitto_pub -t home/rtl_433 -h localhost -l


data = {"type": "RTL433Client", "device.server": "localhost"}


# Get the class that would be able to construct a matching device given the data
c = get_class(data)
print(c)


class RTLWatcher(c):
    def on_data_change(self, point, value, timestamp, annotation):
        print(point + " is now " + str(value))

    def print(self, s, title=""):
        # This logs to this invisible log.info by default
        print(str(title) + ":" + str(s))


# Make an instance of that device
device = RTLWatcher("RTL433 Spy", data)

import time

while 1:
    time.sleep(1)
