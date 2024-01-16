from iot_devices import device

import subprocess
import platform
import time
import threading
import requests

def ping_ok(sHost) -> bool:
    try:
        subprocess.check_output(
            "ping -{} 1 {}".format("n" if platform.system().lower() == "windows" else "c", sHost), shell=True
        )
    except Exception:
        return False

    return True


class ServerMonitor(device.Device):
    device_type = "ServerMonitor"

    config_properties = {'device.target': {
                        'description': "Hostname or URL to poll"
                    }
                }

    def __init__(self, name, data, **kw):
        device.Device.__init__(self, name, data, **kw)

        self.set_config_default("device.target", "")

        self.set_config_default("device.check_interval", "300")

        # Push type data point set by the device
        self.numeric_data_point("status", subtype='bool')
        self.set_alarm("External Server Down", 'status',
                       "value<1", priority="error")

        self.stop_flag = id(self)

        t = threading.Thread(target=self.work_loop, daemon=True, name="Monitor for "+self.config['device.target'])
        t.start()


    def close(self):
        self.stop_flag = False
        return super().close()

    def work_loop(self):
        "This runs until the device is closed"
        val = self.stop_flag
        url = self.config['device.target']
        if not url:
            return

        while self.stop_flag == val:
            try:
                reachable = 1

                host = url.split(":", 1)[-1].split(':')[0].split("/")[0].split("?")[0].split("@")[-1]
                
                if not ping_ok(host):
                    reachable = 0
                    self.print("Unreachable host")

                if reachable:
                    if url.startswith("http://") or url.startswith("https://"):
                        try:
                            r = requests.get(url, timeout=5)
                            r.raise_for_status()
                        except Exception:
                            self.handle_exception()
                            reachable = 0

                self.set_data_point('status', reachable)

                time.sleep(float(self.config['device.check_interval']))

            except Exception:
                self.handle_exception()
