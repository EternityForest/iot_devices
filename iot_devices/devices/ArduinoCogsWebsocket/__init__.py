from __future__ import annotations
from typing import Any
import json
import time
from threading import Thread, RLock, Event
import niquests
import logging

from websockets.sync.client import connect
from websockets.exceptions import ConcurrencyError
from scullery import scheduling

import iot_devices.device
import iot_devices.util

from iot_devices.util import str_to_bool as s2b

ILLEGAL_NAME_CHARS = "{}|\\<>,?-=+)(*&^%$#@!~`\n\r\t\0"

logger = logging.getLogger(__name__)


# Maintains an auto-reconnecting websocket client
class ArduinoCogsClient(iot_devices.device.Device):
    device_type = "ArduinoCogsClient"

    def checker(self):
        with self.lock:
            h = self.thread_handle
            if h:
                if h.is_alive():
                    return

            if not self.should_run:
                return
            if self.last_start_time > (time.time() - 30):
                return

            self.last_start_time = time.time()

            t = Thread(
                target=self.thread, name="ArduinoCogsClient:" + self.name, daemon=True
            )
            t.start()

            self.thread_handle = t

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

        msg = msg.lower()
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

        if "__notification__" in d:
            self.print(d["__notification__"])

        if "__success__" in d:
            self.print(d["__success__"])

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

            self.update_remote_on_reconnect[var] = (val, ts)
            self.sendVar(var, val)

        return handler

    def sendVar(self, var: str, val: float):
        if var in self.scale_factors:
            val = float(val) * self.scale_factors[var]

        try:
            if self.ws:
                with self.lock:
                    self.ws.send(json.dumps({var: val}))
        except Exception:
            self.handle_exception()
            if self.should_run:
                self.set_data_point("api_connected", 0)

    def thread(self):
        url = self.url
        url = url.split("//")[-1]
        if url.endswith("/"):
            url = url[:-1]

        wsurl = "ws://" + url + "/api/ws"
        device_info_url = "http://" + url + "/api/cogs.info"
        info_url = "http://" + url + "/api/cogs.tags"
        details_url = "http://" + url + "/api/cogs.tag"
        trouble_code_url = "http://" + url + "/api/cogs.trouble-codes"

        send_on_connect = iot_devices.util.str_to_bool(
            self.config.get("update_on_reconnect", "true")
        )
        try:
            r = niquests.get(device_info_url, timeout=15)
            r.raise_for_status()

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
                if not self.should_run:
                    return
                r.raise_for_status()
                assert isinstance(r.text, str)
                tagdata = json.loads(r.text)["tags"]

                for i in tagdata:
                    if "$" in i:
                        continue
                    if i.startswith("_"):
                        continue

                    n = i
                    for c in ILLEGAL_NAME_CHARS:
                        n = n.replace(c, "")
                    n = n.lower()

                    val: float = tagdata[i]
                    details = niquests.get(details_url + "?tag=" + i, timeout=5)
                    if not self.should_run:
                        return
                    details.raise_for_status()

                    assert isinstance(details.text, str)
                    dt = json.loads(details.text)
                    unit = dt["unit"]
                    scale = dt["scale"] or 1

                    subtype = ""

                    if unit in ("bool", "boolean"):
                        subtype = "bool"
                        unit = ""
                    if unit in ("bang", "trigger"):
                        subtype = "trigger"
                        unit = ""

                    if i not in self.datapoints:
                        readonly = dt.get("readonly", False)

                        self.ext_to_internal_names[i] = n
                        self.internal_to_ext_names[n] = i

                        if readonly or subtype == "trigger":
                            self.exclude_update_on_reconnect[i] = True

                        self.scale_factors[i] = float(scale)

                        # Trigger values are special.
                        # We don't want to trigger on old stuff
                        if not subtype == "trigger":
                            default = val / scale
                        else:
                            default = 0

                        self.numeric_data_point(
                            n,
                            min=dt["min"] / scale,
                            max=dt["max"] / scale,
                            subtype=subtype,
                            unit=unit,
                            default=default,
                            writable=not readonly,
                            handler=self.makeHandler(i),
                        )

                        # We need to handle data that the host may tell us about,
                        # which might have existed before the device itself.
                        if not subtype == "trigger":
                            try:
                                if not readonly:
                                    if self.datapoint_timestamps.get(i, 0):
                                        # Uh oh race condition between data and timestamp
                                        # But I think it's irrelevant for now
                                        self.update_remote_on_reconnect[i] = (
                                            self.datapoints[i],
                                            self.datapoint_timestamps[i],
                                        )
                            except Exception:
                                logger.exception(
                                    "Failed to handle data that was set before the device connected"
                                )

                    if not subtype == "trigger":
                        if not send_on_connect or (
                            i not in self.update_remote_on_reconnect
                        ):
                            self.set_data_point(
                                n, val / scale, annotation="FromRemoteDevice"
                            )

                self.ws = ws
                if send_on_connect:
                    for i in self.update_remote_on_reconnect:
                        if i not in self.exclude_update_on_reconnect:
                            self.sendVar(i, self.update_remote_on_reconnect[i][0])

                self.set_data_point("api_connected", 1)
                self.running = True

                pong: Event | None = None

                if not self.should_run:
                    return
                original = self.should_run

                while self.should_run == original:
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

                    if msg and self.should_run:
                        if isinstance(msg, str):
                            try:
                                self.handle_message(msg)
                            except Exception:
                                self.handle_exception()

        except Exception:
            if not self.suppress_connect_error:
                self.suppress_connect_error = True
                self.handle_exception()
            if self.should_run:
                self.set_data_point("api_connected", 0)

        try:
            if not self:
                return
        except Exception:
            self.running = 0
            return

        self.running = 0
        self.ws = None
        if self.should_run:
            self.set_data_point("api_connected", 0)

    def __init__(self, name: str, data: dict[str, str], **kw: Any):
        super().__init__(name, data, **kw)

        try:
            self.thread_handle = None
            self.suppress_connect_error = False
            self.numeric_data_point(
                "api_connected", min=0, max=1, default=0, subtype="bool", writable=False
            )

            self.set_config_default("update_on_reconnect", "true")
            self.config_properties["update_on_reconnect"] = {
                "title": "Update on Reconnect",
                "type": "bool",
                "default": "true",
                "description": "Update remote datapoints on reconnect, treating this client as the source of truth.",
            }

            self.set_config_default("intermittent_availability", "false")

            self.config_properties["intermittent_availability"] = {
                "title": "Intermittent Availability",
                "type": "bool",
                "default": "false",
                "description": "If false, treat device being offline as an error",
            }

            if not s2b(self.config.get("intermittent_availability", "false")):
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

            self.update_remote_on_reconnect: dict[str, Any] = {}
            self.exclude_update_on_reconnect: dict[str, bool] = {}

            self.last_start_time = 0
            self.scale_factors: dict[str, float] = {}
            self.ws = None
            self.lock = RLock()
            self.running = False
            self.should_run = time.time()
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

        try:
            for i in range(500):
                if self.thread_handle and self.thread_handle.is_alive():
                    time.sleep(0.001)
        except Exception:
            pass

        return super().close()
