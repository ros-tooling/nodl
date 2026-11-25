# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A lifecycle node with sealed transition callbacks and optional ``handle_*`` hooks."""

from dataclasses import dataclass
from typing import Any, Callable, final

from rclpy.lifecycle import LifecycleNode as RclpyLifecycleNode
from rclpy.lifecycle import LifecycleState, TransitionCallbackReturn

# The transition callbacks that a subclass must not define, because this class implements them.
_SEALED_CALLBACKS = (
    'on_configure',
    'on_activate',
    'on_deactivate',
    'on_cleanup',
    'on_shutdown',
    'on_error',
)


@dataclass(frozen=True)
class _Slot:
    """A pair of functions that create and destroy one endpoint."""

    id: int
    create: Callable[[], None]
    destroy: Callable[[], None]


class LifecycleNode(RclpyLifecycleNode):
    """A lifecycle node with sealed ``on_*`` transition callbacks, ``handle_*`` hooks and an activation registry.

    Derive it and override the ``handle_*`` hooks that need custom behavior.
    Each hook takes the previous ``LifecycleState`` and returns a ``TransitionCallbackReturn``.
    The ``on_*`` transition callbacks run the standard lifecycle management of ``rclpy``, for example activating lifecycle publishers, and call the hooks.
    A subclass that defines an ``on_*`` callback raises ``TypeError`` naming the hook to define instead when the class is defined.

    The registry creates endpoints when the node activates and destroys them when it deactivates.
    Create a ``Managed`` member for each endpoint, in the order the endpoints must be created.
    ``add_activation_slot`` is the underlying primitive.

    Call ``super().__init__()`` before constructing a ``Managed`` or calling ``add_activation_slot``, which raise ``AttributeError`` before it.

    Transitions take no lock, and a timer that ``handle_activate`` creates is destroyed only if ``handle_deactivate`` destroys it.
    See the ``nodl_runtime_py`` overview for the order on each transition.
    """

    # True from a successful activation until ``handle_deactivate`` runs, so shutdown and error know whether it is still owed.
    _nodl_deactivate_pending = False
    # True from the start of the creation of the slots until they are destroyed.
    _nodl_slots_locked = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # The registry exists before the rclpy constructor runs, so a cooperative mixin that registers a slot after its own super().__init__() call finds it.
        self._nodl_slots: list[_Slot] = []
        self._nodl_next_slot_id = 0
        self._nodl_created_slots = 0
        super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        sealed = [name for name in _SEALED_CALLBACKS if getattr(cls, name) is not LifecycleNode.__dict__[name]]
        if sealed:
            hooks = ', '.join(f'handle_{name.removeprefix("on_")}' for name in sealed)
            raise TypeError(
                f'{cls.__qualname__} defines {", ".join(sealed)}, which LifecycleNode implements and does not allow overriding.'
                f' Define {hooks} instead.'
            )

    @final
    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from unconfigured to inactive. Calls ``handle_configure``."""
        return self.handle_configure(state)

    @final
    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from inactive to active. Runs the standard activation, creates the slots, then calls ``handle_activate``.

        When ``handle_activate`` does not return SUCCESS or raises, the slots are destroyed and the standard deactivation runs.
        A result other than SUCCESS is returned, and an exception propagates.
        A slot that raises rolls back the slots created before it, and the exception propagates.
        """
        self._nodl_deactivate_pending = False
        base_result = super().on_activate(state)
        if TransitionCallbackReturn.SUCCESS != base_result:
            return base_result
        try:
            self._activate_slots()
            hook_result = self.handle_activate(state)
        except BaseException:
            self._deactivate_slots()
            super().on_deactivate(state)
            raise
        if TransitionCallbackReturn.SUCCESS != hook_result:
            self._deactivate_slots()
            super().on_deactivate(state)
        else:
            self._nodl_deactivate_pending = True
        return hook_result

    @final
    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from active to inactive. Calls ``handle_deactivate``, then destroys the slots and runs the standard deactivation if it succeeded."""
        self._nodl_deactivate_pending = False
        hook_result = self.handle_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != hook_result:
            self._nodl_deactivate_pending = True
            return hook_result
        self._deactivate_slots()
        return super().on_deactivate(state)

    @final
    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from inactive to unconfigured. Calls ``handle_cleanup``."""
        return self.handle_cleanup(state)

    @final
    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """End the active state, then call ``handle_shutdown``.

        From the active state this runs ``handle_deactivate``, destroys the slots and runs the standard deactivation first.
        A shutdown cannot be vetoed, so the result of ``handle_deactivate`` is ignored and an exception from it is logged.
        """
        self._end_active_state(state)
        return self.handle_shutdown(state)

    @final
    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """End the active state, then call ``handle_error``.

        From the active state this runs ``handle_deactivate`` first, unless an exception from it caused the error,
        then destroys the slots and runs the standard deactivation.
        The result of ``handle_deactivate`` is ignored and an exception from it is logged.
        """
        self._end_active_state(state)
        return self.handle_error(state)

    def add_activation_slot(self, create: Callable[[], None], destroy: Callable[[], None]) -> int:
        """Register a pair of functions that create and destroy an endpoint with the node's activation.

        ``create`` runs at activation in registration order, after the standard activation and before ``handle_activate``.
        ``destroy`` runs in reverse registration order at deactivation, shutdown and error,
        and when ``handle_activate`` fails or a later slot raises.
        ``destroy`` runs only for a slot whose ``create`` returned, and an exception from it is logged.
        A ``create`` that raises must leave nothing behind.

        :return: The opaque id of the slot.
        :raises RuntimeError: When called while the node is activating or active.
        """
        if self._nodl_slots_locked:
            raise RuntimeError('slots can be registered only while the node is not active')
        slot = _Slot(self._nodl_next_slot_id, create, destroy)
        self._nodl_next_slot_id += 1
        self._nodl_slots.append(slot)
        return slot.id

    def handle_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the configure transition."""
        return TransitionCallbackReturn.SUCCESS

    def handle_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the activate transition, after the standard activation and the creation of the slots.

        FAILURE leaves the node inactive, and ERROR runs ``handle_error``.
        """
        return TransitionCallbackReturn.SUCCESS

    def handle_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the deactivate transition, before the slots are destroyed.

        FAILURE leaves the node active, and ERROR runs ``handle_error``.
        It also runs before shutdown and error from the active state, where the result is ignored.
        """
        return TransitionCallbackReturn.SUCCESS

    def handle_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the cleanup transition."""
        return TransitionCallbackReturn.SUCCESS

    def handle_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the shutdown transition, after the slots are destroyed."""
        return TransitionCallbackReturn.SUCCESS

    def handle_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the error transition, after the slots are destroyed.

        SUCCESS takes the node to the unconfigured state, and any other result finalizes it.
        """
        return TransitionCallbackReturn.SUCCESS

    def _end_active_state(self, state: LifecycleState) -> None:
        """Run the deactivation that shutdown and error need: the authored hook if the node is active, then the slots and the standard deactivation."""
        if self._nodl_deactivate_pending:
            self._nodl_deactivate_pending = False
            try:
                if TransitionCallbackReturn.SUCCESS != self.handle_deactivate(state):
                    self.get_logger().warning('handle_deactivate did not succeed, and the shutdown continues')
            except Exception as error:
                self.get_logger().error(f'handle_deactivate raised, and the shutdown continues: {error!r}')
        self._deactivate_slots()
        super().on_deactivate(state)

    def _activate_slots(self) -> None:
        """Create the slots in order, and leave the destruction of the created ones to the caller if one raises."""
        self._nodl_slots_locked = True
        while self._nodl_created_slots < len(self._nodl_slots):
            self._nodl_slots[self._nodl_created_slots].create()
            self._nodl_created_slots += 1

    def _deactivate_slots(self) -> None:
        """Destroy the created slots in reverse, and do nothing when the slots are not active.

        Destroying an entity wakes the executor that spins the node, so the executor releases the entity.
        This is rclpy behavior, verified on Jazzy only.
        """
        if not self._nodl_slots_locked:
            return
        while self._nodl_created_slots:
            self._nodl_created_slots -= 1
            try:
                self._nodl_slots[self._nodl_created_slots].destroy()
            except Exception as error:
                self.get_logger().error(f'Destroying an activation slot failed: {error!r}')
        self._nodl_slots_locked = False
