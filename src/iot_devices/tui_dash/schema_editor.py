"""A lightweight JSON-schema based form editor.

This module provides the :class:`SchemaForm` widget, a form editor driven
by a (subset of a) JSON schema.  It supports the basic scalar types,
enums, nested objects and arrays, and offers text suggestions for string
inputs from the schema's ``examples`` property.

The form mutates a deep copy of the data passed in, so callers can show
the form, validate the result against the schema, and only commit the new
data when the user saves.
"""

from __future__ import annotations

import copy
from collections.abc import Awaitable, Callable
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import (
    Button,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    Switch,
)

Path = tuple[str | int, ...]
"""A path to a value in the form data.

Tuples are used rather than dotted strings so that config keys which
themselves contain dots stay unambiguous.
"""


class CallbackButton(Button):
    """A Button that runs a callback when pressed.

    The callback is a closure created at compose time, so any per-button
    data (keys, indices) is captured at creation rather than stored on
    the button instance. This avoids the late-binding problem of loop
    variables shared across buttons.
    """

    def __init__(
        self,
        label: Any,
        callback: Callable[[], Awaitable[None] | None],
        *,
        classes: str | None = None,
    ) -> None:
        super().__init__(label, classes=classes)
        self._callback = callback

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        # Stop propagation: the callback fully owns the button's action.
        event.stop()
        result = self._callback()
        if result is not None:
            await result


def _key_to_title(key: str) -> str:
    """Make a human readable title out of a config key."""
    return key.replace(".", " / ").replace("_", " ").title()


def _default_for(schema: dict[str, Any]) -> Any:
    """Return a sensible empty/default value for a schema node."""
    if "default" in schema:
        return copy.deepcopy(schema["default"])
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        return {}
    if t == "array":
        return []
    if t == "boolean":
        return False
    if t in ("integer", "number"):
        return 0
    return ""


class SchemaForm(Widget):
    """Holds a JSON schema and a mutable deep copy of the data being edited.

    All editors update ``form.data`` in place through this class, so after
    the user is done, ``form.data`` contains the edited result. The
    ``dirty`` flag reports whether anything was changed.
    """

    DEFAULT_CSS = """
    SchemaForm {
        height: auto;
        layout: vertical;
    }
    """

    def __init__(
        self,
        schema: dict[str, Any],
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.schema = copy.deepcopy(schema)
        self.data: dict[str, Any] = copy.deepcopy(data) if data else {}
        self.dirty = False

    def compose(self) -> ComposeResult:
        yield ObjectEditor(self, (), self.schema, self.data)

    # --- Data access/mutation API used by the editors ---

    def get_value(self, path: Path) -> Any:
        """Get the value at path, or None if it does not exist."""
        cur: Any = self.data
        for k in path:
            if isinstance(cur, list) and isinstance(k, int):
                try:
                    cur = cur[k]
                except IndexError:
                    return None
            elif isinstance(cur, dict):
                cur = cur.get(k)
            else:
                return None
        return cur

    def set_value(self, path: Path, value: Any) -> None:
        """Set the value at path. A value of None deletes the key."""
        if value is None:
            self.delete_value(path)
            return
        if not path:
            return
        parent = self.get_value(path[:-1])
        k = path[-1]
        if isinstance(parent, dict) and isinstance(k, str):
            parent[k] = value
        elif isinstance(parent, list) and isinstance(k, int):
            try:
                parent[k] = value
            except IndexError:
                pass
        self.dirty = True

    def delete_value(self, path: Path) -> None:
        """Delete the key or list index at path."""
        if not path:
            return
        parent = self.get_value(path[:-1])
        k = path[-1]
        try:
            if isinstance(parent, dict) and isinstance(k, str):
                parent.pop(k, None)
            elif isinstance(parent, list) and isinstance(k, int):
                parent.pop(k)
        except IndexError:
            pass
        self.dirty = True

    def append_value(self, path: Path, value: Any) -> None:
        """Append value to the list at path."""
        cur = self.get_value(path)
        if isinstance(cur, list):
            cur.append(value)
            self.dirty = True

    def ensure_object(self, path: Path) -> dict[str, Any]:
        """Make sure a dict exists at path, creating one if needed."""
        cur = self.get_value(path)
        if not isinstance(cur, dict):
            cur = {}
            self.set_value(path, cur)
        return cur

    def ensure_array(self, path: Path) -> list[Any]:
        """Make sure a list exists at path, creating one if needed."""
        cur = self.get_value(path)
        if not isinstance(cur, list):
            cur = []
            self.set_value(path, cur)
        return cur


class BaseEditor(Widget):
    """Base class for editors that are bound to a single path."""

    DEFAULT_CSS = """
    BaseEditor {
        height: auto;
        width: 1fr;
    }
    """

    def __init__(
        self,
        form: SchemaForm,
        path: Path,
        schema: dict[str, Any],
        value: Any,
    ) -> None:
        super().__init__()
        self.form = form
        self.path = path
        self.schema = schema
        self.value = value

    def _emit(self, value: Any) -> None:
        """Write the new value into the form data."""
        self.form.set_value(self.path, value)


class StringEditor(BaseEditor):
    """Plain text input for strings."""

    DEFAULT_CSS = """
    StringEditor {
        height: auto;
        width: 1fr;
    }
    StringEditor Input {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Input(value=self.value if isinstance(self.value, str) else "")

    @on(Input.Changed)
    def _changed(self, event: Input.Changed) -> None:
        self._emit(event.value or None)


class NumberEditor(BaseEditor):
    """Text input for numbers."""

    DEFAULT_CSS = """
    NumberEditor {
        height: auto;
        width: 1fr;
    }
    NumberEditor Input {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Input(
            value="" if self.value is None else str(self.value),
            # Textual Input only accepts 'integer', 'number' or 'text'.
            type="integer"
            if self.schema.get("type") == "integer"
            else "number",
        )

    @on(Input.Changed)
    def _changed(self, event: Input.Changed) -> None:
        v = event.value
        if not v:
            self._emit(None)
            return
        try:
            if self.schema.get("type") == "integer":
                self._emit(int(v))
            else:
                self._emit(float(v))
        except ValueError:
            # Invalid partial input: keep whatever value was there before.
            pass


class BooleanEditor(BaseEditor):
    """Switch for booleans."""

    DEFAULT_CSS = """
    BooleanEditor {
        height: auto;
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Switch(value=bool(self.value))

    @on(Switch.Changed)
    def _changed(self, event: Switch.Changed) -> None:
        self._emit(event.value)


class EnumEditor(BaseEditor):
    """Dropdown for enum values."""

    DEFAULT_CSS = """
    EnumEditor {
        height: auto;
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        opts = self.schema.get("enum", [])
        yield Select(
            [(str(o), o) for o in opts],
            allow_blank=True,
            value=self.value if self.value in opts else Select.BLANK,
        )

    @on(Select.Changed)
    def _changed(self, event: Select.Changed) -> None:
        if event.value == Select.BLANK:
            self._emit(None)
        else:
            self._emit(event.value)


class SuggestInput(Widget):
    """A text input with a dropdown of suggestions.

    Used to implement the schema ``examples`` property: as the user types,
    matching examples are shown in a dropdown below the input.
    """

    DEFAULT_CSS = """
    SuggestInput {
        height: auto;
        layout: vertical;
        width: 1fr;
    }
    SuggestInput Input {
        width: 1fr;
    }
    SuggestInput .suggest-list {
        display: none;
        position: absolute;
        offset-y: 3;
        width: 100%;
        height: auto;
        max-height: 6;
        layer: overlay;
        background: $surface;
        border: round $accent;
    }
    SuggestInput.open .suggest-list {
        display: block;
    }
    """

    def __init__(self, editor: BaseEditor) -> None:
        super().__init__()
        self.editor = editor
        self.examples = [
            str(e) for e in editor.schema.get("examples", []) if e is not None
        ]
        self._input = Input(
            value=editor.value if isinstance(editor.value, str) else ""
        )
        self._dropdown = OptionList(*self.examples, classes="suggest-list")
        # Input posts a Changed message for the value set at construction
        # (when non-empty), which must not open the dropdown.
        self._constructed_value = self._input.value
        self._seen_user_edit = False
        self._suppress_next_changed = False

    def compose(self) -> ComposeResult:
        yield self._input
        yield self._dropdown

    @on(Input.Changed)
    def _input_changed(self, event: Input.Changed) -> None:
        q = event.value
        if self._suppress_next_changed:
            # The Changed posted for the programmatic value assignment made
            # when a suggestion is chosen; do not re-open the dropdown.
            self._suppress_next_changed = False
            return
        if q == self._constructed_value and not self._seen_user_edit:
            # This is the Changed posted for the value set at construction.
            return
        self._seen_user_edit = True
        if q:
            ql = q.lower()
            matches = [e for e in self.examples if ql in e.lower()]
            if matches:
                self._dropdown.clear_options()
                self._dropdown.add_options(matches)
                self.add_class("open")
            else:
                self.remove_class("open")
        else:
            self.remove_class("open")
        self.editor._emit(q or None)

    @on(OptionList.OptionSelected)
    def _selected(self, event: OptionList.OptionSelected) -> None:
        value = str(
            self._dropdown.get_option_at_index(event.option_index).prompt
        )
        # Assigning the value programmatically makes Input post a Changed
        # message; suppress it so the dropdown does not re-open.
        self._suppress_next_changed = True
        self._input.value = value
        self.remove_class("open")
        self.editor._emit(value)


class SuggestEditor(BaseEditor):
    """String editor with suggestions from the schema examples property."""

    DEFAULT_CSS = """
    SuggestEditor {
        height: auto;
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield SuggestInput(self)


class ObjectEditor(Widget):
    """Recursive editor for object schemas."""

    DEFAULT_CSS = """
    ObjectEditor {
        height: auto;
        width: 1fr;
        layout: vertical;
    }
    ObjectEditor ObjectEditor,
    ObjectEditor ArrayEditor,
    ArrayEditor ObjectEditor,
    ArrayEditor ArrayEditor {
        margin-left: 2;
        padding-left: 1;
        border-left: heavy $accent;
    }
    ObjectEditor .prop-row {
        height: auto;
    }
    ObjectEditor .prop-label {
        width: auto;
        max-width: 30;
        padding-top: 1;
        margin-right: 1;
    }
    ObjectEditor .prop-readonly {
        width: 1fr;
        padding-top: 1;
        color: $text-muted;
    }
    ObjectEditor .container-label {
        width: 100%;
        padding-top: 1;
        text-style: bold;
    }
    ObjectEditor .remove-key {
        width: auto;
    }
    ObjectEditor .add-key-input {
        width: 1fr;
    }
    """

    def __init__(
        self,
        form: SchemaForm,
        path: Path,
        schema: dict[str, Any],
        value: Any = None,
    ) -> None:
        super().__init__()
        self.form = form
        self.path = path
        self.schema = schema
        if path:
            # Make sure the dict this editor edits actually exists.
            self.form.ensure_object(path)

    @staticmethod
    def _ordered(props: dict[str, Any]) -> list[str]:
        keys = list(props.keys())

        def order(k: str) -> float:
            ps = props.get(k)
            if isinstance(ps, dict):
                po = ps.get("propertyOrder")
                if isinstance(po, (int, float)):
                    return float(po)
            return 0.0

        return sorted(keys, key=order)

    def compose(self) -> ComposeResult:
        value = self.form.get_value(self.path)
        if not isinstance(value, dict):
            value = {}
        props = self.schema.get("properties", {})
        for key in self._ordered(props):
            ps = props[key]
            if not isinstance(ps, dict):
                continue
            ppath = self.path + (key,)
            title = ps.get("title") or _key_to_title(key)
            lbl = Label(title, classes="prop-label")
            if ps.get("description"):
                lbl.tooltip = ps["description"]
            if ps.get("readOnly"):
                v = value.get(key)
                yield Horizontal(
                    lbl,
                    Static(
                        "—" if v is None else repr(v), classes="prop-readonly"
                    ),
                    classes="prop-row",
                )
                continue
            t = ps.get("type")
            if t == "object" or "properties" in ps or t == "array":
                yield Label(title, classes="container-label")
                yield make_editor(self.form, ppath, ps, value.get(key))
            else:
                with Horizontal(classes="prop-row"):
                    yield lbl
                    yield make_editor(self.form, ppath, ps, value.get(key))

        ap = self.schema.get("additionalProperties")
        if ap is True or isinstance(ap, dict):
            for key in [k for k in value.keys() if k not in props]:
                aps = ap if isinstance(ap, dict) else {}
                with Horizontal(classes="prop-row"):
                    yield Label(key, classes="prop-label")
                    yield make_editor(
                        self.form, self.path + (key,), aps, value.get(key)
                    )
                    # Callback captures this row's key at creation time,
                    # avoiding loop-scope late binding.
                    yield CallbackButton(
                        "✕",
                        classes="remove-key",
                        callback=self._make_remove_key_cb(key),
                    )
            with Horizontal(classes="prop-row"):
                self._add_key_input = Input(
                    placeholder="New key", classes="add-key-input"
                )
                yield self._add_key_input
                b = CallbackButton(
                    "+ Add key",
                    classes="add-key-btn",
                    callback=self._make_add_key_cb(),
                )
                yield b

    async def refresh_rows(self) -> None:
        """Rebuild the rows after a structural change."""
        # Fire-and-forget: awaiting remove_children() here deadlocks the
        # message pump when the button triggering this callback is nested
        # inside a container being pruned (circular pump-task wait).
        self.remove_children()
        await self.mount_compose(self.compose())

    def _make_remove_key_cb(self, key: str) -> Callable[[], Awaitable[None]]:
        """Build a closure capturing this row's key at creation time."""

        async def cb() -> None:
            self.form.delete_value(self.path + (key,))
            await self.refresh_rows()

        return cb

    def _make_add_key_cb(self) -> Callable[[], Awaitable[None]]:
        """Build a closure for the add-key button."""

        async def cb() -> None:
            key = self._add_key_input.value.strip()
            props = self.schema.get("properties", {})
            cur = self.form.get_value(self.path)
            if (
                not key
                or key in props
                or (isinstance(cur, dict) and key in cur)
            ):
                return
            aps = self.schema.get("additionalProperties")
            aps = aps if isinstance(aps, dict) else {}
            self.form.set_value(self.path + (key,), _default_for(aps))
            await self.refresh_rows()

        return cb


class ArrayEditor(Widget):
    """Editor for arrays."""

    DEFAULT_CSS = """
    ArrayEditor {
        height: auto;
        width: 1fr;
        layout: vertical;
    }
    ArrayEditor .array-row {
        height: auto;
    }
    ArrayEditor .array-remove,
    ArrayEditor .array-add {
        width: auto;
    }
    """

    def __init__(
        self,
        form: SchemaForm,
        path: Path,
        schema: dict[str, Any],
        value: Any = None,
    ) -> None:
        super().__init__()
        self.form = form
        self.path = path
        self.schema = schema
        if path:
            # Make sure the list this editor edits actually exists.
            self.form.ensure_array(path)

    def compose(self) -> ComposeResult:
        value = self.form.get_value(self.path)
        if not isinstance(value, list):
            value = []
        items = self.schema.get("items") or {}
        for i, item in enumerate(value):
            with Horizontal(classes="array-row"):
                yield make_editor(self.form, self.path + (i,), items, item)
                # Callback captures this row's index at creation time,
                # avoiding loop-scope late binding.
                yield CallbackButton(
                    "✕",
                    classes="array-remove",
                    callback=self._make_remove_item_cb(i),
                )
        yield CallbackButton(
            "+ Add item",
            classes="array-add",
            callback=self._make_add_item_cb(),
        )

    async def refresh_rows(self) -> None:
        # Fire-and-forget: awaiting remove_children() here deadlocks the
        # message pump when the button triggering this callback is nested
        # inside a container being pruned (circular pump-task wait).
        self.remove_children()
        await self.mount_compose(self.compose())

    def _make_remove_item_cb(self, index: int) -> Callable[[], Awaitable[None]]:
        """Build a closure capturing this row's index at creation time."""

        async def cb() -> None:
            self.form.delete_value(self.path + (index,))
            await self.refresh_rows()

        return cb

    def _make_add_item_cb(self) -> Callable[[], Awaitable[None]]:
        """Build a closure for the add-item button."""

        async def cb() -> None:
            self.form.append_value(
                self.path, _default_for(self.schema.get("items") or {})
            )
            await self.refresh_rows()

        return cb


def make_editor(
    form: SchemaForm, path: Path, schema: dict[str, Any], value: Any
) -> Widget:
    """Create the right editor widget for a schema node."""
    if "enum" in schema:
        return EnumEditor(form, path, schema, value)
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        return ObjectEditor(form, path, schema, value)
    if t == "array":
        return ArrayEditor(form, path, schema, value)
    if t == "boolean":
        return BooleanEditor(form, path, schema, value)
    if t in ("integer", "number"):
        return NumberEditor(form, path, schema, value)
    if schema.get("examples"):
        return SuggestEditor(form, path, schema, value)
    return StringEditor(form, path, schema, value)
