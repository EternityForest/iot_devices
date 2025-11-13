# iot_devices.datapoints

## Attributes

| [`AnyDataPointType`](#iot_devices.datapoints.AnyDataPointType)   |    |
|------------------------------------------------------------------|----|
| [`DataPointTypeVar`](#iot_devices.datapoints.DataPointTypeVar)   |    |

## Classes

| [`DataPoint`](#iot_devices.datapoints.DataPoint)               |    |
|----------------------------------------------------------------|----|
| [`StringDataPoint`](#iot_devices.datapoints.StringDataPoint)   |    |
| [`NumericDataPoint`](#iot_devices.datapoints.NumericDataPoint) |    |
| [`ObjectDataPoint`](#iot_devices.datapoints.ObjectDataPoint)   |    |
| [`BytesDataPoint`](#iot_devices.datapoints.BytesDataPoint)     |    |

## Module Contents

### iot_devices.datapoints.AnyDataPointType

### iot_devices.datapoints.DataPointTypeVar

### *class* iot_devices.datapoints.DataPoint(device: [iot_devices.device.Device](../device/index.md#iot_devices.device.Device), datapoint_name: str, requestable: bool = True, writable: bool = True)

Bases: `Generic`[[`DataPointTypeVar`](#iot_devices.datapoints.DataPointTypeVar)]

#### device

#### datapoint_name

#### full_name

#### \_\_repr_\_() → str

#### *abstractmethod* get() → tuple[DataPointTypeVar, float, Any]

#### *abstractmethod* set(value: DataPointTypeVar, timestamp: float | None = None, annotation: Any | None = None) → None

#### request() → None

Asynchronously ask the device to refresh it's data point

### *class* iot_devices.datapoints.StringDataPoint(device: [iot_devices.device.Device](../device/index.md#iot_devices.device.Device), datapoint_name: str, requestable: bool = True, writable: bool = True)

Bases: [`DataPoint`](#iot_devices.datapoints.DataPoint)[`str`]

#### get() → tuple[str, float, Any]

#### set(value: str, timestamp: float | None = None, annotation: Any | None = None) → None

### *class* iot_devices.datapoints.NumericDataPoint(device: [iot_devices.device.Device](../device/index.md#iot_devices.device.Device), datapoint_name: str, requestable: bool = True, writable: bool = True)

Bases: [`DataPoint`](#iot_devices.datapoints.DataPoint)[`float`]

#### get() → tuple[float, float, Any]

#### set(value: float | int, timestamp: float | None = None, annotation: Any | None = None) → None

### *class* iot_devices.datapoints.ObjectDataPoint(device: [iot_devices.device.Device](../device/index.md#iot_devices.device.Device), datapoint_name: str, requestable: bool = True, writable: bool = True)

Bases: [`DataPoint`](#iot_devices.datapoints.DataPoint)[`dict`[`str`, `Any`]]

#### get() → tuple[dict[str, Any], float, Any]

#### set(value: dict[str, Any], timestamp: float | None = None, annotation: Any | None = None) → None

### *class* iot_devices.datapoints.BytesDataPoint(device: [iot_devices.device.Device](../device/index.md#iot_devices.device.Device), datapoint_name: str, requestable: bool = True, writable: bool = True)

Bases: [`DataPoint`](#iot_devices.datapoints.DataPoint)[`bytes`]

#### get() → tuple[bytes, float, Any]

#### set(value: bytes, timestamp: float | None = None, annotation: Any | None = None) → None

#### fast_push(value: bytes, timestamp: float | None = None, annotation: Any | None = None) → None
