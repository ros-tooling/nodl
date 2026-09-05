# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass


@dataclass
class GeneratedFile:
    """A generated file ready to be written to disk."""

    filename: str
    content: str
