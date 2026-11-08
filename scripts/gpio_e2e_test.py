"""End-to-end test of the GPIO devices against a kernel gpio-sim chip.

Unlike :mod:`tests.test_gpio`, which runs against the in-process gpiod
mock, this script exercises the real kernel GPIO character device path:
a fake chip is created with the ``gpio-sim`` kernel module, the devices
talk to it through libgpiod exactly as they would talk to real hardware,
and this script plays the role of the outside world through the chip's
sysfs interface (``value`` readback and ``pull`` writes).

``gpio-sim`` is used instead of the older ``gpio-mockup`` because Ubuntu
kernels stopped shipping the latter; ``gpio-sim`` is its successor and
provides the same capabilities.

Root is required to load the module and to write configfs/sysfs, so the
script re-executes itself under sudo on first run.  The simulated chip
is torn down again at the end, even on failure.  Run via
``make test-gpio-e2e``.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SIM_DEVICE_NAME = "iot-devices-e2e"
"""Name of the gpio-sim configfs device this script creates."""

CONFIGFS_ROOT = Path("/sys/kernel/config/gpio-sim")

NUM_LINES = 8

OUTPUT_OFFSET = 0
"""Offset of the line the GPIOOutput tests run against."""

LINE_NAMES = {OUTPUT_OFFSET: "E2E_LED"}
"""Line names to configure, so name lookup is exercised too."""

_loaded_module = False
"""True if this script loaded the gpio-sim module and must unload it."""


def elevate_to_root() -> None:
    """Re-run this script under sudo if not already root."""
    if os.geteuid() == 0:
        return
    print("The GPIO E2E test needs root to load gpio-sim and to access")
    print("the character device.  Re-running under sudo (accept the")
    print("password prompt if asked)...")
    script = Path(__file__).resolve()
    cmd = ["sudo", sys.executable, str(script), *sys.argv[1:]]
    try:
        os.execvp("sudo", cmd)
    except OSError as ex:
        raise SystemExit(f"Could not re-run under sudo: {ex}")


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{shlex.join(cmd)} failed: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _remove_configfs_dir(path: Path) -> None:
    """Remove a configfs directory tree, deepest directories first.

    configfs only supports removing empty directories (attributes cannot
    be unlinked), so directories are rmdir()ed bottom up and files are
    never touched.
    """
    for child in path.iterdir():
        if child.is_dir():
            _remove_configfs_dir(child)
    path.rmdir()


@dataclass
class SimRig:
    """A live gpio-sim chip plus the handles needed to drive it."""

    chip_name: str
    line_dirs: dict[int, Path] = field(default_factory=dict)

    def pin(self, offset: int) -> str:
        """The canonical pin spec used in device configs."""
        return f"{self.chip_name}:{offset}"

    def named_pin(self, name: str) -> str:
        return f"{self.chip_name}:{name}"

    def drive(self, offset: int, level: bool) -> None:
        """Simulate the outside world by changing a line's pull.

        This stands in for a switch or sensor attached to an input pin.
        """
        pull = "pull-up" if level else "pull-down"
        (self.line_dirs[offset] / "pull").write_text(pull + "\n")

    def read_value(self, offset: int) -> int:
        """Read the physical level of a line, including driven outputs."""
        return int((self.line_dirs[offset] / "value").read_text().strip())


def setup_sim() -> SimRig:
    """Load gpio-sim, create and enable a chip, find its interfaces."""
    global _loaded_module

    already_loaded = "gpio_sim" in Path("/proc/modules").read_text()
    if not already_loaded:
        _run(["modprobe", "gpio-sim"])
        _loaded_module = True

    if not CONFIGFS_ROOT.is_dir():
        _run(["mount", "-t", "configfs", "none", "/sys/kernel/config"])
    if not CONFIGFS_ROOT.is_dir():
        raise RuntimeError(
            "configfs gpio-sim subsystem is unavailable even after mount"
        )

    dev_dir = CONFIGFS_ROOT / SIM_DEVICE_NAME
    if dev_dir.exists():
        print(f"Removing leftover {dev_dir} from an earlier run...")
        disable_and_remove_sim()

    dev_dir.mkdir()
    bank_dir = dev_dir / "bank0"
    bank_dir.mkdir()
    (bank_dir / "num_lines").write_text(f"{NUM_LINES}\n")
    (bank_dir / "label").write_text(SIM_DEVICE_NAME + "\n")
    for offset, name in LINE_NAMES.items():
        line_dir = bank_dir / f"line{offset}"
        line_dir.mkdir()
        (line_dir / "name").write_text(name + "\n")

    # Instantiate the platform device.  The write returns once the chip
    # has been probed, or fails with an error.
    (dev_dir / "live").write_text("1\n")

    chip_name = (bank_dir / "chip_name").read_text().strip()
    dev_name = (dev_dir / "dev_name").read_text().strip()

    device_path = Path("/dev") / chip_name
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline and not device_path.exists():
        time.sleep(0.05)
    if not device_path.exists():
        raise RuntimeError(
            f"{device_path} never appeared after enabling the sim device"
        )

    chip_dir = Path("/sys/devices/platform") / dev_name / chip_name
    line_dirs = {
        offset: chip_dir / f"sim_gpio{offset}" for offset in range(NUM_LINES)
    }
    for offset, line_dir in line_dirs.items():
        if not (line_dir / "pull").exists():
            raise RuntimeError(f"Missing sysfs interface at {line_dir}")

    print(
        f"Created simulated chip {chip_name} ({dev_name}) "
        f"with {NUM_LINES} lines"
    )
    return SimRig(chip_name=chip_name, line_dirs=line_dirs)


def disable_and_remove_sim() -> None:
    """Disable the sim device and remove its configfs entry."""
    dev_dir = CONFIGFS_ROOT / SIM_DEVICE_NAME
    if dev_dir.exists():
        live = dev_dir / "live"
        try:
            # Writing 0 to an already disabled device is an error, so
            # only disable when needed (leftovers can be either state).
            if live.read_text().strip() == "1":
                live.write_text("0\n")
        except OSError as ex:
            print(f"WARNING: could not disable sim device: {ex}")
        try:
            _remove_configfs_dir(dev_dir)
        except OSError as ex:
            print(f"WARNING: could not remove {dev_dir}: {ex}")
            print(
                "Remove it manually or later runs will not be able to "
                "create their own chip."
            )


def teardown_sim() -> None:
    """Undo everything setup_sim did."""
    global _loaded_module

    print("Tearing down simulated chip...")
    disable_and_remove_sim()
    if _loaded_module:
        try:
            _run(["rmmod", "gpio-sim"])
        except RuntimeError as ex:
            print(f"WARNING: could not unload gpio-sim: {ex}")
        _loaded_module = False


# ---------------------------------------------------------------------------
# The actual tests
# ---------------------------------------------------------------------------

from iot_devices.devices.GPIODevice import backend  # noqa: E402
from tests.recording_host import RecordingHost  # noqa: E402


def add_device(host: RecordingHost, config: dict[str, Any]) -> Any:
    return host.add_new_device(config).wait_device_ready()


def wait_for_value(dev: Any, expected: int, timeout: float = 3.0) -> None:
    """Poll a device's ``value`` datapoint until it matches, or fail."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dp = dev.datapoints.get("value")
        if dp is not None and dp.get()[0] == expected:
            return
        time.sleep(0.01)
    dp = dev.datapoints.get("value")
    actual = dp.get()[0] if dp is not None else "<missing>"
    raise AssertionError(
        f"{dev.name}: value never became {expected} (got {actual})"
    )


def test_output_active_high(rig: SimRig) -> None:
    """A datapoint write drives the simulated line, active high."""
    host = RecordingHost()
    try:
        out = add_device(
            host,
            {
                "type": "GPIOOutput",
                "name": "out",
                "pin": rig.pin(OUTPUT_OFFSET),
            },
        )
        assert not host.errors, host.errors
        assert "gpiod" in out.metadata["driver"]

        # The device really holds the line in the kernel.
        resolved = backend.resolve_name(rig.pin(OUTPUT_OFFSET))
        assert resolved.used, "The line should be claimed"
        assert "iot_devices" in resolved.consumer

        assert out.datapoints["value"].get()[0] == 0
        assert rig.read_value(OUTPUT_OFFSET) == 0

        out.set_data_point("value", 1)
        assert out.datapoints["value"].get()[0] == 1
        assert rig.read_value(OUTPUT_OFFSET) == 1

        out.set_data_point("value", 0)
        assert out.datapoints["value"].get()[0] == 0
        assert rig.read_value(OUTPUT_OFFSET) == 0
    finally:
        host.close()


def test_output_initial_value(rig: SimRig) -> None:
    """initial_value=1 drives the line right away."""
    host = RecordingHost()
    try:
        out = add_device(
            host,
            {
                "type": "GPIOOutput",
                "name": "out",
                "pin": rig.pin(OUTPUT_OFFSET),
                "initial_value": 1,
            },
        )
        assert not host.errors, host.errors
        assert out.datapoints["value"].get()[0] == 1
        assert rig.read_value(OUTPUT_OFFSET) == 1
    finally:
        host.close()


def test_output_active_low(rig: SimRig) -> None:
    """active_high=False inverts the physical level."""
    host = RecordingHost()
    try:
        out = add_device(
            host,
            {
                "type": "GPIOOutput",
                "name": "out",
                "pin": rig.pin(OUTPUT_OFFSET),
                "active_high": False,
                "initial_value": 0,
            },
        )
        assert not host.errors, host.errors

        # Logically off means physically high when active low.
        assert out.datapoints["value"].get()[0] == 0
        assert rig.read_value(OUTPUT_OFFSET) == 1

        out.set_data_point("value", 1)
        assert rig.read_value(OUTPUT_OFFSET) == 0

        out.set_data_point("value", 0)
        assert rig.read_value(OUTPUT_OFFSET) == 1
    finally:
        host.close()


def test_output_named_line(rig: SimRig) -> None:
    """Pins can be addressed by the line name the kernel reports."""
    host = RecordingHost()
    try:
        out = add_device(
            host,
            {
                "type": "GPIOOutput",
                "name": "out",
                "pin": rig.named_pin(LINE_NAMES[OUTPUT_OFFSET]),
            },
        )
        assert not host.errors, host.errors
        assert out.line is not None
        assert out.line.offset == OUTPUT_OFFSET

        out.set_data_point("value", 1)
        assert rig.read_value(OUTPUT_OFFSET) == 1
    finally:
        host.close()


def test_input_active_high(rig: SimRig) -> None:
    """Pull writes reach the datapoint through edge events."""
    host = RecordingHost()
    try:
        inp = add_device(
            host,
            {"type": "GPIOInput", "name": "in", "pin": rig.pin(1)},
        )
        assert not host.errors, host.errors

        # gpio-sim lines rest at pull-down, so a floating input is low.
        assert inp.datapoints["value"].get()[0] == 0

        rig.drive(1, True)
        wait_for_value(inp, 1)

        rig.drive(1, False)
        wait_for_value(inp, 0)
    finally:
        host.close()


def test_input_active_low(rig: SimRig) -> None:
    """active_high=False inverts the logical level."""
    host = RecordingHost()
    try:
        inp = add_device(
            host,
            {
                "type": "GPIOInput",
                "name": "in",
                "pin": rig.pin(2),
                "active_high": False,
            },
        )
        assert not host.errors, host.errors

        # Resting low reads as "active" when active low.
        assert inp.datapoints["value"].get()[0] == 1

        rig.drive(2, True)
        wait_for_value(inp, 0)

        rig.drive(2, False)
        wait_for_value(inp, 1)
    finally:
        host.close()


def test_input_pull_up(rig: SimRig) -> None:
    """pull_up=True is applied by the chip; grounding it activates."""
    host = RecordingHost()
    try:
        inp = add_device(
            host,
            {
                "type": "GPIOInput",
                "name": "in",
                "pin": rig.pin(3),
                "pull_up": True,
                "active_high": False,
            },
        )
        assert not host.errors, host.errors

        # The requested pull-up is applied by the kernel: the line rests
        # high, which is inactive when active low.
        assert rig.read_value(3) == 1
        assert inp.datapoints["value"].get()[0] == 0

        # Pulling the line to ground, like a switch wired to ground,
        # activates it.
        rig.drive(3, False)
        wait_for_value(inp, 1)

        rig.drive(3, True)
        wait_for_value(inp, 0)
    finally:
        host.close()


def test_input_pull_down(rig: SimRig) -> None:
    """pull_down=True rests low; driving high activates."""
    host = RecordingHost()
    try:
        inp = add_device(
            host,
            {
                "type": "GPIOInput",
                "name": "in",
                "pin": rig.pin(4),
                "pull_down": True,
                "active_high": True,
            },
        )
        assert not host.errors, host.errors

        assert rig.read_value(4) == 0
        assert inp.datapoints["value"].get()[0] == 0

        rig.drive(4, True)
        wait_for_value(inp, 1)

        rig.drive(4, False)
        wait_for_value(inp, 0)
    finally:
        host.close()


def test_input_invalid_pull_combinations(rig: SimRig) -> None:
    """Bad pull/active_high combinations are rejected."""
    cases = [
        (
            {"pull_up": True, "pull_down": True},
            "pull up and pull down",
        ),
        (
            {"pull_up": True},
            "pull up and active high",
        ),
        (
            {"pull_down": True, "active_high": False},
            "pull down and active low",
        ),
    ]
    for extra, message in cases:
        host = RecordingHost()
        try:
            dev = add_device(
                host,
                {
                    "type": "GPIOInput",
                    "name": "in",
                    "pin": rig.pin(5),
                    **extra,
                },
            )
            assert len(host.errors) == 1, host.errors
            assert message in host.errors[0], host.errors[0]
            # A failed init must not leave a usable datapoint behind.
            assert "value" not in dev.datapoints
        finally:
            host.close()


def test_input_debounce(rig: SimRig) -> None:
    """The debounce config is accepted by the kernel; events still flow."""
    host = RecordingHost()
    try:
        inp = add_device(
            host,
            {
                "type": "GPIOInput",
                "name": "in",
                "pin": rig.pin(6),
                "debounce_time_ms": 100,
            },
        )
        assert not host.errors, host.errors

        rig.drive(6, True)
        wait_for_value(inp, 1, timeout=4.0)

        rig.drive(6, False)
        wait_for_value(inp, 0, timeout=4.0)
    finally:
        host.close()


TESTS: list[tuple[str, Callable[[SimRig], None]]] = [
    ("output: active high value mapping", test_output_active_high),
    ("output: initial value", test_output_initial_value),
    ("output: active low inversion", test_output_active_low),
    ("output: named line lookup", test_output_named_line),
    ("input: active high level changes", test_input_active_high),
    ("input: active low level changes", test_input_active_low),
    ("input: pull up rests high", test_input_pull_up),
    ("input: pull down rests low", test_input_pull_down),
    ("input: invalid pull combinations", test_input_invalid_pull_combinations),
    ("input: debounce", test_input_debounce),
]


def run_tests(rig: SimRig) -> int:
    """Run all tests, collecting results.  Returns the failure count."""
    failures = 0
    for name, test in TESTS:
        print(f"[ RUN  ] {name}")
        try:
            test(rig)
        except Exception as ex:
            failures += 1
            print(f"[ FAIL ] {name}: {ex}")
        else:
            print(f"[ PASS ] {name}")
    return failures


def main() -> int:
    elevate_to_root()

    rig: SimRig | None = None
    try:
        rig = setup_sim()
        failures = run_tests(rig)
        if failures:
            print(f"\nGPIO E2E: {failures} test(s) FAILED")
            return 1
        print(f"\nGPIO E2E: all {len(TESTS)} tests passed")
        return 0
    finally:
        teardown_sim()


if __name__ == "__main__":
    raise SystemExit(main())
