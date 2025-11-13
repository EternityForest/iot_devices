from __future__ import annotations
from typing import Any
import json
import time
from threading import Thread, RLock, Event
import niquests
import logging
import asyncio

import starlette.responses
import starlette.requests
import starlette.types
import starlette.websockets
import starlette.applications
from starlette.routing import Route, WebSocketRoute
import uvicorn


from websockets.sync.client import connect
from websockets.exceptions import ConcurrencyError
from scullery import scheduling

import iot_devices.device

ILLEGAL_NAME_CHARS = "{}|\\<>,?-=+)(*&^%$#@!~`\n\r\t\0"

logger = logging.getLogger(__name__)

client_schema = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "default": ""},
        "update_on_reconnect": {
            "type": "boolean",
            "default": True,
            "description": "Update remote datapoints on reconnect, treating this client as the source of truth.",
        },
        "intermittent_availability": {"type": "boolean", "default": False},
    },
}


# Maintains an auto-reconnecting websocket client
class ArduinoCogsClient(iot_devices.device.Device):
    device_type = "ArduinoCogsClient"

    config_schema = client_schema

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

    def on_var_msg(self, msg: str, val: float | int):
        if isinstance(val, int):
            self.unknown_incoming_variables[msg] = val

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
        tags_list_url = "http://" + url + "/api/cogs.tags"
        details_url = "http://" + url + "/api/cogs.tag"
        trouble_code_url = "http://" + url + "/api/cogs.trouble-codes"

        send_on_connect = self.config.get("update_on_reconnect", True)
        try:
            r = niquests.get(device_info_url, timeout=15)
            r.raise_for_status()
            # Clear these so we don't try to use data from the previous session
            self.unknown_incoming_variables = {}
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

                r = niquests.get(tags_list_url, timeout=5)
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
                    # To avoid a race condition in case the websocket data arrived
                    # before this, always use thw WS data.
                    # This does not itself make a race because if this happens first,
                    # Then the WS thing will overwrite it as it should
                    if i in self.unknown_incoming_variables:
                        val = self.unknown_incoming_variables[i]

                    details = niquests.get(details_url + "?tag=" + i, timeout=5)
                    if not self.should_run:
                        return
                    details.raise_for_status()

                    assert isinstance(details.text, str)
                    dt = json.loads(details.text)

                    if dt.get("type", "number") not in ("number", "numeric"):
                        continue

                    unit = dt.get("unit", "")
                    scale = dt.get("scale", 1)

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

                        if "min" in dt and dt["min"] is not None:
                            dt["min"] /= scale
                        if "max" in dt and dt["max"] is not None:
                            dt["max"] /= scale

                        self.numeric_data_point(
                            n,
                            min=dt["min"],
                            max=dt["max"],
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
                                    v, t, a = self.datapoints[i].get()
                                    if t:
                                        # Uh oh race condition between data and timestamp
                                        # But I think it's irrelevant for now

                                        self.update_remote_on_reconnect[i] = (v, t)
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

    def __init__(self, data, **kw):
        iot_devices.device.Device.__init__(self, data, **kw)

        try:
            # We might get a variable via WS before getting it's
            # metadata, so we want to use the ws version so everything stays in band
            # and there are no race conditions
            self.unknown_incoming_variables: dict[str, int] = {}

            self.thread_handle = None
            self.suppress_connect_error = False
            self.numeric_data_point(
                "api_connected", min=0, max=1, default=0, subtype="bool", writable=False
            )

            if not self.config.get("intermittent_availability", False):
                self.set_alarm(
                    "Disconnected",
                    "api_connected",
                    "value < 1",
                    priority="warning",
                    auto_ack=True,
                )

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

            if self.config["url"]:
                self.checker()
                self.scheduled = scheduling.scheduler.every(self.checker, 5)

        except Exception:
            self.handle_exception()
            return

    def on_before_close(self):
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
            for _i in range(500):
                if self.thread_handle and self.thread_handle.is_alive():
                    time.sleep(0.001)
        except Exception:
            pass

        return super().close()


server_schema: dict[str, Any] = {
    "type": "object",
    "properties": {
        "port": {"type": "integer"},
        "intermittent_availability": {"type": "boolean", "default": False},
        "tagpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "writable": {"type": "boolean", "default": True},
                    "scale": {"type": "number", "default": 16384},
                    "default": {"type": "number", "default": 0},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "unit": {"type": "string", "default": ""},
                    "subtype": {
                        "type": "string",
                        "default": "",
                        "enum": ["bool", "trigger", ""],
                    },
                },
                "required": ["name", "datapoint"],
            },
        },
    },
    "required": ["port"],
}


class ArduinoCogsServer(iot_devices.device.Device):
    device_type = "ArduinoCogsServer"

    def numeric_handler(self, n: str, scale: float):
        def f(v: float, t: float, a: Any):
            async def push():
                for i in self.clients:
                    await i.send_text(json.dumps({n: v * scale}))

            if not t == "FromRemoteDevice":
                if self.should_run:
                    asyncio.run_coroutine_threadsafe(push(), self.loop)

    def __init__(self, data, **kw):
        iot_devices.device.Device.__init__(self, data, **kw)
        self.should_run = True

        for i in data.get("tagpoints", []):
            self.numeric_data_point(
                i["name"],  # type: ignore
                min=i.get("min", None),  # type: ignore
                max=i.get("max", None),  # type: ignore
                unit=i.get("unit", ""),  # type: ignore
                default=i.get("default", 0),  # type: ignore
                subtype=i.get("subtype", ""),  # type: ignore
                writable=i.get("writable", True),  # type: ignore
                handler=self.numeric_handler(i["name"], i.get("scale", 16384)),
            )

        app = starlette.applications.Starlette(
            routes=[
                WebSocketRoute("/api/ws", self.makews()),
                Route("/api/cogs.tags", self.handle_tags_list_request),
                Route("/api/cogs.tag", self.handle_tag_info_request),
                Route("/api/cogs.trouble-codes", self.handle_trouble_codes_request),
                Route("/api/cogs.info", self.handle_device_info_request),
            ]
        )

        if "port" in data and data["port"]:
            try:
                config = uvicorn.Config(app, port=int(data["port"]), log_level="info")
                server = uvicorn.Server(config)
                self.server = server

                self.clients: list[starlette.websockets.WebSocket] = []

                self.loop = asyncio.new_event_loop()

                def f():
                    self.loop.run_until_complete(server.serve())

                self.thread_handle = Thread(
                    target=f, daemon=True, name="ArduinoCogsServer:" + self.name
                )
                self.thread_handle.start()

            except Exception:
                self.handle_exception()

    def makews(self):
        async def ws(
            ws: starlette.websockets.WebSocket,
        ):
            await ws.accept()
            self.clients.append(ws)
            while self.should_run:
                try:
                    x = await ws.receive()
                    assert isinstance(x, str)
                except Exception:
                    break

                try:
                    x = json.loads(x)
                    for i in x:
                        if not i.startswith("_"):
                            self.set_data_point(i, x[i], annotation="FromRemoteDevice")

                except Exception:
                    self.handle_exception()
            try:
                self.clients.remove(ws)
            except Exception:
                pass

        return ws

    def handle_device_info_request(self, request: starlette.requests.Request):
        return starlette.responses.JSONResponse(
            {
                "name": self.name,
                "type": self.device_type,
                "version": "1.0",
            }
        )

    def handle_tag_info_request(self, request: starlette.requests.Request):
        tag = request.query_params["tag"]
        return starlette.responses.JSONResponse(
            {
                "name": tag,
                "writable": self.config.get("writable", True),
                "min": self.config.get("min", None),
                "max": self.config.get("max", None),
                "unit": self.config.get("unit", ""),
                "scale": self.config.get("scale", 16384),
                "subtype": self.config.get("subtype", ""),
            }
        )

    def handle_trouble_codes_request(self, request: starlette.requests.Request):
        return starlette.responses.JSONResponse({})

    def handle_tags_list_request(self, request: starlette.requests.Request):
        d = self.datapoints

        r = {
            "tags": {
                i["name"]: d[i["name"]].get()[0] * i.get("scale", 16384)
                for i in self.config.get("tagpoints", {})
                if d[i["name"]].get()[0] is not None
            }
        }
        return starlette.responses.JSONResponse(r)

    def on_before_close(self):
        self.should_run = False
        try:
            self.loop.call_soon_threadsafe(self.server.shutdown)

            if self.loop.is_running():
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.loop.shutdown_asyncgens(), self.loop
                    )
                except RuntimeError:
                    pass

            time.sleep(0.05)
            self.loop.stop()

            for _i in range(50):
                if not self.loop.is_running():
                    self.loop.close()
                    break
                time.sleep(0.1)

        except Exception:
            self.handle_exception()

        return super().close()
