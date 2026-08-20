# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import pytest

from nodl_schema import AmentIndexResolver, ResolutionError, dump_nodl
from nodl_schema.models import NodlDocument


@pytest.mark.parametrize('ref', ['nodl://sensor_common/imu_driver', 'nodl://pkg/x'])
def test_ament_resolver_handles_nodl_refs(ref):
    assert AmentIndexResolver().handles(ref)


@pytest.mark.parametrize('ref', ['test://x', 'common/telemetry.nodl.yaml', 'ftp://example.com/x.yaml', ''])
def test_ament_resolver_does_not_handle_other_forms(ref):
    assert not AmentIndexResolver().handles(ref)


def _write_ament_resource(prefix: Path, key: str, doc: NodlDocument) -> Path:
    from ament_index_python.constants import RESOURCE_INDEX_SUBFOLDER

    resource_path = Path(prefix, RESOURCE_INDEX_SUBFOLDER, AmentIndexResolver.ament_resource_type, key)
    resource_path.parent.mkdir(parents=True, exist_ok=True)
    resource_path.write_text(dump_nodl(doc))
    return resource_path


def test_ament_resolver_looks_up_the_registered_resource(monkeypatch, tmp_path: Path):
    written_path = _write_ament_resource(tmp_path, 'sensor_common__imu_driver', NodlDocument())

    def fake_has_resource(resource_type: str, resource_name: str):
        return tmp_path

    import ament_index_python.resources as resources

    monkeypatch.setattr(resources, 'has_resource', fake_has_resource)

    path = AmentIndexResolver().resolve('nodl://sensor_common/imu_driver')
    assert path == written_path


def test_ament_resolver_missing_resource_raises():
    with pytest.raises(ResolutionError, match='nodl://pkg/absent'):
        AmentIndexResolver().resolve('nodl://pkg/absent')


@pytest.mark.parametrize('ref', ['nodl://pkg', 'nodl://pkg/', 'nodl:///name'])
def test_ament_resolver_rejects_malformed_uri(ref):
    # The schema checks URI shape only, so the body is checked here.
    with pytest.raises(ResolutionError, match='expected nodl://'):
        AmentIndexResolver().resolve(ref)
