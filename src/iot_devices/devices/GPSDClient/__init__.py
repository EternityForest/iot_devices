from gpsdclient.client import GPSDClient as _gps

from typing import Any
import time
import threading
import json

import iot_devices.device as device


class GPSDClient(device.Device):
    device_type = "GPSDClient"

    # This schema determines the config a host will give us.
    # The host will also give us a few extra special keys.
    config_schema = {
        "properties": {
            "device": {
                "type": "string",
                "default": "",
                "description": "GPSD Device Filter, leave blank for all devices",
            },
            "host": {
                "type": "string",
                "default": "127.0.0.1",
                "description": "GPSD Server IP Address. 127.0.0.1 if GPSD is running on this host",
            },
        }
    }

    def thread(self):
        dev = self.config.get("device", "").strip()
        while self.should_run:
            try:
                with _gps(host=self.config.get("host", "127.0.0.1")) as client:
                    for result_raw in client.json_stream():
                        if isinstance(result_raw, str):
                            result = json.loads(result_raw)
                        else:
                            result = result_raw
                        if not dev or result["device"] == dev:
                            self.set_data_point(
                                "has_fix", 1 if (result.get("mode", 0) > 1) else 0
                            )
                            alt = 0
                            fix_time = 0

                            if "time" in result:
                                # parse the iso 8601 timestamp
                                t = result["time"].split(".")
                                fix_time = time.mktime(
                                    time.strptime(t[0], "%Y-%m-%dT%H:%M:%S")
                                )

                            if "speed" in result:
                                self.set_data_point("speed", result["speed"])

                            if "altMSE" in result:
                                self.set_data_point("altitude", result["altMSE"])
                                alt = result["altMSE"]
                            elif "altHAE" in result:
                                self.set_data_point("altitude", result["altHAE"])
                                alt = result["altHAE"]
                            elif "alt" in result:
                                self.set_data_point("altitude", result["alt"])
                                alt = result["alt"]

                            if "lat" in result and "lon" in result:
                                self.set_data_point(
                                    "location",
                                    {
                                        "latitude": result["lat"],
                                        "longitude": result["lon"],
                                        "altitude": alt,
                                        "time": fix_time,
                                    },
                                )

                            if "track" in result:
                                self.set_data_point("heading", result["track"])

                            if "jamming" in result:
                                self.set_data_point(
                                    "jamming_detected", result["jamming"] / 255.0
                                )

            except Exception:
                self.handle_exception()
                time.sleep(60)

    def __init__(self, config: dict[str, Any], **kw: Any):
        device.Device.__init__(self, config, **kw)
        self.should_run = True
        self.thread_handle = threading.Thread(target=self.thread, name="GPS Client")
        self.thread_handle.start()

        # Push type data point set by the device
        self.numeric_data_point("has_fix", default=0, subtype="bool", writable=False)
        self.numeric_data_point("jamming_detected", default=0, min=0, max=1, hi=0.05)

        self.set_alarm(
            "No GPS Fix", "has_fix", "value<1", priority="error", trip_delay=3 * 60
        )
        self.set_alarm(
            "GPS Jamming Detected",
            "jamming_detected",
            "value>0.05",
            priority="error",
            trip_delay=3,
        )

        self.object_data_point(
            "location",
            writable=False,
            subtype="gps",
            default={"lat": 0, "lon": 0, "alt": 0, "time": 0},
        )

        self.object_data_point("speed", writable=False, unit="m/s")
        self.object_data_point(
            "altitude", writable=False, unit="m", description="Altitude above sea level"
        )
        self.object_data_point("heading", writable=False, unit="deg")

    def on_before_close(self):
        device.Device.close(self)
        self.should_run = False
