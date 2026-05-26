# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Entry point for ``python -m nodl_schema``.

Delegates to nodl_schema.validator.main so the CLI logic lives next to the
library functions it exercises. Kept as a separate module so ``python -m
nodl_schema`` does not double-import nodl_schema.validator
(which __init__.py already pulls in) and emit a RuntimeWarning.
"""

import sys

from nodl_schema.validator import main

if __name__ == '__main__':
    sys.exit(main())
