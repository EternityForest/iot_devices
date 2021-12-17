import logging
import time
import threading
import os
import weakref
from collections import OrderedDict
from weakref import WeakValueDictionary
lock = threading.Lock()

from scullery import mqtt, messagebus

all_devs = weakref.WeakValueDictionary()

import asyncio

eventLoop = asyncio.new_event_loop()

mqttlock = threading.Lock()

import iot_devices.device as devices


@asyncio.coroutine
def scan():
    while 1:
        yield from asyncio.sleep(9)
        with lock:
            try:
                for i in all_devs:
                    # If the last signal was very strong, we don't need to wait as long before considering
                    # it gone, because packet loss will be less
                    m = 3 if all_devs.datapoints['rssi'] > -65 else 7

                    if all_devs.lastseen < time.monotonic() - (float(
                            all_devs.config.get('interval', 60) or 60) * m):
                        # This is how we mark it as not there
                        all_devs.set_data_point('rssi', -180)
            except:
                logging.exception("RTL err")


t = threading.Thread(target=eventLoop.run_forever, name="RTL433Task")
t.start()

eventLoop.call_soon_threadsafe(scan)

from mako.lookup import TemplateLookup

templateGetter = TemplateLookup(os.path.dirname(__file__))

defaultSubclassCode = """
class CustomDeviceType(DeviceType):
    pass
"""

import json
import uuid


class RTL433Client(devices.Device):
    device_type = 'RTL433Client'
    readme = os.path.join(os.path.dirname(__file__), "README.md")
    defaultSubclassCode = defaultSubclassCode
    shortDescription = "This device lets you get data from a device using an RTL433 daemon and MQTT"

    def onConnectionChange(self, status):
        if status == "connected":
            self.set_data_point("mqttStatus", 1)
        else:
            self.set_data_point("mqttStatus", 0)

    def __init__(self, name, data):
        devices.Device.__init__(self, name, data)

        try:
            self.set_config_default('device.interval', '300')

            self.numeric_data_point(
                "rssi",
                min=-180,
                max=12,
                interval=float(self.config["device.interval"]),
                description=
                "-75 if recetly seen, otherwise -180, we don't have real RSSI data",
                writable=False)

            self.set_config_default('device.id', '')
            self.set_config_default('device.model', '')
            self.set_config_default('device.server', 'localhost')
            self.set_config_default('device.port', '1883')
            self.set_config_default('device.password', '')
            self.set_config_default('device.mqttTopic', 'home/rtl_433')

            # This connection is actually  possibly shared
            # Scullery does the deduplication for us

            # Kaithem already puts an alarm on this for us.
            self.connection = mqtt.getConnection(
                self.config["device.server"],
                int(self.config["device.port"].strip() or 1883),
                password=self.config["device.password"].strip(),
                connectionID=str("RTL433Connection"))

            self.numeric_data_point("mqttStatus", writable=False)
            self.connection.subscribeToStatus(self.onConnectionChange)
            self.set_data_point("mqttStatus",
                                1 if self.connection.isConnected else 0)

            topic = data.get("device.mqtttopic", "home/rtl_433")

            # We cannot use priority greater than info because these are unencrypted and untruusted and higher could make noise.

            def onBattery(t, m):
                m = float(m)
                if not 'battery' in self.datapoints:
                    self.numeric_data_point("battery",
                                            default=50,
                                            writable=False,
                                            unit="%")

                    # Always set before setting the alarm.
                    self.set_data_point("battery", m)

                    self.set_alarm(name="Low battery",
                                   datapoint="battery",
                                   expression="value < 15",
                                   priority="info")

                self.set_data_point("battery", m)

            def onWind(t, m):
                m = float(m)
                if not 'wind' in self.datapoints:
                    self.numeric_data_point("wind",
                                            unit="km/h",
                                            writable=False)

                    self.set_alarm(name="High Wind",
                                   datapoint="wind",
                                   expression="value > 35",
                                   priority="info")

                self.set_data_point("wind", m)

            def onTemp(t, m):
                m = float(m)
                if not 'temp' in self.datapoints:
                    self.numeric_data_point("temp",
                                            unit="degC",
                                            writable=False)
                    self.set_alarm(name="Freezing temperatures",
                                   datapoint="temp",
                                   expression="value < 2",
                                   priority="info")

                self.set_data_point("temp", m)

            def onHum(t, m):
                m = float(m)
                if not 'humidity' in self.datapoints:
                    self.numeric_data_point("humidity",
                                            unit="%",
                                            writable=False)
                    self.set_alarm(name="High humidity",
                                   datapoint="humidity",
                                   expression="value > 80",
                                   priority="info")
                    self.set_alarm(name="Low humidity",
                                   datapoint="humidity",
                                   expression="value < 20",
                                   priority="info",
                                   autoAck=True)

                self.set_data_point("humidity", m)

            def onMoist(t, m):
                m = float(m)
                if not 'moisture' in self.datapoints:
                    self.numeric_data_point("moisture",
                                            unit="%",
                                            writable=False)
                self.set_data_point("moisture", m)

            def onPres(t, m):
                m = float(m)
                if not 'pressure' in self.datapoints:
                    self.numeric_data_point("pressure",
                                            unit="Pa",
                                            writable=False)
                self.set_data_point("pressure", m)

            def onWeight(t, m):
                m = float(m)
                if not 'weight' in self.datapoints:
                    self.numeric_data_point("weight", writable=False)
                self.set_data_point("weight", m)

            def onCommandCode(t, m):
                m = float(m)
                if not 'lastCommandCode' in self.datapoints:
                    self.object_data_point("lastCommandCode", writable=False)
                self.set_data_point("lastCommandCode", (m, time.time()))

            def onCommandName(t, m):
                m = float(m)
                if not 'lastCommandName' in self.datapoints:
                    self.object_data_point("lastCommandName", writable=False)
                self.set_data_point("lastCommandName", (m, time.time()))

            def onJSON(t, m):
                m = json.loads(m)
                self.print(m, "Saw packet on air")

                # Going to do an ID match.
                if 'device.id' in self.config and self.config['device.id']:
                    if not ('id' in m
                            and str(m['id']) == self.config['device.id']):
                        self.print(m, "Packet filter miss")
                        return

                if 'device.model' in self.config and self.config['device.id']:
                    if not ('model' in m
                            and m['model'] == self.config['device.model']):
                        self.print(m, "Packet filter miss")
                        return

                self.print(m, "Packet filter hit")

                # No real RSSI
                self.set_data_point("rssi", -75)
                self.lastSeen = time.monotonic()

                if 'humidity' in m:
                    onHum(0, m['humidity'])

                if 'moisture' in m:
                    onHum(0, m['moisture'])

                if 'temperature_C' in m:
                    onTemp(0, m['temperature_C'])

                if 'wind_avg_km_h' in m:
                    onWind(0, m['wind_avg_km_h'])

                if 'pressure_kPa' in m:
                    onPres(0, m['pressure_kPa'] * 1000)

                if 'pressure_hPa' in m:
                    onPres(0, m['pressure_hPa'] * 100)

                # Keep a percent based API with randomly chosen high and low numbers
                if 'battery_ok' in m:
                    onBattery(0, 100 if m['battery_ok'] else 5)

                if 'cmd' in m:
                    onCommandCode(0, m['cmd'])

                if 'button_id' in m:
                    onCommandCode(0, m['button_id'])

                if 'button_name' in m:
                    onCommandName(0, m['button_name'])

                if 'event' in m:
                    onCommandName(0, m['event'])

                if 'code' in m:
                    onCommandCode(0, m['code'])

            self.noGarbage = [onJSON]

            self.connection.subscribe(topic, onJSON, encoding="raw")

            all_devs[self.name] = self
        except Exception as e:
            self.handle_exception()

    def close(self):
        return super().close()
        self.connection.unsubscribe(self.noGarbage[0])

    def getManagementForm(self):
        return ""
