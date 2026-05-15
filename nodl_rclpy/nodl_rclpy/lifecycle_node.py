"""NodlLifecycleNode: rclpy.lifecycle.LifecycleNode initialized from a NoDL document."""
from __future__ import annotations

from pathlib import Path
from typing import Union

from rclpy.lifecycle import LifecycleNode

from nodl.models import NodlDocument
from nodl_rclpy._setup import setup_nodl
from nodl_rclpy.node import _load_doc


class NodlLifecycleNode(LifecycleNode):
    """rclpy.lifecycle.LifecycleNode base class initialized from a NoDL document.

    Same interface as NodlNode; use this when the node participates in the
    ROS 2 managed-node lifecycle.
    """

    def __init__(
        self,
        nodl_source: Union[str, Path, dict, NodlDocument],
        node_name: str | None = None,
        **kwargs,
    ):
        doc = _load_doc(nodl_source)
        name = node_name or (doc.node.name if doc.node else None)
        if not name:
            raise ValueError(
                'node_name must be supplied when the NoDL document has no node.name'
            )
        super().__init__(name, **kwargs)
        setup_nodl(self, doc)
