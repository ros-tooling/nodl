# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Entry point for ``python -m nodl_schema``.

Delegates to nodl_schema.validator.main.
"""

import sys

from nodl_schema.validator import main

if __name__ == '__main__':
    sys.exit(main())
