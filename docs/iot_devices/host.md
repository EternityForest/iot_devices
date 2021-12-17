Module iot_devices.host
=======================

Variables
---------

    
`device_classes`
:   This dict lets you programmatically add new devices

Functions
---------

    
`discover() ‑> Dict[str, Dict]`
:   Search system paths for modules that have a devices manifest.
    
    Returns:
        A dict indexed by the device type name, with the values being info dicts.
        Keys not documented here should be considered opaque.
    
        description: A free text, paragraph or less short description, taken from the device manifest.
    
        importable: The full module(including the submodule) you would import to get the class to build this device.
    
        classname: The name of the class you would import

    
`get_class(data) ‑> Type`
:   Return the class that one would use to construct a device given it's data.  Automatically search all system paths.
    
    Returns:
        A class, not an instance