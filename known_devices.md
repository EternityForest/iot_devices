# Known Device Plugins

All devices shown, some config params may be unlisted.

## DemoDevice

From: iot_devices.devices.demo
### (config) device.fixed_number_multiplier


### (data) random   writable

### (data) dyn_random   writable

### (data) useless_toggle bool  writable

### (data) do_nothing trigger  writable

### (data) read_only   readonly


## RTL433Client

From: iot_devices.devices.RTL433
### (config) device.interval


### (config) device.id


### (config) device.model


### (config) device.server


### (config) device.port


### (config) device.password


### (config) device.mqttTopic


### (data) rssi   readonly
-75 if recetly seen, otherwise -180, we don't have real RSSI data
### (data) mqttStatus   readonly


## ConfigurableAlarm

From: iot_devices.devices.alarm

### (config) device.alarm_name


### (config) device.priority


### (config) device.auto_acknowledge


### (data) trigger   writable



## Zigbee2MQTT

### (config) device.mqtt_server


### (config) device.friendly_name



## YeelightRGB

From: iot_devices.devices.Yeelight

### (data) rssi   readonly

### (data) switch bool  writable

### (data) fade light_fade_duration  writable

## color color  writable


## RokuRemoteApp

From: iot_devices.devices.RokuRemoteApp
### (config) device.serial


### (config) device.uuid


### (config) device.bind


### (data) battery  % writable


## YoLinkService

From: iot_devices.devices.YoLink
### (config) device.user_id


### (config) device.key


### (data) connected bool  readonly


## WeatherClient

From: iot_devices.devices.WeatherPlugin

### (config) device.update_interval
Values below 90 minutes are ignored

### (config) device.location


### (config) device.update_minutes


### (data) temperature  degC readonly

### (data) humidity  % readonly

### (data) wind  KPH readonly

### (data) pressure  millibar readonly

### (data) uv_index   readonly


## ESPHomeDevice

From: iot_devices.devices.ESPHomePlugin

### (config) device.update_interval
Values below 90 minutes are ignored

### (config) device.apikey


### (config) device.hostname


### (data) native_api_connected bool  readonly


## ServerMonitor

### (config) device.target
Hostname or URL to ping.  If an http:// url is used, will poll with HTTP as well as ping.

### (config) device.check_interval


### (data) status bool  writable