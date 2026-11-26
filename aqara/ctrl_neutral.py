"""Quirk for Aqara Wall Switch (No Neutral) QBKG03LM and QBKG04LM."""

from typing import Any, Final

from zha.application import Platform
from zigpy import types as t
from zigpy.profiles import zha
from zigpy.typing import AddressingMode
from zigpy.zcl import AttributeReportedEvent, ClusterType, foundation
from zigpy.zcl.clusters.general import (
    Basic,
    DeviceTemperature,
    Identify,
    OnOff,
)
from zigpy.zcl.foundation import ZCLAttributeDef, ZCLHeader
from zigpy.zdo.types import NodeDescriptor

from zhaquirks import CustomCluster, LocalDataCluster
from zhaquirks.builder import (
    ButtonEvent,
    ButtonEventType,
    EntityFilter,
    QuirkBuilder,
)
from zhaquirks.const import (
    BUTTON_1,
    BUTTON_2,
    COMMAND,
    DOUBLE_PRESS,
    ENDPOINT_ID,
    LONG_PRESS,
    LONG_RELEASE,
    SHORT_PRESS,
    ZHA_SEND_EVENT,
)
from zhaquirks.xiaomi import LUMI, OnOffCluster
from zhaquirks.xiaomi.aqara.opple_remote import (
    COMMAND_1_DOUBLE,
    COMMAND_1_HOLD,
    COMMAND_1_RELEASE,
    COMMAND_1_SINGLE,
    COMMAND_2_DOUBLE,
    COMMAND_2_HOLD,
    COMMAND_2_RELEASE,
    COMMAND_2_SINGLE,
    COMMAND_3_DOUBLE,
    COMMAND_3_HOLD,
    COMMAND_3_RELEASE,
    COMMAND_3_SINGLE,
)


AQARA_MFG_CODE: Final = 0x115F
BOTH_BUTTONS = "both_buttons"


class SingleRockerOperationMode(t.enum8):
    """Single-rocker operation mode."""

    Control_relay = 0x12
    Decoupled = 0xFE


class DoubleRockerOperationMode(t.enum8):
    """Double-rocker operation mode."""

    Control_left_relay = 0x12
    Control_right_relay = 0x22
    Decoupled = 0xFE


class CtrlNeutralBasicCluster(CustomCluster, Basic):
    """Aqara wall switch basic cluster."""

    class AttributeDefs(Basic.AttributeDefs):
        """Attribute definitions."""

        operation_mode_left: Final = ZCLAttributeDef(
            id=0xFF22,
            type=t.uint8_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        operation_mode_right: Final = ZCLAttributeDef(
            id=0xFF23,
            type=t.uint8_t,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        reset_request: Final = ZCLAttributeDef(
            id=0xFFF0,
            type=t.LVBytes,
            access="rwp",
            manufacturer_code=AQARA_MFG_CODE,
        )
        aqara_heartbeat: Final = ZCLAttributeDef(
            id=0xFF01,
            type=t.LVBytes,
            access="rp",
            manufacturer_code=AQARA_MFG_CODE,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the wall switch basic cluster."""
        super().__init__(*args, **kwargs)
        self.on_event(AttributeReportedEvent.event_type, self._handle_attribute_report)

    def deserialize(self, data):
        """Normalize Aqara heartbeat data type."""
        hdr, payload = ZCLHeader.deserialize(data)

        if (
            hdr.frame_control.frame_type == foundation.FrameType.GLOBAL_COMMAND
            and hdr.command_id == foundation.GeneralCommand.Report_Attributes
            and len(payload) >= 3
        ):
            attr_id, remaining_payload = t.uint16_t.deserialize(payload)
            if (
                attr_id == self.AttributeDefs.aqara_heartbeat.id
                and remaining_payload[:1] == b"\x42"
            ):
                payload = payload[:2] + b"\x41" + payload[3:]

        return super().deserialize(hdr.serialize() + payload)

    async def apply_custom_configuration(self, *args, **kwargs):
        """Read Aqara wall switch attributes."""
        try:
            await self.read_attributes([self.AttributeDefs.operation_mode_left.id])
            await self.endpoint.device_temperature.read_attributes(
                [DeviceTemperature.AttributeDefs.current_temperature.id]
            )
            await self.endpoint.device.endpoints[2].on_off.read_attributes(
                [OnOff.AttributeDefs.on_off.id]
            )

            if self.endpoint.device.model == "lumi.ctrl_neutral2":
                await self.read_attributes([self.AttributeDefs.operation_mode_right.id])
                await self.endpoint.device.endpoints[3].on_off.read_attributes(
                    [OnOff.AttributeDefs.on_off.id]
                )
        except Exception as exc:  # noqa: BLE001
            self.debug("Failed to read attributes: %s", exc, exc_info=True)

    def _handle_attribute_report(self, event: AttributeReportedEvent) -> None:
        """Handle Aqara wall switch attribute reports."""
        if event.attribute_id == self.AttributeDefs.reset_request.id and bytes(
            event.value
        ).startswith(bytes.fromhex("AA 10 05 41 87")):
            # Prevent the device from resetting on a long button press.
            self.create_catching_task(
                self.write_attributes(
                    {
                        self.AttributeDefs.reset_request: bytes.fromhex(
                            "AA 10 05 41 47 01 01 10 01"
                        )
                    },
                    update_cache=False,
                )
            )
        elif event.attribute_id == self.AttributeDefs.aqara_heartbeat.id:
            self._handle_heartbeat(event.value)

    def _handle_heartbeat(self, data: bytes) -> None:
        """Parse Aqara wall switch heartbeat and update attributes."""
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
                    value,
                )
            elif tag == 0x64:
                self.endpoint.device.endpoints[2].on_off.update_attribute(
                    OnOff.AttributeDefs.on_off.id,
                    value,
                )
            elif tag == 0x65 and self.endpoint.device.model == "lumi.ctrl_neutral2":
                self.endpoint.device.endpoints[3].on_off.update_attribute(
                    OnOff.AttributeDefs.on_off.id,
                    value,
                )


class CtrlNeutralButtonOnOff(LocalDataCluster, OnOff):
    """Local OnOff cluster for wall switch button events."""

    PRESS_TYPES: Final = {
        (0, 1): (COMMAND_1_SINGLE, COMMAND_2_SINGLE, COMMAND_3_SINGLE),
        (2,): (COMMAND_1_DOUBLE, COMMAND_2_DOUBLE, COMMAND_3_DOUBLE),
        (0,): (COMMAND_1_HOLD, COMMAND_2_HOLD, COMMAND_3_HOLD),
        (1,): (COMMAND_1_RELEASE, COMMAND_2_RELEASE, COMMAND_3_RELEASE),
    }

    def handle_cluster_general_request(
        self,
        hdr: ZCLHeader,
        args: list,
        *,
        dst_addressing: AddressingMode | None = None,
    ) -> None:
        """Handle cluster general requests."""
        if hdr.command_id == foundation.GeneralCommand.Report_Attributes:
            values = tuple(
                int(attr.value.value)
                for attr in args.attribute_reports
                if attr.attrid == OnOff.AttributeDefs.on_off.id
            )

            if commands := self.PRESS_TYPES.get(values):
                self.listener_event(
                    ZHA_SEND_EVENT,
                    commands[self.endpoint.endpoint_id - 4],
                    {},
                )

        super().handle_cluster_general_request(hdr, args, dst_addressing=dst_addressing)


class CtrlNeutralDeviceTemperatureCluster(CustomCluster, DeviceTemperature):
    """Normalize device temperature values to hundredths of a degree."""

    def _update_attribute(self, attrid, value):
        """Normalize temperature reports."""
        if attrid == self.AttributeDefs.current_temperature.id and value is not None:
            value *= 100
        super()._update_attribute(attrid, value)


ctrl_neutral = (
    QuirkBuilder()
    .node_descriptor(
        NodeDescriptor(0x02, 0x40, 0x84, 0x1037, 0x7F, 0x0064, 0x0000, 0x0064, 0x00)
    )
    .replaces(CtrlNeutralBasicCluster)
    .replaces(OnOffCluster, endpoint_id=2)
    .replaces(CtrlNeutralButtonOnOff, endpoint_id=4)
    .replaces(CtrlNeutralDeviceTemperatureCluster)
    .removes_entity(
        EntityFilter(
            endpoint_id=4,
            cluster_id=OnOff.cluster_id,
            platform=Platform.SWITCH,
        ),
        EntityFilter(
            endpoint_id=6,
            cluster_id=OnOff.cluster_id,
            platform=Platform.SWITCH,
        ),
    )
    .replaces_endpoint(2, device_type=zha.DeviceType.ON_OFF_SWITCH)
    .removes(Identify.cluster_id)
    .skip_configuration()
    .device_automation_triggers(
        {
            (SHORT_PRESS, BUTTON_1): {ENDPOINT_ID: 4, COMMAND: COMMAND_1_SINGLE},
            (DOUBLE_PRESS, BUTTON_1): {ENDPOINT_ID: 4, COMMAND: COMMAND_1_DOUBLE},
            (LONG_PRESS, BUTTON_1): {ENDPOINT_ID: 4, COMMAND: COMMAND_1_HOLD},
            (LONG_RELEASE, BUTTON_1): {ENDPOINT_ID: 4, COMMAND: COMMAND_1_RELEASE},
        }
    )
)


ctrl_neutral1_quirk = (
    ctrl_neutral.clone()
    .applies_to(LUMI, "lumi.ctrl_neutral1")
    .friendly_name(
        manufacturer="Aqara", model="Wall Switch (No Neutral, Single Rocker)"
    )
    .removes_entity(
        EntityFilter(
            endpoint_id=3,
            cluster_id=OnOff.cluster_id,
            platform=Platform.LIGHT,
        ),
        EntityFilter(
            endpoint_id=5,
            cluster_id=OnOff.cluster_id,
            platform=Platform.SWITCH,
        ),
    )
    .enum(
        attribute_name="operation_mode_left",
        enum_class=SingleRockerOperationMode,
        cluster_id=Basic.cluster_id,
        translation_key="relay_operation_mode",
        fallback_name="Operation mode",
    )
    .button_event(
        events=[
            ButtonEvent(
                event_type=ButtonEventType.SINGLE_PRESS,
                trigger=(SHORT_PRESS, BUTTON_1),
            ),
            ButtonEvent(
                event_type=ButtonEventType.MULTI_PRESS,
                trigger=(DOUBLE_PRESS, BUTTON_1),
                press_count=2,
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_START,
                trigger=(LONG_PRESS, BUTTON_1),
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_END,
                trigger=(LONG_RELEASE, BUTTON_1),
            ),
        ],
        cluster_id=OnOff.cluster_id,
        cluster_type=ClusterType.Server,
        endpoint_id=4,
        unique_id_suffix="button",
        translation_key="button",
        fallback_name="Button",
    )
    .add_to_registry()
)


ctrl_neutral2_quirk = (
    ctrl_neutral.clone()
    .applies_to(LUMI, "lumi.ctrl_neutral2")
    .friendly_name(
        manufacturer="Aqara", model="Wall Switch (No Neutral, Double Rocker)"
    )
    .removes_entity(
        EntityFilter(
            endpoint_id=5,
            cluster_id=OnOff.cluster_id,
            platform=Platform.SWITCH,
        ),
    )
    .replaces(OnOffCluster, endpoint_id=3)
    .replaces(CtrlNeutralButtonOnOff, endpoint_id=5)
    .replaces(CtrlNeutralButtonOnOff, endpoint_id=6)
    .replaces_endpoint(3, device_type=zha.DeviceType.ON_OFF_SWITCH)
    .device_automation_triggers(
        {
            (SHORT_PRESS, BUTTON_2): {ENDPOINT_ID: 5, COMMAND: COMMAND_2_SINGLE},
            (DOUBLE_PRESS, BUTTON_2): {ENDPOINT_ID: 5, COMMAND: COMMAND_2_DOUBLE},
            (LONG_PRESS, BUTTON_2): {ENDPOINT_ID: 5, COMMAND: COMMAND_2_HOLD},
            (LONG_RELEASE, BUTTON_2): {ENDPOINT_ID: 5, COMMAND: COMMAND_2_RELEASE},
            (SHORT_PRESS, BOTH_BUTTONS): {ENDPOINT_ID: 6, COMMAND: COMMAND_3_SINGLE},
            (DOUBLE_PRESS, BOTH_BUTTONS): {ENDPOINT_ID: 6, COMMAND: COMMAND_3_DOUBLE},
            (LONG_PRESS, BOTH_BUTTONS): {ENDPOINT_ID: 6, COMMAND: COMMAND_3_HOLD},
            (LONG_RELEASE, BOTH_BUTTONS): {ENDPOINT_ID: 6, COMMAND: COMMAND_3_RELEASE},
        }
    )
    .enum(
        attribute_name="operation_mode_left",
        enum_class=DoubleRockerOperationMode,
        cluster_id=Basic.cluster_id,
        translation_key="relay_operation_mode_left",
        fallback_name="Operation mode left",
    )
    .enum(
        attribute_name="operation_mode_right",
        enum_class=DoubleRockerOperationMode,
        cluster_id=Basic.cluster_id,
        translation_key="relay_operation_mode_right",
        fallback_name="Operation mode right",
    )
    .button_event(
        events=[
            ButtonEvent(
                event_type=ButtonEventType.SINGLE_PRESS,
                trigger=(SHORT_PRESS, BUTTON_1),
            ),
            ButtonEvent(
                event_type=ButtonEventType.MULTI_PRESS,
                trigger=(DOUBLE_PRESS, BUTTON_1),
                press_count=2,
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_START,
                trigger=(LONG_PRESS, BUTTON_1),
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_END,
                trigger=(LONG_RELEASE, BUTTON_1),
            ),
        ],
        cluster_id=OnOff.cluster_id,
        cluster_type=ClusterType.Server,
        endpoint_id=4,
        unique_id_suffix="button_1",
        translation_key="button_numbered",
        translation_placeholders={"number": "1"},
        fallback_name="Button 1",
    )
    .button_event(
        events=[
            ButtonEvent(
                event_type=ButtonEventType.SINGLE_PRESS,
                trigger=(SHORT_PRESS, BUTTON_2),
            ),
            ButtonEvent(
                event_type=ButtonEventType.MULTI_PRESS,
                trigger=(DOUBLE_PRESS, BUTTON_2),
                press_count=2,
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_START,
                trigger=(LONG_PRESS, BUTTON_2),
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_END,
                trigger=(LONG_RELEASE, BUTTON_2),
            ),
        ],
        cluster_id=OnOff.cluster_id,
        cluster_type=ClusterType.Server,
        endpoint_id=5,
        unique_id_suffix="button_2",
        translation_key="button_numbered",
        translation_placeholders={"number": "2"},
        fallback_name="Button 2",
    )
    .button_event(
        events=[
            ButtonEvent(
                event_type=ButtonEventType.SINGLE_PRESS,
                trigger=(SHORT_PRESS, BOTH_BUTTONS),
            ),
            ButtonEvent(
                event_type=ButtonEventType.MULTI_PRESS,
                trigger=(DOUBLE_PRESS, BOTH_BUTTONS),
                press_count=2,
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_START,
                trigger=(LONG_PRESS, BOTH_BUTTONS),
            ),
            ButtonEvent(
                event_type=ButtonEventType.LONG_PRESS_END,
                trigger=(LONG_RELEASE, BOTH_BUTTONS),
            ),
        ],
        cluster_id=OnOff.cluster_id,
        cluster_type=ClusterType.Server,
        endpoint_id=6,
        unique_id_suffix="button_both",
        translation_key="both_buttons",
        fallback_name="Both buttons",
    )
    .add_to_registry()
)
