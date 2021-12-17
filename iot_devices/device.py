import collections
import traceback
from typing import Any, Callable, Dict, Optional, Union
import logging
import time
import json
import copy

# example device_manifest.json file that should be in any module declaring devices. keys are device type names.


# submodule values are the submodule you would have to import to get access to that device type. blank is the root.
# easy to read manually!
"""
"devices": {
  "Device":{
    "submodule": ""
    "description": "Device base clas
  }
}
"""

#Gonna overwrite these functions insude functions...
minimum = min
maximum = max

class Device():
    """represents exactly one "device".   
    should not be used to represent an interface to a large collection, use
    one instance per device.
    

    Note that this is meant to be subclassed twice.  Once by the actual driver, and again by the 
    host application, to detemine how to handle calls made by the driver.

    """


    # this name must be the same as the name of the device itself
    device_type: str="Device"
    default_config={}

    # Iterable of config keys that should be considered secret, and hidden behind asterisks and such.
    config_secrets={}

    def __init__(self, name: str, config: Dict[str, str],**kw):
        """ 
        
        Args:
            name: must be a special char free string.  
                It may contain slashes, for compatibility with hosts using that for heirarchy
       
            config: must contain a name field, and must contain a type field matching the device type name.
                All other fields must be optional, and a blank unconfigured device should be creatable.  
                The device should set it's own missing fields for use as a template 
                
                Options starting with temp. are reserved for device specific things that should not actually be saved.
                Options endning with __ are used to add additional fields with special meaning.  Don't use these!


                All your device-specific options should begin with device.
        """

        config=copy.deepcopy(config)

        if config.get("type",self.device_type) != self.device_type:
            raise ValueError("This config does not match this class type:"+str((config['type'], self,type)))
    

        # Raise error on bad data.
        json.dumps(config)

        self.config: Dict[str, str] = config
        self.__datapointhandlers: Dict[str, Callable] = {}
        self.datapoints = {}

        #Functions that can be called to explicitly request a data point
        #That return the new value
        self.__datapoint_getters: Dict[str, Callable] = {}

        for i in self.default_config:
            if not i in self.config:
                self.set_config_option(i,self.default_config[i])

        self.name=name
        if 'name' in self.config:
            if not self.config['name']== name:
                raise ValueError("Nonmatching name")
            name=self.name = config['name']
        else:
            self.set_config_option('name', name)
        

    @staticmethod
    def discover_devices(config:Dict[str, str] = {}, current_device: Optional[object]=None, intent="", **kwargs) -> Dict[str, Dict]:
        """ 
        Discover a set of suggested configs that could be used to build a new device.        
        
        Not required to be implemented and may just return {}  

        ***********************
        Discovered suggestions MUST NOT have any passwords or secrets if the suggestion would cause them to be tried somewhere
        other than what the user provided them for, unless the protocol does not actually reveal the secrets to the server.
        
        You do not want to autosuggest trying the same credentials at bad.com that the user gave for example.com.

    
        The suggested UI semantics for discover commands is "Add a similar device" and "Reconfigure this device".
        
        Reconfiguration should always be available as the user might always want to take an existing device object and
        swap out the actual physical device it connects to.


        Args:
            config: You may pass a partial config, or a completed config to find other
                similar devices. The device should reuse as much of the given config as possible and logical,
                discarding anything that wouldn't  work with the selected device.

            current_device: May be set to the current version of a device, if it is being used in a UI along the lines of
                suggesting how to further set up a partly configured device, or suggesting ways to add another similar device.

            kwargs: is reserved for further hints on what kinds of devices should be discovered.

        
            intent: may be a hint as to what kind of config you are looking for.  
                If it is "new", that means the host wants to add another
                similar device.  If it is "replace", the host wants to keep the same config 
                but point at a different physical device.  If it is
                "configure",  the host wants to look for alternate configurations available for the same exact device.

                If it is "step", the user wants to refine the existing config.

        Returns:
            A dict of device data dicts that could be used to create a new device, indexed by a descriptive name.


      

        """

        return {}

    def set_config_option(self, key: str, value: str):
        """sets an option in self.config. used for subclassing as you may want to persist.

        __init__ will automatically set the state when passed the config dict, you don't have to do that part.
        
        this is used by the device itself to set it's own persistent values at runtime, perhaps in response to a websocket message.

        
        the host is responsible for subclassing this and actually saving the data somehow, should that feature be needed.
        """

        if not isinstance(key,str):
            raise TypeError("Key must be str")

        value = str(value)
        if len(value)>8192:
            logging.error("Excessively long param for "+key+" starting with "+value[:128])

        # Auto strip the values to clean them up
        self.config[key] = value.strip()


    def set_config_default(self, key: str, value: str):
        """sets an option in self.config if it does not exist or is blank.        
         Calls into set_config_option, you should not need to subclass this.
        """

        if not key in self.config or not self.config[key].strip():
            self.set_config_option(key,value.strip())


    def print(self, s: str, title: str = ""):
        """used by the device to print to the hosts live device message feed, if such a thing should happen to exist"""
        logging.info(title + ': ' + str(s))

    def handle_error(self, s: str, title: str = ""):
        """like print but specifically marked as error. may get special notification.  should not be used for brief network loss
        """
        logging.error(title + ': ' + str(s))

    def handle_exception(self):
        "Helper function that just calls handle_error with a traceback."
        self.handle_error(traceback.format_exc())

    def numeric_data_point(self,
                           name: str,
                           min: Optional[float] = None,
                           max: Optional[float] = None,
                           hi: Optional[float] = None,
                           lo: Optional[float] = None,
                           description: str = "",
                           unit: str = '',
                           handler:  Optional[Callable[[float,float,Any], Any]] = None,
                           interval: float = 0,
                           writable=True,
                           **kwargs):
        """Register a new numeric data point with the given properties. 
        
        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None


        Most fields are just extra annotations to the host.

        Args:
            min: The min value the point can take on
            max: The max value the point can take on

            hi: A value the point can take on that would be considered excessive
            lo: A value the point can take on that would be considered excessively low

            description: Free text

            unit: A unit of measure, such as "degC" or "MPH"
            
            handler: A function taking the value,timestamp, and annotation on changes

            interval :annotates the default data rate the point will produce, for use in setting default poll
                rates by the host, if the host wants to poll.  It does not mean the host SHOULD poll this, 
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

        """

        if min is None:
            min = -10**24

        if max is None:
            max = 10**24

        self.datapoints[name] = None

        def onChangeAttempt(v: Optional[float], t, a):
            if v is None:
                return
            if callable(v):
                v = v()
            v = float(v)
            v = minimum(max, v)
            v = maximum(min, v)
            t = t or time.monotonic()

            if self.datapoints[name] == v:
                return

            self.datapoints[name] = v

            #Handler used by the device
            if handler:
                handler(v, t, a)

            self.on_data_change(name, v, t, a)

        self.__datapointhandlers[name] = onChangeAttempt


    def string_data_point(self,
                           name: str,
                           description: str = "",
                           unit: str = '',
                           handler: Optional[Callable[[str,float,Any], Any]] = None,
                           interval: float = 0,
                           writable=True,
                           **kwargs):
        """Register a new string data point with the given properties. 
        
        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None


        Most fields are just extra annotations to the host.


        Args:
            description: Free text
            
            handler: A function taking the value,timestamp, and annotation on changes

            interval: annotates the default data rate the point will produce, for use in setting default poll
                rates by the host if the host wants to poll.  
                
                It does not mean the host SHOULD poll this, 
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

        """

        self.datapoints[name] = None

        def onChangeAttempt(v: Optional[str], t, a):
            if v is None:
                return
            if callable(v):
                v = v()
            v = str(v)
            t = t or time.monotonic()

            if self.datapoints[name] == v:
                return

            self.datapoints[name] = v

            #Handler used by the device
            if handler:
                handler(v, t, a)

            self.on_data_change(name, v, t, a)

        self.__datapointhandlers[name] = onChangeAttempt


    def object_data_point(self,
                           name: str,
                           description: str = "",
                           unit: str = '',
                           handler: Optional[Callable[[Dict,float,Any], Any]] = None,
                           interval: float = 0,
                            writable=True,
                           **kwargs):
        """Register a new object data point with the given properties.   Here "object"
        means a JSON-like object.
        
        Handler will be called when it changes.
        self.datapoints[name] will start out with tha value of None


        Most fields are just extra annotations to the host.

        Args:
            description: Free text
            
            handler: A function taking the value,timestamp, and annotation on changes

            interval :annotates the default data rate the point will produce, for use in setting default poll
                rates by the host, if the host wants to poll.  It does not mean the host SHOULD poll this, 
                it only suggest a rate to poll at if the host has an interest in this data.

            writable:  is purely for a host that might subclass this, to determine if it should allow writing to the point.

        """
        self.datapoints[name] = None

        def onChangeAttempt(v: Optional[str], t, a):
            if v is None:
                return
            if callable(v):
                v = v()

            # Validate
            json.dumps(v)

            # Mutability trouble
            v = copy.deepcopy(v)

            t = t or time.monotonic()

            if self.datapoints[name] == v:
                return

            self.datapoints[name] = v

            #Handler used by the device
            if handler:
                handler(v, t, a)

            self.on_data_change(name, v, t, a)

        self.__datapointhandlers[name] = onChangeAttempt




    def set_data_point(self,
                       name: str,
                       value,
                       timestamp: Optional[float] = None,
                       annotation: Optional[float] = None):
        """
        Set a data point of the device. may be called by the device itself or by user code. 
        
        This is the primary api and we try to funnel as much as absolutely possible into it.
        
        things like button presses that are not actually "data points" can be represented as things like
        (button_event_name, timestamp) tuples in object_tags.
        
        things like autodiscovered ui can be done just by adding more descriptive metadata to a data point.
        
        Args:
            name: The data point to set

            timestamp: if present is a time.monotonic() time.  

            annotation: is an arbitrary object meant to be compared for identity,
                for various uses, such as loop prevention when dealting with network sync, when you need to know where a value came from.


        This must be thread safe, but the change detection could glitch out and discard if you go from A to B and back to A again.
        
        When there is multiple writers you will want to aither do your own lock or ensure that you use unique values, 
        like with an event counter.
        
        """


        self.__datapointhandlers[name](value, timestamp, annotation)

    
    def set_data_point_getter(self,name:str, getter: Callable):
        """Set the Getter of a datapoint, making it into an on-request point.
        The callable may return either the new value, or None if it has no new data.
        """
        self.__datapoint_getters[name] = getter

    def on_data_change(self, name: str, value, timestamp: float, annotation):
        "Used for subclassing, this is how you watch for data changes"
        pass

    def request_data_point(self, name: str):
        """Rather than just passively read, actively request a data point's new value.

        Meant to be called by external host code.
        
        """
        if name in self.__datapoint_getters:
            x = self.__datapoint_getters[name]()
            if not x is None:
                # there has been a change! Maybe!  call a handler
                self.__datapointhandlers[name](x, time.monotonic(), "From getter")
                self.datapoints[name] = x
                return x

        return self.datapoints[name]

    def set_alarm(self, name:str, datapoint:str, 
            expression:str, priority:str="info" ,
            trip_delay:float=0, auto_ack:bool=False,
             release_condition:Optional[str]=None, **kw):
        """ declare an alarm on a certain data point.   this means we should consider the data point to be in an
            alarm state whenever the expression is true.  
            
            used by the device itself to tell the host what it considers to be an alarm condition.
            
            the expression must look like "value > 90", where the operator can be any of the common comparision operators.
            
            you may set the trip delay to require it to stay tripped for a certain time,
            polling during that time and resettig if it is not tripped.
            
            the alarm remains in the alarm state till the release condition is met, by default it's just when the trip
            condition is inactive.  at which point it will need to be acknowledged by the user.
            
            
            these alarms should be considered "presets" that the user can override if possible.   
            by default this function could just be a no-op, it's here because of kaithem_automation's alarm support,
            but many applications may be better off with full manual alarming.  
            
            in kaithem the expression is arbitrary, but for this lowest common denominator definition it's likely best to
            limit it to easily semantically parsible strings.
        
        """
        pass


    def close(self):
        "Release all resources and clean up"

    def on_delete(self):
        """
        release all persistent resources, used by the host app to tell the user the device is being permanently deleted.
        may be used to delete any files automatically created.
        """


    # optional ui integration features
    # these are here so that device drivers can device fully custom u_is.


    def on_ui_message(self,msg:Union[float, int, str, bool, None, dict, list],**kw):
        """recieve a json message from the ui page.  the host is responsible for providing a send_ui_message(msg)
        function to the manage and create forms, and a set_ui_message_callback(f) function.
        
        these messages are not directed at anyone in particular, have no semantics, and will be recieved by all
        manage forms including yourself.  they are only meant for very tiny amounts of general interest data and fast commands.
        
        this lowest common denominator approach is to ensure that the ui can be fully served over mqtt if desired.
    
        """

    def send_ui_message(self, msg:Union[float, int, str, bool, None, dict, list]):
        """
        send a message to everyone including yourself.
        """

    def get_management_form(self,) -> Optional[str]:
        """must return a snippet of html suitable for insertion into a form tag, but not the form tag itself.
        the host application is responsible for implementing the post target, the authentication, etc.
        
        when the user posts the form, the config options will be used to first close the device, then build 
        a completely new device.
        
        the host is responsible for the name and type parts of config, and everything other than the device.* keys.
        """

    @classmethod
    def get_create_form(cls, **kwargs) -> Optional[str]:
        """must return a snippet of html used the same way as get_management_form, but for creating brand new devices"""
