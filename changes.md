# Change Log

## 0.25.0

Remove some low quality unmaintained devices, and add unit tests.

* :coffin: Remove RTL433 MQTT Client
* :coffin: Remove RokuRemote
* Switch to UV
* Document send_ui_message removal
* The legacy config_properties interface is deprecated.  It will still work for a while with the compatibility shims, but it raises warnings.
* There is a fixed set of reserved keys.  No more device. prefixes.
* Nonstandard additional properties added by the framework must go in a top level "extensions" section.

## 0.24.0

* DemoDevice does more random stuff
* Avoid a theoretical race condition when first connecting with ArduinoCogs

## 0.23.0

* Now we use JSON Schemas to describe config.  Legacy config still works, we are completely backwards compatible.
* This means config can have true nested data.
* Autogenerate schemas for legacy config.
* Legacy config metadata is not exactly deprecated but is no longer recommended. Use a JSON schema.

## 0.22.0

* Expose datapoint_timestamps
* ArduinoCogs read only points automatically considered the source of truth
* ArduinoCogs set remote device points on first connect if host app has data for it

## 0.21.1

* Improvements to the ArduinoCogs protocol support
* send_ui_message is now window.send_ui_message, but that whole API is alpha/not recommented anyway.

## 0.21.0

* Add experimental support for the ArduinoCogs websocket protocol

## 0.20.0

* BIG BREAKING CHANGE(not really): Use UTC instead of monotonic timestamps

## 0.19.0

* Fix ESPHome
* Get rid of long-untested zigbee2mqtt
* Add yolink Vibration and Motion
* Fix yolink temperature and humidity giving wrong values
