from iot_devices import device

import subprocess
import platform
import time
import threading
import requests
import socket
import re

imported_time = time.time()


def ping_ok(sHost) -> bool:
    try:
        subprocess.check_output(
            "ping -{} 1 {}".format(
                "n" if platform.system().lower() == "windows" else "c", sHost
            ),
            shell=True,
        )
    except Exception:
        return False

    return True


class ServerMonitor(device.Device):
    device_type = "ServerMonitor"

    config_properties = {
        "device.target": {
            "description": "Hostname or URL to ping.  If an http:// url is used, will poll with HTTP as well as ping."
        },
        "device.expect_pattern": {
            "description": "With HTTP URLs, expects to find string matching this regex in the returned data"
        },
    }

    def __init__(self, name, data, **kw):
        device.Device.__init__(self, name, data, **kw)

        self.set_config_default("device.target", "")
        self.set_config_default("device.expect_pattern", "")
        self.set_config_default("device.check_interval", "300")

        # Push type data point set by the device
        self.numeric_data_point("status", subtype="bool", writable=False)
        self.set_alarm("External Server Down", "status", "value<1", priority="error")

        self.stop_flag = id(self)

        t = threading.Thread(
            target=self.work_loop,
            daemon=True,
            name="Monitor for " + self.config["device.target"],
        )
        t.start()

    def close(self):
        self.stop_flag = False
        return super().close()

    def work_loop(self):
        "This runs until the device is closed"
        val = self.stop_flag
        url = self.config["device.target"]
        if not url:
            return

        first = False

        if (time.time() - imported_time) < 15:
            time.sleep(min(15 - (time.time() - imported_time), 2))

        while self.stop_flag == val:
            reachable = 1

            try:
                host = (
                    url.split("://", 1)[-1]
                    .split(":")[0]
                    .split("/")[0]
                    .split("?")[0]
                    .split("@")[-1]
                )

                if not ping_ok(host):
                    reachable = 0
                    if (time.time() - imported_time) > 100:
                        self.print("Unreachable host")

                try:
                    self.metadata["IP Address"] = socket.gethostbyname(host)
                except Exception:
                    if (time.time() - imported_time) > 100:
                        self.handle_exception()

                if reachable:
                    if url.startswith(("http://", "https://")):
                        try:
                            r = requests.get(url, timeout=5)
                            r.raise_for_status()

                            if self.config["device.expect_pattern"]:
                                r = re.search(
                                    self.config["device.expect_pattern"], r.text
                                )

                            if not r:
                                raise ValueError(
                                    "Server response does not match regex pattern"
                                )

                        except Exception:
                            if (time.time() - imported_time) > 100:
                                self.handle_exception()
                            reachable = 0

                # When booting up, let everything get to a steady state first so we don't
                # get spurious alerts. Until the ready point we can set it true but not false.
                if reachable or ((time.time() - imported_time) > 300):
                    self.set_data_point("status", reachable)

            except Exception:
                self.handle_exception()

            if reachable or first:
                time.sleep(float(self.config["device.check_interval"]))
            else:
                # Retry faster at first, try to get good data as soon as possible
                first = True
                time.sleep(30)
