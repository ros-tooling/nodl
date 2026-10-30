# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import sys
from pathlib import Path

# `python -m pytest` in the package directory, as colcon runs it, puts the source package first on the path.
# The source package has no generated modules, so the tests import the built package instead.
PACKAGE_DIR = Path(__file__).resolve().parent.parent
sys.path[:] = [entry for entry in sys.path if Path(entry or '.').resolve() != PACKAGE_DIR]
