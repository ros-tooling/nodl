"""Factory that produces a launch_testing-compatible conformance test pair."""
from __future__ import annotations

import time
import unittest
from pathlib import Path
from typing import Optional

import pytest


def nodl_conformance_test(
    package: str,
    executable: str,
    nodl_file: str,
    *,
    node_name: Optional[str] = None,
    node_namespace: str = '/',
    startup_timeout: float = 15.0,
):
    """Return ``(generate_test_description, TestClass)`` for a NoDL conformance test.

    The returned pair is designed to be unpacked at module level in a pytest test file::

        from nodl_test import nodl_conformance_test

        generate_test_description, TestNodlConformance = nodl_conformance_test(
            package='my_package',
            executable='my_node',
            nodl_file='/path/to/my_node.nodl.yaml',
        )

    pytest + launch_testing discover ``generate_test_description`` (via the
    ``@pytest.mark.launch_test`` marker) and all ``unittest.TestCase`` subclasses
    in the module.  The test class introspects the launched node via
    ``nodl.describe`` and compares the result against the NoDL spec.

    Parameters
    ----------
    package:
        ROS 2 package containing the executable.
    executable:
        Name of the executable to launch.
    nodl_file:
        Absolute path to the reference ``.nodl.yaml`` file.
    node_name:
        Override the node name to wait for.  Defaults to ``node.name`` in the
        NoDL document.
    node_namespace:
        Namespace the node will be started in.  Defaults to ``'/'``.
    startup_timeout:
        Seconds to wait for the node to appear in the graph.
    """
    from nodl.resolve import resolve
    from nodl.schema import load_nodl

    nodl_path = Path(nodl_file)
    with open(nodl_path) as f:
        raw_doc = load_nodl(f)

    # Resolve base + fragments into a merged expected document.
    layered = resolve(raw_doc, source_path=nodl_path)
    reference = layered.merged()

    target_name = node_name or (reference.node.name if reference.node else None)
    if not target_name:
        raise ValueError(
            'node_name must be provided when the NoDL document has no node.name'
        )

    ns = node_namespace.rstrip('/')
    target_fqn = f'{ns}/{target_name}' if ns else f'/{target_name}'

    # -----------------------------------------------------------------------
    # Launch description
    # -----------------------------------------------------------------------

    def _generate_test_description():
        import launch
        import launch_ros.actions
        import launch_testing.actions

        return launch.LaunchDescription([
            launch_ros.actions.Node(
                package=package,
                executable=executable,
            ),
            launch_testing.actions.ReadyToTest(),
        ])

    generate_test_description = pytest.mark.launch_test(_generate_test_description)

    # -----------------------------------------------------------------------
    # Test class
    # -----------------------------------------------------------------------

    class TestNodlConformance(unittest.TestCase):
        """Verifies that the running node's interfaces match its NoDL specification."""

        _reference = reference
        _target_fqn = target_fqn
        _startup_timeout = startup_timeout
        _actual = None
        _setup_error: Optional[Exception] = None

        @classmethod
        def setUpClass(cls):
            from nodl.conversion import to_nodl
            from nodl.describe import describe

            deadline = time.monotonic() + cls._startup_timeout
            last_error: Optional[Exception] = None

            while time.monotonic() < deadline:
                try:
                    node_msg = describe(
                        cls._target_fqn,
                        discovery_timeout_sec=min(2.0, deadline - time.monotonic()),
                    )
                    cls._actual = to_nodl(node_msg)
                    return
                except RuntimeError as exc:
                    last_error = exc
                time.sleep(0.5)

            cls._setup_error = RuntimeError(
                f'Node {cls._target_fqn!r} did not appear within '
                f'{cls._startup_timeout}s. Last error: {last_error}'
            )

        def _require_setup(self):
            if self._setup_error is not None:
                raise self._setup_error

        def _assert_no_diffs(self, diffs, label: str):
            if diffs:
                self.fail(
                    f'{label} differences between NoDL spec and running node:\n'
                    + '\n'.join(f'  {d}' for d in diffs)
                )

        def test_publishers_match_nodl(self):
            from nodl_test._compare import _compare_topics
            self._require_setup()
            self._assert_no_diffs(
                _compare_topics(
                    self._reference.publishers or [],
                    self._actual.publishers or [],
                    'publisher',
                    self._target_fqn,
                ),
                'Publisher',
            )

        def test_subscriptions_match_nodl(self):
            from nodl_test._compare import _compare_topics
            self._require_setup()
            self._assert_no_diffs(
                _compare_topics(
                    self._reference.subscriptions or [],
                    self._actual.subscriptions or [],
                    'subscription',
                    self._target_fqn,
                ),
                'Subscription',
            )

        def test_service_servers_match_nodl(self):
            from nodl_test._compare import _compare_services
            self._require_setup()
            self._assert_no_diffs(
                _compare_services(
                    self._reference.service_servers or [],
                    self._actual.service_servers or [],
                    'service_server',
                    self._target_fqn,
                ),
                'Service server',
            )

        def test_service_clients_match_nodl(self):
            from nodl_test._compare import _compare_services
            self._require_setup()
            self._assert_no_diffs(
                _compare_services(
                    self._reference.service_clients or [],
                    self._actual.service_clients or [],
                    'service_client',
                    self._target_fqn,
                ),
                'Service client',
            )

        def test_parameters_match_nodl(self):
            from nodl_test._compare import _compare_parameters
            self._require_setup()
            self._assert_no_diffs(
                _compare_parameters(
                    self._reference.parameters or {},
                    self._actual.parameters or {},
                ),
                'Parameter',
            )

    return generate_test_description, TestNodlConformance
