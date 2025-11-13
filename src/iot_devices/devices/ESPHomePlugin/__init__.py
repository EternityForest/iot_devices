from typing import Dict
import aioesphomeapi
import aioesphomeapi.client as client
import aioesphomeapi.model as model
import asyncio
import threading
import zeroconf
import time
from typing import Any

import iot_devices.device
import iot_devices.host


class ESPHomeDevice(iot_devices.device.Device):
    device_type = "ESPHomeDevice"

    config_schema = {
        "type": "object",
        "properties": {
            "hostname": {"type": "string", "default": ""},
            "apikey": {
                "type": "string",
                "default": "",
                "secret": True,
                "format": "password",
            },
        },
    }
    upgrade_legacy_config_keys = {
        "device.hostname": "hostname",
        "device.apikey": "apikey",
    }

    def wait_ready(self, timeout=15):
        # Wait for connection ready
        s = time.time()
        while not self.datapoints["native_api_connected"].get()[0]:
            if (time.time() - s) > timeout:
                raise RuntimeError("Could not connect")
            time.sleep(timeout / 100)

    def async_on_service_call(self, service: model.HomeassistantServiceCall) -> None:
        """Call service when user automation in ESPHome config is triggered."""
        domain, service_name = service.service.split(".", 1)
        service_data = service.data

        if service.data_template:
            self.handle_error("Can't do HASS service call templating")
            return

        if service.is_event:
            # ESPHome uses servicecall packet for both events and service calls
            # Ensure the user can only send events of form 'esphome.xyz'
            if domain != "esphome":
                self.handle_error("Can't do non esphome domains, yours was: " + domain)

                return

            # Call native tag scan
            if service_name == "tag_scanned":
                tag_id = service_data["tag_id"]

                # Don't clutter up the system with unneeded data points.
                if "scanned_tag" not in self.datapoints:
                    self.object_data_point(
                        "scanned_tag", description="RFID reading", writable=False
                    )

                self.set_data_point("scanned_tag", [str(tag_id), time.time(), ""])
                return

    def update_wireless(self):
        pass

    def handle_log(self, msg):
        self.print(msg)

    def add_bool(self, name: str, w=False):
        def handler(v, t, a):
            if not a == "FromRemoteDevice":
                if v >= 1:
                    self.api.switch_command(self.name_to_key[name], True)
                else:
                    self.api.switch_command(self.name_to_key[name], False)

        self.numeric_data_point(
            name, min=0, max=1, subtype="bool", writable=w, handler=handler
        )

    def add_button(self, name: str, buttonid: int):
        def handler(v, t, a):
            if not a == "FromRemoteDevice":
                if v >= 1:
                    self.api.button_command(buttonid)

        self.numeric_data_point(name, min=0, max=1, subtype="trigger", handler=handler)

    def obj_to_tag(self, i):
        try:
            self.key_to_name[i.key] = i.object_id
            self.name_to_key[i.object_id] = i.key

            if isinstance(i, model.BinarySensorInfo):
                self.add_bool(i.object_id)

            if isinstance(i, model.ButtonInfo):
                self.add_button(i.object_id, i.key)

            elif isinstance(i, model.SwitchInfo):

                def handler(v, t, a):
                    self.api.switch_command(i.key, True if v > 0.5 else False)

                self.numeric_data_point(
                    i.object_id,
                    min=0,
                    max=1,
                    subtype="bool",
                    writable=True,
                    handler=handler,
                )

            elif isinstance(i, model.NumberInfo):

                def handler(v, t, a):
                    if not a == "FromRemoteDevice":
                        self.api.number_command(i.key, v)

                self.numeric_data_point(
                    i.object_id,
                    min=i.min_value,
                    max=i.max_value,
                    writable=True,
                    handler=handler,
                )

            elif isinstance(i, model.SensorInfo):
                self.numeric_data_point(
                    i.object_id,
                    unit=i.unit_of_measurement.replace("°", "deg").replace("³", "3"),
                    writable=False,
                )

                # Onboard WiFi and die temperature get special treatment, always want
                if (
                    i.device_class == "signal_strength"
                    and i.unit_of_measurement == "dBm"
                    and i.entity_category == "diagnostic"
                ):
                    self.set_alarm(
                        "WiFi Signal low", i.object_id, "value < -89", auto_ack=True
                    )

                if (
                    i.device_class == "signal_strength"
                    and i.unit_of_measurement == "°C"
                    and i.entity_category == "diagnostic"
                ):
                    self.set_alarm(
                        "Temperature Below Freezing",
                        i.object_id,
                        "value < 0",
                        auto_ack=True,
                        priority="warning",
                    )

                    self.set_alarm(
                        "Temperature High",
                        i.object_id,
                        "value > 75",
                        auto_ack=True,
                        priority="warning",
                    )

            elif isinstance(i, model.TextSensorInfo):
                self.string_data_point(i.object_id)

            elif isinstance(i, model.AlarmControlPanelInfo):
                objid = "alarm_control_panel"
                self.string_data_point(objid, writable=False)
                self.set_alarm(
                    self.name + " " + objid + "Triggered",
                    objid,
                    "value =='TRIGGERED'",
                    priority="critical",
                    auto_ack=True,
                )
                self.set_alarm(
                    self.name + " " + objid,
                    objid,
                    "value =='PENDING'",
                    priority="warning",
                    auto_ack=True,
                )

        except Exception:
            self.handle_exception()

    def incoming_state(self, s):
        try:
            if isinstance(s, (model.BinarySensorState, model.SwitchState)):
                self.set_data_point(
                    self.key_to_name[s.key],
                    1 if s.state else 0,
                    annotation="FromRemoteDevice",
                )

            elif isinstance(s, model.NumberState):
                self.set_data_point(
                    self.key_to_name[s.key], s.state, annotation="FromRemoteDevice"
                )

            elif isinstance(s, model.AlarmControlPanelState):
                self.set_data_point(self.key_to_name["alarm_control_panel"], s.name)

            elif isinstance(s, model.SensorState) or isinstance(
                s, model.TextSensorState
            ):
                self.set_data_point(
                    self.key_to_name[s.key], s.state, annotation="FromRemoteDevice"
                )
        except Exception:
            self.handle_exception()

    def __init__(self, config: Dict[str, Any], **kw):
        super().__init__(config, **kw)

        self.zc = zeroconf.Zeroconf()

        self.name_to_key = {}
        self.key_to_name = {}
        self.input_units = {}

        self.stopper = asyncio.Event()

        self.loop = asyncio.new_event_loop()

        self.thread = threading.Thread(
            target=self.asyncloop, name="ESPHOME " + self.name
        )
        self.numeric_data_point(
            "native_api_connected", min=0, max=1, subtype="bool", writable=False
        )
        self.set_alarm(
            "Not Connected",
            "native_api_connected",
            "value<1",
            trip_delay=120,
            auto_ack=True,
        )

        if self.config.get("hostname") and self.config.get("apikey"):
            self.thread.start()

    def asyncloop(self):
        self.loop.run_until_complete(self.main())

    def on_before_close(self):
        if hasattr(self, "api") and self.api:
            try:
                t = asyncio.run_coroutine_threadsafe(self.api.disconnect(), self.loop)

                d = False

                st = time.time()
                while (time.time() - st) < 1:
                    if t.done():
                        d = True
                        break
                    time.sleep(0.025)

                if not d:
                    self.handle_error("Timeout waiting for clean disconnect")
            except Exception:
                self.handle_exception()

        self.loop.call_soon_threadsafe(self.stopper.set)

        if self.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self.loop.shutdown_asyncgens(), self.loop
                )
            except RuntimeError:
                pass

        time.sleep(0.05)
        try:
            self.loop.stop()
        except RuntimeError:
            return super().close()

        for i in range(50):
            if not self.loop.is_running():
                self.loop.close()
                break
            time.sleep(0.1)

        try:
            self.zc.close()
        except Exception:
            pass

        return super().close()

    async def main(self, *a, **k):
        """Connect to an ESPHome device and get details."""
        try:
            # Establish connection
            api = aioesphomeapi.APIClient(
                self.config["hostname"],
                6053,
                None,
                noise_psk=self.config["apikey"] or None,
                keepalive=10,
            )
            self.api = api

            reconnect_logic = aioesphomeapi.ReconnectLogic(
                client=self.api,
                on_connect=self.on_connect,
                on_disconnect=self.on_disconnect,
                zeroconf_instance=self.zc,
            )

            self.reconnect_logic = reconnect_logic
            await reconnect_logic.start()

            await self.stopper.wait()

        except Exception:
            self.handle_exception()
            raise

    async def on_connect(self, *a):
        try:
            api = self.api

            # Get API version of the device's firmware
            self.metadata["API Version"] = api.api_version

            # Show device details
            device_info = await api.device_info()
            self.metadata["Model"] = device_info.model
            self.metadata["Manufacturer"] = device_info.manufacturer
            self.metadata["Project Version"] = device_info.project_version
            self.metadata["Has Deep Sleep"] = device_info.has_deep_sleep

            # List all entities of the device
            entities = await api.list_entities_services()
            for i in entities[0]:
                self.obj_to_tag(i)

            def cb(state):
                self.incoming_state(state)

            api.subscribe_states(cb)
            api.subscribe_logs(
                self.handle_log, log_level=client.LogLevel.LOG_LEVEL_INFO
            )
            api.subscribe_service_calls(self.async_on_service_call)
            time.sleep(0.5)
            self.set_data_point("native_api_connected", 1)

        except Exception:
            self.handle_exception()
            raise

    async def on_disconnect(self, *a):
        self.set_data_point("native_api_connected", 0)
