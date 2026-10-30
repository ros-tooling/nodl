# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Executor that records its construction, to show that an executable spins its node with the executor it was given."""

import os
from pathlib import Path

from rclpy.executors import SingleThreadedExecutor

MARKER_ENVIRONMENT_VARIABLE = 'RECORDING_EXECUTOR_MARKER'


class RecordingExecutor(SingleThreadedExecutor):
    def __init__(self):
        super().__init__()
        Path(os.environ[MARKER_ENVIRONMENT_VARIABLE]).write_text('constructed')
