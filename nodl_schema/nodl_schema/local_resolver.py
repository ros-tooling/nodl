# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from nodl_schema.composition import ResolutionError, Resolver


class LocalResolver(Resolver):
    """
    Resolves ``local://<path>`` from the source tree, relative to the document holding it.
    """

    prefix = 'local://'

    def handles(self, ref: str) -> bool:
        return ref.startswith(self.prefix)

    def resolve(self, ref: str, origin: Path | None = None) -> Path:
        assert origin, 'Local resolver requires an originating path'
        assert origin.is_absolute(), 'Originating document path must be absolute'

        path = Path(origin.parent, ref[len(self.prefix) :])
        if not path.is_file():
            raise ResolutionError(f'could not read {str(path)!r} for reference {ref!r}')
        return path
