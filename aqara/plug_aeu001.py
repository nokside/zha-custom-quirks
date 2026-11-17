"""Quirk for Aqara Wall Outlet H2 EU lumi.plug.aeu001 / WP-P01D."""

from typing import Any, Final

from zha.application.helpers import write_attributes_safe
from zha.application.platforms.number import NumberConfigurationEntity
from zha.application.platforms.sensor import (
    ElectricalMeasurementApparentPower,
    ElectricalMeasurementFrequency,
    ElectricalMeasurementPowerFactor,
    SmartEnergyMetering,
)
from zigpy import types as t
from zigpy.zcl import AttributeReadEvent, AttributeReportedEvent, foundation
from zigpy.zcl.clusters.general import DeviceTemperature, OnOff
from zigpy.zcl.clusters.homeautomation import ElectricalMeasurement
from zigpy.zcl.clusters.measurement import TemperatureMeasurement
from zigpy.zcl.clusters.smartenergy import Metering
from zigpy.zcl.foundation import BaseAttributeDefs, DataTypeId, ZCLAttributeDef

from zhaquirks import CustomCluster
from zhaquirks.builder import EntityFilter, EntityType, QuirkBuilder, UnitOfPower
from zhaquirks.xiaomi import (
    AnalogInputCluster,
    DeviceTemperatureCluster,
    ElectricalMeasurementCluster,
    MeteringCluster,
)

AQARA_MFG_CODE: Final = 0x115F


class PowerOnBehavior(t.enum8):
    """Relay state after power loss."""

    On = 0x00
    Previous = 0x01
    Off = 0x02
    Inverted = 0x03


class WallOutletH2EUManufacturerCluster(CustomCluster):
    """Aqara Wall Outlet H2 EU manufacturer cluster."""

    cluster_id = 0xFCC0
    ep_attribute = "wall_outlet_h2_eu_manu"

    class AttributeDefs(BaseAttributeDefs):
        """Attribute definitions."""

        aqara_heartbeat: Final = ZCLAttributeDef(
            id=0x00F7,
            type=t.LVBytes,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        button_lock: Final = ZCLAttributeDef(
            id=0x0200,
            type=t.uint8_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        charging_protection: Final = ZCLAttributeDef(
            id=0x0202,
            type=t.Bool,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        led_indicator: Final = ZCLAttributeDef(
            id=0x0203,
            type=t.Bool,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        charging_protection_limit: Final = ZCLAttributeDef(
            id=0x0206,
            type=t.Single,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        overload_protection: Final = ZCLAttributeDef(
            id=0x020B,
            type=t.Single,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        power_on_behavior: Final = ZCLAttributeDef(
            id=0x0517,
            type=PowerOnBehavior,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init."""
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
        """Parse Wall Outlet H2 EU heartbeat and update attributes."""
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

            if tag == 0x03:
                self.endpoint.device_temperature.update_attribute(
                    DeviceTemperature.AttributeDefs.current_temperature.id,
                    value * 100,
                )
            elif tag == 0x95:
                self.endpoint.smartenergy_metering.update_attribute(
                    Metering.AttributeDefs.current_summ_delivered.id,
                    round(value * 1000),
                )
            elif tag == 0x96:
                self.endpoint.electrical_measurement.update_attribute(
                    ElectricalMeasurement.AttributeDefs.rms_voltage.id,
                    value * 0.1,
                )
            elif tag == 0x97:
                self.endpoint.electrical_measurement.update_attribute(
                    ElectricalMeasurement.AttributeDefs.rms_current.id,
                    value,
                )
            elif is_reported_event:
                if tag == 0x64:
                    self.endpoint.device.endpoints[2].on_off.update_attribute(
                        OnOff.AttributeDefs.on_off.id,
                        bool(value),
                    )
                elif tag == 0x98:
                    self.endpoint.electrical_measurement.update_attribute(
                        ElectricalMeasurement.AttributeDefs.active_power.id,
                        round(value * 10),
                    )

    async def apply_custom_configuration(self, *args: Any, **kwargs: Any) -> None:
        """Read Wall Outlet H2 EU attributes."""
        try:
            await self.read_attributes([attr.id for attr in self.AttributeDefs])
            await self.endpoint.device.endpoints[21].analog_input.read_attributes(
                [AnalogInputCluster.AttributeDefs.present_value.id]
            )
        except Exception as exc:  # noqa: BLE001
            self.debug("Failed to read attributes: %s", exc, exc_info=True)


class WallOutletH2EUElectricalMeasurementCluster(ElectricalMeasurementCluster):
    """Wall Outlet H2 EU electrical measurement cluster."""

    _VALID_ATTRIBUTES = {ElectricalMeasurementCluster.AttributeDefs.rms_current.id}

    _CONSTANT_ATTRIBUTES = {
        **ElectricalMeasurementCluster._CONSTANT_ATTRIBUTES,
        ElectricalMeasurementCluster.AttributeDefs.ac_current_multiplier.id: 1,
        ElectricalMeasurementCluster.AttributeDefs.ac_current_divisor.id: 1000,
    }


class WallOutletH2EUDeviceTemperatureCluster(DeviceTemperatureCluster):
    """Wall Outlet H2 EU device temperature cluster."""

    _VALID_ATTRIBUTES = {DeviceTemperature.AttributeDefs.current_temperature.id}


class ChargingProtectionLimitNumber(NumberConfigurationEntity):
    """Wall Outlet H2 EU charging protection limit number entity."""

    _attribute_name = (
        WallOutletH2EUManufacturerCluster.AttributeDefs.charging_protection_limit.name
    )

    @property
    def native_value(self) -> float | None:
        """Return the limit rounded to the supported precision."""
        value = super().native_value
        return None if value is None else round(value, 1)

    async def async_set_native_value(self, value: float) -> None:
        """Write a floating-point limit to the device."""
        await write_attributes_safe(self._cluster, {self._attribute_name: float(value)})
        self.maybe_emit_state_changed_event()


(
    QuirkBuilder("Aqara", "lumi.plug.aeu001")
    .friendly_name(manufacturer="Aqara", model="Wall Outlet H2 EU")
    .removes(TemperatureMeasurement.cluster_id)
    .removes_entity(
        EntityFilter(endpoint_id=2, cluster_id=OnOff.cluster_id),
        EntityFilter(entity_cls=ElectricalMeasurementPowerFactor),
        EntityFilter(entity_cls=ElectricalMeasurementApparentPower),
        EntityFilter(entity_cls=ElectricalMeasurementFrequency),
        EntityFilter(entity_cls=SmartEnergyMetering),
    )
    .adds(WallOutletH2EUDeviceTemperatureCluster)
    .replaces(WallOutletH2EUManufacturerCluster)
    .replaces(WallOutletH2EUElectricalMeasurementCluster)
    .replaces(MeteringCluster)
    .replaces(AnalogInputCluster, endpoint_id=21)
    .adds_entity(
        ChargingProtectionLimitNumber,
        endpoint_id=1,
        cluster_id=WallOutletH2EUManufacturerCluster.cluster_id,
        min_value=0.1,
        max_value=2.0,
        step=0.1,
        unit=UnitOfPower.WATT,
        entity_type=EntityType.CONFIG,
        unique_id_suffix="charging_protection_limit",
        translation_key="charging_protection_limit",
        fallback_name="Charging protection limit",
    )
    .switch(
        attribute_name="button_lock",
        cluster_id=WallOutletH2EUManufacturerCluster.cluster_id,
        force_inverted=True,
        translation_key="child_lock",
        fallback_name="Child lock",
    )
    .switch(
        attribute_name="charging_protection",
        cluster_id=WallOutletH2EUManufacturerCluster.cluster_id,
        translation_key="charging_protection",
        fallback_name="Charging protection",
    )
    .switch(
        attribute_name="led_indicator",
        cluster_id=WallOutletH2EUManufacturerCluster.cluster_id,
        translation_key="led_indicator",
        fallback_name="LED indicator",
    )
    .enum(
        attribute_name="power_on_behavior",
        enum_class=PowerOnBehavior,
        cluster_id=WallOutletH2EUManufacturerCluster.cluster_id,
        translation_key="power_on_behavior",
        fallback_name="Power on behavior",
    )
    .number(
        attribute_name="overload_protection",
        cluster_id=WallOutletH2EUManufacturerCluster.cluster_id,
        min_value=100,
        max_value=3840,
        step=1,
        unit=UnitOfPower.WATT,
        translation_key="overload_protection",
        fallback_name="Overload protection",
    )
    .skip_configuration()
    .add_to_registry()
)
