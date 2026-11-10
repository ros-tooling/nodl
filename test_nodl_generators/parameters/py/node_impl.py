# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Authored class that records the parameter changes it is told about."""

from nodl_generated.test_nodl_generators.parameters_node_base import ParametersNodeBase


class RecordingParametersNode(ParametersNodeBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Declared after the base is constructed and before the attributes below exist.
        self.declare_parameter('unrelated', 0)
        self.changes = []
        self.committed_during_hook = []

    def on_parameters_changed(self, params):
        self.changes.append(params)
        self.committed_during_hook.append(self.get_parameter('max_speed').value)
