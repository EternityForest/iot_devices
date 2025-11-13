# iot_devices.tui_dash._\_main_\_

## Attributes

| [`dev_to_widgets`](#iot_devices.tui_dash.__main__.dev_to_widgets)     |    |
|-----------------------------------------------------------------------|----|
| [`point_to_widgets`](#iot_devices.tui_dash.__main__.point_to_widgets) |    |
| [`host`](#iot_devices.tui_dash.__main__.host)                         |    |
| [`log`](#iot_devices.tui_dash.__main__.log)                           |    |
| [`devices_screen`](#iot_devices.tui_dash.__main__.devices_screen)     |    |
| [`config`](#iot_devices.tui_dash.__main__.config)                     |    |

## Classes

| [`Host`](#iot_devices.tui_dash.__main__.Host)                                         |    |
|---------------------------------------------------------------------------------------|----|
| [`OneDataPointWidget`](#iot_devices.tui_dash.__main__.OneDataPointWidget)             |    |
| [`OneDeviceDashboardWidget`](#iot_devices.tui_dash.__main__.OneDeviceDashboardWidget) |    |
| [`Header`](#iot_devices.tui_dash.__main__.Header)                                     |    |
| [`Footer`](#iot_devices.tui_dash.__main__.Footer)                                     |    |
| [`DevicesGrid`](#iot_devices.tui_dash.__main__.DevicesGrid)                           |    |
| [`TweetScreen`](#iot_devices.tui_dash.__main__.TweetScreen)                           |    |
| [`LayoutApp`](#iot_devices.tui_dash.__main__.LayoutApp)                               |    |

## Functions

| [`main`](#iot_devices.tui_dash.__main__.main)()   |    |
|---------------------------------------------------|----|

## Module Contents

### iot_devices.tui_dash._\_main_\_.dev_to_widgets

### iot_devices.tui_dash._\_main_\_.point_to_widgets

### *class* iot_devices.tui_dash._\_main_\_.Host

Bases: [`iot_devices.host.simple_host.SimpleHost`](../../host/simple_host/index.md#iot_devices.host.simple_host.SimpleHost)

#### get_config_for_device(parent_device: Any | None, full_device_name: str)

When a device wants to add a subdevice,
The host can give it extra config

#### set_data_point(name: str, value: int | float | str | bytes | Mapping[str, Any] | list[Any], timestamp: float | None = None, annotation: Any | None = None, force_push_on_repeat: bool = False)

This is how devices send data to hosts

#### numeric_data_point(device: str, name: str, , min: float | None = None, max: float | None = None, hi: float | None = None, lo: float | None = None, default: float | None = None, description: str = '', unit: str = '', handler: Callable[[float, float, Any], Any] | None = None, interval: float = 0, subtype: str = '', writable: bool = True, dashboard: bool = True, \*\*kwargs: Any)

#### on_before_device_added(name: str, device: [iot_devices.host.simple_host.SimpleHostDeviceContainer](../../host/simple_host/index.md#iot_devices.host.simple_host.SimpleHostDeviceContainer), \*args: Any, \*\*kwargs: Any)

#### on_device_error(device: [iot_devices.host.host.DeviceHostContainer](../../host/host/index.md#iot_devices.host.host.DeviceHostContainer), error: str)

### iot_devices.tui_dash._\_main_\_.host

### *class* iot_devices.tui_dash._\_main_\_.OneDataPointWidget(devname: str, pointname: str, point_type: str, point_subtype: str)

Bases: `textual.widget.Widget`

#### DEFAULT_CSS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    OneDataPointWidget {
        border: solid $accent;
        text-wrap: wrap;
        width: 100%;
        height: auto;
        layout: vertical;
    }
    """
```

</details>

#### header

#### val_display

#### compose() → textual.app.ComposeResult

### *class* iot_devices.tui_dash._\_main_\_.OneDeviceDashboardWidget(device: [iot_devices.host.simple_host.SimpleHostDeviceContainer](../../host/simple_host/index.md#iot_devices.host.simple_host.SimpleHostDeviceContainer))

Bases: `textual.widget.Widget`

#### DEFAULT_CSS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    OneDeviceDashboardWidget {
        border: solid $accent;
        text-wrap: wrap;
        width: 28;
        margin: 1;
        height: auto;
        layout: vertical;
    }
    """
```

</details>

#### device

#### header

#### scroll

#### compose() → textual.app.ComposeResult

### *class* iot_devices.tui_dash._\_main_\_.Header

Bases: `textual.widgets.Placeholder`

#### DEFAULT_CSS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    Header {
        height: 1;
        dock: top;
    }
    """
```

</details>

### *class* iot_devices.tui_dash._\_main_\_.Footer

Bases: `textual.widgets.Placeholder`

#### DEFAULT_CSS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    Footer {
        height: 1;
        dock: bottom;
    }
    """
```

</details>

### *class* iot_devices.tui_dash._\_main_\_.DevicesGrid

Bases: `textual.widget.Widget`

#### DEFAULT_CSS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    DevicesGrid {
    layout: grid;
    width: 100%;
    grid-size: 5;
    }
    """
```

</details>

### iot_devices.tui_dash._\_main_\_.log

### *class* iot_devices.tui_dash._\_main_\_.TweetScreen

Bases: `textual.screen.Screen`

#### DEFAULT_CSS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    TweetScreen {
    border: solid $accent;
    }"""
```

</details>

#### devs

#### on_mount() → None

#### compose() → textual.app.ComposeResult

### iot_devices.tui_dash._\_main_\_.devices_screen

### iot_devices.tui_dash._\_main_\_.config

### *class* iot_devices.tui_dash._\_main_\_.LayoutApp

Bases: `textual.app.App`

#### BINDINGS *= [('up', 'move_up', 'Up'), ('down', 'move_down', 'Down')]*

#### on_mount() → None

### iot_devices.tui_dash._\_main_\_.main()
