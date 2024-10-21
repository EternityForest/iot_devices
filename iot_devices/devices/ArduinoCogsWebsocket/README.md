## ArduinoCogs WS API

WARNING:  This device type is extremely beta.

## Currrent API

This lets you transfer integer-only variables, with scale factors for fixed point.
The semantics are eventually consistent: If you update a variable to 1,2,3,4 on the device,
firmware can decide to only send the 4 once it stops changing, dropping intermediates.

### /api/tags

Return a list of every exposed tag and the value, as a json object.

### /api/tag?tag=NAME

Return a json object that has:

min and max, as integers, scale, as an integer(Multiply real value by this to get the encoded val that is transferred).

unit, a string.  Normally a unit of measure, can also be bool, or bang for simple counter triggers.


### /api/trouble-codes

Returns a json dict of brief trouble codes, starting with one of DIWEC to indicate level,
like "WLOWBATTERY", with values being True when there is trouble, and False meaning they
are no longer active but have also not been cleared.


### /api/ws

This websocket connection.  Messages TO device look like: `{"vars":{"varname":877}}` and request to
set one or more variables.

Messages FROM the device set 