import weakref

import sys
import os
import importlib
import json
import copy 
import logging
from typing import Dict,Type
known_device_types = {}




# Programmatically generated device classes go here
device_classes= weakref.WeakValueDictionary()

def discover() -> Dict[str,Dict]:
    """Search system paths for modules that have a devices manifest.

    Returns:
        A dict indexed by the device type name, with the values being info dicts.
        The contents of these is currently opaque, there are no standard keys.  You should just look at the names for now.
    
    """

    paths = copy.deepcopy(sys.path)
    here = os.path.dirname(os.path.abspath(__file__))
    paths.append(here)

    # Priority
    for i in reversed(paths):
        if not os.path.isdir(i):
            continue
        for d in os.listdir(i):
            folder = os.path.join(i,d)
            if os.path.isdir(folder):
                if os.path.isfile(os.path.join(folder, "devices_manifest.json")):
                    try:
                        with open(os.path.join(folder, "devices_manifest.json")) as f:
                            d = f.read()
                            d = json.loads(d)

                        for dev in d['devices']:
                            known_device_types[dev] = d['devices'][dev]

                            #Special case handling devices included in this library for demo purposes.
                            modulename =os.path.basename(folder)
                            if os.path.dirname(folder)== here:
                                modulename= "iot_device"

                            x = d['devices'][dev].get("submodule",None)
                            if x:
                                modulename=modulename+"."+x

                            known_device_types[dev]['importable'] = modulename

                    except:
                        logging.exception("Error with devices manifest in: "+folder)
    return known_device_types


def get_class(data) -> Type:
    """
    Return the class that one would use to construct a device given it's data.  Automatically search all system paths.

    Returns:
        A class, not an instance
    """
    t = data['type']

    if t in device_classes:
        try:
            return device_classes[data]
        except KeyError:
            pass

    if not t in known_device_types:
        discover()

    m = known_device_types[t]['importable']
    module  =  importlib.import_module(m)
    return module.__dict__[t]
 
