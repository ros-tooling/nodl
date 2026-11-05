# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Marks for tests that depend on the installed tools, shared by the ``ament_python`` tests."""

import shutil

import pytest
import setuptools

SETUPTOOLS_MAJOR = int(setuptools.__version__.split('.')[0])

needs_colcon = pytest.mark.skipif(shutil.which('colcon') is None, reason='colcon is not installed')

# From setuptools 80, develop only runs pip install -e, and colcon --symlink-install does not work.
needs_setuptools_lt_80 = pytest.mark.skipif(
    SETUPTOOLS_MAJOR >= 80, reason='setup.py develop needs setuptools older than 80'
)
