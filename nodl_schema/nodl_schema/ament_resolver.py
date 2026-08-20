# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from ament_index_python import resources as ament_index
from ament_index_python.constants import RESOURCE_INDEX_SUBFOLDER

from nodl_schema.composition import ResolutionError


class AmentIndexResolver:
    """Resolves ``nodl://<package>/<name>`` through the ament index."""

    prefix = 'nodl://'
    ament_resource_type = 'nodl'

    def handles(self, ref: str) -> bool:
        return ref.startswith(self.prefix)

    def resolve(self, ref: str) -> Path:
        package, _, name = ref[len(self.prefix) :].partition('/')
        if not package or not name:
            raise ResolutionError(f'invalid reference {ref!r}: expected nodl://<package>/<name>')

        key = f'{package}__{name}'
        resource_prefix = ament_index.has_resource(self.ament_resource_type, key)
        if not resource_prefix:
            raise ResolutionError(
                f'NoDL document {ref!r} not found in ament index (resource {self.ament_resource_type}/{key})'
            )

        resource_path = Path(resource_prefix, RESOURCE_INDEX_SUBFOLDER, self.ament_resource_type, key)
        if not resource_path.exists():
            raise ResolutionError(f'NoDL document {ref} not found at registered path {resource_path}')

        return resource_path
