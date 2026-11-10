# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Authored class that records the parameter changes it is told about."""

from nodl_generated.test_nodl_generators.parameters_node_base import ParametersNodeBase


class RecordingParametersNode(ParametersNodeBase):
    def __init__(self, **kwargs):
        self.changes = []
        super().__init__(**kwargs)

    def on_parameters_changed(self, params):
        self.changes.append(params)
