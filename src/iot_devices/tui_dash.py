#!/usr/bin/python3

"""
# Run tui-dash, with the tui-dash.conf  as the first command line argument
# Or put your config in ~/tui-dash/tui-dash.conf

"""

import time
import sys
import configparser
import os
import threading
import logging
import urwid
import urwid.numedit
import traceback
import copy
import json

from iot_devices.host import get_class, discover
from iot_devices.device import Device

from typing import Dict


def main():
    user_conf_dir = os.path.expanduser("~/.config/tui-dash")
    os.makedirs(user_conf_dir, exist_ok=True)

    DEFAULT_CONF = """
[A demo device]
type=DemoDevice
"""

    try:
        file = sys.argv[1]
    except Exception:
        file = os.path.join(user_conf_dir, "tui-dash.conf")

        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write(DEFAULT_CONF)

    with open(file) as f:
        cfg = configparser.ConfigParser()
        cfg.read_file(f)

    all_device_data = {}
    ordering_list = []

    for i in cfg.sections():
        data = cfg[i]
        data["name"] = i

        ordering_list.append(i)

        # Make it a real dict
        d = {}
        for j in data:
            d[j] = data[j]
        data = d

        all_device_data[i] = data

    class LineBox2(urwid.LineBox):
        def selectable(self):
            return True

    # Reverse lock? We release it from in the loop so other threads can act like they are part of the loop.

    lock = threading.RLock()
    # cols = urwid.Columns([])

    cols = urwid.GridFlow([], cell_width=60, h_sep=2, v_sep=1, align="left")
    loop = urwid.MainLoop(urwid.Filler(cols, "top"))

    def work(*a):
        # Let someone else do stuff
        lock.release()
        time.sleep(0.0001)

        lock.acquire()
        loop.draw_screen()
        loop.set_alarm_in(0.1, work)

    loop.set_alarm_in(0.1, work)

    class CustomButton(urwid.Button):
        button_left = urwid.Text("[", align="right")
        button_right = urwid.Text("]", align="left")

    def Button(*args, **kwargs):
        b = CustomButton(*args, **kwargs)
        b = urwid.AttrMap(b, "", "highlight")
        b = urwid.Padding(b, left=1, right=1)
        return b

    # Not assigned a display location yet
    pending_devices = {}

    loaded = False

    def customize(c):
        class Mixin:
            def __init__(self, name, *a, **k) -> None:
                pending_devices[name] = self
                self.txts = {}
                self.edits = {}

                with lock:
                    title = urwid.Text(("bold", self.title), "center", "any")
                    self.pile = urwid.Pile([title])

            def create_subdevice(self, cls, name: str, config: Dict, *a, **k):
                """
                Allows a device to create it's own subdevices.
                """

                fn = self.name + "." + name
                # Mix in the config for the data
                try:
                    if fn in all_device_data:
                        config.update(all_device_data[fn])
                except KeyError:
                    logging.exception(
                        "Probably a race condition. Can probably ignore this one."
                    )

                # Customize the class we are given

                m = Device.create_subdevice(self, customize(cls), name, config, *a, **k)

                if loaded:
                    if not self.config.get("hidden", False):
                        with lock:
                            cols.contents.append((self.pile, cols.options()))

                return m

            def on_data_change(self, point, value, timestamp, annotation):
                if isinstance(value, (int, float)):
                    value = round(value, 6)

                with lock:
                    if point in self.txts:
                        self.txts[point].set_text(str(value))
                    if point in self.edits:
                        self.edits[point].set_edit_text(str(value))

            def numeric_data_point(
                self, name, writable=True, default=0, unit="", subtype="", **kwargs
            ):
                c.numeric_data_point(self, name, **kwargs)

                with lock:
                    t = urwid.Text(("bold", name), "left", "any")

                    if not writable:
                        t2 = urwid.Text("no data ")
                        ut = urwid.Text(unit)

                        def refresh(*a):
                            self.request_data_point(name)

                        b2 = Button("get", refresh)

                        cols = urwid.Columns(
                            [(20, t), (8, t2), (6 + 8 + 2, ut), (9, b2)],
                            min_width=4,
                            dividechars=1,
                        )
                        self.txts[name] = t2

                    elif subtype == "trigger":

                        def set(*a):
                            self.set_data_point(
                                name, (self.datapoints.get(name, 0) or 0) + 1
                            )

                        b = Button("go", set)

                        cols = urwid.Columns(
                            [(29 + 8 + 6 + 2 + 1, t), (9, b)],
                            min_width=4,
                            dividechars=1,
                        )

                    elif subtype == "bool":
                        t2 = urwid.Text("no data ")

                        def refresh(*a):
                            self.request_data_point(name)

                        b2 = Button("get", refresh)

                        def toggle(*a):
                            self.set_data_point(
                                name,
                                0 if (self.datapoints.get(name, 0) or 0) > 0.5 else 1,
                            )

                        b2 = Button("Toggle", toggle)

                        cols = urwid.Columns(
                            [(20, t), (22, t2), (12, b2)], min_width=4, dividechars=1
                        )
                        self.txts[name] = t2

                    else:
                        t2 = urwid.numedit.FloatEdit("", str(default))
                        ut = urwid.Text(unit)

                        self.edits[name] = t2

                        def set(*a):
                            self.set_data_point(name, t2.value())

                        b = Button("set", set)

                        def refresh(*a):
                            self.request_data_point(name)

                        b2 = Button("get", refresh)

                        cols = urwid.Columns(
                            [(20, t), (8, t2), (6, ut), (9, b), (9, b2)],
                            min_width=4,
                            dividechars=1,
                        )
                        cols.set_focus(t2)

                    self.pile.contents.append((cols, ("pack", 1)))
                    self.pile.set_focus(cols)

                    # self.pile.contents.append(   (t2,('pack', 1)) )

            def print(self, *a):
                pass

        class ImportedDevice(Mixin, c):
            def __init__(self, name, *a, **k) -> None:
                Device.__init__(self, name, *a, **k)
                Mixin.__init__(self, name, *a, **k)
                c.__init__(self, name, *a, **k)

        return ImportedDevice

    devs = []

    for i, data in all_device_data.items():
        if (data.get("is_subdevice", False) in (True, "true")) or "type" not in data:
            # Name placeholder
            devs.append(i)
            continue

        # Get the class that would be able to construct a matching device given the data
        c = get_class(data)
        Cls = customize(c)

        # Make an instance of that device
        device = Cls(i, data)
        devs.append(device)

    for i in ordering_list:
        if i in pending_devices:
            if not pending_devices[i].config.get("hidden", False):
                cols.contents.append((pending_devices[i].pile, cols.options()))
                del pending_devices[i]

    for i, val in pending_devices.items():
        if not val.config.get("hidden", False):
            cols.contents.append((val.pile, cols.options()))

    loaded = True
    lock.acquire()
    loop.run()


if __name__ == "__main__":
    main()
