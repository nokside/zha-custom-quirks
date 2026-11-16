"""Quirk for Aqara Presence Multi-Sensor FP300 lumi.sensor_occupy.agl8 / PS-S04D / PS-S04E.

The FP300 will only work correctly if the Zigbee coordinator's manufacturer
code is set to 0x115F. However, forcing this code for the entire Zigbee network may
break devices from other manufacturers.

To ensure correct operation, use coordinator firmware that reports
manufacturer code 0x115F for Aqara devices, such as Koenkk's Z-Stack firmware, or use Ziggurat.

Factory reset the FP300 before re-pairing it after switching Zigbee
platforms or quirk implementations.
"""

from typing import Any, Final

from zha.application.helpers import write_attributes_safe
from zha.application.platforms.number import NumberConfigurationEntity
from zigpy import types as t
from zigpy.typing import AddressingMode
from zigpy.zcl import AttributeReadEvent, AttributeReportedEvent, foundation
from zigpy.zcl.foundation import (
    BaseAttributeDefs,
    DataTypeId,
    ZCLAttributeDef,
    ZCLHeader,
)

from zhaquirks import CustomCluster
from zhaquirks.builder import (
    PERCENTAGE,
    BinarySensorDeviceClass,
    EntityType,
    NumberDeviceClass,
    QuirkBuilder,
    SensorDeviceClass,
    SensorStateClass,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from zhaquirks.const import BatterySize
from zhaquirks.xiaomi import (
    BATTERY_QUANTITY_ATTR,
    BATTERY_SIZE_ATTR,
    XiaomiPowerConfigurationPercent,
)

AQARA_MFG_CODE: Final = 0x115F


class PresenceSensitivity(t.enum8):
    """Presence sensitivity."""

    Low = 1
    Medium = 2
    High = 3


class PresenceDetectionMode(t.enum8):
    """Presence detection mode."""

    Hybrid = 0
    Radar_only = 1
    PIR_only = 2


class SamplingFrequency(t.enum8):
    """Sampling frequency."""

    Off = 0
    Low = 1
    Medium = 2
    High = 3
    Custom = 4


class ReportMode(t.enum8):
    """Report mode."""

    Threshold = 1
    Interval = 2
    Threshold_and_interval = 3


class FP300PowerConfigurationCluster(XiaomiPowerConfigurationPercent):
    """FP300 power configuration cluster."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the cluster."""
        super().__init__(*args, **kwargs)

        self._CONSTANT_ATTRIBUTES = {
            BATTERY_QUANTITY_ATTR: 2,
            BATTERY_SIZE_ATTR: BatterySize.CR2450,
        }

    def handle_cluster_general_request(
        self,
        hdr: ZCLHeader,
        args: list,
        *,
        dst_addressing: AddressingMode | None = None,
    ) -> None:
        """Ignore reports from the device on this cluster."""
        if hdr.command_id == foundation.GeneralCommand.Report_Attributes:
            if not hdr.frame_control.disable_default_response:
                self.send_default_rsp(hdr, foundation.Status.SUCCESS)
            return
        super().handle_cluster_general_request(hdr, args, dst_addressing=dst_addressing)


class FP300ManufacturerCluster(CustomCluster):
    """Aqara FP300 manufacturer cluster."""

    cluster_id = 0xFCC0
    ep_attribute = "fp300_manu"

    class AttributeDefs(BaseAttributeDefs):
        """Attribute definitions."""

        presence: Final = ZCLAttributeDef(
            id=0x0142,
            type=t.Bool,
            zcl_type=DataTypeId.uint8,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        presence_detection_mode: Final = ZCLAttributeDef(
            id=0x0199,
            type=PresenceDetectionMode,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        absence_delay: Final = ZCLAttributeDef(
            id=0x0197,
            type=t.uint32_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        presence_sensitivity: Final = ZCLAttributeDef(
            id=0x010C,
            type=PresenceSensitivity,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        detection_range: Final = ZCLAttributeDef(
            id=0x019A,
            type=t.LVBytes,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        pir_detection_interval: Final = ZCLAttributeDef(
            id=0x014F,
            type=t.uint16_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        pir_detection: Final = ZCLAttributeDef(
            id=0x014D,
            type=t.Bool,
            zcl_type=DataTypeId.uint8,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        ai_interference_source_self_identification: Final = ZCLAttributeDef(
            id=0x015E,
            type=t.uint8_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        ai_adaptive_sensitivity: Final = ZCLAttributeDef(
            id=0x015D,
            type=t.uint8_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        ai_spatial_learning: Final = ZCLAttributeDef(
            id=0x0157,
            type=t.uint8_t,
            access="wp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        light_report_threshold: Final = ZCLAttributeDef(
            id=0x0195,
            type=t.uint16_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        light_sampling: Final = ZCLAttributeDef(
            id=0x0192,
            type=SamplingFrequency,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        light_report_mode: Final = ZCLAttributeDef(
            id=0x0196,
            type=ReportMode,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        light_sampling_period: Final = ZCLAttributeDef(
            id=0x0193,
            type=t.uint32_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        light_report_interval: Final = ZCLAttributeDef(
            id=0x0194,
            type=t.uint32_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        temperature_humidity_sampling: Final = ZCLAttributeDef(
            id=0x0170,
            type=SamplingFrequency,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        temperature_humidity_sampling_period: Final = ZCLAttributeDef(
            id=0x0162,
            type=t.uint32_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        temperature_report_mode: Final = ZCLAttributeDef(
            id=0x0165,
            type=ReportMode,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        temperature_report_threshold: Final = ZCLAttributeDef(
            id=0x0164,
            type=t.uint16_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        temperature_report_interval: Final = ZCLAttributeDef(
            id=0x0163,
            type=t.uint32_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        humidity_report_mode: Final = ZCLAttributeDef(
            id=0x016C,
            type=ReportMode,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        humidity_report_threshold: Final = ZCLAttributeDef(
            id=0x016B,
            type=t.uint16_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        humidity_report_interval: Final = ZCLAttributeDef(
            id=0x016A,
            type=t.uint32_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        led_indicator_off_period: Final = ZCLAttributeDef(
            id=0x0203,
            type=t.Bool,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        led_indicator_off_time: Final = ZCLAttributeDef(
            id=0x023E,
            type=t.uint32_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        target_distance: Final = ZCLAttributeDef(
            id=0x015F,
            type=t.uint32_t,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        track_target_distance: Final = ZCLAttributeDef(
            id=0x0198,
            type=t.uint8_t,
            access="wp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        restart_device: Final = ZCLAttributeDef(
            id=0x00E8,
            type=t.Bool,
            access="wp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        aqara_heartbeat: Final = ZCLAttributeDef(
            id=0x00F7,
            type=t.LVBytes,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the FP300 manufacturer cluster."""
        super().__init__(*args, **kwargs)

        for event_type in (AttributeReadEvent, AttributeReportedEvent):
            self.on_event(event_type.event_type, self._handle_attribute_event)

    def _handle_attribute_event(
        self, event: AttributeReadEvent | AttributeReportedEvent
    ) -> None:
        """Handle attribute events."""
        if event.attribute_id == self.AttributeDefs.aqara_heartbeat.id:
            self._handle_heartbeat(
                event.value,
                is_reported_event=isinstance(event, AttributeReportedEvent),
            )

    def _handle_heartbeat(self, data: bytes, is_reported_event: bool) -> None:
        """Parse FP300 heartbeat and update attributes."""

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

            if tag == 0x18:
                self.endpoint.power.battery_percent_reported(value)
            elif tag == 0x17:
                self.endpoint.power.battery_reported(value)
            elif is_reported_event:
                if tag == 0x64:
                    self.update_attribute(self.AttributeDefs.presence.id, value)
                elif tag == 0x67:
                    self.update_attribute(self.AttributeDefs.pir_detection.id, value)

    async def apply_custom_configuration(self, *args, **kwargs):
        """Read FP300 attributes."""
        try:
            await self.read_attributes(
                [
                    attr.id
                    for attr in self.AttributeDefs
                    if attr.access and foundation.ZCLAttributeAccess.Read in attr.access
                ]
            )
            for cluster in (
                self.endpoint.illuminance,
                self.endpoint.temperature,
                self.endpoint.humidity,
            ):
                await cluster.read_attributes(
                    [cluster.AttributeDefs.measured_value.id]
                )
        except Exception as exc:  # noqa: BLE001
            self.debug("Failed to read attributes: %s", exc, exc_info=True)


class FP300DetectionRangeNumber(NumberConfigurationEntity):
    """FP300 detection range number entity."""

    _attribute_name = FP300ManufacturerCluster.AttributeDefs.detection_range.name

    @property
    def native_value(self) -> float | None:
        """Return the detection range in meters."""
        value = self._cluster.get(self._attribute_name)
        if value is None:
            return None

        mask = int.from_bytes(value[2:5], "little")
        return mask.bit_length() * self._multiplier

    async def async_set_native_value(self, value: float) -> None:
        """Write the detection range in meters."""
        steps = round(value / self._multiplier)
        mask = (1 << steps) - 1
        encoded_value = t.LVBytes(b"\x00\x03" + mask.to_bytes(3, "little"))

        await write_attributes_safe(
            self._cluster, {self._attribute_name: encoded_value}
        )
        self.maybe_emit_state_changed_event()


class FP300LedIndicatorOffTimeNumber(NumberConfigurationEntity):
    """FP300 LED indicator off time number entity."""

    _attribute_name = FP300ManufacturerCluster.AttributeDefs.led_indicator_off_time.name

    def __init__(self, *args: Any, bit_shift: int, **kwargs: Any) -> None:
        """Initialize the LED indicator off time entity."""
        self._bit_shift = bit_shift
        super().__init__(*args, **kwargs)

    @property
    def native_value(self) -> float | None:
        """Return the configured hour."""
        value = self._cluster.get(self._attribute_name)
        if value is None:
            return None

        return (value >> self._bit_shift) & 0xFF

    async def async_set_native_value(self, value: float) -> None:
        """Write the configured hour."""
        current_value = self._cluster.get(self._attribute_name)
        encoded_value = (
            (current_value & ~(0xFF << self._bit_shift))
            | (int(value) << self._bit_shift)
        ) & 0x00FF00FF

        await write_attributes_safe(
            self._cluster, {self._attribute_name: encoded_value}
        )
        self.maybe_emit_state_changed_event()


(
    QuirkBuilder("Aqara", "lumi.sensor_occupy.agl8")
    .friendly_name(manufacturer="Aqara", model="Presence Multi-Sensor FP300")
    .replaces(FP300ManufacturerCluster)
    .replaces(FP300PowerConfigurationCluster)
    .binary_sensor(
        attribute_name="presence",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        entity_type=EntityType.STANDARD,
        primary=True,
        fallback_name="Occupancy",
    )
    .enum(
        attribute_name="presence_detection_mode",
        enum_class=PresenceDetectionMode,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="presence_detection_mode",
        fallback_name="Presence detection mode",
    )
    .number(
        attribute_name="absence_delay",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=1,
        max_value=300,
        step=1,
        unit=UnitOfTime.SECONDS,
        translation_key="absence_delay",
        fallback_name="Absence delay",
    )
    .enum(
        attribute_name="presence_sensitivity",
        enum_class=PresenceSensitivity,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="presence_sensitivity",
        fallback_name="Presence sensitivity",
    )
    .adds_entity(
        FP300DetectionRangeNumber,
        endpoint_id=1,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DISTANCE,
        min_value=0.0,
        max_value=6.0,
        step=0.25,
        multiplier=0.25,
        unit=UnitOfLength.METERS,
        mode="slider",
        unique_id_suffix="detection_range",
        translation_key="detection_range",
        fallback_name="Detection range",
    )
    .number(
        attribute_name="pir_detection_interval",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=2,
        max_value=300,
        step=1,
        unit=UnitOfTime.SECONDS,
        translation_key="pir_detection_interval",
        fallback_name="PIR detection interval",
    )
    .binary_sensor(
        attribute_name="pir_detection",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=BinarySensorDeviceClass.MOTION,
        initially_disabled=True,
        fallback_name="PIR detection",
    )
    .switch(
        attribute_name="ai_interference_source_self_identification",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="ai_interference_source_self_identification",
        fallback_name="AI interference source self-identification",
    )
    .switch(
        attribute_name="ai_adaptive_sensitivity",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="ai_adaptive_sensitivity",
        fallback_name="AI adaptive sensitivity",
    )
    .write_attr_button(
        attribute_name="ai_spatial_learning",
        attribute_value=1,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="ai_spatial_learning",
        fallback_name="AI spatial learning",
    )
    .number(
        attribute_name="light_report_threshold",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        min_value=3.0,
        max_value=20.0,
        step=0.5,
        multiplier=0.01,
        unit=PERCENTAGE,
        translation_key="light_report_threshold",
        fallback_name="Light report threshold",
    )
    .enum(
        attribute_name="light_sampling",
        enum_class=SamplingFrequency,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="light_sampling",
        fallback_name="Light sampling",
    )
    .enum(
        attribute_name="light_report_mode",
        enum_class=ReportMode,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="light_report_mode",
        fallback_name="Light report mode",
    )
    .number(
        attribute_name="light_sampling_period",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=0.5,
        max_value=3600,
        step=0.5,
        multiplier=0.001,
        unit=UnitOfTime.SECONDS,
        translation_key="light_sampling_period",
        fallback_name="Light sampling period",
    )
    .number(
        attribute_name="light_report_interval",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=20,
        max_value=3600,
        step=1,
        multiplier=0.001,
        unit=UnitOfTime.SECONDS,
        translation_key="light_report_interval",
        fallback_name="Light report interval",
    )
    .enum(
        attribute_name="temperature_humidity_sampling",
        enum_class=SamplingFrequency,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="temperature_humidity_sampling",
        fallback_name="Temperature and humidity sampling",
    )
    .number(
        attribute_name="temperature_humidity_sampling_period",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=0.5,
        max_value=3600,
        step=0.5,
        multiplier=0.001,
        unit=UnitOfTime.SECONDS,
        translation_key="temperature_humidity_sampling_period",
        fallback_name="Temperature and humidity sampling period",
    )
    .enum(
        attribute_name="temperature_report_mode",
        enum_class=ReportMode,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="temperature_report_mode",
        fallback_name="Temperature report mode",
    )
    .number(
        attribute_name="temperature_report_threshold",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        min_value=0.2,
        max_value=3.0,
        step=0.1,
        multiplier=0.01,
        unit=UnitOfTemperature.CELSIUS,
        translation_key="temperature_report_threshold",
        fallback_name="Temperature report threshold",
    )
    .number(
        attribute_name="temperature_report_interval",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=600,
        max_value=3600,
        step=1,
        multiplier=0.001,
        unit=UnitOfTime.SECONDS,
        translation_key="temperature_report_interval",
        fallback_name="Temperature report interval",
    )
    .enum(
        attribute_name="humidity_report_mode",
        enum_class=ReportMode,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="humidity_report_mode",
        fallback_name="Humidity report mode",
    )
    .number(
        attribute_name="humidity_report_threshold",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.HUMIDITY,
        min_value=2.0,
        max_value=15.0,
        step=0.5,
        multiplier=0.01,
        unit=PERCENTAGE,
        translation_key="humidity_report_threshold",
        fallback_name="Humidity report threshold",
    )
    .number(
        attribute_name="humidity_report_interval",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=NumberDeviceClass.DURATION,
        min_value=600,
        max_value=3600,
        step=1,
        multiplier=0.001,
        unit=UnitOfTime.SECONDS,
        translation_key="humidity_report_interval",
        fallback_name="Humidity report interval",
    )
    .switch(
        attribute_name="led_indicator_off_period",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="led_indicator_off_period",
        fallback_name="LED indicator off period",
    )
    .adds_entity(
        FP300LedIndicatorOffTimeNumber,
        endpoint_id=1,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        bit_shift=0,
        min_value=0,
        max_value=23,
        step=1,
        mode="box",
        unique_id_suffix="led_indicator_off_start_time",
        translation_key="led_indicator_off_start_time",
        fallback_name="LED indicator off start time",
    )
    .adds_entity(
        FP300LedIndicatorOffTimeNumber,
        endpoint_id=1,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        bit_shift=16,
        min_value=0,
        max_value=23,
        step=1,
        mode="box",
        unique_id_suffix="led_indicator_off_end_time",
        translation_key="led_indicator_off_end_time",
        fallback_name="LED indicator off end time",
    )
    .sensor(
        attribute_name="target_distance",
        cluster_id=FP300ManufacturerCluster.cluster_id,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfLength.METERS,
        divisor=100,
        entity_type=EntityType.DIAGNOSTIC,
        translation_key="target_distance",
        fallback_name="Target distance",
    )
    .write_attr_button(
        attribute_name="track_target_distance",
        attribute_value=1,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="track_target_distance",
        fallback_name="Track target distance",
    )
    .write_attr_button(
        attribute_name="restart_device",
        attribute_value=1,
        cluster_id=FP300ManufacturerCluster.cluster_id,
        translation_key="restart",
        fallback_name="Restart",
    )
    .skip_configuration()
    .add_to_registry()
)
