from __future__ import annotations

import time
from collections.abc import Mapping
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from .device import Device

AnyDataPointType = str, int | float | str | bytes | Mapping[str, Any] | None
DataPointTypeVar = TypeVar("DataPointTypeVar")


class DataPoint(Generic[DataPointTypeVar]):
    def __init__(
        self,
        device: Device,
        datapoint_name: str,
        requestable: bool = True,
        writable: bool = True,
    ):
        self.device = device
        self.datapoint_name = datapoint_name
        self.full_name = device.host.resolve_datapoint_name(
            device.name, datapoint_name
        )

    def __repr__(self) -> str:
        formarttedtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return f"<{self.__class__.__name__}({self.full_name}): {str(self.get()[0])[:20]} at {formarttedtime} annotation={str(self.get()[2])[:20]}>"  # noqa: E501

    def get(self) -> tuple[DataPointTypeVar, float, Any]:
        raise NotImplementedError

    def set(
        self,
        value: DataPointTypeVar,
        timestamp: float | None = None,
        annotation: Any | None = None,
    ) -> None:
        raise NotImplementedError

    def request(self) -> None:
        """Asynchronously ask the device to refresh it's data point"""
        self.device.host.request_data_point(
            self.device.name, self.datapoint_name
        )


class StringDataPoint(DataPoint[str]):
    def get(self) -> tuple[str, float, Any]:
        return self.device.host.get_string(
            self.device.name, self.datapoint_name
        )

    def set(
        self,
        value: str,
        timestamp: float | None = None,
        annotation: Any | None = None,
    ) -> None:
        self.device.host.set_string(
            self.device.name, self.datapoint_name, value, timestamp, annotation
        )


class NumericDataPoint(DataPoint[float]):
    def get(self) -> tuple[float, float, Any]:
        return self.device.host.get_number(
            self.device.name, self.datapoint_name
        )

    def set(
        self,
        value: float | int,
        timestamp: float | None = None,
        annotation: Any | None = None,
    ) -> None:
        self.device.host.set_number(
            self.device.name,
            self.datapoint_name,
            float(value),
            timestamp,
            annotation,
        )


class ObjectDataPoint(DataPoint[dict[str, Any]]):
    def get(self) -> tuple[dict[str, Any], float, Any]:
        return self.device.host.get_object(
            self.device.name, self.datapoint_name
        )

    def set(
        self,
        value: dict[str, Any],
        timestamp: float | None = None,
        annotation: Any | None = None,
    ) -> None:
        self.device.host.set_object(
            self.device.name,
            self.datapoint_name,
            deepcopy(value),
            timestamp,
            annotation,
        )


class BytesDataPoint(DataPoint[bytes]):
    def get(self) -> tuple[bytes, float, Any]:
        return self.device.host.get_bytes(self.device.name, self.datapoint_name)

    def set(
        self,
        value: bytes,
        timestamp: float | None = None,
        annotation: Any | None = None,
    ) -> None:
        self.device.host.set_bytes(
            self.device.name, self.datapoint_name, value, timestamp, annotation
        )

    def fast_push(
        self,
        value: bytes,
        timestamp: float | None = None,
        annotation: Any | None = None,
    ) -> None:
        self.device.host.fast_push_bytes(
            self.device.name, self.datapoint_name, value, timestamp, annotation
        )
