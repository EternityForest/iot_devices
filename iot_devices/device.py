from __future__ import annotations
import traceback
from typing import Any
from collections.abc import Callable
import logging
import time
import json
import copy
import weakref
import threading

# example device_manifest.json file that should be in any module declaring devices. keys are device type names.


# submodule values are the
# submodule you would have to import to get access to that
# device type. blank is the root.
# easy to read manually!
# """
# "devices": {
#   "Device":{
#     "submodule": ""
#     "description": "Device base class
#   }
# }
# """

devices_list_lock = threading.RLock()

all_devices: dict[str, weakref.ref[Device]] = {}
_all_devices: dict[str, weakref.ref[Device]] = {}


def new_notification(msg: str, title: str = "Notification", priority: str = "info"):
    "Push a notification to every device"
    with devices_list_lock:
        for i in all_devices.values():
            x = i()
            if x:
                x.handle_notification(msg, title, priority)


def set_alert_state(state: dict[str, dict[str, Any]]):
    "Push a notification to every device"
    with devices_list_lock:
        for i in all_devices.values():
            x = i()
            if x:
                x.handle_alert_state(state)


def get_alerts(*a, **k):  # pylint: disable=unused-argument
    """
    Return a list of currently active "alerts", if the framework supports such a concept,
    In an order suitable for display to humans.

    Args:
        a:
            Reserved
        k:
            Reserved

    Returns:
        A list of dicts, each having, at minimum:

        priority: 10 debug, 20 info, 30 warning, 40 error, 50 critical
        name: Freetext nonunique long descriptive name
        id: Some unique ID
        state: May be 'active' or 'acknowledged'
    """
    return []


# Gonna overwrite these functions insude functions...
minimum = min
maximum = max


class Device:
    """represents exactly one "device".
    should not be used to represent an interface to a large collection, use
    one instance per device.


    Note that this is meant to be subclassed twice.
    Once by the actual driver, and again by the
    host application, to detemine how to handle calls
    made by the driver.
    """

    # this name must be the same as the name of the device itself
    device_type: str = "Device"
    default_config: dict[str, str] = {}

    # This represents either a long text readme or an absolute path beginning with / to such
    readme: str = ""

    def __init__(
        self,
        name: str,
        config: dict[str, str],
        subdevice_config: dict[str, Any] | None = None,
        **kw: Any,
    ):  # pylint: disable=unused-argument
        """

        The base class __init__ does nothing if
        called a second time, to simplify the complex
        inheritance.

        Attributes:

            title:
                Taken from config['title'] if possible, otherwise it is the name.

            config:
                The current configuration of the device

            config_properties:

                For each key in config, there MAY be a
                key in this dict, that can contain any of these optional keys.

                secret:
                    Denotes that the key must be protected from shoulder surfing

                description:
                    Free text

                type:
                    Values may be

                    bool:
                        'yes', 'true', or 'enable' should represent true, with yes being preferred

                    local_fs_path:
                        String is a path on the same folder as the device

            subdevice_config:
                A dict indexed by subdevice name(Either just the child name or
                the full name with parent) containing extra config
                override dicts to be applied when this device creates subdevices.


        Args:
            name: must be a special char free string.
                It may contain slashes, for compatibility with hosts using that for heirarchy

            config: must contain a name field, and must contain
                a type field matching the device type name.
                All other fields must be optional, and a blank
                unconfigured device should be creatable.
                The device should set it's own missing fields for
                use as a template

                Options starting with temp. are reserved for
                device specific things that should not actually
                be saved.

                Options ending with __ are used to add
                additional fields with special meaning.
                Don't use these!


                All your device-specific options should begin with device.

                Subdevice configuration must have is_subdevice: True in save files so the host does not try to create it by itself.
        """

        if not hasattr(self, "config_properties"):
            # Used to store properties about config keys
            self.config_properties: dict[str, dict[str, Any]] = {}

        # Due to complex inheritance patterns, this could be called more than once
        if not hasattr(self, "__initial_setup"):
            config = copy.deepcopy(config)

            if config.get("type", self.device_type) != self.device_type:
                # Special placeholder
                if self.device_type not in ("unsupported", "placeholder"):
                    raise ValueError(
                        "Configured type "
                        + config.get("type", self.device_type)
                        + " does not match this class type:"
                        + str((config["type"], self, type))
                    )

            if subdevice_config and not callable(subdevice_config):
                raise ValueError("subdevice_config must be callable")

            self._subdevice_config = subdevice_config

            # here is where we keep track of our list of
            # sub-devices for each device.
            # Sub-devices will always have a name like
            # ParentDevice.ChildDevice
            self.subdevices: dict[str, Device] = {}

            # allows us to show large amounts of data that
            # do not warrant a datapoint, as it is unlikely anyone
            # would want to show them in a main listing,
            # and nobody wants to see them clutter up anything
            # or slow down the system when they change.
            # Putting data here should have no side effects.
            self.metadata: dict[str, Any] = {}

            # Raise error on bad data.
            json.dumps(config)

            self.config: dict[str, str] = config

            self.title: str = self.config.get("title", "").strip() or name

            self.__datapointhandlers: dict[
                str,
                Callable[
                    [
                        Any,
                        float,
                        Any,
                    ],
                    None,
                ],
            ] = {}
            self.datapoints: dict[str, int | float | str | bytes | dict[str, Any]] = {}

            # Used mostly to determine if the data is still the default.
            self.datapoint_timestamps: dict[str, float] = {}

            # Functions that can be called to explicitly request a data point
            # That return the new value
            self.__datapoint_getters: dict[str, Callable] = {}

            for i, v in self.default_config.items():
                if i not in self.config:
                    self.set_config_option(i, v)

            self.name = name
            if "name" in self.config:
                if not self.config["name"] == name:
                    raise ValueError("Nonmatching name")
                name = self.name = config["name"]
            else:
                self.set_config_option("name", name)

            self.text_config_files: list[str] = []
            """
                Expose files in the config dir for easy editing if the framework supports it.
            """

            # hasattr checked later
            self.__initial_setup = True  # pylint: disable=unused-private-member

            with devices_list_lock:
                global all_devices
                _all_devices[name] = weakref.ref(self)
                all_devices = copy.deepcopy(_all_devices)

    def create_subdevice(self, cls, name: str, config: dict, *a, **k) -> object:
        """
        Args:
            cls: The class used to make the device
            name: The base name of the device.  The full name will be parent.basename
            config: The config as would be passed to any other device

        Returns:
            The device object


        Allows a device to create it's own subdevices.

        The host implementation must take the class, make whatever subclass
        is needed based on it,
        Then instantiate it as if the other parameters were given straight to
        the device.

        When the device is closed, the host must clean up all subdevices
        before cleaning up the master device.
        The host will put the device object into the parent device's subdevice
          dict.

        The host will rename the device to reflect that it is a subdevice.
        It's full name will be parent.basename.

        The host will allow configuration of the device like any other device.
        It will override whatever config that you give this function
        with the user config.

        However the entry in self.subdevices will always be exactly as given
        to this function, referred to as the base name

        The host will add is_subdevice=True to the config dict.
        """

        fn = f"{self.name}.{name}"
        config = copy.deepcopy(config)

        config["name"] = fn
        config["is_subdevice"] = "true"
        config["type"] = cls.device_type

        if self._subdevice_config:
            c = self._subdevice_config(name)
            config.update(c)

        k = copy.copy(k)

        sd = cls(fn, config, *a, **k)

        self.subdevices[name] = sd
        return sd

    def get_config_folder(self, create=True):
        """
        Devices may, in some frameworks, have their own folder in which they can place additional
        configuration, allowing for advanced features that depend on user content.

        Returns:
            An absolute path
        """

        # Can still call with create false just to check
        if create:
            raise NotImplementedError(
                "Your framework probably doesn't support this device"
            )

    @staticmethod
    def discover_devices(
        config: dict[str, str],  # pylint: disable=unused-argument
        current_device: object | None = None,  # pylint: disable=unused-argument
        intent="",  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ) -> dict[str, dict]:
        """
        Discover a set of suggested configs that could be used to build a new device.

        Not required to be implemented and may just return {}

        ***********************
        Discovered suggestions MUST NOT have any passwords or secrets
        if the suggestion would cause them to be tried somewhere
        other than what the user provided them for,
        unless the protocol does not actually reveal the secrets
        to the server.

        You do not want to autosuggest trying the same credentials
        at bad.com that the user gave for example.com.


        The suggested UI semantics for discover commands is
        "Add a similar device" and "Reconfigure this device".

        Reconfiguration should always be available as the user
        might always want to take an existing device object and
        swap out the actual physical device it connects to.

        Kwargs is reserved for further hints on what kinds of
        devices should be discovered.

        Args:
            config: You may pass a partial config, or a completed
                config to find other
                similar devices. The device should reuse as much
                of the given config as possible and logical,
                discarding anything that wouldn't  work with the
                selected device.

            current_device: May be set to the current version of a
                device, if it is being used in a UI along the lines of
                suggesting how to further set up a partly configured
                device, or suggesting ways to add another
                similar device.

            kwargs: is reserved for further hints on what kinds
                of devices should be discovered.


            intent: may be a hint as to what kind of config you are
                    looking for.
                If it is "new", that means the host wants to add
                another similar device.  If it is "replace",
                the host wants to keep the same config
                but point at a different physical device.

                If it is "configure",  the host wants to look
                for alternate configurations available for the
                same exact device.

                If it is "step", the user wants to refine
                the existing config.

        Returns:
            A dict of device data dicts that could be used
            to create a new device, indexed by a descriptive name.

        """

        return {}

    def set_config_option(self, key: str, value: str):
        """sets an option in self.config. used for subclassing as you may want
        to persist.
        __init__ will automatically set the state.  this is used by the device
        itself to set it's own persistent values at runtime, perhaps in response
        to a websocket message.

        __init__ will automatically set the state when passed the config dict,
        you don't have to do that part.

        this is used by the device itself to set it's own persistent values at
        runtime, perhaps in response to a websocket message.


        the host is responsible for subclassing this and actually saving the
        data somehow, should that feature be needed.

        The device may subclass this to respond to realtime config changes.
        """

        if not isinstance(key, str):
            raise TypeError("Key must be str")

        value = str(value)

        if len(value) > 8192:
            logging.error(
                f"Excessively long param for {key} starting with {value[:128]}"
            )

        # Auto strip the values to clean them up
        self.config[key] = value.strip()

    def set_config_default(self, key: str, value: str):
        """sets an option in self.config if it does not exist or is blank.
        Calls into set_config_option, you should not need to subclass this.
        """

        if key not in self.config or not self.config[key].strip():
            self.set_config_option(key, value.strip())

    def wait_ready(self, timeout=15):  # pylint: disable=unused-argument
        """Call this to block for up to timeout seconds for the device to be fully initialized.
        Use this in quick scripts with a devices that readies itself asynchronously
        """
        return

    def print(self, s: str, title: str = ""):
        """used by the device to print to the hosts live device message feed, if such a thing should happen to exist"""
        logging.info(f"{title}: {str(s)}")

    def handle_error(self, s: str, title: str = ""):
        """like print but specifically marked as error. may get special notification.  should not be used for brief network loss"""
        logging.error(f"{title}: {str(s)}")

    def handle_exception(self):
        "Helper function that just calls handle_error with a traceback."
        self.handle_error(traceback.format_exc())

    def handle_event(self, event: str, data: Any | None):
        "Handle arbitrary messages from the host"

    def numeric_data_point(
        self,
        name: str,
        *,
        min: float | None = None,
        max: float | None = None,
        hi: float | None = None,  # pylint: disable=unused-argument
        lo: float | None = None,  # pylint: disable=unused-argument
        default: float | None = None,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[float, float, Any], Any] | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        writable: bool = True,  # pylint: disable=unused-argument
        dashboard: bool = True,  # pylint: disable=unused-argument
        **kwargs: Any,  # pylint: disable=unused-argument
    ):
        """Register a new numeric data point with the given properties.

        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None

        The intent is that you can subclass this and have your own implementation of data points,
        such as exposing an MQTT api or whatever else.

        Most fields are just extra annotations to the host.

        Args:
            min: The min value the point can take on
            max: The max value the point can take on

            hi: A value the point can take on that would be
                considered excessive
            lo: A value the point can take on that would be
                considered excessively low

            description: Free text

            unit: A unit of measure, such as "degC" or "MPH"

            default: If unset default value is None,
                or may be framework defined. Default does not trigger handler.

            handler: A function taking the value,timestamp,
                and annotation on changes.

            interval :annotates the default data rate the point
                will produce, for use in setting default poll
                rates by the host, if the host wants to poll.
                It does not mean the host SHOULD poll this,
                it only suggest a rate to poll at if the host
                has an interest in this data.

            writable:  is purely for a host that might subclass
                this, to determine if it should allow writing to the point.

            subtype: A string further describing the data
                type of this value, as a hint to UI generation.

            dashboard: Whether to show this data point in overview displays.

        """

        if min is None:
            minval: float = -(10**24)
        else:
            minval = min

        if max is None:
            maxval: float = 10**24
        else:
            maxval = max

        self.datapoints[name] = default

        def on_change_attempt(v1: float | None, t, a):
            if v1 is None:
                return
            if callable(v1):
                v1 = v1()

            if v1 is not None:
                v: float = v1
            else:
                return

            v = float(v)

            v = minimum(maxval, v)
            v = maximum(minval, v)

            t = t or time.time()

            if self.datapoints[name] == v:
                # It's still considered a change if the previous value
                # was the default.
                if self.datapoint_timestamps.get(name, 0):
                    return

            self.datapoints[name] = v

            # Handler used by the device
            if handler:
                handler(v, t, a)

            self.on_data_change(name, v, t, a)

        self.__datapointhandlers[name] = on_change_attempt

    def string_data_point(
        self,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[str, float, Any], Any] | None = None,
        default: str | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        writable=True,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        dashboard=True,  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ):
        """Register a new string data point with the given properties.

        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None

        Interval annotates the default data rate the point will produce, for use in setting default poll
        rates by the host, if the host wants to poll.

        Most fields are just extra annotations to the host.


        Args:
            description: Free text

            default: If unset default value is None, or may be framework defined. Default does not trigger handler.

            handler: A function taking the value,timestamp, and annotation on changes.

            interval: annotates the default data rate the point will produce, for use in setting default poll
                rates by the host if the host wants to poll.

                It does not mean the host SHOULD poll this,
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

            subtype: A string further describing the data type of this value, as a hint to UI generation.

            dashboard: Whether to show this data point in overview displays.
        """

        self.datapoints[name] = default

        def on_change_attempt(v: str | None, t, a):
            "This function handles the change detection by itself"
            if v is None:
                return
            if callable(v):
                v = v()
            v = str(v)
            t = t or time.time()

            if self.datapoints[name] == v:
                # It's still considered a change if the previous value
                # was the default.
                if self.datapoint_timestamps.get(name, 0):
                    return

            self.datapoints[name] = v

            # Handler used by the device
            if handler:
                handler(v, t, a)

            self.on_data_change(name, v, t, a)

        self.__datapointhandlers[name] = on_change_attempt

    def object_data_point(
        self,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[dict, float, Any], Any] | None = None,
        interval: float = 0,  # pylint: disable=unused-argument
        writable=True,  # pylint: disable=unused-argument
        subtype: str = "",  # pylint: disable=unused-argument
        dashboard=True,  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ):
        """Register a new object data point with the given properties.   Here "object"
        means a JSON-like object.

        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None

        Interval annotates the default data rate the point will produce, for use in setting default poll
        rates by the host, if the host wants to poll.

        Most fields are just extra annotations to the host.

        Args:
            description: Free text

            handler: A function taking the value,timestamp, and annotation on changes

            interval :annotates the default data rate the point will produce, for use in setting default poll
                rates by the host, if the host wants to poll.  It does not mean the host SHOULD poll this,
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

            subtype: A string further describing the data type of this value, as a hint to UI generation.

            dashboard: Whether to show this data point in overview displays.
        """

        self.datapoints[name] = None

        def on_change_attempt(v1: dict[str, Any] | None, t, a):
            if v1 is None:
                return

            v: dict[str, Any] = v1

            if callable(v):
                v = v()

            # Validate
            json.dumps(v)

            # Mutability trouble
            v = copy.deepcopy(v)

            t = t or time.time()

            if self.datapoints[name] == v:
                # It's still considered a change if the previous value
                # was the default.
                if self.datapoint_timestamps.get(name, 0):
                    return

            self.datapoints[name] = v

            # Handler used by the device
            if handler:
                handler(v, t, a)

            self.on_data_change(name, v, t, a)

        self.__datapointhandlers[name] = on_change_attempt

    def bytestream_data_point(
        self,
        name: str,
        *,
        description: str = "",  # pylint: disable=unused-argument
        unit: str = "",  # pylint: disable=unused-argument
        handler: Callable[[bytes, float, Any], Any] | None = None,
        writable=True,  # pylint: disable=unused-argument
        dashboard=True,  # pylint: disable=unused-argument
        **kwargs,  # pylint: disable=unused-argument
    ):
        """register a new bytestream data point with the
        given properties. handler will be called when it changes.
        only meant to be called from within __init__.

        Bytestream data points do not store data,
        they only push it through.

        Despite the name, buffers of bytes may not be broken up or combined, this is buffer oriented,

        """

        self.datapoints[name] = None

        def on_change_attempt(v: bytes | None, t, a):
            if not v:
                return
            t = t or time.time()
            self.datapoints[name] = v

            # Handler used by the device
            if handler:
                handler(v, t, a)

            self.on_data_change(name, v, t, a)

        self.__datapointhandlers[name] = on_change_attempt

    def push_bytes(self, name: str, value: bytes):
        """Same as set_data_point but for bytestream data"""
        self.set_data_point(name, value)

    def set_data_point(
        self,
        name: str,
        value: int | float | str | bytes,
        timestamp: float | None = None,
        annotation: Any | None = None,
    ):
        """
        Set a data point of the device. may be called by the device itself or by user code.

        This is the primary api and we try to funnel as much as absolutely possible into it.

        things like button presses that are not actually
        "data points" can be represented as things like
        (button_event_name, timestamp) tuples in object_tags.

        things like autodiscovered ui can be done just by
        adding more descriptive metadata to a data point.

        Args:
            name: The data point to set

            value: The literal value.
                Use set_data_point_getter for a
                callable which will return such.

            timestamp: if present is a time.time() time.

            annotation: is an arbitrary object meant to be
                compared for identity,
                for various uses, such as loop prevention
                when dealting with network sync, when you need
                to know where a value came from.


        This must be thread safe, but the change detection
        could glitch out and discard if you go from A to B
        and back to A again.

        When there is multiple writers you will want
        to either do your own lock or ensure that
        dyou use unique values,
        like with an event counter.

        """

        self.datapoint_timestamps[name] = timestamp
        self.__datapointhandlers[name](value, timestamp, annotation)

    def set_data_point_getter(self, name: str, getter: Callable):
        """Set the Getter of a datapoint, making it into an
        on-request point.
        The callable may return either the new value,
        or None if it has no new data.
        """
        self.__datapoint_getters[name] = getter

    def on_data_change(self, name: str, value, timestamp: float, annotation):
        """Used for subclassing, this is how you watch for
        data changes"""

    def request_data_point(self, name: str):
        """Rather than just passively read, actively
        request a data point's new value.

        Meant to be called by external host code.

        """
        if name in self.__datapoint_getters:
            x = self.__datapoint_getters[name]()
            if x is not None:
                timestamp = time.time()
                # there has been a change! Maybe!  call a handler
                self.__datapointhandlers[name](x, timestamp, "From getter")

                self.datapoint_timestamps[name] = timestamp
                self.datapoints[name] = x
                return x

        return self.datapoints[name]

    def set_alarm(
        self,
        name: str,
        datapoint: str,
        expression: str,
        priority: str = "info",
        trip_delay: float = 0,
        auto_ack: bool = False,
        release_condition: str | None = None,
        **kw: Any,
    ):
        """declare an alarm on a certain data point.
        means we should consider the data point to be in an
        alarm state whenever the expression is true.

        used by the device itself to tell the host what
        it considers to be an alarm condition.

        the expression must look like "value > 90", where
        the operator can be any of the common comparision
        operators.

        you may set the trip delay to require it to stay
        tripped for a certain time,
        polling during that time and resettig if it is not
        tripped.

        the alarm remains in the alarm state till the release
        condition is met, by default it's just when the trip
        condition is inactive.  at which point it will need
        to be acknowledged by the user.


        these alarms should be considered "presets" that
        the user can override if possible.
        by default this function could just be a no-op,
        it's here because of kaithem_automation's alarm support,
        but many applications may be better off with full manual
        alarming.

        in kaithem the expression is arbitrary,
        but for this lowest common denominator definition
        it's likely best to
        limit it to easily semantically parsible strings.

        """

    def close(self):
        "Release all resources and clean up"
        for i in list(self.subdevices.keys()):
            self.subdevices[i].close()
            del self.subdevices[i]

    def on_delete(self):
        """
        release all persistent resources, used by the host
        app to tell the user the device is being permanently
        deleted.
        may be used to delete any files automatically created.
        """

    def update_config(self, config: dict[str, Any]):
        "Update the config dynamically at runtime. May be subclassed by the device, not the host.  Uses set_config_option to notify the host."
        for i in config:
            if not self.config.get(i, None) == config[i]:
                self.set_config_option(i, config[i])

        self.title = self.config.get("title", "").strip() or self.name

    # optional ui integration features
    # these are here so that device drivers
    # can device fully custom u_is.

    def on_ui_message(self, msg: float | int | str | bool | None | dict | list, **kw):
        """recieve a json message from the ui page.  the host is
        responsible for providing a window.send_ui_message(msg)
        function to the manage and create forms, and a
        set_ui_message_callback(f) function.

        these messages are not directed at anyone in particular,
        have no semantics, and will be recieved by all
        manage forms including yourself.  they are only meant
        for very tiny amounts of general interest data and fast
         commands.

        this lowest common denominator approach is to
        ensure that the ui can be fully served over mqtt if desired.

        The host page should provide a single JS function
         window.send_ui_message(m) to send this message.

        Manage forms should stay with Vanilla JS as much
        as possible, or else use an iframe.

        """

    def send_ui_message(self, msg: float | int | str | bool | None | dict | list):
        """
        send a message to everyone including yourself.
        The host page should provide a function window.set_ui_message_handler(f)
        To set a JS callback to recieve these.
        """

    def get_management_form(
        self,
    ) -> str | None:
        """must return a snippet of html suitable for insertion into a form tag, but not the form tag itself.
        the host application is responsible for implementing the post target, the authentication, etc.

        when the user posts the form, the config options will be used to first close the device, then build
        a completely new device.

        the host is responsible for the name and type parts of config, and everything other than the device.* keys.
        """

    def notification(self, message: str, title="Notification", priority="info"):
        "Publish a notification"

    def handle_notification(self, message: str, title="Notification", priority="info"):
        """Handle a global system notification, of the sort that the device may want to present to the user in some manner.
        Priority can be any alert priority including "important"
        """

    def handle_alert_state(self, state: dict[str, dict[str, Any]]):
        """Allows a device to stay informed about the state of alerts on the system,
         Assuming that the host supports alerts.

        State must map alarm IDs, which are arbitrary strings, to the following structure:

        {
         priority: 'error' # debug, info, warning, important, error
         state: 'active',  # active, tripped, normal, cleared, acknowledged, error
         description: '',
         message: '',
        }
        """

    @classmethod
    def get_create_form(cls, **kwargs) -> str | None:
        """must return a snippet of html used the same way as get_management_form, but for creating brand new devices"""

    def handle_web_request(self, relpath, params, method, **kwargs):  # pylint: disable=unused-argument
        """To be called by the framework.  Security must be handled by the framework.
        Frameworks may implement separate read and write permissions that apply separately
        to GET and other requests.

        For this reason you should always check that the method is a POST before accepting a write operation.
        """
        return "No web content here"

    def web_serve_file(self, path, filename=None, mime=None):
        """
        From within your web handler, you can return the result of this to serve that file
        """
        raise NotImplementedError("This host framework does not support this feature")
