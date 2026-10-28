"""Shared test host that records errors and prints."""

from __future__ import annotations

from typing import Any

from iot_devices.host.simple_host import SimpleHost


class RecordingHost(SimpleHost):
    """A host that records errors and prints so tests can assert on them."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []
        self.prints: list[tuple[str, str]] = []

    def on_device_error(self, device: Any, error: str) -> None:
        self.errors.append(error)

    def on_device_print(
        self, device: Any, message: str, title: str = ""
    ) -> None:
        self.prints.append((message, title))
