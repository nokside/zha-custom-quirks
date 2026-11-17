"""Quirk for SONOFF ZBMINIL2."""

from zigpy.zcl import ClusterType
from zigpy.zcl.clusters.general import KeepAlive, PowerConfiguration
from zigpy.zdo.types import NodeDescriptor

from zhaquirks.builder import EntityFilter, QuirkBuilder

(
    QuirkBuilder("SONOFF", "ZBMINIL2")
    .node_descriptor(
        NodeDescriptor(0x02, 0x40, 0x84, 0x1286, 0x52, 0x0400, 0x2C00, 0x0400, 0x00)
    )
    .adds(KeepAlive, cluster_type=ClusterType.Client)
    .removes_entity(
        EntityFilter(endpoint_id=1, cluster_id=PowerConfiguration.cluster_id)
    )
    .add_to_registry()
)
