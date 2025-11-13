from iot_devices.host import Host
from textual.widgets import Pretty, Button, Switch, Input


def makeDataPointControl(
    host: Host,
    devname: str,
    pointname: str,
    type: str,
    subtype: str,
    writable: bool = True,
):
    if type == "numeric":
        if subtype in ("bool", "boolean"):

            class MySwitch(Switch):
                DEFAULT_CSS = """
                MySwitch {
                }
                """

                def on_switch_toggled(self, *a):
                    v = self.value
                    host.set_number(devname, pointname, v)

            return MySwitch()

        if subtype == "trigger":

            class MyButton(Button):
                DEFAULT_CSS = """
                MyButton {
                width: 100%;

                }
                """

                def __init__(self, label):
                    super().__init__(label=label)
                    self.compact = True

                def on_button_pressed(self, *a):
                    old_value = host.get_number(devname, pointname)
                    v = (old_value[0] or 0) + 1
                    if v > 65534:
                        v = 1
                    host.set_number(devname, pointname, v)

                def update(self, v):
                    if v is not None:
                        self.label = f"Go! ({v})"
                    else:
                        self.label = "Go!"

            return MyButton("Go!")

        else:

            class MyNumInput(Input):
                DEFAULT_CSS = """
                MyNumInput {
                    width: 100%;
                }
                """

                def __init__(self):
                    super().__init__()
                    self.compact = True
                    self.type = "number"

                def on_input_changed(self, *a):
                    v = self.value
                    host.set_number(devname, pointname, float(v))

                def update(self, v):
                    self.value = str(v)

            return MyNumInput()

    return Pretty("")
