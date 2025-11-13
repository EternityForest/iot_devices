# iot_devices.schema_editor

## Attributes

| [`demo_schema`](#iot_devices.schema_editor.demo_schema)   |    |
|-----------------------------------------------------------|----|
| [`demo_data`](#iot_devices.schema_editor.demo_data)       |    |
| [`app`](#iot_devices.schema_editor.app)                   |    |

## Classes

| [`SchemaNodeSelected`](#iot_devices.schema_editor.SchemaNodeSelected)   |    |
|-------------------------------------------------------------------------|----|
| [`ValueChanged`](#iot_devices.schema_editor.ValueChanged)               |    |
| [`UndoManager`](#iot_devices.schema_editor.UndoManager)                 |    |
| [`WidgetFactory`](#iot_devices.schema_editor.WidgetFactory)             |    |
| [`DefaultInput`](#iot_devices.schema_editor.DefaultInput)               |    |
| [`BoolSwitch`](#iot_devices.schema_editor.BoolSwitch)                   |    |
| [`MyTree`](#iot_devices.schema_editor.MyTree)                           |    |
| [`TreePane`](#iot_devices.schema_editor.TreePane)                       |    |
| [`InspectorPane`](#iot_devices.schema_editor.InspectorPane)             |    |
| [`TwoPaneSchemaEditor`](#iot_devices.schema_editor.TwoPaneSchemaEditor) |    |

## Module Contents

### *class* iot_devices.schema_editor.SchemaNodeSelected(sender, path: str, schema: dict, value)

Bases: `textual.message.Message`

#### bubble *= True*

#### path

#### schema

#### value

### *class* iot_devices.schema_editor.ValueChanged(sender, path: str, value)

Bases: `textual.message.Message`

#### bubble *= True*

#### path

#### value

### *class* iot_devices.schema_editor.UndoManager

#### stack *= []*

#### position *= -1*

#### push_state(state)

#### undo()

### *class* iot_devices.schema_editor.WidgetFactory

#### registry

#### *classmethod* register(format_name, widget_class)

#### *classmethod* create(schema, path, value)

### *class* iot_devices.schema_editor.DefaultInput(schema, path, value)

Bases: `textual.containers.Container`

#### schema

#### path

#### value

#### input

#### label

#### on_mount()

#### *async* on_input_blurred(event: textual.events.Blur) → None

### *class* iot_devices.schema_editor.BoolSwitch(schema, path, value)

Bases: `textual.containers.Container`

#### schema

#### path

#### value

#### label

#### switch

#### on_mount()

#### *async* on_switch_changed(event)

### *class* iot_devices.schema_editor.MyTree(title: str, pane: [TreePane](#iot_devices.schema_editor.TreePane))

Bases: `textual.widgets.Tree`[`str`]

#### pane

#### *async* on_tree_node_selected(event: textual.widgets.Tree.NodeSelected) → None

### *class* iot_devices.schema_editor.TreePane(schema: dict, data: dict)

Bases: `textual.widget.Widget`

#### schema

#### data

#### on_mount()

#### *async* on_tree_node_selected(event: [MyTree](#iot_devices.schema_editor.MyTree)) → None

### *class* iot_devices.schema_editor.InspectorPane

Bases: `textual.containers.Vertical`

#### content

#### on_mount()

#### *async* inspect(schema, path, value)

### *class* iot_devices.schema_editor.TwoPaneSchemaEditor(schema: dict, data: dict)

Bases: `textual.app.App`

#### CSS *= Multiline-String*

<details><summary>Show Value</summary>
```python
"""
    Screen {
        layout: horizontal;
    }
    TreePane {
        width: 40%;
        border: solid gray;
    }
    InspectorPane {
        width: 60%;
        border: solid gray;
    }
    """
```

</details>

#### schema

#### data

#### undo_manager

#### inspector

#### compose() → textual.app.ComposeResult

#### follow_keys(path: str, new_value=None)

#### *async* on_value_changed(message: [ValueChanged](#iot_devices.schema_editor.ValueChanged))

#### *async* on_schema_node_selected(message: [SchemaNodeSelected](#iot_devices.schema_editor.SchemaNodeSelected))

### iot_devices.schema_editor.demo_schema

### iot_devices.schema_editor.demo_data

### iot_devices.schema_editor.app
