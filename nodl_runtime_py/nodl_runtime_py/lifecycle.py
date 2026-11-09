# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A lifecycle node base class with fixed transition behavior and optional hooks."""

from typing import Any, final

from rclpy.lifecycle import LifecycleNode as RclpyLifecycleNode
from rclpy.lifecycle import LifecycleState, SimpleManagedEntity, TransitionCallbackReturn

# The transition callbacks that subclasses must not define, because this class implements them.
_SEALED_CALLBACKS = (
    'on_configure',
    'on_activate',
    'on_deactivate',
    'on_cleanup',
    'on_shutdown',
    'on_error',
)


class LifecycleNode(RclpyLifecycleNode):
    """An ``rclpy`` lifecycle node whose transition callbacks are sealed, with ``handle_*`` hooks to add behavior.

    A subclass that defines an ``on_*`` transition callback raises ``TypeError`` when the class is defined.
    It overrides the matching optional hook instead, each taking the previous state and returning a ``TransitionCallbackReturn``.
    See the ``nodl_runtime_py`` overview for the order of the hooks and for an example.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Construct the node, with the same arguments as ``rclpy.lifecycle.LifecycleNode``."""
        super().__init__(*args, **kwargs)
        self._activation_gate = SimpleManagedEntity()
        self.add_managed_entity(self._activation_gate)

    @property
    def activation_gate(self) -> SimpleManagedEntity:
        """The activation gate, open while the node is active and during ``handle_activate``."""
        return self._activation_gate

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        sealed = [name for name in _SEALED_CALLBACKS if name in cls.__dict__]
        if sealed:
            hooks = ', '.join(f'handle_{name.removeprefix("on_")}' for name in sealed)
            raise TypeError(
                f'{cls.__qualname__} defines {", ".join(sealed)}, which LifecycleNode implements and does not allow overriding.'
                f' Define {hooks} instead.'
            )

    def handle_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Run when configuring, and return SUCCESS to reach the inactive state."""
        return TransitionCallbackReturn.SUCCESS

    def handle_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Run when activating, after lifecycle publishers are active."""
        return TransitionCallbackReturn.SUCCESS

    def handle_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Run when deactivating, before lifecycle publishers are deactivated."""
        return TransitionCallbackReturn.SUCCESS

    def handle_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Run when cleaning up."""
        return TransitionCallbackReturn.SUCCESS

    def handle_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Run when shutting down, after lifecycle publishers are deactivated."""
        return TransitionCallbackReturn.SUCCESS

    def handle_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Run after a failed transition raised or returned ERROR, after lifecycle publishers are deactivated."""
        return TransitionCallbackReturn.SUCCESS

    @final
    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        return self.handle_configure(state)

    @final
    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = super().on_activate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        result = self.handle_activate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            super().on_deactivate(state)
        return result

    @final
    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = self.handle_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        return super().on_deactivate(state)

    @final
    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        return self.handle_cleanup(state)

    @final
    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = super().on_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        return self.handle_shutdown(state)

    @final
    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = super().on_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        return self.handle_error(state)
