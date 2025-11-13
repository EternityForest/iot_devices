from typing import Any, Mapping, Callable
import weakref
import tomllib
import sys, os

from iot_devices.host.host import DeviceHostContainer
from iot_devices.host.simple_host import SimpleHost, SimpleHostDeviceContainer

from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.screen import Screen
from textual.widgets import Label, Button, Placeholder, Pretty, RichLog
from textual.containers import VerticalScroll

from iot_devices.tui_dash.datapoint_controls import makeDataPointControl

dev_to_widgets = weakref.WeakValueDictionary()
point_to_widgets = weakref.WeakValueDictionary()


class Host(SimpleHost):
    def get_config_for_device(self, parent_device: Any | None, full_device_name: str):
        """When a device wants to add a subdevice,
        The host can give it extra config
        """
        return {"device.fixed_number_multiplier": "10000000"}

    def set_data_point(
        self,
        name: str,
        value: int | float | str | bytes | Mapping[str, Any] | list[Any],
        timestamp: float | None = None,
        annotation: Any | None = None,
        force_push_on_repeat: bool = False,
    ):
        "This is how devices send data to hosts"
        print(
            f"set_data_point({self}, {name}, {value}, {timestamp}, {annotation}, {force_push_on_repeat})"
        )
        super().set_data_point(name, value, timestamp, annotation, force_push_on_repeat)
        if name in point_to_widgets:
            point_to_widgets[name].val_display.update(value)

    def numeric_data_point(
        self,
        device: str,
        name: str,
        *,
        min: float | None = None,
        max: float | None = None,
        hi: float | None = None,
        lo: float | None = None,
        default: float | None = None,
        description: str = "",
        unit: str = "",
        handler: Callable[[float, float, Any], Any] | None = None,
        interval: float = 0,
        subtype: str = "",
        writable: bool = True,
        dashboard: bool = True,
        **kwargs: Any,
    ):
        super().numeric_data_point(
            device,
            name,
            min=min,
            max=max,
            hi=hi,
            lo=lo,
            default=default,
            description=description,
            unit=unit,
            handler=handler,
            interval=interval,
            subtype=subtype,
            writable=writable,
            dashboard=dashboard,
            **kwargs,
        )
        if device in dev_to_widgets:
            dev_to_widgets[device].scroll.mount(
                OneDataPointWidget(device, name, "numeric", subtype)
            )

    def on_before_device_added(
        self, name: str, device: SimpleHostDeviceContainer, *args: Any, **kwargs: Any
    ):
        devices_screen.devs.mount(OneDeviceDashboardWidget(device))
        return super().on_before_device_added(name, device, *args, **kwargs)

    def on_device_error(self, device: DeviceHostContainer, error: str):
        log.write(f"{device.name}: {error}")
        return super().on_device_error(device, error)


host = Host()


class OneDataPointWidget(Widget):
    DEFAULT_CSS = """
    OneDataPointWidget {
        border: solid $accent;
        text-wrap: wrap;
        width: 100%;
        height: auto;
        layout: vertical;
    }
    """

    def __init__(
        self, devname: str, pointname: str, point_type: str, point_subtype: str
    ):
        super().__init__()

        self.header = Label(pointname)
        self.header.styles.text_align = "left"
        self.header.styles.width = "100%"
        full = host.resolve_datapoint_name(devname, pointname)
        self.val_display = makeDataPointControl(
            host, devname, pointname, point_type, point_subtype
        )
        self.val_display.styles.text_align = "center"

        point_to_widgets[full] = self

    def compose(self) -> ComposeResult:
        yield self.header
        yield self.val_display


class OneDeviceDashboardWidget(Widget):
    DEFAULT_CSS = """
    OneDeviceDashboardWidget {
        border: solid $accent;
        text-wrap: wrap;
        width: 28;
        margin: 1;
        height: auto;
        layout: vertical;
    }
    """

    def __init__(self, device: SimpleHostDeviceContainer):
        super().__init__()
        self.device = device

        self.header = Label(device.name)
        self.header.styles.text_style = "bold"
        self.header.styles.text_align = "left"
        self.header.styles.width = "100%"

        self.scroll = VerticalScroll()

        dev_to_widgets[device.name] = self

    def compose(self) -> ComposeResult:
        yield self.header
        yield self.scroll


class Header(Placeholder):
    DEFAULT_CSS = """
    Header {
        height: 1;
        dock: top;
    }
    """


class Footer(Placeholder):
    DEFAULT_CSS = """
    Footer {
        height: 1;
        dock: bottom;
    }
    """


class DevicesGrid(Widget):
    DEFAULT_CSS = """
    DevicesGrid {
    layout: grid;
    width: 100%;
    grid-size: 5;
    }
    """


log = RichLog()
log.styles.height = 8
log.styles.dock = "bottom"


class TweetScreen(Screen):
    DEFAULT_CSS = """
    TweetScreen {
    border: solid $accent;
    }"""

    def __init__(self):
        super().__init__()
        self.devs = DevicesGrid()

    def on_mount(self) -> None:
        self.devs.styles.grid_size_columns = int(max(1, self.size.width / 30))

    def compose(self) -> ComposeResult:
        yield Header(sys.argv[1])
        with VerticalScroll():
            yield self.devs

        yield log


devices_screen = TweetScreen()


config = {}


class LayoutApp(App):
    BINDINGS = [
        ("up", "move_up", "Up"),
        ("down", "move_down", "Down"),
    ]

    def on_mount(self) -> None:
        self.push_screen(devices_screen)

        x = config["devices"]
        s = sorted(x, key=lambda i: i["name"])

        for d in s:
            host.add_new_device(d)

        log.write("Running...")


def main():
    if not len(sys.argv) > 1:
        sys.argv.append(
            os.path.normpath(
                os.path.join(
                    os.path.dirname(__file__),
                    "../../../tui-dash.toml",
                )
            )
        )
    fn = sys.argv[1]
    with open(fn, "rb") as f:
        cfg = tomllib.load(f)
    config.update(cfg)
    app = LayoutApp()
    app.run()


if __name__ == "__main__":
    main()
