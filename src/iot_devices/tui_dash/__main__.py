import copy
import os
import sys
import tomllib
import weakref
from collections.abc import Callable, Mapping
from typing import Any

import tomli_w
from jsonschema import ValidationError, validate
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Label,
    ListItem,
    ListView,
    Placeholder,
    RichLog,
    Select,
)

from iot_devices.host.host import DeviceHostContainer, apply_defaults
from iot_devices.host.simple_host import SimpleHost, SimpleHostDeviceContainer
from iot_devices.host.util import discover, get_class
from iot_devices.tui_dash.datapoint_controls import makeDataPointControl
from iot_devices.tui_dash.schema_editor import SchemaForm

dev_to_widgets = weakref.WeakValueDictionary()
point_to_widgets = weakref.WeakValueDictionary()


class Host(SimpleHost):
    def get_config_for_device(
        self, parent_device: Any | None, full_device_name: str
    ):
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
        super().set_data_point(
            name, value, timestamp, annotation, force_push_on_repeat
        )
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
            dev_to_widgets[device].queue_point(
                OneDataPointWidget(device, name, "numeric", subtype)
            )

    def on_before_device_added(
        self,
        name: str,
        device: SimpleHostDeviceContainer,
        *args: Any,
        **kwargs: Any,
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
        # Data points may be registered by the device before this widget's
        # compose children exist; queue them until on_mount can flush them.
        self._pending_points: list[OneDataPointWidget] = []

        dev_to_widgets[device.name] = self

    def queue_point(self, widget: OneDataPointWidget) -> None:
        if self.scroll.is_attached:
            self.scroll.mount(widget)
        else:
            self._pending_points.append(widget)

    def on_mount(self) -> None:
        for widget in self._pending_points:
            self.scroll.mount(widget)
        self._pending_points.clear()

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
    }
    #config-btn {
        dock: bottom;
        height: 3;
        width: 100%;
    }
    """

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
        yield Button("Config", id="config-btn")

    @on(Button.Pressed, "#config-btn")
    def _open_config(self) -> None:
        self.app.push_screen(DeviceConfigScreen())


devices_screen = TweetScreen()


config = {}

CONFIG_FILE = "tui-dash.toml"


def _normalize_schema(cls: Any, old_config: dict[str, Any]) -> dict[str, Any]:
    """Get a normalized, editor-friendly schema for a device class."""
    schema = copy.deepcopy(cls.dynamic_schema(old_config))
    # Legacy schemas are flat dicts of dotted keys; wrap them so the editor
    # sees a proper JSON-schema object with properties.
    if "properties" not in schema:
        schema = {"type": "object", "properties": dict(schema)}
    schema.setdefault("type", "object")
    props = schema.setdefault("properties", {})
    props.setdefault(
        "name", {"type": "string", "title": "Name", "propertyOrder": -1}
    )
    props["type"] = {
        "type": "string",
        "title": "Type",
        "readOnly": True,
        "propertyOrder": -1,
    }
    props.setdefault(
        "title", {"type": "string", "title": "Title", "propertyOrder": 1000}
    )
    props.setdefault(
        "notes", {"type": "string", "title": "Notes", "propertyOrder": 1000000}
    )
    return schema


def save_config_file() -> None:
    """Write the current config out to the active TOML file."""
    try:
        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(config, f)
        log.write(f"Saved config to {CONFIG_FILE}")
    except Exception as e:
        log.write(f"Error saving config: {e}")


def _remove_dashboard_widget(name: str) -> None:
    w = dev_to_widgets.pop(name, None)
    if w:
        w.remove()


def apply_device_config(
    old_name: str | None, data: dict[str, Any], is_new: bool
) -> str | None:
    """Save config, then destroy and recreate the affected device.

    Returns an error message on failure, or None on success. The caller
    displays errors to the user; they are intentionally NOT logged since
    the main-page RichLog sits behind modal settings panes where it can't
    be seen.
    """
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return "Device must have a non-empty name"
    name = name.strip()
    data["name"] = name

    # Check for name collisions when the name is new or changed.
    if is_new or (old_name and name != old_name):
        for d in config.get("devices", []):
            if d.get("name") == name:
                return f"A device named {name} already exists"

    if is_new:
        config.setdefault("devices", []).append(copy.deepcopy(data))
    else:
        for i, d in enumerate(config.get("devices", [])):
            if d.get("name") == old_name:
                config["devices"][i] = copy.deepcopy(data)
                break
    save_config_file()

    # Destroy the old device (this also closes any subdevices it created).
    if not is_new and old_name:
        if old_name in host.devices:
            host.close_device(old_name)
        _remove_dashboard_widget(old_name)

    try:
        host.add_new_device(copy.deepcopy(data))
    except Exception as e:
        return f"Error creating device {name}: {e}"
    return None


def remove_device(name: str) -> None:
    config["devices"] = [
        d for d in config.get("devices", []) if d.get("name") != name
    ]
    save_config_file()
    if name in host.devices:
        host.close_device(name)
    _remove_dashboard_widget(name)


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-box {
        width: auto;
        height: auto;
        border: round $error;
        background: $surface;
        padding: 1 2;
    }
    #confirm-buttons {
        height: auto;
        margin-top: 1;
    }
    #confirm-buttons Button {
        margin-right: 1;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.message)
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", variant="error", classes="yes-btn")
                yield Button("No", classes="no-btn")

    @on(Button.Pressed, ".yes-btn")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, ".no-btn")
    def _no(self) -> None:
        self.dismiss(False)


class ErrorScreen(ModalScreen):
    """Splash dialog shown when saving a device fails."""

    DEFAULT_CSS = """
    ErrorScreen {
        align: center middle;
    }
    #error-box {
        width: auto;
        max-width: 80%;
        height: auto;
        border: round $error;
        background: $surface;
        padding: 1 2;
    }
    #error-buttons {
        height: auto;
        margin-top: 1;
    }
    #error-buttons Button {
        margin-right: 1;
    }
    """

    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="error-box"):
            yield Label(self.message)
            with Horizontal(id="error-buttons"):
                yield Button("OK", classes="ok-btn")

    @on(Button.Pressed, ".ok-btn")
    def _ok(self) -> None:
        self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()


class DeviceEditScreen(ModalScreen):
    """Schema-driven editor for one device's config."""

    DEFAULT_CSS = """
    DeviceEditScreen {
        align: center middle;
    }
    #edit-box {
        width: 90%;
        max-width: 100;
        height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #edit-form-scroll {
        height: 1fr;
        border: heavy $primary;
    }
    #edit-buttons {
        height: auto;
        margin-top: 1;
    }
    #edit-buttons Button {
        margin-right: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        original_name: str | None,
        data: dict[str, Any],
        cls: Any = None,
        is_new: bool = False,
    ) -> None:
        super().__init__()
        self.original_name = original_name
        self.is_new = is_new
        self.dev_cls = cls
        self.schema = _normalize_schema(cls, data)
        self.form = SchemaForm(self.schema, data)

    def compose(self) -> ComposeResult:
        if self.is_new and self.dev_cls is not None:
            title = f"New device: {getattr(self.dev_cls, 'device_type', '?')}"
        else:
            title = f"Edit device: {self.original_name}"
        with Vertical(id="edit-box"):
            yield Label(title)
            with VerticalScroll(id="edit-form-scroll"):
                yield self.form
            with Horizontal(id="edit-buttons"):
                yield Button("Save", variant="success", classes="save-btn")
                yield Button("Cancel", classes="cancel-btn")

    @on(Button.Pressed, ".save-btn")
    def _save(self) -> None:
        try:
            validate(self.form.data, self.schema)
        except ValidationError as e:
            self.app.push_screen(ErrorScreen(f"Invalid config: {e.message}"))
            return
        err = apply_device_config(
            None if self.is_new else self.original_name,
            copy.deepcopy(self.form.data),
            self.is_new,
        )
        if err is not None:
            self.app.push_screen(ErrorScreen(err))
            return
        # Saved successfully.
        self.app.pop_screen()
        if self.is_new:
            # Close the device creation pane behind this editor, returning
            # to the main dashboard.
            self.app.pop_screen()

    @on(Button.Pressed, ".cancel-btn")
    def _cancel(self) -> None:
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


class AddDeviceTypeScreen(ModalScreen):
    """Screen for choosing the type of a new device."""

    DEFAULT_CSS = """
    AddDeviceTypeScreen {
        align: center middle;
    }
    #type-box {
        width: 60;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #new-type {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="type-box"):
            yield Label("Choose a device type to add:")
            yield Select(
                [(t, t) for t in sorted(discover().keys())],
                prompt="Device type",
                allow_blank=True,
                id="new-type",
            )
            yield Button("Cancel", classes="cancel-btn")

    @on(Select.Changed, "#new-type")
    def _chosen(self, event: Select.Changed) -> None:
        if event.value == Select.BLANK:
            return
        t = event.value
        try:
            cls = get_class({"type": t})
            skeleton: dict[str, Any] = {"name": "", "type": t}
            apply_defaults(skeleton, _normalize_schema(cls, skeleton))
        except Exception as e:
            log.write(f"Error loading device type {t}: {e}")
            return
        self.app.pop_screen()
        self.app.push_screen(DeviceEditScreen(None, skeleton, cls, is_new=True))

    @on(Button.Pressed, ".cancel-btn")
    def _cancel(self) -> None:
        self.app.pop_screen()


class DeviceConfigScreen(ModalScreen):
    """Screen for adding, editing, and deleting device configs."""

    DEFAULT_CSS = """
    DeviceConfigScreen {
        align: center middle;
    }
    #config-box {
        width: 70;
        height: 70%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #device-list {
        height: 1fr;
        border: heavy $primary;
    }
    #config-buttons {
        height: auto;
        margin-top: 1;
    }
    #config-buttons Button {
        margin-right: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._items: dict[ListItem, dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="config-box"):
            yield Label("Device configuration")
            yield ListView(id="device-list")
            with Horizontal(id="config-buttons"):
                yield Button("Add", classes="add-btn")
                yield Button("Edit", classes="edit-btn")
                yield Button("Delete", variant="error", classes="delete-btn")
                yield Button("Close", classes="close-btn")

    async def on_screen_resume(self) -> None:
        await self._refresh_list()

    async def _refresh_list(self) -> None:
        lv = self.query_one("#device-list", ListView)
        self._items = {}
        await lv.clear()
        for d in sorted(
            config.get("devices", []), key=lambda i: i.get("name", "")
        ):
            item = ListItem(
                Label(f"{d.get('name', '')}  ({d.get('type', '?')})")
            )
            self._items[item] = d
            await lv.append(item)

    def _selected_config(self) -> dict[str, Any] | None:
        lv = self.query_one("#device-list", ListView)
        if lv.index is None:
            return None
        try:
            item = lv.children[lv.index]
        except IndexError:
            return None
        return self._items.get(item)

    def _edit(self, d: dict[str, Any]) -> None:
        try:
            cls = get_class(d)
        except Exception as e:
            log.write(f"Error loading device class for {d.get('name')}: {e}")
            return
        self.app.push_screen(DeviceEditScreen(d.get("name"), d, cls))

    @on(ListView.Selected, "#device-list")
    def _open_selected(self) -> None:
        d = self._selected_config()
        if d:
            self._edit(d)

    @on(Button.Pressed, ".edit-btn")
    def _edit_btn(self) -> None:
        d = self._selected_config()
        if d:
            self._edit(d)

    @on(Button.Pressed, ".add-btn")
    def _add(self) -> None:
        self.app.push_screen(AddDeviceTypeScreen())

    @on(Button.Pressed, ".delete-btn")
    def _delete(self) -> None:
        d = self._selected_config()
        if d:
            name = d.get("name")

            def cb(result: bool | None) -> None:
                if result and name:
                    remove_device(name)
                    self.call_after_refresh(self._refresh_list)

            self.app.push_screen(ConfirmScreen(f"Delete device {name}?"), cb)

    @on(Button.Pressed, ".close-btn")
    def _close(self) -> None:
        self.app.pop_screen()


class LayoutApp(App):
    BINDINGS = [
        ("up", "move_up", "Up"),
        ("down", "move_down", "Down"),
        ("c", "open_config", "Device config"),
    ]

    def action_open_config(self) -> None:
        self.push_screen(DeviceConfigScreen())

    async def on_mount(self) -> None:
        # Wait for the dashboard screen (and its DevicesGrid) to mount
        # before creating devices, which mount their widgets.
        await self.push_screen(devices_screen)

        x = config.get("devices", [])
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
    if os.path.exists(fn):
        with open(fn, "rb") as f:
            cfg = tomllib.load(f)
        config.update(cfg)
    global CONFIG_FILE
    CONFIG_FILE = fn
    app = LayoutApp()
    app.run()


if __name__ == "__main__":
    main()
