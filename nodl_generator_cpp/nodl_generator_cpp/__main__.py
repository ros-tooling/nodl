# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Entry point for ``python -m nodl_generator_cpp``.

Delegates to nodl_generator_cpp.cli.main.
"""

import sys

from nodl_generator_cpp.cli import main

if __name__ == '__main__':
    sys.exit(main())
