/**
 * Fake Matter devices for the iot_devices end-to-end tests.
 *
 * Runs one of each fake device (an on/off light, a dimmable light and
 * an extended color light) using matter.js in a single process, one
 * ServerNode per device.  Each device's Matter persistent state is
 * kept under MATTER_STORAGE_PATH, and a human readable copy of the
 * current attribute values is mirrored to DATA_PATH/state-<kind>.json
 * so tests running on the host can inspect the values the devices
 * actually hold.
 *
 * Unless the --commissionable command line flag is given, the devices
 * start but do not open their commissioning windows, so they cannot be
 * paired.  Passcodes and discriminators are fixed so tests know the
 * pairing pins in advance.  A commissioned device does not advertise
 * again on later starts, which keeps the reconnect scenario clean.
 */

import { ColorControlServer } from "@matter/main/behaviors";
import { ServerNode } from "@matter/main/node";
import {
    DimmableLightDevice,
    ExtendedColorLightDevice,
    OnOffLightDevice,
} from "@matter/main/devices";
import "@matter/nodejs";

import {
    closeSync,
    mkdirSync,
    openSync,
    renameSync,
    writeSync,
} from "node:fs";
import { join } from "node:path";

const COMMISSIONABLE = process.argv.includes("--commissionable");
const DATA_PATH = process.env.FAKE_DEVICE_DATA_PATH ?? "/data";

const DEVICE_KINDS = ["onoff", "dimmable", "color"];

const DEVICE_SPECS = {
    onoff: {
        label: "E2E OnOff Light",
        passcode: 20202021,
        discriminator: 3840,
        port: 5540,
        deviceType: OnOffLightDevice,
    },
    dimmable: {
        label: "E2E Dimmable Light",
        passcode: 20202022,
        discriminator: 3841,
        port: 5541,
        deviceType: DimmableLightDevice,
    },
    color: {
        label: "E2E Color Light",
        passcode: 20202023,
        discriminator: 3842,
        port: 5542,
        // The stock ExtendedColorLightDevice preset only enables the
        // XY and color temperature features; hue/saturation writes
        // need the HueSaturation feature turned on explicitly.
        deviceType: ExtendedColorLightDevice.withBehaviors(
            ColorControlServer.with(
                "HueSaturation",
                "EnhancedHue",
                "ColorTemperature",
                "XY",
            ),
        ),
    },
};

/** Last JSON written for each kind, to skip redundant file writes. */
const lastStateJson = {};

/** Mirrors the readable/writable attributes of a node to a JSON file. */
function currentState(kind, spec, node) {
    const endpoint = node.parts.get("light");
    if (endpoint === undefined) {
        throw new Error(`Device endpoint not found on the ${kind} node`);
    }
    const state = endpoint.state;

    const result = {
        kind: kind,
        label: spec.label,
        onOff: state.onOff.onOff,
    };
    if (state.levelControl !== undefined) {
        result.currentLevel = state.levelControl.currentLevel;
    }
    if (state.colorControl !== undefined) {
        result.currentHue = state.colorControl.currentHue;
        result.currentSaturation = state.colorControl.currentSaturation;
    }
    return result;
}

/** Writes state-<kind>.json atomically so readers never see a partial file. */
function writeState(kind, spec, node) {
    const json = JSON.stringify(currentState(kind, spec, node), null, 4) +
        "\n";
    if (json === lastStateJson[kind]) {
        return;
    }
    lastStateJson[kind] = json;

    const path = join(DATA_PATH, `state-${kind}.json`);
    mkdirSync(DATA_PATH, { recursive: true });
    const tmpPath = `${path}.tmp`;
    const fd = openSync(tmpPath, "w");
    try {
        writeSync(fd, json);
    } finally {
        closeSync(fd);
    }
    renameSync(tmpPath, path);
}

function nodeConfig(kind, spec) {
    const config = {
        basicInformation: {
            nodeLabel: spec.label,
            vendorName: "iot-devices E2E",
            vendorId: 0xfff1,
            productName: spec.label,
            productId: 0x8000,
        },
        productDescription: {
            name: kind,
            deviceType: spec.deviceType,
        },
        commissioning: {
            passcode: spec.passcode,
            discriminator: spec.discriminator,
            enabled: COMMISSIONABLE,
        },
        // All three devices run in one process, so each binds its own
        // Matter port.
        network: { port: spec.port },
    };

    const part = {
        type: spec.deviceType,
        id: "light",
        onOff: { onOff: false },
    };

    if (kind === "dimmable") {
        part.levelControl = { currentLevel: 128 };
    } else if (kind === "color") {
        part.levelControl = { currentLevel: 128 };
        // colorMode 0 selects the hue/saturation mode, and the color
        // temperature attributes must be inside the physical bounds
        // or the cluster refuses to initialize.
        part.colorControl = {
            colorMode: 0,
            colorTempPhysicalMinMireds: 147,
            colorTempPhysicalMaxMireds: 500,
            colorTemperatureMireds: 250,
            coupleColorTempToLevelMinMireds: 147,
        };
    }
    config.parts = [part];
    return config;
}

const nodes = {};

// Nodes must be created in a fixed order: the matter.js persistent
// storage namespaces each node by its creation index.
for (const kind of DEVICE_KINDS) {
    const spec = DEVICE_SPECS[kind];
    const node = await ServerNode.create(nodeConfig(kind, spec));

    // Mirror attribute values to the bind-mounted data dir.
    setInterval(() => {
        try {
            writeState(kind, spec, node);
        } catch (error) {
            console.error(`Failed to write ${kind} state file:`, error);
        }
    }, 250);

    await node.start();
    writeState(kind, spec, node);
    nodes[kind] = node;
    console.log(
        `Fake device ${kind} (${spec.label}) started, ` +
            `commissionable=${COMMISSIONABLE}`,
    );
}

let closing = false;
async function shutdown() {
    if (closing) {
        return;
    }
    closing = true;
    try {
        for (const kind of DEVICE_KINDS) {
            const spec = DEVICE_SPECS[kind];
            try {
                writeState(kind, spec, nodes[kind]);
                await nodes[kind].close();
            } catch (error) {
                console.error(`Failed to close ${kind}:`, error);
            }
        }
    } finally {
        process.exit(0);
    }
}
process.on("SIGTERM", () => {
    void shutdown();
});
process.on("SIGINT", () => {
    void shutdown();
});
