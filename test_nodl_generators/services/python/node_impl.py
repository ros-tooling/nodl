# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete implementation of the generated service base class."""

from test_nodl_generators.generated.services_node import ServicesNodeBase


class ServicesNode(ServicesNodeBase):
    def on_add(self, request, response):
        response.sum = request.a + request.b
        return response
