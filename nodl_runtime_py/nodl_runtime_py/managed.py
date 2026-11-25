# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A member that holds an endpoint of a lifecycle node while the node is active."""

from typing import Callable, Generic, Optional, TypeVar

from nodl_runtime_py.lifecycle import LifecycleNode

EntityT = TypeVar('EntityT')


class Managed(Generic[EntityT]):
    """A member that holds an endpoint of a ``LifecycleNode`` while the node is active.

    Construct it in ``__init__`` of the node.
    It registers an activation slot with the node: ``create`` runs when the node activates, and ``destroy`` runs with the endpoint when it deactivates.
    ``Managed`` members register in construction order, so reordering them changes the order of creation.

    ``destroy`` is explicit, for example ``node.destroy_subscription``, because dropping a reference does not destroy an ``rclpy`` entity.
    Its result is ignored.

    The endpoint is not accessible through this class, so callbacks and hooks use the node's own state and the endpoint is only created and destroyed.
    ``bool(managed)`` is true while the endpoint exists.
    """

    def __init__(
        self, node: LifecycleNode, create: Callable[[], EntityT], destroy: Callable[[EntityT], object]
    ) -> None:
        """Register the slot with ``node``.

        :param node: The node whose activation creates the endpoint.
        :param create: Returns the endpoint, for example ``lambda: node.create_subscription(...)``.
        :param destroy: Destroys the endpoint it is given, for example ``node.destroy_subscription``.
        :raises RuntimeError: When the node is activating or active.
        """
        self._entity: Optional[EntityT] = None
        self._create = create
        self._destroy = destroy
        node.add_activation_slot(self._create_entity, self._destroy_entity)

    def __bool__(self) -> bool:
        """Whether the endpoint currently exists."""
        return self._entity is not None

    def _create_entity(self) -> None:
        self._entity = self._create()

    def _destroy_entity(self) -> None:
        entity, self._entity = self._entity, None
        if entity is not None:
            self._destroy(entity)
