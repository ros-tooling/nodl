# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A member that holds an outgoing entity of a lifecycle node and hands it out only while the node is active."""

from typing import Generic, Optional, TypeVar

from nodl_runtime_py.lifecycle import LifecycleNode

EntityT = TypeVar('EntityT')


class Gated(Generic[EntityT]):
    """A member that holds an outgoing entity of a ``LifecycleNode`` and hands it out only while the node is active.

    The entity exists for the lifetime of the node, so a client keeps its graph presence and discovery.
    ``get()`` returns it from the standard activation until the standard deactivation, and ``None`` otherwise.
    The flag turns on before ``handle_activate`` and off after ``handle_deactivate``,
    so both hooks get the entity, and a failed activation turns it off again.

    Construct it in ``__init__`` of the node with the entity.
    It registers an activation slot, so ``Gated`` and ``Managed`` members register in construction order together.
    A slot cannot be unregistered, so construct ``Gated`` members for the lifetime of the node.
    """

    def __init__(self, node: LifecycleNode, entity: EntityT) -> None:
        """Register the slot with ``node``.

        :param node: The node whose activation hands out the entity.
        :param entity: The entity, for example ``node.create_client(...)``.
        :raises RuntimeError: When the node is activating or active.
        """
        self._entity = entity
        self._active = False
        node.add_activation_slot(self._turn_on, self._turn_off)

    def get(self) -> Optional[EntityT]:
        """Return the entity while the node is active, otherwise ``None``.

        An entity obtained while the node is active stays usable after it deactivates, as a lifecycle publisher does.
        """
        return self._entity if self._active else None

    def _turn_on(self) -> None:
        self._active = True

    def _turn_off(self) -> None:
        self._active = False
