# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Resolve explicit deployment inputs using the native ROS argument parser."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParameterValue:
    """A typed expectation, separate from contract defaults and observations."""

    type: str
    value: Any


_VALUE_FIELDS = {
    1: ('bool', 'bool_value'),
    2: ('int', 'integer_value'),
    3: ('double', 'double_value'),
    4: ('string', 'string_value'),
    5: ('byte_array', 'byte_array_value'),
    6: ('bool_array', 'bool_array_value'),
    7: ('int_array', 'integer_array_value'),
    8: ('double_array', 'double_array_value'),
    9: ('string_array', 'string_array_value'),
}


def resolve_configuration(
    *,
    node_fqn: str,
    params_files: Iterable[str | Path] = (),
    parameters: Iterable[str] = (),
) -> dict[str, ParameterValue]:
    """Resolve files in order, followed by inline overrides, with native ROS semantics.

    No ambient ROS arguments are read and no node is created or modified.
    Node-qualified overrides and wildcard file selectors are handled by ROS itself.
    """
    files, items = list(params_files), list(parameters)
    if not files and not items:
        return {}
    from ament_index_python.packages import get_package_prefix

    binary = Path(get_package_prefix('nodl_observe')) / 'lib/nodl_observe/resolve_parameters'
    command = [str(binary), node_fqn, '--ros-args']
    for file in files:
        command.extend(['--params-file', str(file)])
    for item in items:
        command.extend(['-p', item])
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip() or 'failed to resolve deployment configuration')
    from rcl_interfaces.msg import Parameter
    from rclpy.serialization import deserialize_message

    resolved = {}
    stream = BytesIO(result.stdout)
    while header := stream.readline():
        length = int(header)
        payload = stream.read(length)
        if len(payload) != length:
            raise ValueError('incomplete parameter message from configuration resolver')
        message = deserialize_message(payload, Parameter)
        value = message.value
        type_name, field = _VALUE_FIELDS[value.type]
        parsed = getattr(value, field)
        if value.type >= 5:
            parsed = list(parsed)
        resolved[message.name] = ParameterValue(type_name, parsed)
    return resolved
