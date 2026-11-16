"""Quirk for Aqara Door and Window Sensor E1 lumi.magnet.acn001 / MCCGQ14LM."""

from typing import Any, Final

from zigpy import types as t
from zigpy.zcl import AttributeReadEvent, AttributeReportedEvent, foundation
from zigpy.zcl.clusters.security import IasZone
from zigpy.zcl.foundation import BaseAttributeDefs, ZCLAttributeDef

from zhaquirks import CustomCluster
from zhaquirks.builder import QuirkBuilder
from zhaquirks.const import BatterySize
from zhaquirks.xiaomi import BATTERY_SIZE_ATTR, XiaomiPowerConfiguration

AQARA_MFG_CODE: Final = 0x115F


class MagnetE1PowerConfigurationCluster(XiaomiPowerConfiguration):
    """Aqara Door and Window Sensor E1 power configuration cluster."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the cluster."""
        super().__init__(*args, **kwargs)

        self._CONSTANT_ATTRIBUTES[BATTERY_SIZE_ATTR] = BatterySize.CR1632

    def _update_battery_percentage(self, voltage_mv: int) -> None:
        """Update battery percentage from voltage."""
        # Aqara-like battery percentage.
        percentage = 0.00045 * voltage_mv**2 - 2.277 * voltage_mv + 2880

        self._update_attribute(
            self.BATTERY_PERCENTAGE_REMAINING,
            round(max(0, min(200, percentage * 2))),
        )


class MagnetE1ManufacturerCluster(CustomCluster):
    """Aqara Door and Window Sensor E1 manufacturer cluster."""

    cluster_id = 0xFCC0
    ep_attribute = "magnet_e1_manu"

    class AttributeDefs(BaseAttributeDefs):
        """Attribute definitions."""

        aqara_heartbeat: Final = ZCLAttributeDef(
            id=0x00F7,
            type=t.LVBytes,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the E1 manufacturer cluster."""
        super().__init__(*args, **kwargs)
        for event_type in (AttributeReadEvent, AttributeReportedEvent):
            self.on_event(event_type.event_type, self._handle_attribute_event)

    def _handle_attribute_event(
        self, event: AttributeReadEvent | AttributeReportedEvent
    ) -> None:
        """Handle manufacturer attribute events."""
        if event.attribute_id == self.AttributeDefs.aqara_heartbeat.id:
            self._handle_heartbeat(
                event.value,
                is_reported_event=isinstance(event, AttributeReportedEvent),
            )

    def _handle_heartbeat(self, data: bytes, is_reported_event: bool) -> None:
        """Parse Door and Window Sensor E1 heartbeat."""
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
            elif is_reported_event and tag == 0x64:
                zone_status_attr = IasZone.AttributeDefs.zone_status.id
                current_status = self.endpoint.ias_zone.get(zone_status_attr) or 0
                alarm_bit = IasZone.ZoneStatus.Alarm_1

                self.endpoint.ias_zone.update_attribute(
                    zone_status_attr,
                    (current_status & ~alarm_bit) | (value & alarm_bit),
                )

    async def apply_custom_configuration(self, *args, **kwargs):
        """Read Door and Window Sensor E1 attributes."""
        try:
            await self.read_attributes([self.AttributeDefs.aqara_heartbeat.id])
            await self.endpoint.ias_zone.read_attributes(
                [IasZone.AttributeDefs.zone_status.id]
            )
        except Exception as exc:  # noqa: BLE001
            self.debug("Failed to read attributes: %s", exc, exc_info=True)


(
    QuirkBuilder("LUMI", "lumi.magnet.acn001")
    .friendly_name(manufacturer="Aqara", model="Door and Window Sensor E1")
    .replaces(MagnetE1ManufacturerCluster)
    .replaces(MagnetE1PowerConfigurationCluster)
    .skip_configuration()
    .add_to_registry()
)
