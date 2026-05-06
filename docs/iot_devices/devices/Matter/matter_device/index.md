# iot_devices.devices.Matter.matter_device

## Attributes

| [`GAS_NAMES`](#iot_devices.devices.Matter.matter_device.GAS_NAMES)   |    |
|----------------------------------------------------------------------|----|
| [`GAS_UNITS`](#iot_devices.devices.Matter.matter_device.GAS_UNITS)   |    |

## Classes

| [`MatterDevice`](#iot_devices.devices.Matter.matter_device.MatterDevice)   | Represents a single Matter node with its clusters and endpoints.   |
|----------------------------------------------------------------------------|--------------------------------------------------------------------|

## Module Contents

### iot_devices.devices.Matter.matter_device.GAS_NAMES

### iot_devices.devices.Matter.matter_device.GAS_UNITS

### *class* iot_devices.devices.Matter.matter_device.MatterDevice(config: dict[str, Any], \*\*kw: Any)

Bases: [`iot_devices.device.Device`](../../../device/index.md#iot_devices.device.Device)

Represents a single Matter node with its clusters and endpoints.

#### device_type *= 'MatterDevice'*

Every device must have a unique device_type name

#### config_schema

Schema defining the config

#### CLUSTER_HANDLERS

#### eeprom_ratelimiter

#### command_ratelimiters *: dict[str, scullery.ratelimits.RateLimiter]*

#### node_id

#### parent_controller *: [iot_devices.devices.Matter.MatterControllerClient](../index.md#iot_devices.devices.Matter.MatterControllerClient) | None*

#### subscriptions *: dict[tuple[int, int, int], collections.abc.Callable]*

#### set_parent_controller(parent: [iot_devices.devices.Matter.MatterControllerClient](../index.md#iot_devices.devices.Matter.MatterControllerClient)) → None

Set reference to parent MatterControllerClient.

Args:
: parent: The parent MatterControllerClient device

#### register_subscription(endpoint_id: int, cluster_id: int, attribute_id: int, handler: collections.abc.Callable) → None

Register a subscription for a cluster attribute.

Args:
: endpoint_id: Endpoint ID
  cluster_id: Cluster ID
  attribute_id: Attribute ID
  handler: Callable(value) that handles updates for this attribute

#### get_subscriptions() → dict[tuple[int, int, int], collections.abc.Callable]

Get all registered subscriptions for this device.

Returns:
: Dict mapping (endpoint_id, cluster_id, attribute_id)
  to handler functions

#### on_delete()

release all persistent resources, used by the host
app to tell the user the device is being permanently
deleted.
may be used to delete any files automatically created.

#### *static* setup_onoff_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.OnOff) → None

Setup OnOff cluster handler.

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID with OnOff cluster
  cluster_id: Cluster ID (0x0006)

#### *static* setup_level_control_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.LevelControl) → None

Setup Level Control cluster handler (brightness/dimming).

Args:
: device: MatterDevice instance
  endpoint: Endpoint ID with Level Control cluster
  cluster_id: Cluster ID (0x0008)

#### *static* setup_color_control_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.ColorControl) → None

Setup Color Control cluster handler (brightness/dimming).

Args:
: device: MatterDevice instance
  endpoint: Endpoint ID
  cluster_id: Cluster ID (0x0008)

#### *static* setup_temperature_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.TemperatureMeasurement) → None

Setup Temperature Measurement cluster handler.

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID with Temperature cluster
  cluster_id: Cluster ID (0x0402)

#### *static* setup_humidity_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.RelativeHumidityMeasurement) → None

Setup Relative Humidity cluster handler.

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID with Humidity cluster
  cluster_id: Cluster ID (0x0405)

#### *static* setup_occupancy_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.OccupancySensing) → None

Setup Occupancy Sensing cluster handler.

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID
  cluster_id: Cluster ID (0x0406)

#### *static* setup_smoke_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.SmokeCoAlarm) → None

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID
  cluster_id: Cluster ID (0x005C)

#### *static* setup_gas_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.CarbonDioxideConcentrationMeasurement) → None

Setup Concentration Sensing cluster handler.

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID
  cluster_id: Cluster ID (can be multiple)

#### *static* setup_boolean_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.BooleanState) → None

Setup Boolean Sensing cluster handler.

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID
  cluster_id: Cluster ID (0x0045)

#### *static* setup_switch_cluster(device: [MatterDevice](#iot_devices.devices.Matter.matter_device.MatterDevice), endpoint_id: int, cluster_id: int, cluster_dict: chip.clusters.Objects.Switch) → None

Setup Switch cluster handler.

Args:
: device: MatterDevice instance
  endpoint_id: Endpoint ID with Switch cluster
  cluster_id: Cluster ID (0x003B)
