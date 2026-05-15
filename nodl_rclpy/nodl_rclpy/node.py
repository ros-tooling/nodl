"""NodlNode: rclpy.node.Node initialized from a NoDL document."""
from __future__ import annotations

from pathlib import Path
from typing import Union

import rclpy.node

from nodl.models import NodlDocument
from nodl.schema import load_nodl
from nodl_rclpy._setup import setup_nodl


def _load_doc(source: Union[str, Path, dict, NodlDocument]) -> NodlDocument:
    if isinstance(source, NodlDocument):
        return source
    if isinstance(source, dict):
        return NodlDocument.model_validate(source)
    with open(source) as f:
        return load_nodl(f)


class NodlNode(rclpy.node.Node):
    """rclpy.node.Node base class initialized from a NoDL document.

    Publishers, subscriptions, service clients/servers, and parameters are
    created at construction time from the NoDL spec.  Subscription and service
    server callbacks are resolved by looking for an on_<identifier> method on
    the subclass instance.

    The nodl_source argument accepts:
      - a file path (str or Path) to a .nodl.yaml file
      - a plain dict matching the NoDL schema
      - a NodlDocument instance
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
