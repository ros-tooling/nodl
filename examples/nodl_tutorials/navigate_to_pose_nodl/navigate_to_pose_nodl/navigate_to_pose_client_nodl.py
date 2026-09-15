#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""NoDL-backed action client used as the migrated implementation."""

from navigate_to_pose_nodl.generated.navigate_to_pose_client_py_base import NavigateToPoseClientPyBase
from navigate_to_pose_nodl.navigation import run


class NavigateToPoseClientNodl(NavigateToPoseClientPyBase):
    """Use the action client created by the generated base class."""


def main(args=None):
    """Send one navigation goal with the NoDL-backed client."""
    return run(NavigateToPoseClientNodl, args)


if __name__ == '__main__':
    raise SystemExit(main())
