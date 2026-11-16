"""Quirk for Aqara Motion Sensor P1 lumi.motion.ac02 / RTCGQ14LM."""

import asyncio
from typing import Any, Final

from zigpy import types as t
from zigpy.zcl import AttributeReadEvent, AttributeReportedEvent, foundation
from zigpy.zcl.clusters.measurement import IlluminanceMeasurement, OccupancySensing
from zigpy.zcl.foundation import BaseAttributeDefs, DataTypeId, ZCLAttributeDef

from zhaquirks import CustomCluster, LocalDataCluster
from zhaquirks.builder import NumberDeviceClass, QuirkBuilder, UnitOfTime
from zhaquirks.const import BatterySize
from zhaquirks.xiaomi import (
    BATTERY_QUANTITY_ATTR,
    BATTERY_SIZE_ATTR,
    LocalIlluminanceMeasurementCluster,
    XiaomiPowerConfiguration,
)

AQARA_MFG_CODE: Final = 0x115F


class MotionSensitivity(t.enum8):
    """Motion sensitivity."""

    Low = 0x01
    Medium = 0x02
    High = 0x03


class MotionP1PowerConfigurationCluster(XiaomiPowerConfiguration):
    """Aqara P1 power configuration cluster."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the cluster."""
        super().__init__(*args, **kwargs)

        self._CONSTANT_ATTRIBUTES = {
            BATTERY_QUANTITY_ATTR: 2,
            BATTERY_SIZE_ATTR: BatterySize.CR2450,
        }

    def _update_battery_percentage(self, voltage_mv: int) -> None:
        """Update battery percentage from voltage."""
        # Aqara-like battery percentage.
        percentage = 0.00045 * voltage_mv**2 - 2.277 * voltage_mv + 2880

        self._update_attribute(
            self.BATTERY_PERCENTAGE_REMAINING,
            round(max(0, min(200, percentage * 2))),
        )


class MotionP1ManufacturerCluster(CustomCluster):
    """Aqara Motion Sensor P1 manufacturer cluster."""

    cluster_id = 0xFCC0
    ep_attribute = "motion_p1_manu"

    class AttributeDefs(BaseAttributeDefs):
        """Attribute definitions."""

        detection_interval: Final = ZCLAttributeDef(
            id=0x0102,
            type=t.uint8_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        motion_sensitivity: Final = ZCLAttributeDef(
            id=0x010C,
            type=MotionSensitivity,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        led_trigger_indicator: Final = ZCLAttributeDef(
            id=0x0152,
            type=t.uint8_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        motion_illuminance: Final = ZCLAttributeDef(
            id=0x0112,
            type=t.uint32_t,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        aqara_heartbeat: Final = ZCLAttributeDef(
            id=0x00F7,
            type=t.LVBytes,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the P1 manufacturer cluster."""
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

        elif (
            isinstance(event, AttributeReportedEvent)
            and event.attribute_id == self.AttributeDefs.motion_illuminance.id
        ):
            self.endpoint.illuminance.update_attribute(
                IlluminanceMeasurement.AttributeDefs.measured_value.id,
                event.value - 65536,
            )
            self.endpoint.occupancy.set_occupied()

    def _handle_heartbeat(self, data: bytes, is_reported_event: bool) -> None:
        """Parse P1 heartbeat; battery from any event, the rest from reports only."""
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
            elif is_reported_event:
                if tag == 0x65:
                    self.endpoint.illuminance.update_attribute(
                        IlluminanceMeasurement.AttributeDefs.measured_value.id,
                        value,
                    )
                elif tag == 0x69:
                    self.update_attribute(
                        self.AttributeDefs.detection_interval.id, value
                    )
                elif tag == 0x6A:
                    self.update_attribute(
                        self.AttributeDefs.motion_sensitivity.id, value
                    )
                elif tag == 0x6B:
                    self.update_attribute(
                        self.AttributeDefs.led_trigger_indicator.id, value
                    )

    async def apply_custom_configuration(self, *args, **kwargs):
        """Read P1 attributes."""
        try:
            await self.read_attributes(
                [attr.id for attr in self.AttributeDefs]
            )
        except Exception as exc:  # noqa: BLE001
            self.debug("Failed to read attributes: %s", exc, exc_info=True)


class MotionP1OccupancySensingCluster(LocalDataCluster, OccupancySensing):
    """Aqara Motion Sensor P1 occupancy cluster."""

    OCCUPANCY_ATTR_ID: Final = OccupancySensing.AttributeDefs.occupancy.id

    _VALID_ATTRIBUTES: set[int] = {OCCUPANCY_ATTR_ID}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize local occupancy timer."""
        super().__init__(*args, **kwargs)
        self._timer_handle: asyncio.TimerHandle | None = None

    def set_occupied(self) -> None:
        """Set occupancy and restart the timer that clears it."""
        self._update_attribute(
            self.OCCUPANCY_ATTR_ID, OccupancySensing.Occupancy.Occupied
        )
        self._restart_timer()

    def _set_unoccupied(self) -> None:
        """Clear occupancy after the detection interval expires."""
        self._timer_handle = None
        self._update_attribute(
            self.OCCUPANCY_ATTR_ID, OccupancySensing.Occupancy.Unoccupied
        )

    def _restart_timer(self) -> None:
        """Restart the timer that clears occupancy."""
        if self._timer_handle is not None:
            self._timer_handle.cancel()

        detection_interval = self.endpoint.motion_p1_manu.get(
            MotionP1ManufacturerCluster.AttributeDefs.detection_interval.id,
            30,
        )

        self._timer_handle = asyncio.get_running_loop().call_later(
            detection_interval, self._set_unoccupied
        )


class MotionP1IlluminanceMeasurementCluster(LocalIlluminanceMeasurementCluster):
    """Aqara Motion Sensor P1 illuminance measurement cluster."""

    def _update_attribute(self, attrid, value):
        if attrid == self.AttributeDefs.measured_value.id and (
            value < 0 or value > 0xFDE8
        ):
            self.debug(
                "Received invalid illuminance value: %s - setting illuminance to 0",
                value,
            )
            value = 0

        super()._update_attribute(attrid, value)


(
    QuirkBuilder("LUMI", "lumi.motion.ac02")
    .friendly_name(manufacturer="Aqara", model="Motion Sensor P1")
    .adds(MotionP1OccupancySensingCluster)
    .adds(MotionP1IlluminanceMeasurementCluster)
    .replaces(MotionP1PowerConfigurationCluster)
    .replaces(MotionP1ManufacturerCluster)
    .number(
        attribute_name="detection_interval",
        cluster_id=MotionP1ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=2,
        max_value=200,
        step=1,
        unit=UnitOfTime.SECONDS,
        translation_key="detection_interval",
        fallback_name="Detection interval",
    )
    .enum(
        attribute_name="motion_sensitivity",
        enum_class=MotionSensitivity,
        cluster_id=MotionP1ManufacturerCluster.cluster_id,
        translation_key="motion_sensitivity",
        fallback_name="Motion sensitivity",
    )
    .switch(
        attribute_name="led_trigger_indicator",
        cluster_id=MotionP1ManufacturerCluster.cluster_id,
        translation_key="led_trigger_indicator",
        fallback_name="LED trigger indicator",
    )
    .skip_configuration()
    .add_to_registry()
)
