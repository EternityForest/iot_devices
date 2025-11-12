from iot_devices.host import Host
from textual.widgets import Pretty, Button


def makeDataPointControl(
    host: Host,
    devname: str,
    pointname: str,
    type: str,
    subtype: str,
    writable: bool = True,
):
    if type == "numeric":
        if subtype == "trigger":

            class MyButton(Button):
                DEFAULT_CSS = """
                MyButton {

                }
                """

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

    return Pretty("")
