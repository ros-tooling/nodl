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

# The seams for generated code, which one class below LifecycleNode may define.
_SEAMS = ('refresh_parameters', 'start_parameter_updates', 'stop_parameter_updates')


class LifecycleNode(RclpyLifecycleNode):
    """An ``rclpy`` lifecycle node whose transition callbacks are sealed, with ``handle_*`` hooks to add behavior.

    A subclass that defines an ``on_*`` transition callback raises ``TypeError`` when the class is defined.
    It overrides the matching optional hook instead, each taking the previous state and returning a ``TransitionCallbackReturn``.
    The node owns an activation gate, see :attr:`activation_gate`.
    See the ``nodl_runtime_py`` overview for the order of the hooks and for an example.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Construct the node, with the same arguments as ``rclpy.lifecycle.LifecycleNode``."""
        super().__init__(*args, **kwargs)
        self._activation_gate = SimpleManagedEntity()
        self.add_managed_entity(self._activation_gate)

    @property
    def activation_gate(self) -> SimpleManagedEntity:
        """The activation gate for :mod:`nodl_runtime_py.active_only`, open while the node is active and during ``handle_activate``."""
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
        for name in _SEAMS:
            if name not in cls.__dict__:
                continue
            definer = next(
                (base for base in cls.__mro__[1:] if name in base.__dict__ and base is not LifecycleNode), None
            )
            if definer is not None:
                raise TypeError(
                    f'{cls.__qualname__} defines {name}, which {definer.__qualname__} already defines.'
                    ' Only one class below LifecycleNode may define it, so use the handle_* hooks and on_parameters_changed instead.'
                )

    def refresh_parameters(self) -> None:
        """Bring the node's parameter values up to date, called by the transitions that need current values."""

    def start_parameter_updates(self) -> None:
        """Start following parameter changes, called while the node activates."""

    def stop_parameter_updates(self) -> None:
        """Stop following parameter changes, called before the node deactivates."""

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
        self.refresh_parameters()
        return self.handle_configure(state)

    @final
    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = super().on_activate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        self.start_parameter_updates()
        self.refresh_parameters()
        result = self.handle_activate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            self.stop_parameter_updates()
            super().on_deactivate(state)
        return result

    @final
    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = self.handle_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        self.stop_parameter_updates()
        return super().on_deactivate(state)

    @final
    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        return self.handle_cleanup(state)

    @final
    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.stop_parameter_updates()
        result = super().on_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        return self.handle_shutdown(state)

    @final
    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.stop_parameter_updates()
        result = super().on_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != result:
            return result
        return self.handle_error(state)
