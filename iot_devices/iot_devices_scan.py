import json
import copy
import traceback

from iot_devices.host import get_class, discover
from iot_devices.device import Device

print("# Known Device Plugins\n")
print("All devices shown, some config params may be unlisted.")
print("This documentation is autogenerated with iot_devices_scan.py\n")
d = discover()
for i in sorted(d.keys()):
    print("## " + i+"\n")
    print(d[i].get('description', '')+'\n')
    try:
        c1 = get_class({'type': i})

        dpi = {}
        dpd = {}
        dpw = {}

        props = {}

        class c(c1):
            def string_data_point(self,
                                  name: str,
                                  description: str = "",
                                  unit: str = '',
                                  handler=None,
                                  interval: float = 0,
                                  writable=True,
                                  subtype: str = '',
                                  **kwargs):
                Device.string_data_point(self, name, description=description, unit=unit,
                                         handler=handler, interval=interval, writable=writable,
                                         subtype=subtype, **kwargs)
                dpi[name] = f"{subtype} {unit}"
                dpd[name] = description
                dpw[name] = writable

            def numeric_data_point(self,
                                   name: str,
                                   description: str = "",
                                   unit: str = '',
                                   handler=None,
                                   interval: float = 0,
                                   writable=True,
                                   subtype: str = '',
                                   **kwargs):
                Device.numeric_data_point(self, name, description=description, unit=unit,
                                          handler=handler, interval=interval, writable=writable,
                                          subtype=subtype, **kwargs)
                dpi[name] = f"""{subtype} {unit}""".strip()
                dpd[name] = description
                dpw[name] = writable

        defaults = {}
        tags = {}

        try:
            inst = c('DeviceName', {'type': i})
            props.update(inst.config_properties)

            for j in inst.config:
                if not j in props:
                    props[j] = {}

            tags.update(inst.datapoints)

        except Exception:
            print(traceback.format_exc())

        print("```python")
        print("from " + d[i]['importable'] + " import " + i + "\n")

        print("dev = " + i+'("name",{')
        count = 0
        for j in props:
            count += 1
            if j.startswith("device."):
                desc = props[j].get('description', '')
                if desc:
                    print(
                        '    # '+props[j].get('description', '')+"")
                ending = "," if count < len(props) else '\n})'
                if j in inst.config:
                    print(f"    '{j}': '{inst.config[j]}'"+ending)

        print("\n\n")
        for j in dpi:
            desc = dpd.get(j, '')
            if dpi[j].strip():
                print(f'# {dpi[j]}')
            if desc:
                print(f"# {desc}")
            print(f"print(dev.datapoints['{j}'])")
            print(f"# >>> {str(inst.datapoints[j])[:64]}\n")

            if dpw.get(j, False):
                print(f"# {j} is writable")
                print(
                    f"# dev.set_data_point('{j}', <your value> )\n")
        print("```")

    except Exception:
        print("## Error getting data for " + i)
        print(traceback.format_exc())

    print("")
