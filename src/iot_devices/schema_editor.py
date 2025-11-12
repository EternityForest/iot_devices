from __future__ import annotations
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widget import Widget
from textual.widgets import Tree, Static, Input, Select, Switch, Button
from textual.message import Message
from textual import events
import copy


# -----------------------------
# Events
# -----------------------------


class SchemaNodeSelected(Message):
    bubble = True

    def __init__(self, sender, path: str, schema: dict, value):
        self.path = path
        self.schema = schema
        self.value = value
        super().__init__()


class ValueChanged(Message):
    bubble = True

    def __init__(self, sender, path: str, value):
        self.path = path
        self.value = value
        super().__init__()


# -----------------------------
# Undo Manager
# -----------------------------


class UndoManager:
    def __init__(self):
        self.stack = []
        self.position = -1

    def push_state(self, state):
        self.stack = self.stack[: self.position + 1]
        self.stack.append(copy.deepcopy(state))
        self.position += 1

    def undo(self):
        if self.position > 0:
            self.position -= 1
            return copy.deepcopy(self.stack[self.position])
        return None


# -----------------------------
# Widget Factory
# -----------------------------


class WidgetFactory:
    registry = {}

    @classmethod
    def register(cls, format_name, widget_class):
        cls.registry[format_name] = widget_class

    @classmethod
    def create(cls, schema, path, value):
        fmt = schema.get("type") or schema.get("format")
        widget_cls = cls.registry.get(fmt, DefaultInput)
        return widget_cls(schema, path, value)


# Example basic widgets


class DefaultInput(Container):
    def __init__(self, schema, path, value):
        super().__init__()
        self.schema = schema
        self.path = path
        self.value = value
        self.input = Input(value=str(value or ""))
        self.label = Static(schema.get("title", path))
        self.input.on_input_blurred = self.on_input_blurred

    def on_mount(self):
        self.mount(self.label)
        self.mount(self.input)

    async def on_input_blurred(self, event: events.Blur) -> None:
        self.post_message(ValueChanged(self, self.path, self.input.value))


class BoolSwitch(Container):
    def __init__(self, schema, path, value):
        super().__init__()
        self.schema = schema
        self.path = path
        self.value = value
        self.label = Static(schema.get("title", path))
        self.switch = Switch(value=bool(value))

    def on_mount(self):
        self.mount(self.label)
        self.mount(self.switch)

    async def on_switch_changed(self, event):
        self.post_message(ValueChanged(self, self.path, self.switch.value))


WidgetFactory.register("boolean", BoolSwitch)


# -----------------------------
# Tree Pane
# -----------------------------


class MyTree(Tree[str]):
    def __init__(self, title: str, pane: TreePane):
        self.pane = pane
        super().__init__(title)

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        await self.pane.on_tree_node_selected(event)


class TreePane(Widget):
    def __init__(self, schema: dict, data: dict):
        super().__init__()
        self.schema = schema
        self.data = data

    def on_mount(self):
        self.treee = MyTree("Config", self)
        self.mount(self.treee)

        self._populate_tree("", self.treee.root, self.schema, self.data)

    def _populate_tree(self, path, node, schema, value):
        if schema.get("type") == "object":
            for k, v in schema.get("properties", {}).items():
                child_path = f"{path}.{k}" if path else k
                child_node = node.add(k)
                child_node.data = child_path
                self._populate_tree(child_path, child_node, v, value.get(k))

        elif schema.get("type") == "array":
            for i, item in enumerate(value or []):
                child_path = f"{path}.i"
                child_node = node.add(f"[{i}]")
                child_node.data = child_path
                self._populate_tree(child_path, child_node, schema["items"], item)

    async def on_tree_node_selected(self, event: MyTree.NodeSelected) -> None:
        path = event.node.data
        if path is None:
            return
        # In a full implementation, you'd map this back to schema/value
        self.post_message(SchemaNodeSelected(self, path, {}, None))


# -----------------------------
# Inspector Pane
# -----------------------------


class InspectorPane(Vertical):
    def __init__(self):
        super().__init__()
        self.content = Static("Select a node to inspect")

    def on_mount(self):
        self.mount(self.content)

    async def inspect(self, schema, path, value):
        self.remove_children()
        widget = WidgetFactory.create(schema, path, value)
        self.mount(widget)


# -----------------------------
# Main Two-Pane Editor
# -----------------------------


class TwoPaneSchemaEditor(App):
    CSS = """
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

    def __init__(self, schema: dict, data: dict):
        super().__init__()
        self.schema = schema
        self.data = data
        self.undo_manager = UndoManager()
        self.inspector = InspectorPane()

    def compose(self) -> ComposeResult:
        yield TreePane(self.schema, self.data)
        yield self.inspector

    def follow_keys(self, path: str, new_value=None):
        root = self.data

        p = path.split(".")
        last = p.pop()
        for key in p:
            try:
                key = int(key)
            except ValueError:
                pass
            if key not in root:
                root[key] = {}
            root = root[key]
        if new_value is not None:
            root[last] = new_value
        return root[last]

    async def on_value_changed(self, message: ValueChanged):
        # Store previous state
        self.undo_manager.push_state(self.data)
        # Apply change (simplified: replace at top level)

        self.follow_keys(message.path, message.value)
        self.refresh()

    async def on_schema_node_selected(self, message: SchemaNodeSelected):
        schema = message.schema or {"type": "string", "title": message.path}

        await self.inspector.inspect(
            schema, message.path, self.follow_keys(message.path)
        )


# -----------------------------
# Demo Schema & Run
# -----------------------------

demo_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "title": "Device Name"},
        "enabled": {"type": "boolean", "title": "Enabled"},
        "settings": {
            "type": "object",
            "properties": {
                "interval": {"type": "number", "title": "Update Interval"},
                "color": {"type": "string", "format": "color"},
            },
        },
    },
}

demo_data = {
    "name": "Sensor A",
    "enabled": True,
    "settings": {"interval": 5, "color": "#ffaa00"},
}

if __name__ == "__main__":
    app = TwoPaneSchemaEditor(demo_schema, demo_data)
    app.run()
