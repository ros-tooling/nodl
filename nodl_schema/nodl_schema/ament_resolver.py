# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from ament_index_python import resources as ament_index

from nodl_schema.composition import ResolutionError


class AmentIndexResolver:
    """Resolves ``nodl://<package>/<name>`` through the ament index."""

    prefix = 'nodl://'
    ament_resource_type = 'nodl'

    def handles(self, ref: str) -> bool:
        return ref.startswith(self.prefix)

    def resolve(self, ref: str) -> str:
        package, _, name = ref[len(self.prefix) :].partition('/')
        if not package or not name:
            raise ResolutionError(f'invalid reference {ref!r}: expected nodl://<package>/<name>')

        key = f'{package}__{name}'
        try:
            content, _ = ament_index.get_resource(self.ament_resource_type, key)
        except Exception as exc:
            raise ResolutionError(
                f'NoDL document {ref!r} not found in ament index (resource {self.ament_resource_type}/{key})'
            ) from exc
        return content
