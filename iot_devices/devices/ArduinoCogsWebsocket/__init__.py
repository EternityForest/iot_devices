from __future__ import annotations
from typing import Any
import json
import time
from threading import Thread, RLock, Event
import niquests
from websockets.sync.client import connect
from websockets.exceptions import ConcurrencyError
from scullery import scheduling

import iot_devices.device

ILLEGAL_NAME_CHARS = "{}|\\<>,?-=+)(*&^%$#@!~`\n\r\t\0"


# Maintains an auto-reconnecting websocket client
class ArduinoCogsClient(iot_devices.device.Device):
    device_type = "ArduinoCogsClient"

    def checker(self):
        with self.lock:
            if self.running:
                return
            if not self.should_run:
                return
            if self.last_start_time > (time.time() - 30):
                return

            self.last_start_time = time.time()

            t = Thread(target=self.thread)
            t.start()

    def handle_trouble_code_state(self, msg: str, val: float):
        level = "warning"
        if msg.startswith("E"):
            level = "error"
        elif msg.startswith("W"):
            level = "warning"
        elif msg.startswith("I"):
            level = "info"
        elif msg.startswith("D"):
            level = "debug"
        elif msg.startswith("C"):
            level = "critical"

        if msg not in self.datapoints:
            self.numeric_data_point(
                msg, min=0, max=1, default=0, subtype="bool", writable=False
            )
            self.set_alarm(msg, msg, "value > 0", priority=level)

        if val > 0.0001:
            self.set_data_point(msg, 1, annotation="FromRemoteDevice")
        else:
            self.set_data_point(msg, 0, annotation="FromRemoteDevice")

    def handle_message(self, msg: str):
        d = json.loads(msg)
        if "__troublecodes__" in d:
            for i in d["__troublecodes__"]:
                self.handle_trouble_code_state(i, d["__troublecodes__"][i])

        if "__error__" in d:
            self.handle_error(d["__error__"])

        for i in d:
            self.on_var_msg(i, d[i])

    def on_var_msg(self, msg: str, val: float):
        if msg in self.scale_factors:
            val = float(val) / self.scale_factors[msg]
        if msg in self.ext_to_internal_names:
            msg = self.ext_to_internal_names[msg]
            self.set_data_point(msg, val, annotation="FromRemoteDevice")

    def makeHandler(self, var: str):
        def handler(val: float, ts: float, a: Any):
            if a == "FromRemoteDevice":
                return

            if var in self.scale_factors:
                val = float(val) * self.scale_factors[var]

            try:
                if self.ws:
                    with self.lock:
                        self.ws.send(json.dumps({var: val}))
            except Exception:
                self.handle_exception()

        return handler

    def thread(self):
        url = self.url
        url = url.split("//")[-1]
        if url.endswith("/"):
            url = url[:-1]

        wsurl = "ws://" + url + "/api/ws"
        info_url = "http://" + url + "/api/cogs.tags"
        details_url = "http://" + url + "/api/cogs.tag"
        trouble_code_url = "http://" + url + "/api/cogs.trouble-codes"

        try:
            with connect(wsurl) as ws:
                self.suppress_connect_error = False
                try:
                    tc = niquests.get(trouble_code_url, timeout=5)
                    tc.raise_for_status()
                    assert isinstance(tc.text, str)
                    td = json.loads(tc.text)
                    for i in td:
                        self.handle_trouble_code_state(i, td[i])
                except Exception:
                    self.handle_exception()

                r = niquests.get(info_url, timeout=5)
                r.raise_for_status()
                assert isinstance(r.text, str)
                tagdata = json.loads(r.text)["tags"]

                for i in tagdata:
                    if "$" in i:
                        continue
                    if i.startswith("_"):
                        continue

                    val: float = tagdata[i]
                    details = niquests.get(details_url + "?tag=" + i, timeout=5)
                    details.raise_for_status()

                    assert isinstance(details.text, str)
                    dt = json.loads(details.text)

                    if i not in self.datapoints:
                        scale = dt["scale"]

                        unit = dt["unit"]

                        subtype = ""

                        if unit in ("bool", "boolean"):
                            subtype = "bool"
                            unit = ""
                        if unit in ("bang", "trigger"):
                            subtype = "trigger"
                            unit = ""

                        readonly = dt.get("readonly", False)

                        n = i
                        for c in ILLEGAL_NAME_CHARS:
                            n = n.replace(c, "")
                        self.ext_to_internal_names[i] = n
                        self.internal_to_ext_names[n] = i
                        self.scale_factors[i] = float(scale)

                        self.numeric_data_point(
                            n,
                            min=dt["min"] / scale,
                            max=dt["max"] / scale,
                            subtype=subtype,
                            unit=unit,
                            default=val / scale,
                            writable=not readonly,
                            handler=self.makeHandler(i),
                        )

                        self.set_data_point(
                            n, val / scale, annotation="FromRemoteDevice"
                        )

                self.set_data_point("api_connected", 1)
                self.ws = ws
                self.running = True

                pong: Event | None = None

                while self.should_run:
                    try:
                        msg = ws.recv(10)
                    except TimeoutError:
                        with self.lock:
                            if pong:
                                if not pong.is_set():
                                    raise Exception("Timeout waiting for pong")

                            # Fixed val to raise concurrency error
                            # if there's a timeout
                            try:
                                pong = ws.ping("keepalive")
                            except ConcurrencyError:
                                raise OSError("WS Disconnected")

                        continue

                    if msg:
                        if isinstance(msg, str):
                            try:
                                self.handle_message(msg)
                            except Exception:
                                self.handle_exception()

        except Exception:
            if not self.suppress_connect_error:
                self.suppress_connect_error = True
                self.handle_exception()
        finally:
            self.running = False
            self.ws = None
            self.set_data_point("api_connected", 0)

    def __init__(self, name: str, data: dict[str, str], **kw: Any):
        super().__init__(name, data, **kw)

        try:
            self.suppress_connect_error = False
            self.numeric_data_point(
                "api_connected", min=0, max=1, default=0, subtype="bool", writable=False
            )
            self.set_alarm(
                "Disconnected",
                "api_connected",
                "value < 1",
                priority="warning",
                auto_ack=True,
            )

            self.set_config_default("url", "example.local")

            self.ext_to_internal_names: dict[str, str] = {}
            self.internal_to_ext_names: dict[str, str] = {}

            self.last_start_time = 0
            self.scale_factors: dict[str, float] = {}
            self.ws = None
            self.lock = RLock()
            self.running = False
            self.should_run = True
            self.url: str = self.config["url"]
            self.checker()
            self.scheduled = scheduling.scheduler.every(self.checker, 5)

        except Exception:
            self.handle_exception()
            return

    def close(self):
        self.should_run = False
        try:
            self.scheduled.unregister()
        except Exception:
            pass

        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

        return super().close()
