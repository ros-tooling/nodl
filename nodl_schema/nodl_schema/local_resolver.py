# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from nodl_schema.composition import ResolutionError

PREFIX = 'local://'


def path_to_ref(path: Path | str) -> str:
    """Turn a filesystem path into an absolute ``local://`` reference."""
    return PREFIX + str(Path(path).resolve())


def ref_to_path(ref: str) -> Path:
    """Turn an absolute ``local://`` reference back into a filesystem path."""
    if not is_absolute(ref):
        raise ResolutionError(f'{ref!r} is relative and names no path on its own')
    return Path(ref[len(PREFIX) :])


def is_absolute(ref: str) -> bool:
    return ref.startswith(PREFIX) and ref[len(PREFIX) :].startswith('/')


class LocalResolver:
    """Resolves ``local://<path>`` from the source tree, relative to the document holding it.

    A reference is written relative to its own document, so ``local://common/telemetry.nodl.yaml``
    means the same thing wherever that document sits. It is resolved against the document's origin
    before it is read, which is why this resolver rebases.

    Relative references only work while the source tree is present.
    They do not survive installation, where a consumer gets document text with no location to be
    relative to, so ``ament_nodl`` rewrites them to ``nodl://`` references when it installs.
    """

    prefix = PREFIX

    def handles(self, ref: str) -> bool:
        return ref.startswith(self.prefix)

    def normalize(self, ref: str, origin: str | None) -> str:
        if is_absolute(ref):
            return ref

        body = ref[len(self.prefix) :]
        if origin is None:
            raise ResolutionError(
                f'{ref!r} is relative, but the document holding it has no location. '
                f'Load it from a file, or pass base= to load_nodl.'
            )
        if not is_absolute(origin):
            raise ResolutionError(
                f'{ref!r} is relative, but the document holding it came from {origin!r}, '
                f'which is not a location in the source tree.'
            )
        return path_to_ref(ref_to_path(origin).parent / body)

    def resolve(self, ref: str) -> str:
        path = ref_to_path(ref)
        try:
            return path.read_text(encoding='utf-8')
        except OSError as exc:
            raise ResolutionError(f'could not read {str(path)!r} for reference {ref!r}: {exc}') from exc
