# Change Log

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
