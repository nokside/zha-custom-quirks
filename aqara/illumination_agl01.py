"""Quirk for Aqara Light Sensor T1 lumi.sen_ill.agl01 / GZCGQ11LM."""

import math
from typing import Any, Final

from zigpy import types as t
from zigpy.zcl import (
    AttributeReportedEvent,
    ClusterType,
    foundation,
)
from zigpy.zcl.clusters.general import Ota
from zigpy.zcl.clusters.measurement import IlluminanceMeasurement
from zigpy.zcl.foundation import BaseAttributeDefs, ZCLAttributeDef
from zigpy.zdo.types import NodeDescriptor

from zhaquirks import CustomCluster
from zhaquirks.builder import QuirkBuilder, UnitOfTime
from zhaquirks.const import BatterySize
from zhaquirks.xiaomi import BATTERY_SIZE_ATTR, XiaomiPowerConfiguration

AQARA_MFG_CODE: Final = 0x115F


class LightT1PowerConfigurationCluster(XiaomiPowerConfiguration):
    """Aqara Light Sensor T1 power configuration cluster."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the cluster."""
        super().__init__(*args, **kwargs)
        self._CONSTANT_ATTRIBUTES[BATTERY_SIZE_ATTR] = BatterySize.CR2450

    def _update_battery_percentage(self, voltage_mv: int) -> None:
        """Update battery percentage from voltage."""
        # Aqara-like battery percentage.
        percentage = 0.00045 * voltage_mv**2 - 2.277 * voltage_mv + 2880

        self._update_attribute(
            self.BATTERY_PERCENTAGE_REMAINING,
            round(max(0, min(200, percentage * 2))),
        )


class LightT1ManufacturerCluster(CustomCluster):
    """Aqara Light Sensor T1 manufacturer cluster."""

    cluster_id = 0xFCC0
    ep_attribute = "light_t1_manu"

    class AttributeDefs(BaseAttributeDefs):
        """Attribute definitions."""

        light_sampling_period: Final = ZCLAttributeDef(
            id=0x0000,
            type=t.uint16_t,
            access="rw",
            manufacturer_code=AQARA_MFG_CODE,
        )
        aqara_heartbeat: Final = ZCLAttributeDef(
            id=0x00F7,
            type=t.LVBytes,
            access="p",
            manufacturer_code=AQARA_MFG_CODE,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the T1 manufacturer cluster."""
        super().__init__(*args, **kwargs)
        self.on_event(AttributeReportedEvent.event_type, self._handle_attribute_event)

    def _handle_attribute_event(self, event: AttributeReportedEvent) -> None:
        """Handle manufacturer attribute events."""
        if event.attribute_id == self.AttributeDefs.aqara_heartbeat.id:
            self._handle_heartbeat(event.value)

    def _handle_heartbeat(self, data: bytes) -> None:
        """Parse Light Sensor T1 heartbeat and update attributes."""
        while len(data) >= 2:
            tag = data[0]

            try:
                typed_value, data = foundation.TypeValue.deserialize(data[1:])
            except (KeyError, ValueError):
                self.debug(
                    "Failed to deserialize heartbeat tag 0x%02X, data: %r",
                    tag,
                    data,
                )
                return

            value = typed_value.value

            if tag == 0x01:
                self.endpoint.power.battery_reported(value)
            elif tag == 0x64:
                self.endpoint.illuminance.update_attribute(
                    IlluminanceMeasurement.AttributeDefs.measured_value.id,
                    round(10000 * math.log10(value) + 1) if value > 0 else 0,
                )

    async def apply_custom_configuration(self, *args, **kwargs):
        """Read Light Sensor T1 attributes."""
        try:
            await self.read_attributes([self.AttributeDefs.light_sampling_period.id])
            await self.endpoint.illuminance.read_attributes(
                [IlluminanceMeasurement.AttributeDefs.measured_value.id]
            )
        except Exception as exc:  # noqa: BLE001
            self.debug("Failed to read attributes: %s", exc, exc_info=True)


(
    QuirkBuilder("LUMI", "lumi.sen_ill.agl01")
    .node_descriptor(
        NodeDescriptor(0x02, 0x40, 0x80, 0x126E, 0x7F, 0x0064, 0x2C00, 0x0064, 0x00)
    )
    .friendly_name(manufacturer="Aqara", model="Light Sensor T1")
    .replaces(LightT1PowerConfigurationCluster)
    .replaces(LightT1ManufacturerCluster)
    .adds(Ota.cluster_id, cluster_type=ClusterType.Client)
    .number(
        attribute_name="light_sampling_period",
        cluster_id=LightT1ManufacturerCluster.cluster_id,
        min_value=1,
        max_value=59,
        step=1,
        unit=UnitOfTime.SECONDS,
        translation_key="light_sampling_period",
        fallback_name="Light sampling period",
    )
    .skip_configuration()
    .add_to_registry()
)
