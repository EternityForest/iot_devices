# iot_devices.devices.ArduinoCogsWebsocket

## Attributes

| [`ILLEGAL_NAME_CHARS`](#iot_devices.devices.ArduinoCogsWebsocket.ILLEGAL_NAME_CHARS)   |    |
|----------------------------------------------------------------------------------------|----|
| [`logger`](#iot_devices.devices.ArduinoCogsWebsocket.logger)                           |    |
| [`client_schema`](#iot_devices.devices.ArduinoCogsWebsocket.client_schema)             |    |
| [`server_schema`](#iot_devices.devices.ArduinoCogsWebsocket.server_schema)             |    |

## Classes

| [`ArduinoCogsClient`](#iot_devices.devices.ArduinoCogsWebsocket.ArduinoCogsClient)   | represents exactly one "device".   |
|--------------------------------------------------------------------------------------|------------------------------------|
| [`ArduinoCogsServer`](#iot_devices.devices.ArduinoCogsWebsocket.ArduinoCogsServer)   | represents exactly one "device".   |

## Package Contents

### iot_devices.devices.ArduinoCogsWebsocket.ILLEGAL_NAME_CHARS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""{}|\<>,?-=+)(*&^%$#@!~`

  """
```

</details>

### iot_devices.devices.ArduinoCogsWebsocket.logger

### iot_devices.devices.ArduinoCogsWebsocket.client_schema

### *class* iot_devices.devices.ArduinoCogsWebsocket.ArduinoCogsClient(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'ArduinoCogsClient'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### checker()

#### handle_trouble_code_state(msg: str, val: float)

#### handle_message(msg: str)

#### on_var_msg(msg: str, val: float | int)

#### makeHandler(var: str)

#### sendVar(var: str, val: float)

#### thread()

#### on_before_close()

Subclass defined cleanup handler.

### iot_devices.devices.ArduinoCogsWebsocket.server_schema *: dict[str, Any]*

### *class* iot_devices.devices.ArduinoCogsWebsocket.ArduinoCogsServer(data, \*\*kw)

Bases: [`iot_devices.device.Device`](../../device/index.md#iot_devices.device.Device)

represents exactly one "device".
should not be used to represent an interface to a large collection, use
one instance per device.

Note that this is meant to be subclassed twice.
Once by the actual driver, and again by the
host application, to detemine how to handle calls
made by the driver.

#### device_type *= 'ArduinoCogsServer'*

Every device must have a unique device_type name

#### numeric_handler(n: str, scale: float)

#### should_run *= True*

#### makews()

#### handle_device_info_request(request: starlette.requests.Request)

#### handle_tag_info_request(request: starlette.requests.Request)

#### handle_trouble_codes_request(request: starlette.requests.Request)

#### handle_tags_list_request(request: starlette.requests.Request)

#### on_before_close()

Subclass defined cleanup handler.
