"""Quirk for SONOFF ZBMINIL2."""

from typing import Final

from zigpy import types as t
from zigpy.zcl import ClusterType
from zigpy.zcl.clusters.general import KeepAlive, PowerConfiguration
from zigpy.zcl.foundation import BaseAttributeDefs, DataTypeId, ZCLAttributeDef
from zigpy.zdo.types import NodeDescriptor

from zhaquirks import CustomCluster
from zhaquirks.builder import EntityFilter, QuirkBuilder


class ExternalTriggerMode(t.enum8):
    """External switch trigger mode."""

    Edge = 0x00
    Pulse = 0x01


class SonoffEwelinkCluster(CustomCluster):
    """Sonoff/eWeLink cluster."""

    cluster_id = 0xFC11

    class AttributeDefs(BaseAttributeDefs):
        """Attribute definitions."""

        external_trigger_mode: Final = ZCLAttributeDef(
            id=0x0016,
            type=ExternalTriggerMode,
            zcl_type=DataTypeId.uint8,
            access="rwp",
            manufacturer_code=None,
        )


zbminil2_quirk = (
    QuirkBuilder("SONOFF", "ZBMINIL2")
    .node_descriptor(
        NodeDescriptor(0x02, 0x40, 0x84, 0x1286, 0x52, 0x0400, 0x2C00, 0x0400, 0x00)
    )
    .removes_entity(
        EntityFilter(endpoint_id=1, cluster_id=PowerConfiguration.cluster_id)
    )
)

(
    zbminil2_quirk.clone(omit_man_model_data=False)
    .firmware_version_filter(max_version=0x00001013, allow_missing=True)
    .adds(KeepAlive, cluster_type=ClusterType.Client)
    .add_to_registry()
)

(
    zbminil2_quirk.clone(omit_man_model_data=False)
    .firmware_version_filter(min_version=0x00001013, allow_missing=False)
    .replaces(SonoffEwelinkCluster)
    .enum(
        attribute_name="external_trigger_mode",
        enum_class=ExternalTriggerMode,
        cluster_id=SonoffEwelinkCluster.cluster_id,
        translation_key="external_trigger_mode",
        fallback_name="External trigger mode",
    )
    .add_to_registry()
)
