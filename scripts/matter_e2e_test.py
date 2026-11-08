"""End-to-end test of the Matter devices against real docker containers.

Unlike the unit tests, which stub out the matter server client, this
script runs the real stack:

- The production js matter server (matterjs-server) is started by
  docker compose on a non-default port.
- A small node:22-slim container built from ``e2e/matter/devices``
  runs three fake matter.js devices (on/off, dimmable and extended
  color lights).  They only open their commissioning windows when the
  ``--commissionable`` flag is passed, and they mirror their current
  attribute values to JSON files that are bind mounted out of the
  container so the host side can inspect what the devices really hold.

The test then commissions the devices through the
MatterControllerClient device, reads and writes every kind of
datapoint, stops (but does not delete) the devices container to check
that unavailability is detected and that writes while unavailable fail
gracefully instead of crashing, starts the container again to check
that everything recovers, and finally tears the containers down.

Docker and docker compose are required.  Run via ``make
test-matter-e2e``.  The rig's storage lives under ``e2e/matter/run/``
and is recreated on every run.
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

COMPOSE_DIR = REPO_ROOT / "e2e" / "matter"
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.yml"
RUN_DIR = COMPOSE_DIR / "run"

SERVER_WS_URL = "ws://127.0.0.1:5581/ws"
"""The non-default port the rig runs the js matter server on."""

SERVER_PORT = 5581

# Must match e2e/matter/devices/fake_devices.mjs.
FAKE_DEVICES: dict[str, dict[str, Any]] = {
    "onoff": {"label": "E2E OnOff Light", "pin": "20202021"},
    "dimmable": {"label": "E2E Dimmable Light", "pin": "20202022"},
    "color": {"label": "E2E Color Light", "pin": "20202023"},
}

COMMISSION_TIMEOUT = 120.0
"""Seconds to wait for one device to be discovered after commissioning."""

AVAILABILITY_TIMEOUT = 150.0
"""Seconds to wait for the server to notice the container going away."""


def _run(cmd: list[str], **kw: Any) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{shlex.join(cmd)} failed: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def wait_until(
    predicate: Callable[[], bool],
    timeout: float,
    description: str,
) -> None:
    """Poll a predicate until it passes, or fail the test."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.25)
    raise AssertionError(
        f"Timed out after {timeout}s waiting for {description}"
    )


@dataclass
class Rig:
    """The docker compose rig and the handles needed to drive it."""

    def state_path(self, kind: str) -> Path:
        """Path of the fake device's mirrored attribute JSON file."""
        return RUN_DIR / "devices-data" / f"state-{kind}.json"

    def read_state(self, kind: str) -> dict[str, Any]:
        """Read the current mirrored state of a fake device."""
        return json.loads(self.state_path(kind).read_text())

    def _compose(self, *args: str) -> str:
        # The devices container runs as this uid so the bind mounted
        # state files stay owned by the invoking user.
        env = {
            **os.environ,
            "E2E_UID": str(os.getuid()),
            "E2E_GID": str(os.getgid()),
        }
        proc = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
            capture_output=True,
            text=True,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"docker compose {' '.join(args)} failed: "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        return proc.stdout.strip()

    def start(self) -> None:
        """(Re)create the rig from scratch and wait for it to come up."""
        # Get rid of any leftovers from an earlier or crashed run
        # before the bind mount targets are recreated.
        self.teardown_quiet()
        if RUN_DIR.exists():
            shutil.rmtree(RUN_DIR)
        (RUN_DIR / "devices-data").mkdir(parents=True)
        (RUN_DIR / "devices-storage").mkdir()

        self._compose("up", "-d", "--build")

        wait_until(
            lambda: self._port_open(),
            60,
            "the matter server to accept connections",
        )
        # A TCP port can be open before the server's HTTP stack is
        # actually serving, which would make the first websocket
        # connection fail. Wait for a real HTTP response instead.
        wait_until(
            lambda: self._http_responding(),
            60,
            "the matter server to respond to HTTP requests",
        )
        wait_until(
            lambda: all(
                self.state_path(kind).exists() for kind in FAKE_DEVICES
            ),
            60,
            "the fake devices to write their state files",
        )

    def _port_open(self) -> bool:
        with socket.socket() as sock:
            sock.settimeout(1)
            try:
                sock.connect(("127.0.0.1", SERVER_PORT))
            except OSError:
                return False
        return True

    def _http_responding(self) -> bool:
        """True once the server answers an HTTP request at all."""
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{SERVER_PORT}/health", timeout=2
            ) as resp:
                return resp.status == 200
        except urllib.error.HTTPError:
            return True
        except OSError:
            return False

    def stop_devices(self) -> None:
        """Stop the devices container, but do not delete it."""
        self._compose("stop", "devices")

    def start_devices(self) -> None:
        """Start the previously stopped devices container again."""
        self._compose("start", "devices")

    def teardown(self) -> None:
        """Tear the containers down, removing any volumes."""
        try:
            self._compose("down", "-v", "--remove-orphans", "--timeout", "30")
        except Exception as ex:
            print(f"WARNING: compose down failed: {ex}")

    def teardown_quiet(self) -> None:
        """Like teardown, but fully silent; used to pre-clean."""
        with contextlib.suppress(Exception):
            self._compose("down", "-v", "--remove-orphans", "--timeout", "30")


def setup_rig() -> Rig:
    """Build and start the containers."""
    print("Building and starting the docker compose rig...")
    rig = Rig()
    rig.start()
    return rig


def teardown_rig(rig: Rig) -> None:
    print("Tearing down the docker compose rig...")
    rig.teardown()


# ---------------------------------------------------------------------------
# The actual tests
# ---------------------------------------------------------------------------

from iot_devices.devices.Matter import (  # noqa: E402
    MatterControllerClient,
)
from tests.recording_host import RecordingHost  # noqa: E402


def start_controller() -> tuple[RecordingHost, MatterControllerClient]:
    """Add a controller device and wait for it to be connected."""
    host = RecordingHost()
    controller = host.add_new_device(
        {
            "type": "MatterControllerClient",
            "name": "controller",
            "server_url": SERVER_WS_URL,
        }
    ).wait_device_ready()
    wait_until(
        lambda: controller.datapoints["connected"].get()[0] == 1,
        60,
        "the controller to connect to the matter server",
    )
    return host, controller


def wait_for_node(
    controller: MatterControllerClient,
    label: str,
    timeout: float,
    known: set[int],
) -> tuple[int, Any]:
    """Wait for a device with the given node label to be discovered.

    Subdevice names fall back to node ids, so nodes are matched through
    their BasicInformation nodeLabel instead.
    """
    wait_until(
        lambda: _find_node(controller, label, known) is not None,
        timeout,
        f"the {label} device to be discovered",
    )
    node_id = _find_node(controller, label, known)
    assert node_id is not None
    known.add(node_id)
    return node_id, controller.devices_by_node_id[node_id]


def _find_node(
    controller: MatterControllerClient,
    label: str,
    known: set[int],
) -> int | None:
    for node_id, node in controller.nodes_by_id.items():
        if node_id in known:
            continue
        info = getattr(node, "device_info", None)
        node_label = getattr(info, "nodeLabel", None)
        # The raw node object is registered before the subdevice is
        # fully created, so wait for the subdevice too.
        if node_label == label and node_id in controller.devices_by_node_id:
            return node_id
    return None


def commission(
    controller: MatterControllerClient,
    kind: str,
    known: set[int],
) -> Any:
    """Commission one fake device and return its MatterDevice."""
    spec = FAKE_DEVICES[kind]
    controller.set_data_point(
        "admin.on_network_commission_with_pin", spec["pin"]
    )
    _, device = wait_for_node(
        controller, spec["label"], COMMISSION_TIMEOUT, known
    )
    return device


def wait_for_availability(
    devices: dict[str, Any],
    expected: int,
    timeout: float,
) -> None:
    """Wait until every device's available datapoint equals expected."""
    wait_until(
        lambda: all(
            dev.datapoints["available"].get()[0] == expected
            for dev in devices.values()
        ),
        timeout,
        f"all devices to report available={expected}",
    )


def wait_for_state(
    rig: Rig,
    kind: str,
    key: str,
    expected: Any,
    timeout: float = 15.0,
) -> None:
    """Wait for a fake device's mirrored JSON state to hold a value."""
    wait_until(
        lambda: rig.read_state(kind).get(key) == expected,
        timeout,
        f"the {kind} device state to have {key}={expected}",
    )


def get_devices(
    controller: MatterControllerClient, known: set[int]
) -> dict[str, Any]:
    """Wait for all three fake devices and return them by kind."""
    devices = {}
    for kind, spec in FAKE_DEVICES.items():
        _, dev = wait_for_node(
            controller, spec["label"], COMMISSION_TIMEOUT, known
        )
        devices[kind] = dev
    return devices


def test_commission_and_read(rig: Rig) -> None:
    """Commissioning creates subdevices that read the initial state."""
    host, controller = start_controller()
    try:
        known: set[int] = set()
        onoff = commission(controller, "onoff", known)
        dimmable = commission(controller, "dimmable", known)
        color = commission(controller, "color", known)

        for dev in (onoff, dimmable, color):
            assert (
                dev.datapoints["available"].get()[0] == 1
            ), f"{dev.name} is not available after commissioning"

        # The devices start with the values their config sets.
        assert onoff.datapoints["on_1"].get()[0] == 0, onoff.datapoints[
            "on_1"
        ].get()[0]
        assert (
            dimmable.datapoints["level_1"].get()[0] == 128
        ), dimmable.datapoints["level_1"].get()[0]
        assert color.datapoints["hue_1"].get()[0] == 0, color.datapoints[
            "hue_1"
        ].get()[0]
        assert color.datapoints["saturation_1"].get()[0] == 0, color.datapoints[
            "saturation_1"
        ].get()[0]

        # The datapoints agree with what the devices actually hold.
        state = rig.read_state("onoff")
        assert state["onOff"] is False, state
        state = rig.read_state("dimmable")
        assert state["currentLevel"] == 128, state
        state = rig.read_state("color")
        assert state["currentHue"] == 0, state
        assert state["currentSaturation"] == 0, state

        assert not host.errors, host.errors
    finally:
        host.close()


def test_write_all_kinds(rig: Rig) -> None:
    """Writes reach the devices and are mirrored to the state files."""
    host, controller = start_controller()
    try:
        devices = get_devices(controller, set())

        devices["onoff"].set_data_point("on_1", 1)
        wait_for_state(rig, "onoff", "onOff", True)
        assert devices["onoff"].datapoints["on_1"].get()[0] == 1

        # Level and hue/saturation moves only apply while the light is
        # on, so the dimmable and color devices are turned on first.
        devices["dimmable"].set_data_point("on_1", 1)
        wait_for_state(rig, "dimmable", "onOff", True)
        devices["dimmable"].set_data_point("level_1", 200)
        wait_for_state(rig, "dimmable", "currentLevel", 200)
        assert devices["dimmable"].datapoints["level_1"].get()[0] == 200

        devices["color"].set_data_point("on_1", 1)
        wait_for_state(rig, "color", "onOff", True)
        devices["color"].set_data_point("hue_1", 100)
        devices["color"].set_data_point("saturation_1", 150)
        wait_for_state(rig, "color", "currentHue", 100)
        wait_for_state(rig, "color", "currentSaturation", 150)
        assert devices["color"].datapoints["hue_1"].get()[0] == 100
        assert devices["color"].datapoints["saturation_1"].get()[0] == 150

        # And back again, to make sure writes are repeatable.
        devices["onoff"].set_data_point("on_1", 0)
        wait_for_state(rig, "onoff", "onOff", False)

        assert not host.errors, host.errors
    finally:
        host.close()


def test_unavailable_detection_and_graceful_write(rig: Rig) -> None:
    """Stopping the container is detected; writes fail gracefully."""
    host, controller = start_controller()
    try:
        devices = get_devices(controller, set())
        wait_for_availability(devices, 1, 30)

        rig.stop_devices()
        wait_for_availability(devices, 0, AVAILABILITY_TIMEOUT)

        # The server itself is still reachable.
        assert controller.datapoints["connected"].get()[0] == 1

        # A write to an unavailable device must fail gracefully: it
        # must not hang the calling thread, raise out of the device,
        # or otherwise take the host down.
        started = time.monotonic()
        devices["onoff"].set_data_point("on_1", 1)
        assert time.monotonic() - started < 5, "the write blocked"

        # Give the command time to fail inside the controller loop.
        # The server can take around 90s to give up on the unreachable
        # node, so poll instead of sleeping a fixed time.
        wait_until(
            lambda: host.errors,
            150,
            "the failed write to be reported as an error",
        )
        assert controller.datapoints["connected"].get()[0] == 1
        assert controller.devices_by_node_id, "the controller crashed"
        assert "on_1" in devices["onoff"].datapoints

        # Nothing was written, so the device state is unchanged.
        assert rig.read_state("onoff")["onOff"] is False

        # The failures are reported as device errors, not crashes.
        assert (
            host.errors
        ), "the failed write should have been reported as an error"
    finally:
        host.close()


def test_reconnect_and_write(rig: Rig) -> None:
    """Restarting the container restores reads and writes."""
    host, controller = start_controller()
    try:
        devices = get_devices(controller, set())

        rig.start_devices()
        wait_for_availability(devices, 1, AVAILABILITY_TIMEOUT)

        # Reads still work.
        assert devices["dimmable"].datapoints["level_1"].get()[0] == 200
        assert devices["color"].datapoints["hue_1"].get()[0] == 100

        # Writes still work too.
        devices["onoff"].set_data_point("on_1", 1)
        wait_for_state(rig, "onoff", "onOff", True)
        devices["onoff"].set_data_point("on_1", 0)
        wait_for_state(rig, "onoff", "onOff", False)

        assert not host.errors, host.errors
    finally:
        host.close()


TESTS: list[tuple[str, Callable[[Rig], None]]] = [
    ("commission: devices pair and read back", test_commission_and_read),
    ("write: all device kinds", test_write_all_kinds),
    (
        "disconnect: unavailable detection and graceful write",
        test_unavailable_detection_and_graceful_write,
    ),
    ("reconnect: reads and writes recover", test_reconnect_and_write),
]


def run_tests(rig: Rig) -> int:
    """Run all tests in order, collecting results."""
    failures = 0
    for name, test in TESTS:
        print(f"[ RUN  ] {name}")
        try:
            test(rig)
        except Exception as ex:
            failures += 1
            traceback.print_exc()
            print(f"[ FAIL ] {name}: {ex}")
        else:
            print(f"[ PASS ] {name}")
    return failures


def main() -> int:
    rig: Rig | None = None
    try:
        rig = setup_rig()
        failures = run_tests(rig)
        if failures:
            print(f"\nMatter E2E: {failures} test(s) FAILED")
            print(f"The rig state was left under {RUN_DIR} for debugging")
            return 1
        print(f"\nMatter E2E: all {len(TESTS)} tests passed")
        return 0
    finally:
        if rig is not None:
            teardown_rig(rig)


if __name__ == "__main__":
    sys.exit(main())
