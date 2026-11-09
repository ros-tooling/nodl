# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A lifecycle node base class with fixed transition behavior and optional hooks."""

from typing import Any, final

from rclpy.lifecycle import LifecycleNode as RclpyLifecycleNode
from rclpy.lifecycle import LifecycleState, TransitionCallbackReturn

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
    """An ``rclpy`` lifecycle node whose transitions always run the standard behavior.

    The ``on_*`` transition callbacks are implemented here and cannot be overridden:
    a subclass that defines one raises ``TypeError`` when the class is defined.
    Subclasses customize a transition by defining the matching optional hook instead,
    ``handle_configure``, ``handle_activate``, ``handle_deactivate``, ``handle_cleanup``, ``handle_shutdown`` or ``handle_error``.
    Each hook takes the previous state and returns a ``TransitionCallbackReturn``, SUCCESS by default.
    A hook that raises makes the transition fail with ERROR, which runs ``handle_error``.

    The standard activation and deactivation are the ``rclpy`` defaults,
    which activate and deactivate every managed entity, lifecycle publishers included.
    They run in this order:

    ===========  ========================================================================================
    Transition   Order
    ===========  ========================================================================================
    configure    hook
    activate     standard activation, then hook.
                 A result that is not SUCCESS runs the standard deactivation and is returned.
    deactivate   hook, then standard deactivation.
                 A result that is not SUCCESS is returned, and the node stays active.
    cleanup      hook
    shutdown     standard deactivation, then hook
    error        standard deactivation, then hook
    ===========  ========================================================================================
    """

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
