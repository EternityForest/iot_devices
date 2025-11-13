# iot_devices.devices.ESPHomePlugin

## Classes

| [`ESPHomeDevice`](#iot_devices.devices.ESPHomePlugin.ESPHomeDevice)   | represents exactly one "device".   |
|-----------------------------------------------------------------------|------------------------------------|

## Package Contents

### *class* iot_devices.devices.ESPHomePlugin.ESPHomeDevice(config: Dict[str, Any], \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'ESPHomeDevice'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### upgrade_legacy_config_keys

\_\_init_\_ uses this to auto rename old config keys to new ones
if your device renames things.  They are type coerced according
to the schema too.

#### wait_ready(timeout=15)

Call this to block for up to timeout seconds for the device to be fully initialized.
Use this in quick scripts with a devices that readies itself asynchronously.

May be implemented by the device, but is not required.

#### async_on_service_call(service: aioesphomeapi.model.HomeassistantServiceCall) → None

Call service when user automation in ESPHome config is triggered.

#### update_wireless()

#### handle_log(msg)

#### add_bool(name: str, w=False)

#### add_button(name: str, buttonid: int)

#### obj_to_tag(i)

#### incoming_state(s)

#### zc

#### name_to_key

#### key_to_name

#### input_units

#### stopper

#### loop

#### thread

#### asyncloop()

#### on_before_close()

Subclass defined cleanup handler.

#### *async* main(\*a, \*\*k)

Connect to an ESPHome device and get details.

#### *async* on_connect(\*a)

#### *async* on_disconnect(\*a)
